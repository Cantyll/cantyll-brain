"""
NE-1 (plano, onda 2): custo e atividade do BioBrain com populações em Izhikevich, ao lado do LIF.

    python ferramentas/comparar_izhikevich.py                 # custo e atividade, todas as configurações
    python ferramentas/comparar_izhikevich.py --so custo
    python ferramentas/comparar_izhikevich.py --so atividade --config todas_membrana
    python ferramentas/comparar_izhikevich.py --calibrar ne2  # QUIET e INHIB contra o LIF, com entrada forte
    python ferramentas/comparar_izhikevich.py --portao ne2    # portão A (20 sementes) com a chave da NE-2 ligada
    python ferramentas/comparar_izhikevich.py --ajustar ne3   # ganhos da NE-3 por bisseção contra o LIF
    python ferramentas/comparar_izhikevich.py --portao ne3    # portão A com as chaves da NE-2 e da NE-3 ligadas

Configurações (nenhuma é o padrão do app: o padrão do BioBrain segue sem população em Izhikevich):

- lif: o BioBrain do T2, todas as populações em LIF (o caminho de sempre, bit a bit).
- ne2: QUIET e INHIB em FS, com os τ sinápticos da spec (5 e 10 ms). É o recorte da NE-2.
- todas_spec: todos os interneurônios e motores em Izhikevich (excitatórios e motores RS, inibitórios FS),
  τ da spec e a escala de partida (escala_de_corrente).
- todas_membrana: o mesmo, com τ sináptico = τ_m que a população tinha no LIF.
- chaves_ne2: o que ajustes.NE_INIBIDORES_FS = True liga (QUIET e INHIB em FS, τ = τ_m, ganhos de ajustes.py).

--calibrar: taxa de cada população com todos os canais em 1,0 e em 0,6 (onde a INHIB dispara de fato), média de 5
sementes, LIF contra a configuração com o ganho de ajustes.py e com outros ganhos ao lado.

--portao: liga as chaves da frente em ajustes.py e roda ferramentas/linha_de_base.py --cerebro bio (portão A contra
o LIF registrado, 20 sementes, 3 cenários). A chave só chega aos processos filhos com o início por fork (Linux);
nos outros sistemas a ferramenta roda num processo só.

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
import math  # noqa: E402
import multiprocessing  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pestinha import ajustes  # noqa: E402
from pestinha.core import nervous_system as ns  # noqa: E402
from pestinha.core.bio import BioBrain, acelerado  # noqa: E402
from pestinha.core.bio.rede import EXCITATORIOS_NE3, gasto_das_chaves, neuronios_das_chaves  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simular_noites  # noqa: E402

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


CHAVES = {
    "ne2": ("NE_INIBIDORES_FS",),
    "ne3": ("NE_INIBIDORES_FS", "NE_EXCITATORIOS"),
}


def _com_chaves(frente):
    """Os argumentos de BioBrain que as chaves da frente pedem (as outras chaves como estão em ajustes.py)."""
    antes = {k: getattr(ajustes, k) for k in CHAVES[frente]}
    try:
        for k in CHAVES[frente]:
            setattr(ajustes, k, True)
        tipos, ganho, tau = neuronios_das_chaves()
        gasta = gasto_das_chaves()
    finally:
        for k, v in antes.items():
            setattr(ajustes, k, v)
    return {"tipos": tipos, "ganho": ganho, "tau_sinaptico": tau, "gasta_corrente": gasta}


CONFIGS["chaves_ne2"] = _com_chaves("ne2")
CONFIGS["chaves_ne3"] = _com_chaves("ne3")


def cerebro(config, seed_ruido=42, numba=None):
    """BioBrain da configuração. numba: True ou False força o caminho do passo; None segue ajustes.NE_NUMBA."""
    antes = ajustes.NE_NUMBA
    if numba is not None:
        ajustes.NE_NUMBA = numba
    try:
        return BioBrain(seed=7, seed_ruido=seed_ruido, **CONFIGS[config])
    finally:
        ajustes.NE_NUMBA = antes


CALIBRAR = {"ne2": ("QUIET", "INHIB")}
VIZINHAS = ("ALERT", "FOCUS", "CURIOUS", "PLAYFUL", "WATCH")


def calibrar(frente, sementes=(3, 7, 11, 13, 17)):
    """Hz por população (as da frente e as que elas inibem), todos os canais em 1,0 e em 0,6, média das sementes."""
    alvo = CALIBRAR[frente]
    nomes = alvo + VIZINHAS
    base = _com_chaves(frente)

    def medir(**kwargs):
        por_nivel = {1.0: [], 0.6: []}
        for semente in sementes:
            b = BioBrain(seed=semente, seed_ruido=3, **kwargs)
            for nivel in por_nivel:
                b.stimulate({c: nivel for c in ns.SENSORY_SPEC})
                for _ in range(5):
                    b.step(100)
                b.disparos[:] = 0
                for _ in range(30):
                    b.step(100)
                taxa = b.disparos / (3.0 * b.pool_sizes)
                por_nivel[nivel].append([taxa[b._pool_index[n]] for n in nomes])
        return {nivel: np.mean(v, axis=0) for nivel, v in por_nivel.items()}

    linhas = [("lif", medir(tipos={}))]
    for fator in (0.8, 1.0, 1.2):
        ganho = {n: g * fator for n, g in base["ganho"].items()}
        rotulo = "ganhos de ajustes.py" if fator == 1.0 else f"ganhos de ajustes.py × {fator}"
        linhas.append((rotulo, medir(tipos=base["tipos"], ganho=ganho, tau_sinaptico=base["tau_sinaptico"])))
    print(f"Calibração da {frente.upper()} (Hz, média das sementes {', '.join(map(str, sementes))}; "
          f"ganhos de ajustes.py: {base['ganho']})\n")
    for nivel in (1.0, 0.6):
        print(f"Todos os canais em {nivel}\n")
        print("| configuração | " + " | ".join(nomes) + " |")
        print("|---|" + "---|" * len(nomes))
        for rotulo, taxas in linhas:
            print(f"| {rotulo} | " + " | ".join(f"{x:.1f}" for x in taxas[nivel]) + " |")
        print()


AJUSTAR = {"ne3": EXCITATORIOS_NE3}
# Os contextos da simulação de noites, mais a dispensa, o carinho e o susto (onde a ALERT dispara).
CONTEXTOS_AJUSTE = [(nome, sentidos) for nome, sentidos, _ in simular_noites.CONTEXTOS] + [
    ("DISPENSA", {"DISMISS": 1.0, "BOREDOM": 0.5}),
    ("CARINHO", {"CARESS": 1.0}),
    ("SUSTO", {"MOTION": 1.0, "IMPACT": 0.5}),
]


def _taxas_por_contexto(nomes, sementes, **kwargs):
    """Hz de cada população em cada contexto (0,3 s de aquecimento, 1,5 s medidos), média das sementes."""
    taxas = np.zeros((len(CONTEXTOS_AJUSTE), len(nomes)))
    for i, (_nome, sentidos) in enumerate(CONTEXTOS_AJUSTE):
        for semente in sementes:
            b = BioBrain(seed=semente, seed_ruido=simular_noites.MEDIDA_SEMENTE, **kwargs)
            b.stimulate(sentidos)
            for _ in range(3):
                b.step(100)
            b.disparos[:] = 0
            for _ in range(15):
                b.step(100)
            taxa = b.disparos / (1.5 * b.pool_sizes)
            taxas[i] += [taxa[b._pool_index[n]] for n in nomes]
    return taxas / len(sementes)


def ajustar(frente, sementes=(3, 7, 11), rodadas=10):
    """
    Ganho de cada população da frente por bisseção (em escala log, entre 0,05 e 2): a taxa somada nos contextos
    de CONTEXTOS_AJUSTE fica igual à do LIF. Todas as populações andam juntas a cada rodada, porque uma muda a
    entrada da outra. Imprime as linhas para ajustes.py e a tabela final por contexto.
    """
    nomes = list(AJUSTAR[frente])
    base = _com_chaves(frente)
    lif = _taxas_por_contexto(nomes, sementes, tipos={})
    baixo = {n: 0.05 for n in nomes}
    alto = {n: 2.0 for n in nomes}
    ganho = {n: math.sqrt(baixo[n] * alto[n]) for n in nomes}
    for rodada in range(rodadas):
        izh = _taxas_por_contexto(nomes, sementes, tipos=base["tipos"], tau_sinaptico=base["tau_sinaptico"],
                                  gasta_corrente=base["gasta_corrente"], ganho={**base["ganho"], **ganho})
        razoes = []
        for j, n in enumerate(nomes):
            alvo, atual = lif[:, j].sum(), izh[:, j].sum()
            if alvo < 0.5:                                 # sem atividade no LIF: não há o que igualar
                continue
            razoes.append(f"{n} {atual / alvo:.2f}")
            if atual > alvo:
                alto[n] = ganho[n]
            else:
                baixo[n] = ganho[n]
            ganho[n] = math.sqrt(baixo[n] * alto[n])
        print(f"rodada {rodada + 1}: Bio/LIF " + ", ".join(razoes))
    print("\nPara ajustes.py:\n")
    for n in nomes:
        print(f"NE_GANHO_{n} = {ganho[n]:.3f}")
    print(f"\nHz por contexto, LIF / Izhikevich (o ganho da última linha de cada população é o da rodada {rodadas})\n")
    print("| população | " + " | ".join(nome for nome, _ in CONTEXTOS_AJUSTE) + " |")
    print("|---|" + "---|" * len(CONTEXTOS_AJUSTE))
    for j, n in enumerate(nomes):
        print(f"| {n} | " + " | ".join(f"{lif[i, j]:.1f} / {izh[i, j]:.1f}" for i in range(len(CONTEXTOS_AJUSTE))) + " |")


def portao(frente, extra=()):
    """Portão A da linha de base com as chaves da frente ligadas."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import linha_de_base
    for k in CHAVES[frente]:
        setattr(ajustes, k, True)
    argv = ["linha_de_base.py", "--cerebro", "bio", *extra]
    if multiprocessing.get_start_method() != "fork" and "--processos" not in extra:
        argv += ["--processos", "1"]
    print(f"Chaves ligadas: {', '.join(CHAVES[frente])}\n")
    sys.argv = argv
    linha_de_base.main()


def custo(config, rodadas=RODADAS, numba=None):
    """Mediana de µs (relógio e CPU) por passo de 1 ms, com 1 s simulado por rodada, e pulsos por passo."""
    b = cerebro(config, numba=numba)

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
        "caminho": "numba" if b.numba else "numpy",
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
    parser.add_argument("--calibrar", choices=sorted(CALIBRAR), help="só a calibração da frente")
    parser.add_argument("--portao", choices=sorted(CHAVES), help="só o portão A com as chaves da frente ligadas")
    parser.add_argument("--ajustar", choices=sorted(AJUSTAR), help="só o ajuste dos ganhos da frente, por bisseção")
    args, extra = parser.parse_known_args(argv)
    if args.portao:
        return portao(args.portao, extra)
    if extra:
        parser.error(f"argumentos desconhecidos: {' '.join(extra)}")
    if args.calibrar:
        return calibrar(args.calibrar)
    if args.ajustar:
        return ajustar(args.ajustar)
    configs = args.config or list(CONFIGS)

    if args.so != "atividade":
        caminhos = (False, True) if acelerado.DISPONIVEL else (False,)
        print("Custo por passo de 1 ms (semente 7, estímulo fixo; mediana de", args.rodadas, "rodadas)")
        print("Numba:", f"versão {acelerado.VERSAO}" if acelerado.DISPONIVEL else acelerado.MOTIVO, "\n")
        print("| configuração | caminho | em Izhikevich | µs/passo | µs CPU/passo | % de um núcleo | pulsos/passo |")
        print("|---|---|---|---|---|---|---|")
        for config in configs:
            for numba in caminhos:
                c = custo(config, args.rodadas, numba=numba)
                print(f"| {config} | {c['caminho']} | {c['izhikevich']} de {c['N']} | {c['us_por_passo']:.1f} | "
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
