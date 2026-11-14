"""
Susto em eventos curtos, com as chaves da frente NE ligadas, contra o LIF (pedido antes da NE-5, 2026-11-13).

O susto é lido na subida do STARTLE (Emotion.STARTLE_HZ; o MotorDecoder põe o STARTLE na frente), e a taxa média
não enxerga isso. Com a NE-3 e a NE-4 como entraram na main, o pet se assustava a mais com estímulo fraco e contínuo
(MOTION 0,5, ANTICIPATE 0,5, cutucão), porque a ALERT em RS respondia achatada. A correção: ALERT em CH e a
adaptação lenta do LIF na ALERT e no STARTLE (rede.ADAPTACAO_LENTA).

Critério: em cada caso de comparar_izhikevich.CASOS_SUSTO, as sementes com susto (de 40, sementes 41 a 80, que não
foram usadas na escolha dos ganhos) ficam a no máximo 2 erros-padrão do LIF, como no portão A.

Rodar: python -m pytest tests/test_ne_susto.py -q
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core.bio.neuronios import Izhikevich, escala_de_corrente
from pestinha.core.bio.rede import ADAPTACAO_LENTA, TIPO_NE3, TIPO_NE4, adaptacao_das_chaves

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import comparar_izhikevich as ci  # noqa: E402

SEMENTES = range(41, 81)


def test_alert_e_startle_em_ch_com_adaptacao_lenta(monkeypatch):
    assert TIPO_NE3["ALERT"] == TIPO_NE4["STARTLE"] == "CH"
    assert ADAPTACAO_LENTA == ("ALERT", "STARTLE")
    for chave in ("NE_INIBIDORES_FS", "NE_EXCITATORIOS", "NE_MOTORES"):
        monkeypatch.setattr(ajustes, chave, False)
    assert adaptacao_das_chaves() == set()                     # chaves desligadas: nada muda
    monkeypatch.setattr(ajustes, "NE_EXCITATORIOS", True)
    assert adaptacao_das_chaves() == {"ALERT"}
    monkeypatch.setattr(ajustes, "NE_MOTORES", True)
    assert adaptacao_das_chaves() == {"ALERT", "STARTLE"}


def test_adaptacao_lenta_faz_o_que_o_lif_faz():
    """
    Um neurônio CH com entrada constante: com a adaptação lenta do LIF da ALERT (b = 0,03, τ = 1,5 s), a taxa cai
    ao longo dos segundos, como no LIF; sem ela, fica. Depois de 5 s parado, volta. adapt_b = 0 é bit a bit o de
    antes.
    """
    tau, b, ta = 20.0, 0.03, 1.5
    esc = escala_de_corrente("CH", tau)
    limiar = esc * (1.0 - np.exp(-1.0 / tau))
    c, zero = np.array([1.6 * (1.0 - np.exp(-1.0 / tau))]), np.zeros(1)

    def taxas(z):
        janelas = []
        for entrada in (c, c, c, zero, zero, zero, zero, zero, c):
            janelas.append(sum(int(z.passo(entrada, zero, zero)[0]) for _ in range(1000)))
        return janelas

    com = taxas(Izhikevich(["CH"], esc, tau, tau, gasto=limiar, adapt_b=b, adapt_tau=ta, limiar=limiar))
    sem = taxas(Izhikevich(["CH"], esc, tau, tau, gasto=limiar))
    assert com[2] < 0.8 * com[0]                                # adapta em segundos
    assert abs(sem[2] - sem[0]) <= 0.1 * sem[0]                 # sem adaptação lenta, não
    assert com[8] >= 0.9 * com[0]                               # e se recupera parado
    zerada = Izhikevich(["CH"], esc, tau, tau, gasto=limiar, adapt_b=0.0, adapt_tau=ta, limiar=limiar)
    assert taxas(zerada) == sem


@pytest.fixture(scope="module")
def comparacao():
    return {linha[0]: linha for linha in ci.comparar_sustos(SEMENTES, "ne4")}


@pytest.mark.parametrize("caso", [c[0] for c in ci.CASOS_SUSTO])
def test_susto_como_no_lif(comparacao, caso):
    nome, lif, ne, pico_lif, pico_ne, z, passou = comparacao[caso]
    assert passou, f"{nome}: {lif} sustos no LIF, {ne} com a NE (de {len(SEMENTES)}), z = {z:+.1f}"
