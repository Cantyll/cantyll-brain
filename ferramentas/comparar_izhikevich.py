"""
NE-1 (plano, onda 2): custo e atividade do BioBrain com populações em Izhikevich, ao lado do LIF.

    python ferramentas/comparar_izhikevich.py                 # custo e atividade, todas as configurações
    python ferramentas/comparar_izhikevich.py --so custo
    python ferramentas/comparar_izhikevich.py --so atividade --config todas_membrana

Configurações (nenhuma é o padrão do app: o padrão do BioBrain segue sem população em Izhikevich):

- lif: o BioBrain do T2, todas as populações em LIF (o caminho de sempre, bit a bit).
- ne2: QUIET e INHIB em FS, com os τ sinápticos da spec (5 e 10 ms). É o recorte da NE-2.
- todas_spec: todos os interneurônios e motores em Izhikevich (excitatórios e motores RS, inibitórios FS),
  τ da spec e a escala de partida (escala_de_corrente).
- todas_membrana: o mesmo, com τ sináptico = τ_m que a população tinha no LIF.

Custo: µs por passo de 1 ms da rede (o Izhikevich integra v em duas metades de 0,5 ms dentro dele), mediana de
RODADAS, uma thread de BLAS, como medir_custo_bio.py. A fração de um núcleo é µs por passo / 1000. Atividade:
Hz por população em 5 situações de 3 s cada (as de test_bio_dinamica.py), com a mesma semente e o mesmo ruído.

Não é a referência: é o que esta máquina fez nesta execução. Rode na máquina de referência
(docs/CUSTO_DO_PASSO.md) antes de decidir o orçamento. A atividade não é calibração: mostra de onde a NE-2 a
NE-4 partem.
"""
import os

# Uma thread só, como em medir_custo_passo.py: o número é o custo de um núcleo.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pestinha.core import nervous_system as ns  # noqa: E402
from pestinha.core.bio import BioBrain  # noqa: E402

RODADAS = 7
ESTIMULO = {"WORK": 0.8, "TYPING": 0.3}
SITUACOES = [
    ("trabalho", {"WORK": 1.0, "TYPING": 0.6}),
    ("brincadeira", {"PLAY": 1.0, "BOREDOM": 0.3}),
    ("dispensa", {"DISMISS": 1.0}),
    ("tédio", {"SILENCE": 0.3, "BOREDOM": 1.0}),
    ("carinho", {"CARESS": 1.0, "POKE": 0.5}),
]


def _todas():
    tipos = {name: ("FS" if kind == "inh" else "RS") for name, kind, *_ in ns.INTER_SPEC}
    tipos.update({m[0]: "RS" for m in ns.MOTOR_SPEC})
    return tipos


CONFIGS = {
    "lif": {},
    "ne2": {"tipos": {"QUIET": "FS", "INHIB": "FS"}},
    "todas_spec": {"tipos": _todas()},
    "todas_membrana": {"tipos": _todas(), "tau_sinaptico": {name: "membrana" for name in _todas()}},
}


def cerebro(config, seed_ruido=42):
    return BioBrain(seed=7, seed_ruido=seed_ruido, **CONFIGS[config])


def custo(config, rodadas=RODADAS):
    """Mediana de µs (relógio e CPU) por passo de 1 ms, com 1 s simulado por rodada, e pulsos por passo."""
    b = cerebro(config)

    def um_segundo():
        b.stimulate(ESTIMULO)
        for _ in range(10):
            b.step(100)

    for _ in range(3):                                   # aquece e deixa a rede ativa
        um_segundo()
    antes = b.disparos.sum()
    tempos = []
    for _ in range(rodadas):
        t0, c0 = time.perf_counter(), time.process_time()
        um_segundo()
        tempos.append((time.perf_counter() - t0, time.process_time() - c0))
    return {
        "us_por_passo": 1e6 * statistics.median(t for t, _ in tempos) / 1000,
        "us_cpu_por_passo": 1e6 * statistics.median(c for _, c in tempos) / 1000,
        "pulsos_por_passo": float(b.disparos.sum() - antes) / (1000 * rodadas),
        "izhikevich": 0 if b.izhikevich is None else b.izhikevich.n,
        "N": b.N,
    }


def atividade(config):
    """Hz por população (só interneurônios e motores) em cada situação, 3 s cada, na ordem de SITUACOES."""
    b = cerebro(config, seed_ruido=5)
    linhas = []
    for _nome, sentidos in SITUACOES:
        b.stimulate(sentidos)
        b.disparos[:] = 0
        for _ in range(30):
            b.step(100)
        linhas.append(b.disparos / (3.0 * b.pool_sizes))
    nomes = [p["name"] for p in b.pools if p["group"] != "sensory"]
    taxas = np.array(linhas)[:, [b._pool_index[n] for n in nomes]]
    return nomes, taxas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--so", choices=("custo", "atividade"), help="só uma das duas partes")
    parser.add_argument("--config", choices=sorted(CONFIGS), action="append",
                        help="configuração (repetível); padrão: todas")
    parser.add_argument("--rodadas", type=int, default=RODADAS)
    args = parser.parse_args(argv)
    configs = args.config or list(CONFIGS)

    if args.so != "atividade":
        print("Custo por passo de 1 ms (semente 7, estímulo fixo; mediana de", args.rodadas, "rodadas)\n")
        print("| configuração | em Izhikevich | µs/passo | µs CPU/passo | % de um núcleo | pulsos/passo |")
        print("|---|---|---|---|---|---|")
        for config in configs:
            c = custo(config, args.rodadas)
            print(f"| {config} | {c['izhikevich']} de {c['N']} | {c['us_por_passo']:.1f} | "
                  f"{c['us_cpu_por_passo']:.1f} | {c['us_por_passo'] / 10:.1f}% | {c['pulsos_por_passo']:.2f} |")
        print()

    if args.so != "custo":
        base_nomes, base = atividade("lif")
        for config in configs:
            if config == "lif":
                continue
            nomes, taxas = atividade(config)
            assert nomes == base_nomes
            print(f"Atividade (Hz), lif / {config}, semente 7, ruído 5, 3 s por situação\n")
            print("| população | " + " | ".join(n for n, _ in SITUACOES) + " |")
            print("|---|" + "---|" * len(SITUACOES))
            for k, nome in enumerate(nomes):
                celulas = " | ".join(f"{base[s, k]:.1f} / {taxas[s, k]:.1f}" for s in range(len(SITUACOES)))
                print(f"| {nome} | {celulas} |")
            print()


if __name__ == "__main__":
    main()
