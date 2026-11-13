"""
Teto do carinho (opção A do lazer no lar; encaixe ajustar_recompensa do registro de módulos): com o lar
ligado, o carinho recente ensina cada vez menos e volta com o tempo. Sem carinho, a recompensa não muda.
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


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def lar(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    from pestinha.settings_store import SettingsStore
    monkeypatch.setattr(config, "FRENTES", dict(config.FRENTES, lar=True))
    monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, rotina=False))
    app = PestinhaApp(store, paths)
    modulo = app.modulos.modulos[0]
    relogio = {"t": 1000.0}
    modulo.relogio = lambda: relogio["t"]
    modulo.tempo = relogio
    yield modulo
    app.floats.hidden_by_tray = True
    app.mischief.clear()
    modulo.cama.close()
    app.tray.icon.hide()


def _carinho(modulo, segundos, dt=0.1, outras=0.0):
    """Faz `segundos` de carinho em passos de dt; devolve a recompensa do último passo."""
    r = None
    for _ in range(int(round(segundos / dt))):
        fontes = {"carinho": ajustes.RECOMPENSA_CARINHO, "castigo": outras}
        r = modulo.app.modulos.ajustar_recompensa(ajustes.RECOMPENSA_CARINHO + outras, fontes, dt)
        modulo.tempo["t"] += dt
    return r


def test_sem_carinho_a_recompensa_nao_muda(lar):
    r = -0.6
    assert lar.app.modulos.ajustar_recompensa(r, {"dispensa": -0.6, "castigo": 0.0}, 0.1) is r


def test_primeiro_carinho_ensina_inteiro(lar):
    assert _carinho(lar, 0.1) == pytest.approx(ajustes.RECOMPENSA_CARINHO)


def test_depois_da_meia_vida_ensina_a_metade_e_o_resto_fica(lar):
    meia = ajustes.LAR_MEIA_VIDA_CARINHO_S
    r = _carinho(lar, meia + 0.1, outras=-0.25)                     # o castigo do mesmo passo não é cortado
    assert r == pytest.approx(0.5 * ajustes.RECOMPENSA_CARINHO - 0.25, rel=0.02)
    r = _carinho(lar, 3 * meia)
    assert r < 0.07 * ajustes.RECOMPENSA_CARINHO                      # 4 meias-vidas: ~6%


def test_volta_com_o_tempo(lar):
    _carinho(lar, 2 * ajustes.LAR_MEIA_VIDA_CARINHO_S)
    assert lar.peso_carinho() == pytest.approx(0.25, rel=0.02)
    lar.tempo["t"] += 3 * ajustes.LAR_RECUPERACAO_CARINHO_H * 3600.0   # 3 τ: a carga cai a ~5%
    assert lar.peso_carinho() > 0.9
    assert lar.estado()["carga_carinho_s"] < 0.06 * 2 * ajustes.LAR_MEIA_VIDA_CARINHO_S


def test_meia_vida_zero_desliga(lar, monkeypatch):
    monkeypatch.setattr(ajustes, "LAR_MEIA_VIDA_CARINHO_S", 0.0)
    assert _carinho(lar, 3 * 30.0) == pytest.approx(ajustes.RECOMPENSA_CARINHO)
    assert lar.peso_carinho() == 1.0


def test_no_think_o_carinho_chega_cortado_ao_aprendizado(lar):
    app = lar.app
    recompensas = []
    original = app.brain.learn
    app.brain.learn = lambda r, *a, **k: (recompensas.append(r), original(r, *a, **k))
    lar.carga_carinho, lar.carga_em = 10 * ajustes.LAR_MEIA_VIDA_CARINHO_S, lar.relogio()   # muito carinho hoje
    app.pet_state.caressing = lambda now: True
    app.think()
    assert recompensas and 0.0 < recompensas[-1] < 0.01 * ajustes.RECOMPENSA_CARINHO
