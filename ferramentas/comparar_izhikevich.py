"""
NE-1 (plano, onda 2): custo e atividade do BioBrain com populações em Izhikevich, ao lado do LIF.

    python ferramentas/comparar_izhikevich.py                 # custo e atividade, todas as configurações
    python ferramentas/comparar_izhikevich.py --so custo
    python ferramentas/comparar_izhikevich.py --so atividade --config todas_membrana
    python ferramentas/comparar_izhikevich.py --calibrar ne2  # QUIET e INHIB contra o LIF, com entrada forte
    python ferramentas/comparar_izhikevich.py --portao ne2    # portão A (20 sementes) com a chave da NE-2 ligada
    python ferramentas/comparar_izhikevich.py --ajustar ne3   # ganhos da NE-3 por bisseção contra o LIF
    python ferramentas/comparar_izhikevich.py --portao ne3    # portão A com as chaves da NE-2 e da NE-3 ligadas
    python ferramentas/comparar_izhikevich.py --ajustar ne4   # ganhos dos motores (menos o STARTLE)
    python ferramentas/comparar_izhikevich.py --comportamento ne4   # reflexo de susto e MotorDecoder contra o LIF
    python ferramentas/comparar_izhikevich.py --portao ne4    # portão A com a NE-2, a NE-3 e a NE-4 ligadas

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
from pestinha.core.bio.rede import (  # noqa: E402
    EXCITATORIOS_NE3, MOTORES_NE4, adaptacao_das_chaves, gasto_das_chaves, neuronios_das_chaves)

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
    "lif": {"tipos": {}},          # tudo no LIF (desde a NE-5 o BioBrain sem argumentos segue as chaves, ligadas)
    "ne2": {"tipos": {"QUIET": "FS", "INHIB": "FS"}},
    "todas_spec": {"tipos": _todas()},
    "todas_membrana": {"tipos": _todas(), "tau_sinaptico": {name: "membrana" for name in _todas()}},
}


CHAVES = {
    "ne2": ("NE_INIBIDORES_FS",),
    "ne3": ("NE_INIBIDORES_FS", "NE_EXCITATORIOS"),
    "ne4": ("NE_INIBIDORES_FS", "NE_EXCITATORIOS", "NE_MOTORES"),
}


def _com_chaves(frente):
    """
    Os argumentos de BioBrain que as chaves da frente pedem: as dela ligadas, as das frentes seguintes desligadas
    (desde a NE-5 as três vêm ligadas em ajustes.py).
    """
    antes = {k: getattr(ajustes, k) for k in CHAVES["ne4"]}
    try:
        for k in CHAVES["ne4"]:
            setattr(ajustes, k, k in CHAVES[frente])
        tipos, ganho, tau = neuronios_das_chaves()
        gasta = gasto_das_chaves()
        lenta = adaptacao_das_chaves()
    finally:
        for k, v in antes.items():
            setattr(ajustes, k, v)
    return {"tipos": tipos, "ganho": ganho, "tau_sinaptico": tau, "gasta_corrente": gasta, "adaptacao_lenta": lenta}


CONFIGS["chaves_ne2"] = _com_chaves("ne2")
CONFIGS["chaves_ne3"] = _com_chaves("ne3")
CONFIGS["chaves_ne4"] = _com_chaves("ne4")


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


# Os contextos da simulação de noites, mais a dispensa, o carinho e o susto (onde a ALERT dispara).
CONTEXTOS_AJUSTE = [(nome, sentidos) for nome, sentidos, _ in simular_noites.CONTEXTOS] + [
    ("DISPENSA", {"DISMISS": 1.0, "BOREDOM": 0.5}),
    ("CARINHO", {"CARESS": 1.0}),
    ("SUSTO", {"MOTION": 1.0, "IMPACT": 0.5}),
]
# NE-4: os de cima, mais cada canal que move algum motor no LIF, em 1,0 e em 0,5 (perto dos limiares de decisão).
CANAIS_DOS_MOTORES = ("MOTION", "NOVELTY", "SILENCE", "WORK", "PLAY", "SOUND", "FATIGUE", "POKE", "DRAG", "DISMISS",
                      "LONELY", "CARESS", "ANTICIPATE", "TOY_NEAR", "TOY_TAKEN", "THROW", "IMPACT", "BOREDOM", "PEDIDO",
                      "PRESO", "LEMBRA_FUGA", "RECUSA", "ANTECIPA_PLACA", "VISITA", "RECEIO", "RANCOR")
CONTEXTOS_NE4 = CONTEXTOS_AJUSTE + [(f"{c} {n:.1f}", {c: n}) for c in CANAIS_DOS_MOTORES for n in (1.0, 0.5)]
# A ALERT (NE-3) e o STARTLE (NE-4) ficam fora da bisseção: os ganhos deles saem do reflexo de susto
# (--comportamento ne4 e tests/test_ne_susto.py), que a taxa somada não vê.
AJUSTAR = {"ne3": (tuple(m for m in EXCITATORIOS_NE3 if m != "ALERT"), CONTEXTOS_AJUSTE),
           "ne4": (tuple(m for m in MOTORES_NE4 if m != "STARTLE"), CONTEXTOS_NE4)}


def _taxas_por_contexto(nomes, sementes, contextos=CONTEXTOS_AJUSTE, **kwargs):
    """Hz de cada população em cada contexto (0,3 s de aquecimento, 1,5 s medidos), média das sementes."""
    taxas = np.zeros((len(contextos), len(nomes)))
    for i, (_nome, sentidos) in enumerate(contextos):
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
    Ganho de cada população da frente por bisseção (em escala log, entre 0,05 e 4): a taxa somada nos contextos
    da frente fica igual à do LIF. Todas as populações andam juntas a cada rodada, porque uma muda a entrada da
    outra. Imprime as linhas para ajustes.py e a tabela final por contexto.
    """
    nomes, contextos = AJUSTAR[frente]
    nomes = list(nomes)
    base = _com_chaves(frente)
    lif = _taxas_por_contexto(nomes, sementes, contextos, tipos={})
    baixo = {n: 0.05 for n in nomes}
    alto = {n: 4.0 for n in nomes}
    ganho = {n: math.sqrt(baixo[n] * alto[n]) for n in nomes}
    for rodada in range(rodadas):
        izh = _taxas_por_contexto(nomes, sementes, contextos, tipos=base["tipos"], tau_sinaptico=base["tau_sinaptico"],
                                  gasta_corrente=base["gasta_corrente"], adaptacao_lenta=base["adaptacao_lenta"],
                                  ganho={**base["ganho"], **ganho})
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
    print(f"\nHz por contexto, LIF / Izhikevich (medido com os ganhos da rodada {rodadas})\n")
    print("| contexto | " + " | ".join(nomes) + " |")
    print("|---|" + "---|" * len(nomes))
    for i, (nome, _) in enumerate(contextos):
        print(f"| {nome} | " + " | ".join(f"{lif[i, j]:.1f} / {izh[i, j]:.1f}" for j in range(len(nomes))) + " |")


# Reflexo de susto: estímulo de 300 ms (o susto real é curto) ou de 3 s (entrada fraca e contínua, onde o susto
# não deveria disparar mais que no LIF). Lido como o app lê: pool_rate a cada 33 ms, susto quando passa de
# Emotion.STARTLE_HZ, rearma abaixo de 30% dele.
CASOS_SUSTO = [
    ("SUSTO 300 ms", {"MOTION": 1.0, "IMPACT": 0.5}, 300), ("MOTION 1.0, 300 ms", {"MOTION": 1.0}, 300),
    ("IMPACT 1.0, 300 ms", {"IMPACT": 1.0}, 300), ("ANTECIPA_PLACA 1.0, 300 ms", {"ANTECIPA_PLACA": 1.0}, 300),
    ("ANTICIPATE 1.0, 300 ms", {"ANTICIPATE": 1.0}, 300), ("IMPACT 0.5, 300 ms", {"IMPACT": 0.5}, 300),
    ("MOTION 0.5, 3 s", {"MOTION": 0.5}, 3000), ("ANTICIPATE 0.5, 3 s", {"ANTICIPATE": 0.5}, 3000),
    ("POKE 1.0, 3 s", {"POKE": 1.0}, 3000), ("DRAG 1.0, 3 s", {"DRAG": 1.0}, 3000),
    ("IDLE, 3 s", {"SILENCE": 0.3, "BOREDOM": 1.0}, 3000),
]


def sustos(sentidos, dur_ms, sementes=range(1, 21), **kwargs):
    """
    (sementes com susto, pico médio do STARTLE em Hz) para um estímulo de dur_ms depois de 0,66 s de repouso, lido
    a cada 33 ms até 1,2 s depois do fim do estímulo (o reflexo sobe e desce nesse tempo). Susto = o pico passa de
    Emotion.STARTLE_HZ.
    """
    from pestinha.core.emotion import STARTLE_HZ
    n, picos = 0, []
    for semente in sementes:
        b = BioBrain(seed=semente, seed_ruido=semente + 100, **kwargs)
        b.stimulate({"SILENCE": 0.2})
        for _ in range(20):
            b.step(33)
        b.stimulate(sentidos)
        i, pico = b._pool_index["STARTLE"], 0.0
        for k in range((dur_ms + 1200) // 33):
            if k * 33 >= dur_ms:
                b.stimulate({"SILENCE": 0.2})
            b.step(33)
            pico = max(pico, b.pool_rate[i])
        n += pico >= STARTLE_HZ
        picos.append(pico)
    return int(n), float(np.mean(picos))


def comparar_sustos(sementes, frente="ne4"):
    """
    Cada caso de CASOS_SUSTO no LIF e na frente: (nome, sustos LIF, sustos frente, picos, z, passou). z é a
    diferença das proporções em erros-padrão (piso de variância 0,025, para os casos em 0 ou em todas); passa com
    |z| ≤ 2, o critério do portão A.
    """
    n = len(sementes)
    linhas = []
    for nome, sentidos, dur in CASOS_SUSTO:
        (nl, pl), (nz, pz) = sustos(sentidos, dur, sementes, tipos={}), sustos(sentidos, dur, sementes, **_com_chaves(frente))
        a, b = nl / n, nz / n
        z = (b - a) / math.sqrt(max(a * (1 - a) + b * (1 - b), 0.025) / n)
        linhas.append((nome, nl, nz, pl, pz, z, abs(z) <= 2.0))
    return linhas


def perfil_de_comportamento(sentidos, sementes=range(1, 11), dur_s=6.0, **kwargs):
    """Fração do tempo em cada comportamento do MotorDecoder (lido a cada 33 ms), média das sementes."""
    from collections import Counter
    conta = Counter()
    for semente in sementes:
        b = BioBrain(seed=semente, seed_ruido=semente + 200, **kwargs)
        d, t = ns.MotorDecoder(), 0.0
        b.stimulate(sentidos)
        for _ in range(int(dur_s / 0.033)):
            b.step(33)
            t += 0.033
            atual, _ = d.update(b.motor_activity(), now=t)
            conta[atual or "-"] += 1
    total = sum(conta.values())
    return {k: v / total for k, v in conta.items()}


def comportamento(frente):
    """
    O que a frente muda no que o app faz com os motores: o reflexo de susto (20 sementes) e o comportamento do
    MotorDecoder em cada contexto da NE-4 com os canais em 1,0 (10 sementes, 6 s). A distância é a da variação
    total entre as frações de tempo (0 = igual ao LIF, 1 = nada em comum).
    """
    lif = {"tipos": {}}
    frente_ = _com_chaves(frente)
    sementes = range(41, 61)
    print(f"Reflexo de susto, LIF / {frente}: sementes com susto, de {len(sementes)} (41 a 60); pico médio do STARTLE em Hz;"
          " z = diferença em erros-padrão (passa com |z| ≤ 2)\n")
    print("| estímulo | sustos | pico Hz | z | passa |")
    print("|---|---|---|---|---|")
    for nome, nl, nz, pl, pz, z, ok in comparar_sustos(sementes, frente):
        print(f"| {nome} | {nl} / {nz} | {pl:.1f} / {pz:.1f} | {z:+.1f} | {'sim' if ok else 'NÃO'} |", flush=True)
    print(f"\nComportamento do MotorDecoder, LIF / {frente} (fração do tempo; os três mais frequentes)\n")
    print("| contexto | LIF | " + frente + " | distância |")
    print("|---|---|---|---|")
    soma = 0.0
    contextos = [(n, s) for n, s in CONTEXTOS_NE4 if not n.endswith(" 0.5")]
    for nome, sentidos in contextos:
        a, b = perfil_de_comportamento(sentidos, **lif), perfil_de_comportamento(sentidos, **frente_)
        dist = 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))
        soma += dist

        def top(p):
            return ", ".join(f"{k} {v:.2f}" for k, v in sorted(p.items(), key=lambda x: -x[1])[:3])
        print(f"| {nome} | {top(a)} | {top(b)} | {dist:.2f} |", flush=True)
    print(f"\nDistância média: {soma / len(contextos):.3f} em {len(contextos)} contextos")


def portao(frente, extra=()):
    """Portão A da linha de base com as chaves da frente ligadas."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import linha_de_base
    for k in CHAVES["ne4"]:
        setattr(ajustes, k, k in CHAVES[frente])
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
    parser.add_argument("--comportamento", choices=("ne3", "ne4"), help="só o reflexo de susto e o MotorDecoder, contra o LIF")
    args, extra = parser.parse_known_args(argv)
    if args.portao:
        return portao(args.portao, extra)
    if extra:
        parser.error(f"argumentos desconhecidos: {' '.join(extra)}")
    if args.calibrar:
        return calibrar(args.calibrar)
    if args.ajustar:
        return ajustar(args.ajustar)
    if args.comportamento:
        return comportamento(args.comportamento)
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
