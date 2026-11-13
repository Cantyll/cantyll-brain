"""
Ligação da guarda de negligência com a app (R1, decisão do Cantyll de 2026-11-13: 10 minutos).

A lógica pura está em tests/test_negligencia.py. Aqui: interagir com o pet zera o tempo, a pausa e a ausência
não contam, e a rede só recebe a guarda quando o tempo chega ao limite com você presente.
Qt em modo offscreen, tudo numa pasta temporária.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def buddy(tmp_path):
    qapp = QApplication.instance() or QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, travessuras=True))
    app = PestinhaApp(store, paths)
    yield app
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()
    app.mischief.clear()
    app.tray.icon.hide()


def _negligente(app):
    """Finge que já se passaram os 10 minutos de presença sem interagir."""
    app.negligencia.parado_s = app.negligencia.limite_s


def test_cutucar_zera_a_negligencia(buddy):
    _negligente(buddy)
    buddy.on_poke()
    assert not buddy.negligencia.ativa
    assert buddy.negligencia.parado_s == 0.0


def test_arrastar_arremessar_e_dispensar_tambem_zeram(buddy, monkeypatch):
    monkeypatch.setattr(buddy.mischief_ctl, "on_dismissed", lambda *a, **k: None)   # o foco é a contagem
    for interacao in (buddy.on_drag_started, lambda: buddy.on_thrown(900.0),
                      lambda: buddy.on_dismissed(None, 5.0), buddy.menu_caress):
        _negligente(buddy)
        interacao()
        assert not buddy.negligencia.ativa, interacao


def test_ausente_nao_acumula_negligencia(buddy):
    buddy.activity = "AWAY"
    antes = buddy.negligencia.parado_s
    buddy.think()
    assert buddy.negligencia.parado_s == antes


def test_pausado_nao_acumula_negligencia(buddy):
    buddy.activity = "PROGRAMMING"
    buddy.paused = True
    antes = buddy.negligencia.parado_s
    buddy.think()
    assert buddy.negligencia.parado_s == antes


def test_a_rede_recebe_a_guarda_so_com_a_negligencia_e_ela_cai_ao_interagir(buddy):
    buddy.activity = "PROGRAMMING"
    buddy.think()
    assert buddy.brain.ausente is False
    _negligente(buddy)
    buddy.think()
    assert buddy.brain.ausente is True
    buddy.on_poke()
    buddy.think()
    assert buddy.brain.ausente is False
