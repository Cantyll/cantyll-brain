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


def _sono(tmp_path):
    class _Necessidades:
        pressao = 0.82

    mem = EpisodicMemory(tmp_path / "episodes.jsonl", tmp_path / "preferences.json")
    return SleepController(None, _Necessidades(), mem, lambda: False)


def _rede(valor=0.05):
    brain = LIFBrain(seed=7, seed_ruido=42)
    brain.learned[:] = valor
    brain._apply_learning()
    return brain


def test_downscaling_do_sono_acontece_uma_vez_por_sono(tmp_path):
    sono = _sono(tmp_path)
    brain = _rede()
    sono.fall_asleep()
    sono.replay_passo(brain, 0, 0.004)                       # orçamento zero: só o downscaling acontece
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY))
    sono.replay_passo(brain, 0, 0.004)                       # mesmo sono: não desfaz de novo
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY))


def test_shy_vale_pela_divida_de_sono_e_nao_por_adormecer(tmp_path):
    """Acordar no meio da noite e dormir de novo não desfaz outra noite; uma noite nova de dívida desfaz."""
    sono = _sono(tmp_path)
    brain = _rede()
    sono.fall_asleep()
    sono.replay_passo(brain, 0, 0.004)
    sono.drives.pressao = 0.6                                # dormiu um pedaço da noite
    sono.wake(startled=False)                                # carinho: acordou
    sono.fall_asleep()                                       # e dormiu de novo, sem a pressão subir
    sono.replay_passo(brain, 0, 0.004)
    assert sono.cota == 0.0
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY))
    sono.drives.pressao = ajustes.LIMIAR_ACORDA_PRESSAO      # o resto da noite
    sono.replay_passo(brain, 0, 0.004)
    sono.wake(startled=False)
    sono.drives.pressao = ajustes.LIMIAR_ACORDA_PRESSAO + 0.5 * sono.noite()   # meio dia acordado
    sono.fall_asleep()
    sono.replay_passo(brain, 0, 0.004)
    assert abs(sono.cota - 0.5) < 1e-9
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY) ** 1.5)
    sono.drives.pressao = ajustes.LIMIAR_ACORDA_PRESSAO
    sono.wake(startled=False)
    sono.drives.pressao = 0.9                                # um dia inteiro acordado: a dívida passa de uma noite
    sono.fall_asleep()
    sono.replay_passo(brain, 0, 0.004)
    assert sono.cota == 1.0                                  # vale um sono completo, não mais
    assert np.allclose(brain.learned, 0.05 * (1.0 - ajustes.HOMEOSTASE_SHY) ** 2.5)


def test_divida_de_sono_sobrevive_ao_app_fechado(tmp_path):
    """Fechado no meio do sono e reaberto: a pressão congelou e a quitada foi gravada; o sono seguinte não cobra outra noite."""
    from pestinha import config
    from pestinha.core.homeostasis import Drives

    drives = Drives()
    drives.pressao = 0.82
    mem = EpisodicMemory(tmp_path / "episodes.jsonl", tmp_path / "preferences.json")
    sono = SleepController(None, drives, mem, lambda: False)
    sono.fall_asleep()
    drives.pressao = 0.5
    sono.replay_passo(_rede(), 0, 0.004)                     # dormindo, a quitada acompanha a pressão
    drives.save(tmp_path / "drives.json")                    # o app fechou dormindo, sem acordar

    reaberto = Drives()
    assert reaberto.load(tmp_path / "drives.json", config.PROFILES["normal"])
    assert reaberto.pressao_quitada == 0.5
    novo = SleepController(None, reaberto, mem, lambda: False)
    novo.fall_asleep()
    assert novo.cota == 0.0 and novo.replay_fila == []


def test_drives_antigo_sem_quitada_vale_uma_noite(tmp_path):
    import json
    from pestinha import config
    from pestinha.core.homeostasis import Drives

    (tmp_path / "drives.json").write_text(json.dumps({"energy": 1.0, "stimulation": 0.5, "contact": 0.1,
                                                      "pressao": 0.8, "saved_at": 1}), encoding="utf-8")
    drives = Drives()
    assert drives.load(tmp_path / "drives.json", config.PROFILES["normal"])
    assert drives.pressao_quitada is None
    sono = SleepController(None, drives, EpisodicMemory(tmp_path / "e.jsonl", tmp_path / "p.json"), lambda: False)
    assert sono.divida() == 1.0
