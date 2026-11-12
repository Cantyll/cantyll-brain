"""
Mede a guarda de negligência (R1): você presente, mas sem interagir com o pet.

Pergunta: com você presente e sem carinho nem dispensa por dias, quanto sobem FUGIR e TRAVESSURA?
Controle: o mesmo protocolo com o modulador de ausência ligado (definir_ausencia(True)), que é a guarda
de ausência. Se o controle cai e a presença não, a guarda de ausência não cobre a negligência.

O que roda é o caminho da app, com as mesmas chamadas e a mesma ordem de App.think():
  Drives.update -> Drives.channels -> ComputerSenses.update(atividade, ociosidade, canais, carinho, mouse)
  -> brain.stimulate -> brain.step(100 ms)
Os canais extras da app (condicionamento, bolinha, pedido, castigo, recusa) ficam zerados: nada disso
acontece neste cenário.

Protocolo (suposições do script, não medidas de uso real):
  - LIFBrain com semente de rede 7 e de ruído 42. Perfil de tempo "normal" (o da app sem modo teste).
  - Relógio: ComputerSenses lê time.monotonic(). O script troca esse relógio por um simulado, que anda
    100 ms por bloco, junto com a rede.
  - Um dia tem 200 blocos de 100 ms para a rede (20 s simulados). A homeostase anda --horas-por-dia
    (padrão 8) por dia: cada bloco faz Drives.update com dt = horas * 3600 / 200 s. Assim a estimulação e a
    carência correm no tempo da app, e a rede vê o dia comprimido.
  - Dois terços dos dias são de trabalho (PROGRAMMING: engajado, digitando, mouse parado). O terço restante
    é de brincadeira (GAMING: não engajado, mouse mexendo, sem digitar). Sorteio com a semente do cenário.
  - Sem carinho, sem dispensa, sem recompensa (a rede não aprende), sem sono, corpo parado, arousal 0.
    O script não dorme: a energia cai a zero em cerca de 3 h e fica lá. Testado à parte, com a energia fixa em
    cheio, as motoras mudam menos de 1 Hz (o cansaço chega a elas por caminhos indiretos, via CURIOUS e PLAYFUL).
  - Habituação restaurada no início de cada dia.
  - Medida, como antes: 1 s de silêncio e 5 s de estímulo, pela taxa suave de cada população, para os dois
    padrões. Antes de cada medida, os sentidos do padrão são aquecidos 30 s simulados, para que o estímulo
    medido seja o de regime, e não a subida. Feita antes do dia 1 e depois de cada dia.
  - O estado da homeostase de cada padrão é o de um dia inteiro desse padrão (--horas-por-dia), a partir do
    estado atual, rodado só na homeostase. Sem isso, a brincadeira seria medida com o tédio que um dia de
    trabalho deixou (e vice-versa).

Uso, a partir da raiz do repositório:
  python ferramentas/medir_negligencia.py --dias 30 --saida negligencia.json

A linha PROTOCOLO descreve a execução; RESULTADO imprime cada medida em JSON; RESUMO, o mínimo e o máximo
de cada motor, por padrão.
"""
import argparse
import copy
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pestinha import config  # noqa: E402
from pestinha.core import homeostasis  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402
from pestinha.sense import senses as sentidos  # noqa: E402


class RelogioSimulado:
    """Usado no lugar de time.monotonic() dentro de sense/senses.py. Só o script o anda."""

    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t


RELOGIO = RelogioSimulado()
sentidos.time = RELOGIO

# Atividade (as de ACTIVITY_CHANNEL em senses.py), ociosidade em segundos e mouse de cada padrão.
PADRAO_TRABALHO = {"atividade": "PROGRAMMING", "ociosidade": 0.1, "mouse": False}
PADRAO_BRINCADEIRA = {"atividade": "GAMING", "ociosidade": 0.1, "mouse": True}
ENGAJADAS = ("PROGRAMMING", "DESIGNING")        # o mesmo conjunto de App.think()
MOTORES = ("FUGIR", "TRAVESSURA")
BLOCO_MS = 100
BLOCOS_POR_DIA = 200
SONDA_MS = 5000
AQUECIMENTO_BLOCOS = 300                        # 30 s simulados só dos sentidos, antes de cada medida


def passo_sentidos(sens, padrao, drives):
    """Um bloco de 100 ms dos sentidos, com os canais de homeostase deste instante (como App.think)."""
    RELOGIO.t += BLOCO_MS / 1000.0
    return sens.update(padrao["atividade"], padrao["ociosidade"], drives.channels(), False, padrao["mouse"])


def medir(brain, drives, padrao):
    """Taxa (Hz) de FUGIR e TRAVESSURA: 1 s de silêncio, depois SONDA_MS do padrão em regime. Não aprende."""
    t0 = RELOGIO.t
    sens = sentidos.ComputerSenses()            # sentidos novos: chegam ao regime deste padrão
    for _ in range(AQUECIMENTO_BLOCOS):
        intensidades = passo_sentidos(sens, padrao, drives)
    RELOGIO.t = t0                              # o dia seguinte continua do ponto em que parou
    brain.stimulate({})
    brain.step(1000)
    brain.stimulate(intensidades)
    restante = SONDA_MS
    while restante > 0:
        passo = min(400, restante)
        brain.step(passo)
        restante -= passo
    taxas = brain.pool_rates()
    return {m: round(taxas[m], 3) for m in MOTORES}


def canais(drives):
    return {k: round(v, 3) for k, v in drives.channels().items()}


def regime(drives, prof, padrao, horas):
    """Homeostase depois de um dia inteiro deste padrão, a partir do estado atual. Só a homeostase anda; a rede não."""
    copia = copy.deepcopy(drives)
    dt = horas * 3600.0 / BLOCOS_POR_DIA
    engajado = padrao["atividade"] in ENGAJADAS
    for _ in range(BLOCOS_POR_DIA):
        copia.update(dt, prof, False, 0.0, 0.0, False, engaged=engajado)
    return copia


def registro(brain, drives, prof, dia, horas):
    saida = {"dia": dia, "fim_do_dia": canais(drives)}
    for nome, padrao in (("trabalho", PADRAO_TRABALHO), ("brincadeira", PADRAO_BRINCADEIRA)):
        estado = regime(drives, prof, padrao, horas)
        saida[nome] = medir(brain, estado, padrao)
        saida["canais_" + nome] = canais(estado)
    return saida


def um_dia(brain, sens, drives, prof, padrao, horas):
    """Um dia de presença sem interação: a homeostase anda as horas do dia; a rede vê 200 blocos de 100 ms."""
    dt_drive = horas * 3600.0 / BLOCOS_POR_DIA
    engajado = padrao["atividade"] in ENGAJADAS
    for _ in range(BLOCOS_POR_DIA):
        drives.update(dt_drive, prof, False, 0.0, 0.0, False, engaged=engajado)
        intensidades = passo_sentidos(sens, padrao, drives)
        brain.stimulate(intensidades)
        brain.step(BLOCO_MS)


def protocolo(ausente, dias, semente_cenario, horas):
    rng = random.Random(semente_cenario)
    RELOGIO.t = 0.0
    brain = LIFBrain(seed=7, seed_ruido=42)
    brain.definir_ausencia(ausente)
    prof = config.profile({})
    drives = homeostasis.Drives()
    sens = sentidos.ComputerSenses()
    medidas = [registro(brain, drives, prof, 0, horas)]
    for dia in range(1, dias + 1):
        padrao = PADRAO_TRABALHO if rng.random() < 2 / 3 else PADRAO_BRINCADEIRA
        brain.reset_habituation()
        um_dia(brain, sens, drives, prof, padrao, horas)
        medidas.append(registro(brain, drives, prof, dia, horas))
    return medidas


def resumo(medidas):
    """Mínimo e máximo de cada motor ao longo dos dias, separados por padrão (não misturar: o de trabalho é zero)."""
    saida = {}
    for padrao in ("trabalho", "brincadeira"):
        saida[padrao] = {}
        for m in MOTORES:
            valores = [r[padrao][m] for r in medidas]
            saida[padrao][m] = {"min_Hz": min(valores), "max_Hz": max(valores)}
    return saida


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--horas-por-dia", type=float, default=8.0,
                    help="horas de presença que a homeostase anda por dia (padrão: 8)")
    ap.add_argument("--seed-cenario", type=int, default=7)
    ap.add_argument("--saida", default="")
    a = ap.parse_args()
    if a.horas_por_dia <= 0:
        ap.error("--horas-por-dia precisa ser maior que zero")

    protocolo_usado = {"dias": a.dias, "horas_por_dia": a.horas_por_dia, "seed_cenario": a.seed_cenario,
                       "perfil": "normal"}
    saida = {"protocolo": protocolo_usado}
    print("PROTOCOLO " + json.dumps(protocolo_usado, ensure_ascii=False), flush=True)
    for condicao, ausente in (("presente", False), ("ausente_controle", True)):
        medidas = protocolo(ausente, a.dias, a.seed_cenario, a.horas_por_dia)
        saida[condicao] = {"dias": medidas, "resumo": resumo(medidas)}
        for r in medidas:
            print("RESULTADO " + json.dumps({"condicao": condicao, **r}, ensure_ascii=False), flush=True)
        print("RESUMO " + condicao + " " + json.dumps(saida[condicao]["resumo"], ensure_ascii=False), flush=True)
    if a.saida:
        Path(a.saida).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
