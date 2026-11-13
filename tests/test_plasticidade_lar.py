"""
PL-1, reforço do lar (opção A do Cantyll, 2026-11-13): o tédio que a travessura de casa tira vira recompensa,
paga ao longo da bagunça pelo encaixe ajustar_recompensa do LarModulo. Só com a plasticidade do PL-1 ligada
(cérebro "bio" e ajustes.PL_DELTA); sem ela, o lar segue sem recompensa (R2).
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from pestinha import ajustes, config  # noqa: E402
from pestinha.paths import Paths  # noqa: E402

PASSO = 0.1


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _montar(qapp, tmp_path, monkeypatch, pl1):
    from pestinha.app import PestinhaApp
    from pestinha.settings_store import SettingsStore
    monkeypatch.setattr(config, "FRENTES", dict(config.FRENTES, lar=True))
    monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
    monkeypatch.setattr(ajustes, "PL_DELTA", pl1)
    if pl1:
        monkeypatch.setattr(config, "CEREBRO", "bio")
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, rotina=False))
    app = PestinhaApp(store, paths)
    app.pet.show()
    return app, app.modulos.modulos[0]


def _fechar(app, modulo):
    app.floats.hidden_by_tray = True
    app.mischief.clear()
    modulo.cama.close()
    app.tray.icon.hide()


@pytest.fixture
def com_pl1(qapp, tmp_path, monkeypatch):
    app, modulo = _montar(qapp, tmp_path, monkeypatch, pl1=True)
    yield modulo
    _fechar(app, modulo)


@pytest.fixture
def sem_pl1(qapp, tmp_path, monkeypatch):
    app, modulo = _montar(qapp, tmp_path, monkeypatch, pl1=False)
    yield modulo
    _fechar(app, modulo)


def _bagunca(modulo, estimulacao):
    """Uma travessura de casa como no app: o lar a começa e o mischief_ctl tira o tédio."""
    modulo.app.drives.stimulation = estimulacao
    assert modulo.travessura(1000.0)
    modulo.app.drives.stimulate("mischief")


def _pagamentos(modulo, segundos):
    """As recompensas que o registro devolve, passo a passo, sem carinho nenhum."""
    return [modulo.app.modulos.ajustar_recompensa(0.0, {"castigo": 0.0}, PASSO)
            for _ in range(int(round(segundos / PASSO)))]


def test_com_pl1_o_tedio_aliviado_vira_recompensa(com_pl1):
    assert com_pl1.app.brain.plasticidade is not None
    _bagunca(com_pl1, estimulacao=0.0)           # tédio 1 → (0,35 − 0,25) / 0,35
    alivio = 1.0 - (0.35 - 0.25) / 0.35
    pagos = _pagamentos(com_pl1, ajustes.LAR_DURACAO_BAGUNCA + 2.0)
    total = sum(r * PASSO for r in pagos)
    assert total == pytest.approx(ajustes.LAR_RECOMPENSA_TEDIO * alivio, rel=1e-6)
    durante = int(round(ajustes.LAR_DURACAO_BAGUNCA / PASSO))
    assert all(r > 0 for r in pagos[:durante])
    assert all(r == 0.0 for r in pagos[durante + 1:])


def test_sem_tedio_a_bagunca_nao_recompensa(com_pl1):
    _bagunca(com_pl1, estimulacao=0.6)           # sem tédio: nada a aliviar
    assert all(r == 0.0 for r in _pagamentos(com_pl1, 3.0))


def test_sem_pl1_o_lar_continua_sem_recompensa(sem_pl1):
    """R2: sem o crítico, a recompensa do lar seria bruta. Ela não existe."""
    assert getattr(sem_pl1.app.brain, "plasticidade", None) is None
    _bagunca(sem_pl1, estimulacao=0.0)
    assert all(r == 0.0 for r in _pagamentos(sem_pl1, ajustes.LAR_DURACAO_BAGUNCA))


def test_dormir_acaba_com_o_reforco(com_pl1):
    _bagunca(com_pl1, estimulacao=0.0)
    _pagamentos(com_pl1, 1.0)
    com_pl1.ao_dormir(com_pl1.app.brain)
    assert all(r == 0.0 for r in _pagamentos(com_pl1, 2.0))


def test_a_bagunca_ensina_o_tedio_a_brincar(com_pl1):
    """
    O que a rede aprende: com o tédio ativo e a recompensa da bagunça (sem pista nenhuma), o tédio passa a
    puxar para PLAYFUL e CALM e para longe de GLOOM.
    """
    brain = com_pl1.app.brain
    brain.plasticidade.neuromod.ach_fixa = 0.5
    _bagunca(com_pl1, estimulacao=0.0)
    for r in _pagamentos(com_pl1, ajustes.LAR_DURACAO_BAGUNCA):
        brain.stimulate({"BOREDOM": 1.0})
        brain.learn(r, 0.0, PASSO, com_pl1.app.prof["learn_rate"])
    i = brain.sensory_names.index("BOREDOM")
    aprendido = dict(zip(brain.plastic_posts, brain.learned[i]))
    assert aprendido["PLAYFUL"] > 0 and aprendido["CALM"] > 0 and aprendido["GLOOM"] < 0
