"""
Habituação à dispensa (decisão 9 = A): dispensas repetidas no mesmo dia pesam cada vez menos no
aprendizado, o peso volta com o tempo, e o carinho devolve a resposta (desabituação). O pulso de
raiva e a memória do episódio não habituam.

Rodar: python -m pytest tests/test_habituacao_dispensa.py -q
Só os rápidos: python -m pytest tests/test_habituacao_dispensa.py -q -k "not trinta_noites"
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core.habituacao import Habituacao

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import simular_noites  # noqa: E402

HORA = 3600.0


# ---------------- o modelo ----------------

def test_primeira_dispensa_pesa_inteira_e_as_seguidas_pesam_menos():
    h = Habituacao(meia_vida=5, recuperacao_s=4 * HORA)
    pesos = [h.registrar(0.0) for _ in range(10)]
    assert pesos[0] == 1.0
    assert all(a > b for a, b in zip(pesos, pesos[1:]))
    assert pesos[5] == pytest.approx(0.5)          # depois de meia_vida dispensas, vale a metade


def test_teto_soma_de_uma_rajada_nunca_passa_do_teto():
    """O teto: mil dispensas seguidas somam menos que teto_rajada() dispensas inteiras (7,7 com meia-vida 5)."""
    h = Habituacao(meia_vida=5, recuperacao_s=4 * HORA)
    total = sum(h.registrar(0.0) for _ in range(1000))
    assert h.teto_rajada() == pytest.approx(7.73, abs=0.01)
    assert total <= h.teto_rajada() + 1e-9
    assert total > h.teto_rajada() - 0.01           # e chega perto dele: o teto é justo


def test_teto_num_dia_inteiro_cresce_bem_menos_que_o_numero_de_dispensas():
    """Num dia de 14 h, 20, 100 ou 400 dispensas: o peso total quase não muda depois de certo ponto."""
    totais = {}
    for n in (20, 100, 400):
        h = Habituacao(meia_vida=5, recuperacao_s=4 * HORA)
        totais[n] = sum(h.registrar(t) for t in np.linspace(0.0, 14 * HORA, n))
    assert totais[20] < 20
    assert totais[400] < 2 * totais[20]             # 20 vezes mais dispensas, menos que o dobro do castigo
    # o limite de um dia: a rajada inicial mais o que a recuperação devolve em 14 h
    limite = Habituacao(5, 4 * HORA).teto_rajada() * (1 + 14 / 4)
    assert all(total < limite for total in totais.values())


def test_o_peso_volta_com_o_tempo():
    h = Habituacao(meia_vida=5, recuperacao_s=4 * HORA)
    for _ in range(20):
        h.registrar(0.0)
    assert h.peso(0.0) < 0.1
    assert h.peso(4 * HORA) > h.peso(HORA) > h.peso(0.0)
    assert h.peso(10 * HORA) > 0.75                  # depois de uma noite de 10 h, perto de inteira de novo


def test_peso_nao_registra_e_registrar_devolve_o_peso_de_antes():
    h = Habituacao(meia_vida=5, recuperacao_s=HORA)
    h.registrar(0.0)
    antes = h.peso(10.0)
    assert h.peso(10.0) == antes
    assert h.registrar(10.0) == antes
    assert h.peso(10.0) < antes


def test_carinho_desabitua():
    h = Habituacao(meia_vida=5, recuperacao_s=8 * HORA)
    for _ in range(10):
        h.registrar(0.0)
    h.desabituar(0.5)
    assert h.peso(0.0) == pytest.approx(0.5)        # metade da carga de 10: peso de carga 5
    h.desabituar(1.0)
    assert h.peso(0.0) == 1.0
    h2 = Habituacao(meia_vida=5, recuperacao_s=HORA)
    h2.desabituar(1.0)                              # carinho antes de qualquer dispensa: nada muda
    assert h2.registrar(0.0) == 1.0


def test_meia_vida_zero_desliga():
    h = Habituacao(meia_vida=0, recuperacao_s=HORA)
    assert [h.registrar(0.0) for _ in range(50)] == [1.0] * 50
    assert h.teto_rajada() == math.inf


def test_recuperacao_precisa_ser_positiva():
    with pytest.raises(ValueError):
        Habituacao(meia_vida=5, recuperacao_s=0.0)


def test_ajustes_validam_os_dois_numeros():
    assert "HABITUACAO_DISPENSA" in ajustes._LIMITES and "RECUPERACAO_DISPENSA_H" in ajustes._LIMITES
    antigo = ajustes.RECUPERACAO_DISPENSA_H
    ajustes.RECUPERACAO_DISPENSA_H = 0.0
    try:
        with pytest.raises(ValueError):
            ajustes.validar()
    finally:
        ajustes.RECUPERACAO_DISPENSA_H = antigo
    ajustes.validar()


# ---------------- no controlador: só o aprendizado habitua ----------------

class _Gravador:
    def __init__(self):
        self.chamadas = []

    def __getattr__(self, nome):
        return lambda *a, **k: self.chamadas.append(nome)


def _controlador():
    from pestinha.mind.mischief_ctl import MischiefController
    sentidos, memoria, necessidades, emocao = _Gravador(), _Gravador(), _Gravador(), _Gravador()
    ctl = MischiefController(None, memoria, necessidades, sentidos, None, emocao, lambda: False)
    return ctl, sentidos, memoria


def test_controlador_diminui_o_peso_da_penalidade_mas_nao_a_raiva_nem_a_memoria():
    ctl, sentidos, memoria = _controlador()
    perfil = {"dismiss_patience": 60.0, "drama_window": 1.0, "drama_count": 999}
    pesos = []
    for i in range(15):
        ctl.on_dismissed(object(), 30.0, perfil, 100.0 + 10.0 * i)
        pesos.append(ctl.peso_penalidade)
        assert ctl.penalty_active(100.0 + 10.0 * i)      # a penalidade ainda vale, só pesa menos
    assert pesos[0] == 1.0 and pesos[-1] < 0.5
    assert sentidos.chamadas.count("dismissed") == 15     # o pulso de raiva, inteiro em toda dispensa
    assert memoria.chamadas.count("on_dismiss") == 15     # o episódio negativo, em toda dispensa


def test_controlador_carinho_devolve_o_peso_so_no_comeco_do_carinho(monkeypatch):
    monkeypatch.setattr(ajustes, "DESABITUACAO_CARINHO", 0.5)
    ctl, _, _ = _controlador()
    perfil = {"dismiss_patience": 60.0, "drama_window": 1.0, "drama_count": 999}
    for i in range(10):
        ctl.on_dismissed(object(), 30.0, perfil, 100.0)
    carga = ctl.habituacao.carga
    ctl.ao_carinho(True)
    assert ctl.habituacao.carga == pytest.approx(carga / 2)
    for _ in range(20):                                   # o mesmo carinho, quadro a quadro: não conta de novo
        ctl.ao_carinho(True)
    assert ctl.habituacao.carga == pytest.approx(carga / 2)
    ctl.ao_carinho(False)
    ctl.ao_carinho(True)                                  # outro carinho
    assert ctl.habituacao.carga == pytest.approx(carga / 4)


# ---------------- na simulação de noites ----------------

def test_simulacao_com_habituacao_desligada_e_a_mesma_de_antes():
    """O sorteio das horas é separado: com HABITUACAO_DISPENSA = 0 nada muda em relação à simulação sem horas."""
    desligada = simular_noites.simular("duro", noites=2, semente=3, dias=(2,), HABITUACAO_DISPENSA=0.0)
    regras = simular_noites.CENARIOS["duro"]
    perfil = simular_noites.config.PROFILES[regras["perfil"]]
    import tempfile
    from pestinha.core.episodic import EpisodicMemory
    with tempfile.TemporaryDirectory() as pasta, simular_noites._memoria_calada():
        pasta = Path(pasta)
        memoria = EpisodicMemory(pasta / "e.jsonl", pasta / "p.json")
        brain = simular_noites._RedeDeSimulacao(seed=3, seed_ruido=1003)
        sono = simular_noites.SleepController(None, simular_noites._Necessidades(), memoria, lambda: False)
        rng = np.random.default_rng(3)
        for _ in range(2):
            simular_noites.simular_dia(brain, memoria, rng, regras, perfil)       # sem habituação e sem horas
            simular_noites.simular_noite(brain, sono, perfil)
    assert desligada[-1]["aprendido"] == brain.learned.tolist()


def test_simulacao_dois_dias_duros_ensinam_menos_tristeza_com_habituacao():
    com = simular_noites.simular("duro", noites=2, semente=3, dias=(2,))
    sem = simular_noites.simular("duro", noites=2, semente=3, dias=(2,), HABITUACAO_DISPENSA=0.0)
    assert ajustes.HABITUACAO_DISPENSA > 0                 # ligada por padrão
    assert com[-1]["peso_gloom_max"] < sem[-1]["peso_gloom_max"]


# ---------------- aceitação: 30 noites, cenário duro ----------------

@pytest.fixture(scope="module")
def trinta_noites_duro():
    com = simular_noites.simular("duro", noites=30, semente=7, dias=(0, 30))
    sem = simular_noites.simular("duro", noites=30, semente=7, dias=(0, 30), HABITUACAO_DISPENSA=0.0)
    return com, sem


def test_trinta_noites_so_dispensas_ensinam_menos_tristeza(trinta_noites_duro):
    """O teto em uso: só dispensas por 30 dias, a GLOOM de uso cai pelo menos 20% (com os números padrão, 29%)."""
    com, sem = trinta_noites_duro
    assert com[-1]["uso_hz"]["GLOOM"] < 0.8 * sem[-1]["uso_hz"]["GLOOM"]
    assert com[-1]["peso_gloom_max"] < sem[-1]["peso_gloom_max"]
    assert com[-1]["uso_hz"]["GLOOM"] > 0                  # ele ainda aprende a ficar triste: não é anestesia


# ---------------- validação com sementes novas (fora das usadas para escolher os números) ----------------
# Os números padrão foram escolhidos com as sementes 3 a 7. Este teste roda o mesmo critério em sementes
# que não entraram na escolha. São 30 simulações de 30 noites (uns 8 min), por isso só roda com
# CANTYLL_SIMULACAO_LONGA=1:  CANTYLL_SIMULACAO_LONGA=1 python -m pytest tests/test_habituacao_dispensa.py -k sementes_novas -s

SEMENTES_NOVAS = (8, 9, 10, 11, 12)
PLASTICAS = ("PLAYFUL", "CALM", "FRUSTRATION", "GLOOM")


@pytest.mark.skipif(os.environ.get("CANTYLL_SIMULACAO_LONGA") != "1",
                    reason="simulação longa: defina CANTYLL_SIMULACAO_LONGA=1")
def test_sementes_novas_mesmo_criterio_nos_tres_cenarios():
    """
    Critério (regra 8, relativo), em sementes novas: no duro, a GLOOM com habituação fica toda abaixo da
    faixa da linha de base (habituação desligada); no misto e no carinhoso, a média de cada população
    plástica fica dentro da faixa da linha de base.
    """
    def uso(cenario, semente, **trocas):
        return simular_noites.simular(cenario, noites=30, semente=semente, dias=(0, 30), **trocas)[-1]["uso_hz"]

    falhas = []
    for cenario in ("duro", "misto", "carinhoso"):
        base = [uso(cenario, s, HABITUACAO_DISPENSA=0.0) for s in SEMENTES_NOVAS]
        nova = [uso(cenario, s) for s in SEMENTES_NOVAS]
        for pop in PLASTICAS:
            b = [u[pop] for u in base]
            n = [u[pop] for u in nova]
            media = sum(n) / len(n)
            print(f"{cenario:9s} {pop:11s} base {sum(b) / len(b):6.2f} ({min(b):.2f} a {max(b):.2f})  "
                  f"habituação {media:6.2f} ({min(n):.2f} a {max(n):.2f})")
            if cenario == "duro":
                if pop == "GLOOM" and not max(n) < min(b):
                    falhas.append(f"duro GLOOM: {max(n):.2f} não fica abaixo de {min(b):.2f}")
            elif not min(b) - 1e-9 <= media <= max(b) + 1e-9:
                falhas.append(f"{cenario} {pop}: média {media:.2f} fora de [{min(b):.2f}, {max(b):.2f}]")
    assert falhas == []
