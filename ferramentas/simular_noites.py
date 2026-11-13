"""
Simula noites de vida do pet, com o código real da rede, da memória e do sono, para ver o que o
aprendizado faz em semanas: se alguma população morre (PLAYFUL) ou satura (GLOOM).

    python ferramentas/simular_noites.py                      # 30 noites, cenário "duro"
    python ferramentas/simular_noites.py --cenario misto      # outro cenário (veja CENARIOS)
    python ferramentas/simular_noites.py --noites 60 --semente 3 --json saida.json
    python ferramentas/simular_noites.py --sonos 3            # a noite picada em 3 sonos (acordado e dormindo de novo)
    python ferramentas/simular_noites.py --sem-shy            # roda também o controle sem SHY
    python ferramentas/simular_noites.py --sem-habituacao     # roda também sem a habituação à dispensa
    python ferramentas/simular_noites.py --pulsos             # o replay simula os pulsos (mais lento, mesmas sinapses)
    python ferramentas/simular_noites.py --cerebro bio        # o mesmo com o BioBrain (core/bio)
    python ferramentas/simular_noites.py --lar                # com a frente lar ligada (teto do carinho)
    python ferramentas/simular_noites.py --cenario so_o_lar   # lar ligado e você sem interagir

É critério de aceitação de toda mudança em dinâmica de neurônio, plasticidade, replay ou homeostase
(tests/test_simulacao_noites.py roda uma versão dela). Com a mesma semente, o resultado se repete.

O que é real: LIFBrain ou BioBrain (aprendizado, replay, SHY), EpisodicMemory (episódios em arquivo, escolha
do replay), SleepController (a noite inteira, quadro a quadro) e os números de ajustes.py e do perfil.

O que é suposição, e não medida de uso real:
- O dia. Cada cenário diz quantas travessuras são dispensadas, quantas ficam na tela e quantos carinhos
  ele ganha por dia, e em que atividade cada coisa acontece (CONTEXTOS). Ninguém mediu isso ainda.
- A hora de cada evento: sorteada por igual nas DIA_ACORDADO_S horas acordado, com um sorteio à parte
  (com a habituação desligada, o resultado é o mesmo de antes dela). Só a habituação à dispensa usa a hora.
- O dia é comprimido: só os instantes com recompensa são simulados. O aprendizado de dia depende dos
  níveis sensoriais e da recompensa, não dos pulsos, então as sinapses saem iguais às de um dia inteiro.
- No replay, por padrão, os pulsos não são simulados (`_RedeDeSimulacao`). No LIFBrain o aprendizado
  depende só dos níveis sensoriais e de δ, então as sinapses saem idênticas (há um teste disso), e a
  simulação fica várias vezes mais rápida. Quando o aprendizado depender dos pulsos (STDP), use --pulsos.
- A noite: ele adormece com pressão de sono PRESSAO_AO_DORMIR e acorda em LIMIAR_ACORDA_PRESSAO. A
  pressão só anda quando não há replay para simular, como numa noite de verdade, em que uma hora de
  sono é muito mais longa que os segundos de replay.
- O lar (--lar): do que a frente lar muda, só o teto do carinho ensina, e é o que entra aqui (o mesmo
  cálculo de mind/lar_ctl.py, no relógio da simulação). A travessura de casa não tem recompensa nem
  episódio, e a carência não entra na rede pelo aprendizado, então nenhuma das duas muda as sinapses.
  O cenário "so_o_lar" é o lar ligado com você presente e sem interagir: sem dispensa, sem carinho e
  sem travessura na tela (a do tédio vai para o canto dele).
- A noite picada (--sonos N): a mesma queda de pressão, repartida por igual em N sonos. Entre um e outro
  ele acorda (carinho, susto, o app reaberto) e adormece de novo na hora. Cada adormecer monta a fila de
  replay outra vez, como no app.

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
from pestinha.core.habituacao import Habituacao  # noqa: E402
from pestinha.core.bio import BioBrain  # noqa: E402
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
    "so_o_lar": {"dispensas": 0, "aceitas": 0, "carinhos": 0, "perfil": "normal", "lar": True,
                 "descricao": "lar ligado e você sem interagir: nada na tela, nenhuma dispensa, nenhum carinho"},
}

PRESSAO_AO_DORMIR = 0.82        # P de quem ficou ~14 h acordado depois de acordar em 0,25 (ritmo.py)
DIA_ACORDADO_S = 14 * 3600.0    # s acordado por dia, em que os eventos do cenário se espalham
DIA_S = 24 * 3600.0
DEGRAUS_DA_NOITE = 40           # em quantos degraus a pressão cai numa noite inteira
MEDIDA_AQUECE_MS = 300
MEDIDA_MS = 2000                # por contexto, em cada medida
MEDIDA_SEMENTE = 99             # ruído do gêmeo de medida: o mesmo em todos os dias
POPULACOES = ("PLAYFUL", "CALM", "FRUSTRATION", "GLOOM", "CHEER", "SAD")
DIAS_PADRAO = (0, 1, 2, 3, 5, 10, 15, 20, 25, 30)


class _ReplaySemPulsos:
    """
    Replay que não simula os pulsos. O aprendizado do LIFBrain (e do BioBrain, que tem a mesma regra até o
    PL-1) usa os níveis sensoriais, a elegibilidade e δ; os pulsos não entram na conta. Pular o passo da rede
    dá as mesmas sinapses.
    """

    def replay(self, sentidos, ms, delta, rate=ns.LEARN_RATE_PADRAO, teto=None):
        entrada = {k: v for k, v in sentidos.items() if k in self.sensory_names}
        restante = int(ms)
        while restante > 0:
            chunk = min(100, restante)
            self.stimulate(entrada)
            self.learn(delta, 0.0, chunk / 1000.0, rate, teto)
            restante -= chunk


class _RedeDeSimulacao(_ReplaySemPulsos, LIFBrain):
    """LIFBrain com o replay sem pulsos."""


class _RedeDeSimulacaoBio(_ReplaySemPulsos, BioBrain):
    """BioBrain com o replay sem pulsos."""


# nome -> (cérebro de verdade, cérebro com o replay sem pulsos)
CEREBROS = {"lif": (LIFBrain, _RedeDeSimulacao), "bio": (BioBrain, _RedeDeSimulacaoBio)}


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


class TetoCarinho:
    """
    O teto do carinho da frente lar (mind/lar_ctl.py, LarModulo.ajustar_recompensa) no relógio da simulação:
    cada segundo de carinho soma 1 a uma carga que vaza com τ = LAR_RECUPERACAO_CARINHO_H, e o carinho
    ensina 0,5 ** (carga / LAR_MEIA_VIDA_CARINHO_S).
    """

    def __init__(self):
        self.carga = 0.0
        self.em = None

    def peso(self, agora):
        """Quanto o carinho ensina em `agora` (s), já com o vazamento desde a última vez."""
        if self.em is not None:
            self.carga *= math.exp(-max(0.0, agora - self.em) / (ajustes.LAR_RECUPERACAO_CARINHO_H * 3600.0))
        self.em = agora
        meia = ajustes.LAR_MEIA_VIDA_CARINHO_S
        return 1.0 if meia <= 0 else 0.5 ** (self.carga / meia)


def _carinho(brain, sentidos, segundos, taxa, teto=None, agora=0.0):
    """
    Carinho como no app: o canal CARESS sobe (0,8 s), o teclado para, e a recompensa vale enquanto dura.
    teto: o TetoCarinho do lar (None: o carinho ensina inteiro, como sem a frente). agora: hora do começo (s).
    """
    nivel = 0.0
    for k in range(int(round(segundos * 10))):
        nivel += (1.0 - nivel) * (1.0 - math.exp(-0.1 / 0.8))
        momento = dict(sentidos, CARESS=nivel, TYPING=0.0)
        brain.stimulate(momento)
        if teto is None:
            brain.learn(ajustes.RECOMPENSA_CARINHO, 0.0, 0.1, taxa)
        else:
            brain.learn(ajustes.RECOMPENSA_CARINHO * teto.peso(agora + 0.1 * k), 0.0, 0.1, taxa)
            teto.carga += 0.1


def simular_dia(brain, memoria, rng, cenario, perfil, habituacao=None, relogio=None, inicio_s=0.0, teto=None):
    """
    Um dia comprimido: os eventos do cenário, em ordem sorteada, cada um num contexto sorteado.
    habituacao: a Habituacao do app (None: toda dispensa pesa 1). relogio: o sorteio das horas (só a
    habituação e o teto usam; separado de rng para não mudar o resto). inicio_s: a hora em que o dia começa.
    teto: o TetoCarinho do lar (None: sem a frente lar).
    """
    taxa = perfil["learn_rate"]
    eventos = ["dispensa"] * cenario["dispensas"] + ["aceita"] * cenario["aceitas"] + ["carinho"] * cenario["carinhos"]
    rng.shuffle(eventos)
    horas = (np.sort(relogio.uniform(0.0, DIA_ACORDADO_S, len(eventos))) if relogio is not None
             else np.zeros(len(eventos)))
    for evento, hora in zip(eventos, horas):
        atividade, sentidos = _sorteia_contexto(rng)
        _assenta(brain, sentidos)
        if evento == "carinho":
            _carinho(brain, sentidos, float(rng.uniform(2.0, 5.0)), taxa, teto, inicio_s + float(hora))
            if habituacao is not None:
                habituacao.desabituar(ajustes.DESABITUACAO_CARINHO)
            continue
        memoria.sentidos_atuais = dict(sentidos)
        objeto = object()
        episodio = memoria.start(memoria.context(atividade, "curioso"), "bilhete", objeto)
        if evento == "dispensa":
            # fechou entre 1 s e a paciência do perfil; a rede sente o pulso DISMISS e a penalidade (mischief_ctl)
            memoria.on_dismiss(objeto, float(rng.uniform(1.0, perfil["dismiss_patience"])), perfil["dismiss_patience"])
            peso = habituacao.registrar(inicio_s + float(hora)) if habituacao is not None else 1.0
            pulso = 0.7
            for _ in range(int(round(ajustes.PENALIDADE_DISPENSA * 10))):
                brain.stimulate(dict(sentidos, DISMISS=pulso))
                brain.learn(ajustes.PUNICAO_DISPENSA * peso, 0.0, 0.1, taxa)
                pulso *= math.exp(-0.1 / 6.0)
        else:
            # ficou na tela até valer como aceita (episodic.tick)
            memoria.tick(episodio["inicio"] + perfil["episode_ok"] + 1.0, perfil["episode_ok"], perfil["episode_window"])


def simular_noite(brain, sono, perfil, pressao_ao_dormir=PRESSAO_AO_DORMIR, pressao_ao_acordar=None):
    """
    Um sono pelo SleepController real: adormece, e a cada quadro o sono tem 100 ms de simulação para o
    replay e a homeostase. A pressão cai um pouco só nos quadros em que não havia nada para simular.
    """
    fim = ajustes.LIMIAR_ACORDA_PRESSAO if pressao_ao_acordar is None else pressao_ao_acordar
    degrau = (PRESSAO_AO_DORMIR - ajustes.LIMIAR_ACORDA_PRESSAO) / DEGRAUS_DA_NOITE
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
        classe = BioBrain if isinstance(brain, BioBrain) else LIFBrain
        gemeo = classe(seed=brain.seed, temperament=brain.temperament, seed_ruido=MEDIDA_SEMENTE)
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


def simular(cenario="duro", noites=30, semente=7, dias=None, pasta=None, pulsos=False, sonos=1, cerebro="lif",
            lar=None, **trocas):
    """
    Roda `noites` dias e noites. dias: em quais manhãs medir (padrão DIAS_PADRAO; o dia 0 e o último entram sempre).
    pulsos: True simula os pulsos no replay, como o app (mais lento, mesmas sinapses no LIFBrain).
    sonos: em quantos sonos cada noite é picada (1: a noite inteira de uma vez).
    cerebro: "lif" (LIFBrain) ou "bio" (BioBrain).
    lar: True liga a frente lar (o teto do carinho). None: o que o cenário disser (só "so_o_lar" liga).
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
        brain = CEREBROS[cerebro][0 if pulsos else 1](seed=semente, seed_ruido=semente + 1000)
        sono = SleepController(None, _Necessidades(), memoria, lambda: False)
        rng = np.random.default_rng(semente)
        relogio = np.random.default_rng(semente + 2000)
        habituacao = Habituacao(ajustes.HABITUACAO_DISPENSA, ajustes.RECUPERACAO_DISPENSA_H * 3600.0)
        teto = TetoCarinho() if (regras.get("lar", False) if lar is None else lar) else None
        j = {post: k for k, post in enumerate(brain.plastic_posts)}
        pressoes = np.linspace(PRESSAO_AO_DORMIR, ajustes.LIMIAR_ACORDA_PRESSAO, int(sonos) + 1)
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
            simular_dia(brain, memoria, rng, regras, perfil, habituacao, relogio, dia * DIA_S, teto)
            for de, ate in zip(pressoes[:-1], pressoes[1:]):
                simular_noite(brain, sono, perfil, float(de), float(ate))
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
              f"{100 * linha['peso_gloom_max']:5.0f}% lim | {-100 * linha['peso_playful_min'] + 0.0:6.0f}% lim")
    print()


def main():
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    parser = argparse.ArgumentParser(description="Simula noites de vida do pet (replay e SHY).")
    parser.add_argument("--cenario", default="duro", choices=sorted(CENARIOS))
    parser.add_argument("--noites", type=int, default=30)
    parser.add_argument("--semente", type=int, default=7)
    parser.add_argument("--sonos", type=int, default=1, help="em quantos sonos cada noite é picada (padrão: 1)")
    parser.add_argument("--sem-shy", action="store_true", help="roda também sem o SHY (HOMEOSTASE_SHY = 0), para comparar")
    parser.add_argument("--sem-habituacao", action="store_true",
                        help="roda também sem a habituação à dispensa (HABITUACAO_DISPENSA = 0), para comparar")
    parser.add_argument("--pulsos", action="store_true", help="simula os pulsos no replay, como o app (mais lento)")
    parser.add_argument("--cerebro", default="lif", choices=sorted(CEREBROS), help="lif (padrão) ou bio")
    parser.add_argument("--lar", action="store_true", help="liga a frente lar (o teto do carinho) em qualquer cenário")
    parser.add_argument("--json", help="grava as linhas neste arquivo")
    args = parser.parse_args()

    regras = CENARIOS[args.cenario]
    print(f"Cenário {args.cenario}: {regras['descricao']}. Perfil {regras['perfil']}, semente {args.semente}, "
          f"{args.noites} noites, {args.sonos} sono(s) por noite, cérebro {args.cerebro}"
          f"{', lar ligado' if args.lar or regras.get('lar') else ''}.\n")
    comum = {"pulsos": args.pulsos, "sonos": args.sonos, "cerebro": args.cerebro, "lar": True if args.lar else None}
    saida = {"com_shy": simular(args.cenario, args.noites, args.semente, **comum)}
    imprimir(f"HOMEOSTASE_SHY = {ajustes.HOMEOSTASE_SHY}, HABITUACAO_DISPENSA = {ajustes.HABITUACAO_DISPENSA}, "
             f"RECUPERACAO_DISPENSA_H = {ajustes.RECUPERACAO_DISPENSA_H}", saida["com_shy"])
    if args.sem_shy:
        saida["sem_shy"] = simular(args.cenario, args.noites, args.semente, HOMEOSTASE_SHY=0.0, **comum)
        imprimir("Sem SHY (HOMEOSTASE_SHY = 0)", saida["sem_shy"])
    if args.sem_habituacao:
        saida["sem_habituacao"] = simular(args.cenario, args.noites, args.semente,
                                          HABITUACAO_DISPENSA=0.0, **comum)
        imprimir("Sem habituação à dispensa (HABITUACAO_DISPENSA = 0)", saida["sem_habituacao"])
    if args.json:
        Path(args.json).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Linhas gravadas em {args.json}")


if __name__ == "__main__":
    main()
