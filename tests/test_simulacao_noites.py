"""
A simulação de noites (B2 do plano; spec, seção 9.4). A simulação de 30 noites é critério de aceitação
de toda mudança em dinâmica de neurônio, plasticidade, replay ou homeostase.

Os testes de aceitação usam réguas relativas: a comparação com a mesma simulação sem SHY e com o dia 0
da própria simulação. O GLOOM absoluto no dia 30 é o critério da seção 10 da spec (decidido pelo Cantyll em 2026-11-13).

Rodar: python -m pytest tests/test_simulacao_noites.py -q
Só os rápidos: python -m pytest tests/test_simulacao_noites.py -q -k "not trinta_noites"
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core.nervous_system import Brain, LIFBrain

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import simular_noites  # noqa: E402


# ---------------- a interface ----------------

def test_interface_brain_tem_taxas():
    class _Minimo(Brain):
        def stimulate(self, intensities): pass
        def step(self, dt_ms): pass
        def motor_activity(self): return {}
        def snapshot(self): return {}
        def learn(self, reward, expected, dt, rate=0.0, teto=None): pass
        def estado(self): return {}

    assert _Minimo().taxas() == {}
    brain = LIFBrain(seed=7, seed_ruido=42)
    assert set(brain.taxas()) == {p["name"] for p in brain.pools}


def test_disparos_contam_os_pulsos_de_cada_populacao():
    brain = LIFBrain(seed=7, seed_ruido=42)
    assert not brain.disparos.any()
    brain.stimulate({"WORK": 1.0, "TYPING": 0.6})
    brain.step(300)
    primeiro = brain.disparos.copy()
    brain.step(300)
    assert primeiro[brain._pool_index["WORK"]] > 0
    assert (brain.disparos >= primeiro).all() and brain.disparos.sum() > primeiro.sum()


# ---------------- a ferramenta ----------------

def test_replay_sem_pulsos_da_as_mesmas_sinapses_que_o_replay_do_app():
    rapido = simular_noites.simular("misto", noites=2, semente=3, dias=(2,))
    com_pulsos = simular_noites.simular("misto", noites=2, semente=3, dias=(2,), pulsos=True)
    assert rapido[-1]["aprendido"] == com_pulsos[-1]["aprendido"]
    assert np.abs(np.array(rapido[-1]["aprendido"])).max() > 0       # a simulação ensinou alguma coisa


def test_mesma_semente_repete_e_outra_semente_muda():
    a = simular_noites.simular("misto", noites=2, semente=3, dias=(2,))
    b = simular_noites.simular("misto", noites=2, semente=3, dias=(2,))
    c = simular_noites.simular("misto", noites=2, semente=4, dias=(2,))
    assert a == b
    assert a[-1]["aprendido"] != c[-1]["aprendido"]


def test_noite_picada_em_sonos_adormece_mais_vezes(monkeypatch):
    """sonos=1 é a noite inteira (o padrão). Com sonos=3, ele adormece três vezes por noite, e o resultado não muda:
    o replay e o SHY valem pela dívida de sono, não por adormecer, e a noite picada tem a mesma dívida."""
    adormeceu = []
    original = simular_noites.SleepController.fall_asleep
    monkeypatch.setattr(simular_noites.SleepController, "fall_asleep",
                        lambda self: (adormeceu.append(self.drives.pressao), original(self))[1])
    inteira = simular_noites.simular("misto", noites=2, semente=3, dias=(2,))
    assert len(adormeceu) == 2
    assert simular_noites.simular("misto", noites=2, semente=3, dias=(2,), sonos=1) == inteira
    adormeceu.clear()
    picada = simular_noites.simular("misto", noites=2, semente=3, dias=(2,), sonos=3)
    assert len(adormeceu) == 6 and adormeceu[0] > adormeceu[1] > adormeceu[2] > ajustes.LIMIAR_ACORDA_PRESSAO
    assert picada == inteira


def test_simular_devolve_os_ajustes_ao_que_eram():
    antes = ajustes.HOMEOSTASE_SHY
    simular_noites.simular("duro", noites=1, semente=3, dias=(), HOMEOSTASE_SHY=0.0)
    assert ajustes.HOMEOSTASE_SHY == antes


# ---------------- aceitação: 30 noites ----------------

DIAS = (0, 10, 20, 30)


@pytest.fixture(scope="module")
def trinta_noites():
    return simular_noites.simular("duro", noites=30, semente=7, dias=DIAS)


@pytest.fixture(scope="module")
def trinta_noites_sem_shy():
    return simular_noites.simular("duro", noites=30, semente=7, dias=DIAS, HOMEOSTASE_SHY=0.0)


def test_trinta_noites_nenhuma_populacao_que_disparava_fica_muda(trinta_noites):
    """Só dispensas, nenhum carinho: toda população que disparava no dia 0 ainda dispara em todos os dias medidos."""
    assert [linha["dia"] for linha in trinta_noites] == list(DIAS)
    vivas = [pop for pop, hz in trinta_noites[0]["uso_hz"].items() if hz > 0]
    assert "PLAYFUL" in vivas and "CALM" in vivas
    for linha in trinta_noites[1:]:
        for pop in vivas:
            assert linha["uso_hz"][pop] > 0, (linha["dia"], pop)


def test_trinta_noites_tristeza_fica_abaixo_do_limite_e_o_shy_e_o_que_segura(trinta_noites, trinta_noites_sem_shy):
    """A maior sinapse aprendida da GLOOM não chega ao limite LEARN_MAX. O controle, sem SHY, termina acima."""
    assert max(linha["peso_gloom_max"] for linha in trinta_noites) < 1.0
    assert trinta_noites[-1]["peso_gloom_max"] < trinta_noites_sem_shy[-1]["peso_gloom_max"]


# GLOOM no dia 30, por cenário (spec, seção 10; decisão do Cantyll, 2026-11-13, opção A).
LIMITE_GLOOM_DIA_30_HZ = {"duro": 2.0, "misto": 0.5, "carinhoso": 0.5}


def test_trinta_noites_gloom_no_cenario_duro_dentro_do_criterio(trinta_noites):
    assert trinta_noites[-1]["dia"] == 30
    assert trinta_noites[-1]["uso_hz"]["GLOOM"] <= LIMITE_GLOOM_DIA_30_HZ["duro"]


@pytest.mark.parametrize("cenario", ["misto", "carinhoso"])
def test_trinta_noites_gloom_nos_cenarios_com_carinho_dentro_do_criterio(cenario):
    ultimo = simular_noites.simular(cenario, noites=30, semente=7, dias=())[-1]
    assert ultimo["dia"] == 30
    assert ultimo["uso_hz"]["GLOOM"] <= LIMITE_GLOOM_DIA_30_HZ[cenario]


# ---------------- frente lar (teto do carinho) ----------------

def test_sem_lar_o_cenario_com_carinho_nao_muda():
    padrao = simular_noites.simular("misto", noites=2, semente=3, dias=(2,))
    assert simular_noites.simular("misto", noites=2, semente=3, dias=(2,), lar=False) == padrao
    com_lar = simular_noites.simular("misto", noites=2, semente=3, dias=(2,), lar=True)
    assert com_lar != padrao                            # o teto tira parte do que o carinho ensina


def test_so_o_lar_roda_e_liga_o_lar_sozinho():
    linhas = simular_noites.simular("so_o_lar", noites=2, semente=3, dias=(2,))
    assert [linha["dia"] for linha in linhas] == [0, 2]
    assert simular_noites.CENARIOS["so_o_lar"]["lar"] is True


def test_teto_da_simulacao_e_o_mesmo_calculo_do_lar():
    from pestinha.mind.lar_ctl import LarModulo
    relogio = [0.0]
    lar = LarModulo.__new__(LarModulo)
    lar.carga_carinho, lar.carga_em, lar.relogio = 0.0, None, lambda: relogio[0]
    teto = simular_noites.TetoCarinho()
    for agora, segundos in ((0.0, 4.0), (60.0, 3.0), (5000.0, 5.0), (40000.0, 2.0)):
        for k in range(int(segundos * 10)):
            relogio[0] = agora + 0.1 * k
            esperado = 1.0 + lar.ajustar_recompensa(0.0, {"carinho": 1.0}, 0.1)
            assert teto.peso(relogio[0]) == pytest.approx(esperado)
            teto.carga += 0.1
