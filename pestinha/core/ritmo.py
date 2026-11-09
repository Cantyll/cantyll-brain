"""
RITMO - o relógio de 24 h e a pressão de sono: quando ele dorme e quando acorda.

C = cos(2π(h − pico)/24) vale 1 no pico de vigília (fim da tarde, por padrão) e −1 no
fundo da noite. A pressão de sono P (0 a 1) sobe devagar acordado e cai dormindo.

Resultado: de dia ele fica acordado; à noite, com P alta, dorme; de manhã, quando P
caiu, acorda. Os limiares de dormir e de acordar são diferentes (histerese), então ele
não fica trocando de estado à toa.

Dormir e acordar são só isso aqui. Se ele está preso, segurado ou em protesto, quem
decide é o sono (sleep.py), que checa essas condições antes de dormir.
"""

import math
from datetime import datetime

from .. import ajustes


def hora_local(agora=None):
    """Hora local com fração: 21,5 é 21h30."""
    t = agora or datetime.now()
    return t.hour + t.minute / 60.0 + t.second / 3600.0


def circadiano(hora, pico=None):
    """C de -1 a 1 para a hora dada, com o pico de vigília em `pico` (horas)."""
    pico = ajustes.PICO_VIGILIA_H if pico is None else pico
    return math.cos(2.0 * math.pi * (hora - pico) / 24.0)


def quer_dormir(pressao, c):
    """Dorme se a pressão passou do limiar e o relógio está na noite; ou se a pressão passou do limite forçado."""
    return ((pressao > ajustes.LIMIAR_DORME_PRESSAO and c < ajustes.LIMIAR_DORME_C)
            or pressao > ajustes.LIMIAR_DORME_FORCADO)


def quer_acordar(pressao, c):
    """Acorda se a pressão caiu; ou se está no pico de vigília com a pressão já baixa."""
    return (pressao < ajustes.LIMIAR_ACORDA_PRESSAO
            or (c > ajustes.LIMIAR_ACORDA_C and pressao < ajustes.LIMIAR_ACORDA_PRESSAO_DIA))


def avancar_pressao(pressao, dt_s, dormindo):
    """P depois de dt_s segundos. A conta é exata para taxa constante, então o tamanho do passo não muda o resultado."""
    horas = dt_s / 3600.0
    if dormindo:
        return pressao * math.exp(-ajustes.K_PRESSAO_DORMINDO * horas)
    return 1.0 - (1.0 - pressao) * math.exp(-ajustes.K_PRESSAO_ACORDADO * horas)
