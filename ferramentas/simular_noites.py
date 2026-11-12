"""
Simula noites de vida do pet, com o código real da rede, da memória e do sono, para ver o que o
aprendizado faz em semanas: se alguma população morre (PLAYFUL) ou satura (GLOOM).

    python ferramentas/simular_noites.py                      # 30 noites, cenário "duro"
    python ferramentas/simular_noites.py --cenario misto      # outro cenário (veja CENARIOS)
    python ferramentas/simular_noites.py --noites 60 --semente 3 --json saida.json
    python ferramentas/simular_noites.py --pulsos             # o replay simula os pulsos (mais lento, mesmas sinapses)

É critério de aceitação de toda mudança em dinâmica de neurônio, plasticidade, replay ou homeostase
(tests/test_simulacao_noites.py roda uma versão dela). Com a mesma semente, o resultado se repete.

O que é real: LIFBrain (aprendizado, replay, SHY), EpisodicMemory (episódios em arquivo, escolha
do replay), SleepController (a noite inteira, quadro a quadro) e os números de ajustes.py e do perfil.

O que é suposição, e não medida de uso real:
- O dia. Cada cenário diz quantas travessuras são dispensadas, quantas ficam na tela e quantos carinhos
  ele ganha por dia, e em que atividade cada coisa acontece (CONTEXTOS). Ninguém mediu isso ainda.
- O dia é comprimido: só os instantes com recompensa são simulados. O aprendizado de dia depende dos
  níveis sensoriais e da recompensa, não dos pulsos, então as sinapses saem iguais às de um dia inteiro.
- No replay, por padrão, os pulsos não são simulados (`_RedeDeSimulacao`). No LIFBrain o aprendizado
  depende só dos níveis sensoriais e de δ, então as sinapses saem idênticas (há um teste disso), e a
  simulação fica várias vezes mais rápida. Quando o aprendizado depender dos pulsos (STDP), use --pulsos.
- A noite: ele adormece com pressão de sono PRESSAO_AO_DORMIR e acorda em LIMIAR_ACORDA_PRESSAO. A
  pressão só anda quando não há replay para simular, como numa noite de verdade, em que uma hora de
  sono é muito mais longa que os segundos de replay.

Como ler a saída: "uso" é a taxa média da população nos contextos do cenário, medida de manhã num
gêmeo da rede com ruído fixo. A coluna % compara com o dia 0 (nada aprendido). "peso GLOOM" é a maior
sinapse aprendida da tristeza, em % do limite LEARN_MAX.
"""
import argparse
import contextlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from pestinha import ajustes  # noqa: E402
from pestinha import config  # noqa: E402
from pestinha.core import episodic  # noqa: E402
from pestinha.core import nervous_system as ns  # noqa: E402
from pestinha.core.episodic import EpisodicMemory  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402
from pestinha.mind.sleep import SleepController  # noqa: E402

# (atividade, níveis sensoriais naquele momento, fração das travessuras e dos carinhos que acontece ali).
# Programando não há tédio (a homeostase trata trabalho como estímulo); nas outras, o tédio vai de leve a alto.
CONTEXTOS = [
    ("PROGRAMMING", {"WORK": 1.0, "TYPING": 0.6}, 0.30),
    ("BROWSING", {"WEB": 1.0, "TYPING": 0.2, "BOREDOM": 0.4}, 0.25),
    ("GAMING", {"PLAY": 1.0, "BOREDOM": 0.3}, 0.15),
    ("SOCIAL", {"SOCIAL": 1.0, "TYPING": 0.5, "BOREDOM": 0.3}, 0.10),
    ("MUSIC", {"SOUND": 1.0, "BOREDOM": 0.6}, 0.10),
    ("IDLE", {"SILENCE": 0.3, "BOREDOM": 1.0}, 0.10),
]

# Por dia: travessuras dispensadas, travessuras que ficam na tela (aceitas) e carinhos. perfil: de config.PROFILES.
CENARIOS = {
    "misto": {"dispensas": 20, "aceitas": 5, "carinhos": 10, "perfil": "normal",
              "descricao": "20 dispensas, 5 aceitas e 10 carinhos por dia (a suposição do PR #5)"},
    "duro": {"dispensas": 20, "aceitas": 0, "carinhos": 0, "perfil": "normal",
             "descricao": "20 dispensas por dia, nenhuma aceita e nenhum carinho"},
    "duro_teste": {"dispensas": 20, "aceitas": 0, "carinhos": 0, "perfil": "teste",
                   "descricao": "o cenário duro com a taxa de aprendizado do modo teste (4 vezes a normal)"},
    "carinhoso": {"dispensas": 3, "aceitas": 10, "carinhos": 25, "perfil": "normal",
                  "descricao": "3 dispensas, 10 aceitas e 25 carinhos por dia"},
}

PRESSAO_AO_DORMIR = 0.82        # P de quem ficou ~14 h acordado depois de acordar em 0,25 (ritmo.py)
MEDIDA_AQUECE_MS = 300
MEDIDA_MS = 2000                # por contexto, em cada medida
MEDIDA_SEMENTE = 99             # ruído do gêmeo de medida: o mesmo em todos os dias
POPULACOES = ("PLAYFUL", "CALM", "FRUSTRATION", "GLOOM", "CHEER", "SAD")
DIAS_PADRAO = (0, 1, 2, 3, 5, 10, 15, 20, 25, 30)


class _RedeDeSimulacao(LIFBrain):
    """
    LIFBrain em que o replay não simula os pulsos. O aprendizado do LIFBrain usa os níveis sensoriais, a
    elegibilidade e δ; os pulsos não entram na conta. Pular o passo da rede dá as mesmas sinapses.
    """

    def replay(self, sentidos, ms, delta, rate=ns.LEARN_RATE_PADRAO, teto=None):
        entrada = {k: v for k, v in sentidos.items() if k in self.sensory_names}
        restante = int(ms)
        while restante > 0:
            chunk = min(100, restante)
            self.stimulate(entrada)
            self.learn(delta, 0.0, chunk / 1000.0, rate, teto)
            restante -= chunk


class _Necessidades:
    """Só a pressão de sono, que a simulação move à mão."""
    pressao = PRESSAO_AO_DORMIR

    def describe(self):
        return f"pressão {self.pressao:.2f}"


@contextlib.contextmanager
def _ajustes_trocados(**valores):
    """Troca valores de ajustes.py durante a simulação e devolve os originais no fim."""
    antigos = {nome: getattr(ajustes, nome) for nome in valores}
    for nome, valor in valores.items():
        setattr(ajustes, nome, valor)
    try:
        yield
    finally:
        for nome, valor in antigos.items():
            setattr(ajustes, nome, valor)


@contextlib.contextmanager
def _memoria_calada():
    """A memória escreve uma linha de log por episódio; em 30 dias são centenas."""
    antigo = episodic.log
    episodic.log = lambda *args, **kwargs: None
    try:
        yield
    finally:
        episodic.log = antigo


def _sorteia_contexto(rng):
    pesos = np.array([peso for _, _, peso in CONTEXTOS])
    nome, sentidos, _ = CONTEXTOS[int(rng.choice(len(CONTEXTOS), p=pesos / pesos.sum()))]
    return nome, dict(sentidos)


def _assenta(brain, sentidos):
    """O contexto já dura bem mais que a elegibilidade (4 s): ela chega ao nível dos sentidos."""
    brain.stimulate(sentidos)
    brain.learn(0.0, 0.0, 60.0, 0.0)


def _carinho(brain, sentidos, segundos, taxa):
    """Carinho como no app: o canal CARESS sobe (0,8 s), o teclado para, e a recompensa vale enquanto dura."""
    nivel = 0.0
    for _ in range(int(round(segundos * 10))):
        nivel += (1.0 - nivel) * (1.0 - math.exp(-0.1 / 0.8))
        momento = dict(sentidos, CARESS=nivel, TYPING=0.0)
        brain.stimulate(momento)
        brain.learn(ajustes.RECOMPENSA_CARINHO, 0.0, 0.1, taxa)


def simular_dia(brain, memoria, rng, cenario, perfil):
    """Um dia comprimido: os eventos do cenário, em ordem sorteada, cada um num contexto sorteado."""
    taxa = perfil["learn_rate"]
    eventos = ["dispensa"] * cenario["dispensas"] + ["aceita"] * cenario["aceitas"] + ["carinho"] * cenario["carinhos"]
    rng.shuffle(eventos)
    for evento in eventos:
        atividade, sentidos = _sorteia_contexto(rng)
        _assenta(brain, sentidos)
        if evento == "carinho":
            _carinho(brain, sentidos, float(rng.uniform(2.0, 5.0)), taxa)
            continue
        memoria.sentidos_atuais = dict(sentidos)
        objeto = object()
        episodio = memoria.start(memoria.context(atividade, "curioso"), "bilhete", objeto)
        if evento == "dispensa":
            # fechou entre 1 s e a paciência do perfil; a rede sente o pulso DISMISS e a penalidade (mischief_ctl)
            memoria.on_dismiss(objeto, float(rng.uniform(1.0, perfil["dismiss_patience"])), perfil["dismiss_patience"])
            pulso = 0.7
            for _ in range(int(round(ajustes.PENALIDADE_DISPENSA * 10))):
                brain.stimulate(dict(sentidos, DISMISS=pulso))
                brain.learn(ajustes.PUNICAO_DISPENSA, 0.0, 0.1, taxa)
                pulso *= math.exp(-0.1 / 6.0)
        else:
            # ficou na tela até valer como aceita (episodic.tick)
            memoria.tick(episodio["inicio"] + perfil["episode_ok"] + 1.0, perfil["episode_ok"], perfil["episode_window"])


def simular_noite(brain, sono, perfil, pressao_ao_dormir=PRESSAO_AO_DORMIR, pressao_ao_acordar=None):
    """
    Uma noite pelo SleepController real: adormece, e a cada quadro o sono tem 100 ms de simulação para
    replay, e o SHY acompanha a pressão. A pressão cai um pouco só nos quadros em que não havia nada para simular.
    """
    fim = ajustes.LIMIAR_ACORDA_PRESSAO if pressao_ao_acordar is None else pressao_ao_acordar
    degrau = (pressao_ao_dormir - fim) / (4.0 * ajustes.HOMEOSTASE_AJUSTES_NOITE)
    sono.drives.pressao = pressao_ao_dormir
    sono.fall_asleep()
    while True:
        usado = sono.replay_passo(brain, ajustes.REPLAY_MS_POR_FRAME, perfil["learn_rate"])
        if usado:
            continue
        if sono.drives.pressao <= fim + 1e-12:
            break
        sono.drives.pressao = max(fim, sono.drives.pressao - degrau)
    sono.wake(startled=False)


def medir(brain):
    """
    Taxa (Hz) de cada população em cada contexto, num gêmeo da rede que começa do zero e usa sempre o
    mesmo ruído. Devolve ({população: média ponderada pelo uso}, {contexto: {população: Hz}}).
    """
    por_contexto = {}
    for nome, sentidos, _ in CONTEXTOS:
        gemeo = LIFBrain(seed=brain.seed, temperament=brain.temperament, seed_ruido=MEDIDA_SEMENTE)
        gemeo.learned[:] = brain.learned
        gemeo._apply_learning()
        gemeo.stimulate(sentidos)
        for _ in range(MEDIDA_AQUECE_MS // 100):
            gemeo.step(100)
        antes = gemeo.disparos.copy()
        for _ in range(MEDIDA_MS // 100):
            gemeo.step(100)
        pulsos = gemeo.disparos - antes
        por_contexto[nome] = {pop: float(pulsos[gemeo._pool_index[pop]] / (gemeo.pool(pop)["n"] * MEDIDA_MS / 1000.0))
                              for pop in POPULACOES}
    total = sum(peso for _, _, peso in CONTEXTOS)
    uso = {pop: sum(peso * por_contexto[nome][pop] for nome, _, peso in CONTEXTOS) / total for pop in POPULACOES}
    return uso, por_contexto


def simular(cenario="duro", noites=30, semente=7, dias=None, pasta=None, pulsos=False, **trocas):
    """
    Roda `noites` dias e noites. dias: em quais manhãs medir (padrão DIAS_PADRAO; o dia 0 e o último entram sempre).
    pulsos: True simula os pulsos no replay, como o app (mais lento, mesmas sinapses no LIFBrain).
    trocas: valores de ajustes.py só para esta simulação (por exemplo HOMEOSTASE_SHY=0.0, para comparar).
    Devolve uma lista de linhas (dict), uma por manhã medida. A última traz também "aprendido".
    """
    regras = CENARIOS[cenario] if isinstance(cenario, str) else cenario
    perfil = config.PROFILES[regras["perfil"]]
    dias = set(DIAS_PADRAO if dias is None else dias) | {0, noites}
    linhas = []
    with contextlib.ExitStack() as pilha:
        pilha.enter_context(_ajustes_trocados(**trocas))
        pilha.enter_context(_memoria_calada())
        if pasta is None:
            pasta = pilha.enter_context(tempfile.TemporaryDirectory())
        pasta = Path(pasta)
        memoria = EpisodicMemory(pasta / "episodes.jsonl", pasta / "preferences.json")
        brain = (LIFBrain if pulsos else _RedeDeSimulacao)(seed=semente, seed_ruido=semente + 1000)
        sono = SleepController(None, _Necessidades(), memoria, lambda: False)
        rng = np.random.default_rng(semente)
        j = {post: k for k, post in enumerate(brain.plastic_posts)}
        base = None
        for dia in range(noites + 1):
            if dia in dias:
                uso, por_contexto = medir(brain)
                base = uso if base is None else base
                linhas.append({
                    "dia": dia,
                    "uso_hz": uso,
                    "uso_relativo": {pop: (uso[pop] / base[pop] if base[pop] > 0 else None) for pop in POPULACOES},
                    "por_contexto": por_contexto,
                    "peso_gloom_max": float(brain.learned[:, j["GLOOM"]].max() / ns.LEARN_MAX),
                    "peso_playful_min": float(brain.learned[:, j["PLAYFUL"]].min() / -ns.LEARN_MIN),
                })
            if dia == noites:
                linhas[-1]["aprendido"] = brain.learned.tolist()
                break
            simular_dia(brain, memoria, rng, regras, perfil)
            simular_noite(brain, sono, perfil)
    return linhas


def _porcento(valor):
    return "   --" if valor is None else f"{100.0 * valor:4.0f}%"


def imprimir(titulo, linhas):
    """Tabela de uma simulação."""
    print(titulo)
    print("  dia | PLAYFUL uso      | CALM uso         | GLOOM uso | SAD uso | peso GLOOM | peso PLAYFUL")
    for linha in linhas:
        uso, rel = linha["uso_hz"], linha["uso_relativo"]
        print(f"  {linha['dia']:3d} | {uso['PLAYFUL']:5.2f} Hz {_porcento(rel['PLAYFUL'])}   | "
              f"{uso['CALM']:5.2f} Hz {_porcento(rel['CALM'])}   | {uso['GLOOM']:6.2f} Hz | {uso['SAD']:5.2f}Hz | "
              f"{100 * linha['peso_gloom_max']:5.0f}% lim | {-100 * linha['peso_playful_min']:6.0f}% lim")
    print()


def main():
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    parser = argparse.ArgumentParser(description="Simula noites de vida do pet (replay e SHY).")
    parser.add_argument("--cenario", default="duro", choices=sorted(CENARIOS))
    parser.add_argument("--noites", type=int, default=30)
    parser.add_argument("--semente", type=int, default=7)
    parser.add_argument("--sem-shy", action="store_true", help="roda também sem o SHY (HOMEOSTASE_SHY = 0), para comparar")
    parser.add_argument("--pulsos", action="store_true", help="simula os pulsos no replay, como o app (mais lento)")
    parser.add_argument("--json", help="grava as linhas neste arquivo")
    args = parser.parse_args()

    regras = CENARIOS[args.cenario]
    print(f"Cenário {args.cenario}: {regras['descricao']}. Perfil {regras['perfil']}, semente {args.semente}, "
          f"{args.noites} noites.\n")
    saida = {"com_shy": simular(args.cenario, args.noites, args.semente, pulsos=args.pulsos)}
    imprimir(f"HOMEOSTASE_SHY = {ajustes.HOMEOSTASE_SHY}", saida["com_shy"])
    if args.sem_shy:
        saida["sem_shy"] = simular(args.cenario, args.noites, args.semente, pulsos=args.pulsos, HOMEOSTASE_SHY=0.0)
        imprimir("Sem SHY (HOMEOSTASE_SHY = 0)", saida["sem_shy"])
    if args.json:
        Path(args.json).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Linhas gravadas em {args.json}")


if __name__ == "__main__":
    main()
