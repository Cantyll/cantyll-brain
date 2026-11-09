"""
Mede quanto custa um passo da rede, em fração de um núcleo de CPU (docs/CUSTO_DO_PASSO.md).

    python ferramentas/medir_custo_passo.py

Duas medidas, na mesma máquina e com uma thread de BLAS só, para o número ser comparável:

1. Rede real: LIFBrain atual (470 neurônios, passo de 1 ms), 1 s simulado por rodada.
2. Rede de 630 neurônios: o mesmo `_substep` do LIFBrain, com arrays do tamanho pedido pela
   spec (seção 10). Os valores são sintéticos, com a mesma densidade da rede real. O custo de
   uma multiplicação densa depende das formas dos arrays, não dos valores, então a medida vale
   para a rede real de 630 quando ela existir. Para o passo de 0,5 ms, cada segundo simulado
   pede 2000 passos (em vez de 1000).

Não é uma previsão: é o que esta máquina fez nesta execução. Rode de novo na máquina de referência
antes de decidir D2 (passo de 0,5 ms) e o orçamento da seção 10.
"""
import os

# Uma thread só: o número é o custo de um núcleo, sem o BLAS espalhar a conta pelos outros.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import platform  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from pestinha.core.nervous_system import LIFBrain  # noqa: E402

RODADAS = 15              # repetições; a conta é a mediana
SIM_MS = 1000             # 1 s simulado por rodada
N_ALVO = 630              # neurônios da spec (seção 10, linha "Total")


def rede_real_por_passo():
    """Custo real de um passo de 1 ms da rede atual, em µs (mediana de RODADAS)."""
    b = LIFBrain(seed=7, seed_ruido=42)

    def simular_um_segundo():
        # step() aceita no máximo 400 ms por chamada: 1 s são dez chamadas de 100 ms
        for _ in range(SIM_MS // 100):
            b.step(100)

    for _ in range(3):                                   # aquece e deixa a rede ativa
        b.stimulate({"WORK": 0.8, "TYPING": 0.3})
        simular_um_segundo()
    tempos = []
    for _ in range(RODADAS):
        b.stimulate({"WORK": 0.8, "TYPING": 0.3})
        t0, c0 = time.perf_counter(), time.process_time()
        simular_um_segundo()
        t1, c1 = time.perf_counter(), time.process_time()
        tempos.append((t1 - t0, c1 - c0))
    passos = SIM_MS                                      # passos de 1 ms por rodada
    wall = statistics.median(t for t, _ in tempos)
    cpu = statistics.median(c for _, c in tempos)
    return {
        "N": b.N, "Ns": b.Ns, "dt_ms": 1.0, "passos_por_s": 1000,
        "us_por_passo": 1e6 * wall / passos,
        "fracao_nucleo": cpu / (SIM_MS / 1000.0),        # CPU por segundo simulado
        "sinapses": int(np.count_nonzero(b.W)),
    }


def rede_sintetica(N, base):
    """LIFBrain com N neurônios e a mesma sensorial da rede real: só os arrays, nada de lógica nova."""
    rng = np.random.default_rng(1)
    b = object.__new__(LIFBrain)                         # sem __init__: só as formas importam
    Ns = base.Ns
    Nl = N - Ns
    P = len(base.pools)
    b.N, b.Ns, b.Nl = N, Ns, Nl
    b.rng = np.random.default_rng(42)
    b.W_lif = np.ascontiguousarray(rng.random((N, Nl)) * (rng.random((N, Nl)) < 0.07) * 0.05)
    b.spikes = np.zeros(N)
    b.pre_gain = np.ones(N)
    b.p = b.pre_gain[:Ns]                                # view, como no __init__
    b.s_prob = rng.random(Ns) * 0.02
    b.s_d = rng.uniform(0.0, 0.05, Ns)
    b.s_rec = np.full(Ns, 0.001 / 5.0)
    b.v = np.zeros(Nl)
    b.a = np.zeros(Nl)
    b.ref = np.zeros(Nl, dtype=int)
    b.decay = np.exp(-1.0 / rng.uniform(5.0, 20.0, Nl))
    b.adapt_decay = np.exp(-1.0 / rng.uniform(50.0, 500.0, Nl))
    b.adapt_b = rng.uniform(0.0, 0.1, Nl)
    b.trace = np.zeros(N)
    b.ausente = False                                    # modulador de ausência: desligado, como com você presente
    b._idx_ausencia = np.empty(0, dtype=int)
    b.pool_counts = np.zeros(P)
    onehot = np.zeros((N, P))
    onehot[np.arange(N), rng.integers(0, P, N)] = 1.0
    b.onehot = onehot
    return b


def sintetica_por_passo(N, base):
    """Custo de um passo (_substep) com N neurônios, em µs (mediana de RODADAS)."""
    b = rede_sintetica(N, base)
    for _ in range(200):                                 # aquece
        b._substep()
    amostras = 2000                                      # passos por rodada
    tempos = []
    for _ in range(RODADAS):
        t0, c0 = time.perf_counter(), time.process_time()
        for _ in range(amostras):
            b._substep()
        t1, c1 = time.perf_counter(), time.process_time()
        tempos.append((t1 - t0, c1 - c0, amostras))
    wall = statistics.median(t / n for t, _, n in tempos)
    cpu = statistics.median(c / n for _, c, n in tempos)
    return {"us_por_passo": 1e6 * wall, "us_cpu_por_passo": 1e6 * cpu}


def ambiente():
    try:
        modelo = next(l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                      if l.startswith("model name"))
    except Exception:
        modelo = platform.processor() or platform.machine()
    return {"cpu": modelo, "nucleos": os.cpu_count(), "python": platform.python_version(),
            "numpy": np.__version__, "sistema": platform.platform()}


def main():
    real = rede_real_por_passo()
    base = LIFBrain(seed=7)
    s1 = sintetica_por_passo(base.N, base)               # 470 pelo mesmo caminho: referência de controle
    s630 = sintetica_por_passo(N_ALVO, base)              # o passo custa o mesmo em 1 ms ou 0,5 ms

    print("Ambiente:", ambiente())
    print()
    print("| Medida | Neurônios | dt | passos/s simulado | µs por passo | fração de 1 núcleo |")
    print("|---|---:|---:|---:|---:|---:|")
    print(f"| Rede real (LIF atual) | {real['N']} | 1 ms | 1000 | {real['us_por_passo']:.1f} "
          f"| {100 * real['fracao_nucleo']:.1f}% |")
    print(f"| Sintética, mesmo caminho (controle) | {base.N} | 1 ms | 1000 | {s1['us_por_passo']:.1f} "
          f"| {100 * 1000 * s1['us_cpu_por_passo'] / 1e6:.1f}% |")
    print(f"| Sintética 630 | {N_ALVO} | 1 ms | 1000 | {s630['us_por_passo']:.1f} "
          f"| {100 * 1000 * s630['us_cpu_por_passo'] / 1e6:.1f}% |")
    print(f"| Sintética 630 | {N_ALVO} | 0,5 ms | 2000 | {s630['us_por_passo']:.1f} "
          f"| {100 * 2000 * s630['us_cpu_por_passo'] / 1e6:.1f}% |")
    print()
    print(f"Sinapses da rede real (semente 7): {real['sinapses']}. Ns = {base.Ns}.")


if __name__ == "__main__":
    main()
