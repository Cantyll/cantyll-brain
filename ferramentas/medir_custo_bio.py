"""
Mede o custo de um passo do BioBrain (sinapses esparsas) ao lado do LIFBrain (matriz densa), na mesma máquina.

    python ferramentas/medir_custo_bio.py

Critério do T2 (plano, T2): com 630 neurônios, o passo esparso não custa mais que o denso.

Duas medidas, com a mesma conta de medir_custo_passo.py (uma thread de BLAS, mediana de RODADAS):

1. Redes reais: LIFBrain e BioBrain da semente 7 (470 neurônios, passo de 1 ms), com a mesma semente de ruído e
   o mesmo estímulo. Pela paridade do T2, as duas disparam os mesmos pulsos: a diferença é só o caminho da conta.
2. Redes sintéticas de 630 neurônios (o tamanho da spec, seção 10): a rede sintética de medir_custo_passo.py
   (pesos aleatórios com a densidade da rede real) e a mesma rede passada para a tabela esparsa do BioBrain.
   Mesmos pesos, mesmos parâmetros e o mesmo ruído: os pulsos saem iguais, e a ferramenta confere isso.

O custo esparso depende de quantos neurônios disparam por passo; por isso a tabela mostra os pulsos por passo.
O passo custa o mesmo com 1 ms ou 0,5 ms; com 0,5 ms (D2), cada segundo simulado pede 2000 passos.

Não é a referência: é o que esta máquina fez nesta execução. Rode de novo na máquina de referência
(docs/CUSTO_DO_PASSO.md) antes de decidir o orçamento.
"""
import os

# Uma thread só, como em medir_custo_passo.py: o número é o custo de um núcleo.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

FERRAMENTAS = Path(__file__).resolve().parent
sys.path.insert(0, str(FERRAMENTAS))
sys.path.insert(0, str(FERRAMENTAS.parent))
import medir_custo_passo as lif  # noqa: E402  (rede sintética do LIF, ambiente e RODADAS)

from pestinha.core.bio import BioBrain  # noqa: E402
from pestinha.core.bio.neuronios import Neuronio  # noqa: E402
from pestinha.core.bio.projecoes import compilar, projecao_de_bloco  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402

AMOSTRAS = 2000             # passos por rodada na rede sintética
ESTIMULO = {"WORK": 0.8, "TYPING": 0.3}


def _cronometrar(passo, n_passos, rodadas):
    """Mediana de µs de relógio e de CPU por passo."""
    tempos = []
    for _ in range(rodadas):
        t0, c0 = time.perf_counter(), time.process_time()
        passo()
        t1, c1 = time.perf_counter(), time.process_time()
        tempos.append(((t1 - t0) / n_passos, (c1 - c0) / n_passos))
    return {"us_por_passo": 1e6 * statistics.median(t for t, _ in tempos),
            "us_cpu_por_passo": 1e6 * statistics.median(c for _, c in tempos)}


def rede_real(classe, rodadas):
    """Custo de um passo de 1 ms da rede real (semente 7), com 1 s simulado por rodada."""
    b = classe(seed=7, seed_ruido=42)

    def um_segundo():
        b.stimulate(ESTIMULO)
        for _ in range(10):
            b.step(100)

    for _ in range(3):                                   # aquece e deixa a rede ativa
        um_segundo()
    antes = b.disparos.sum()
    custo = _cronometrar(um_segundo, 1000, rodadas)
    custo["pulsos_por_passo"] = float(b.disparos.sum() - antes) / (1000 * rodadas)
    custo["N"] = b.N
    custo["sinapses"] = b.n_synapses
    custo["disparos"] = b.disparos.copy()
    return custo


def bio_sintetica(base):
    """A rede sintética do LIF (medir_custo_passo.rede_sintetica) com as sinapses na tabela esparsa do BioBrain."""
    b = object.__new__(BioBrain)                         # sem __init__: os mesmos arrays, outro caminho
    b.N, b.Ns, b.Nl = base.N, base.Ns, base.Nl
    b.rng = np.random.default_rng(42)
    b.sinapses = compilar([projecao_de_bloco("sint", "sint", 0, base.Ns, base.W_lif)], base.N, base.Nl, base.Ns)
    b.neuronios = object.__new__(Neuronio)
    b.neuronios.n = base.Nl
    b.neuronios.decay = base.decay.copy()
    b.neuronios.adapt_b = base.adapt_b.copy()
    b.neuronios.adapt_decay = base.adapt_decay.copy()
    b.neuronios.v = np.zeros(base.Nl)
    b.neuronios.a = np.zeros(base.Nl)
    b.neuronios.ref = np.zeros(base.Nl, dtype=int)
    b.spikes = np.zeros(base.N)
    b.pre_gain = np.ones(base.N)
    b.p = b.pre_gain[:base.Ns]
    b.s_prob = base.s_prob.copy()
    b.s_d = base.s_d.copy()
    b.s_rec = base.s_rec.copy()
    b.trace = np.zeros(base.N)
    b.ausente = False
    b._idx_ausencia = np.empty(0, dtype=int)
    b._pool_de = base.onehot.argmax(axis=1)
    b.pools = [None] * base.onehot.shape[1]
    b.pool_counts = np.zeros(base.onehot.shape[1])
    return b


def sinteticas(N, rodadas):
    """Custo de um passo das duas redes sintéticas de N neurônios, depois de conferir que disparam igual."""
    referencia = LIFBrain(seed=7)
    densa = lif.rede_sintetica(N, referencia)
    esparsa = bio_sintetica(lif.rede_sintetica(N, referencia))
    for _ in range(200):                                 # aquece e confere os pulsos passo a passo
        densa._substep()
        esparsa._substep()
        if not np.array_equal(densa.spikes, esparsa.spikes):
            raise SystemExit("as redes sintéticas divergiram: a medida não compara o mesmo trabalho")

    resultado = {}
    for nome, rede in (("densa", densa), ("esparsa", esparsa)):
        antes = rede.pool_counts.sum()

        def rodar(rede=rede):
            for _ in range(AMOSTRAS):
                rede._substep()

        custo = _cronometrar(rodar, AMOSTRAS, rodadas)
        custo["pulsos_por_passo"] = float(rede.pool_counts.sum() - antes) / (AMOSTRAS * rodadas)
        custo["sinapses"] = int(np.count_nonzero(rede.W_lif)) if nome == "densa" else len(rede.sinapses)
        resultado[nome] = custo
    return resultado


def _fracao(us_cpu, passos_por_s):
    return f"{100 * passos_por_s * us_cpu / 1e6:.1f}%"


def main(rodadas=lif.RODADAS):
    real_lif = rede_real(LIFBrain, rodadas)
    real_bio = rede_real(BioBrain, rodadas)
    if not np.array_equal(real_lif["disparos"], real_bio["disparos"]):
        raise SystemExit("LIF e bio dispararam diferente: a paridade do T2 quebrou")
    s = sinteticas(lif.N_ALVO, rodadas)

    print("Ambiente:", lif.ambiente())
    print()
    print("| Medida | Neurônios | sinapses | pulsos por passo | µs por passo | 1 núcleo, passo de 1 ms "
          "| 1 núcleo, passo de 0,5 ms |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for nome, c in (("Real, LIF (densa)", real_lif), ("Real, bio (esparsa)", real_bio),
                    ("Sintética, densa", s["densa"]), ("Sintética, esparsa", s["esparsa"])):
        n = c.get("N", lif.N_ALVO)
        print(f"| {nome} | {n} | {c['sinapses']} | {c['pulsos_por_passo']:.1f} | {c['us_por_passo']:.1f} "
              f"| {_fracao(c['us_cpu_por_passo'], 1000)} | {_fracao(c['us_cpu_por_passo'], 2000)} |")
    razao = s["esparsa"]["us_por_passo"] / s["densa"]["us_por_passo"]
    print()
    print(f"630 neurônios: esparsa / densa = {razao:.2f}. Critério do T2 (esparsa não mais cara): "
          f"{'passou' if razao <= 1.0 else 'NÃO passou'}.")
    return razao


if __name__ == "__main__":
    main()
