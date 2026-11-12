"""
Homeostase sináptica no sono (decisão D4, hipótese SHY; spec, seção 9.4): o sono desfaz uma fração
das sinapses aprendidas, e o replay para de empurrar uma sinapse perto do seu limite. Sem isso, a
tristeza (GLOOM) de episódios negativos subia ao teto e ficava lá.

Rodar: python -m pytest tests/test_homeostase_sinaptica.py -q
"""
import numpy as np

from pestinha import ajustes
from pestinha.core import nervous_system as ns
from pestinha.core.episodic import EpisodicMemory
from pestinha.core.homeostase_sinaptica import downscaling, saturacao
from pestinha.core.nervous_system import LIFBrain
from pestinha.mind.sleep import SleepController


def _coluna(brain, post):
    return brain.learned[:, brain.plastic_posts.index(post)]


def test_downscaling_reduz_pela_fracao_e_mantem_sinal_e_zero():
    m = np.array([[0.04, -0.02], [0.0, 0.08]])
    out = downscaling(m, 0.25)
    assert np.allclose(out, m * 0.75)
    assert out[1, 0] == 0.0


def test_saturacao_zera_o_empurrao_no_teto_e_nao_freia_o_retorno():
    aprendido = np.array([0.04, 0.04, -0.02, 0.0])
    variacao = np.array([0.001, -0.001, 0.001, 0.001])
    fator = saturacao(variacao, aprendido, teto=0.5, limite_max=0.08, limite_min=-0.05)
    assert np.isclose(fator[0], 0.0)
    assert fator[1] == 1.0                           # puxar de volta para zero não é freado
    assert fator[2] == 1.0                           # sentido oposto ao valor: não é freado
    assert fator[3] == 1.0                           # sem valor aprendido: não é freado


def test_com_teto_a_sinapse_do_medo_nao_passa_da_fracao_do_limite():
    sem = LIFBrain(seed=7)
    com = LIFBrain(seed=7)
    for b in (sem, com):
        b.stimulate({"WORK": 0.8, "TYPING": 0.3})
        b.step(100)
    for _ in range(1500):
        sem.learn(-0.3, 0.0, 0.1, 0.004)
        com.learn(-0.3, 0.0, 0.1, 0.004, teto=ajustes.HOMEOSTASE_TETO)
    j = sem.plastic_posts.index("GLOOM")
    assert sem.learned[:, j].max() == ns.LEARN_MAX           # sem teto, chega ao limite
    assert com.learned[:, j].max() <= ajustes.HOMEOSTASE_TETO * ns.LEARN_MAX + 1e-9


def test_downscaling_do_sono_acontece_uma_vez_por_sono(tmp_path):
    class _Sem:
        pressao = 0.9

    mem = EpisodicMemory(tmp_path / "episodes.jsonl", tmp_path / "preferences.json")
    sono = SleepController(None, _Sem(), mem, lambda: False)
    brain = LIFBrain(seed=7, seed_ruido=42)
    brain.learned[:] = 0.05
    brain._apply_learning()
    sono.fall_asleep()
    sono.replay_passo(brain, 0, 0.004)                       # orçamento zero: só o downscaling acontece
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY))
    sono.replay_passo(brain, 0, 0.004)                       # mesmo sono: não desfaz de novo
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY))
    sono.wake(startled=False)
    sono.fall_asleep()
    sono.replay_passo(brain, 0, 0.004)                       # outro sono: desfaz mais uma vez
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY) ** 2)
