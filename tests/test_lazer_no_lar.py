"""
Lazer no lar, parte de necessidades da opção A (decidida pelo Cantyll em 2026-11-12), com o lar ligado:
a travessura do tédio vira travessura de casa (nada na sua tela) e a dispensa deixa de contar como
atenção. Com o lar desligado (padrão), nada muda: o caminho antigo é o mesmo.
"""
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from pestinha import ajustes, config  # noqa: E402
from pestinha.body.behavior import Behavior  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402
from pestinha.mind.mischief_ctl import MischiefController  # noqa: E402
from pestinha.paths import Paths  # noqa: E402

PERFIL = {"dismiss_patience": 60.0, "drama_window": 1.0, "drama_count": 999, "explore": 0.0, "max_objects": 5}


class _Gravador:
    """Anota cada método chamado; devolve None (falso) em tudo."""
    def __init__(self):
        self.chamadas = []

    def __getattr__(self, nome):
        return lambda *a, **k: self.chamadas.append(nome)


def _controlador(monkeypatch):
    monkeypatch.setattr("pestinha.mind.mischief_ctl.random.random", lambda: 0.0)
    motor, memoria, necessidades, sentidos, emocao = (_Gravador() for _ in range(5))
    corpo = SimpleNamespace(held=False, grounded=True)
    ctl = MischiefController(motor, memoria, necessidades, sentidos, SimpleNamespace(mission=None), emocao,
                             lambda: False)
    casa = []

    def tentar(emocao="curioso", estagio=0, de_casa=True):
        return ctl.maybe_act(1.0, 0.1, (0, 0, 1920, 1080), (0, 0), corpo, motores={"TRAVESSURA": 100.0},
                             activity="IDLE", emotion=emocao, perms={}, prof=PERFIL, fullscreen=False,
                             asleep=False, protest_stage=estagio)

    def ligar(pode=True):
        ctl.travessura_de_casa = lambda now: (casa.append(now), pode)[1]

    return SimpleNamespace(ctl=ctl, motor=motor, necessidades=necessidades, casa=casa, tentar=tentar, ligar=ligar)


# ---------------- travessura de casa ----------------

def test_sem_lar_a_travessura_segue_pela_tela(monkeypatch):
    c = _controlador(monkeypatch)
    assert c.tentar() is None                           # o motor de teste não permite nada
    assert "allowed" in c.motor.chamadas and c.casa == []


def test_com_lar_o_tedio_vira_travessura_de_casa(monkeypatch):
    c = _controlador(monkeypatch)
    c.ligar()
    assert c.tentar() == "casa"
    assert c.casa == [1.0]
    assert c.necessidades.chamadas == ["stimulate"]     # tira o tédio como a travessura da tela
    assert c.motor.chamadas == []                       # nada é pedido à tela: nem permissão, nem objeto


@pytest.mark.parametrize("emocao, estagio", [("triste", 0), ("bravo", 0), ("curioso", 1), ("curioso", 2),
                                             ("curioso", 4)])
def test_protesto_triste_e_bravo_continuam_na_tela(monkeypatch, emocao, estagio):
    c = _controlador(monkeypatch)
    c.ligar()
    c.tentar(emocao=emocao, estagio=estagio)
    assert c.casa == [] and "allowed" in c.motor.chamadas


def test_pedido_do_menu_continua_na_tela(monkeypatch):
    c = _controlador(monkeypatch)
    c.ligar()
    c.ctl.pedir(0.5)
    c.tentar()
    assert c.casa == [] and "allowed" in c.motor.chamadas


def test_lar_que_nao_pode_agora_nao_manda_para_a_tela(monkeypatch):
    c = _controlador(monkeypatch)
    c.ligar(pode=False)
    assert c.tentar() is None
    assert c.casa == [1.0] and c.motor.chamadas == [] and c.necessidades.chamadas == []


# ---------------- dispensa ----------------

def test_dispensa_conta_como_atencao_so_sem_lar(monkeypatch):
    c = _controlador(monkeypatch)
    c.ctl.on_dismissed(object(), 30.0, PERFIL, 100.0)
    assert c.necessidades.chamadas.count("touched") == 1
    c.ctl.dispensa_e_atencao = False
    c.ctl.on_dismissed(object(), 30.0, PERFIL, 200.0)
    assert c.necessidades.chamadas.count("touched") == 1
    assert c.ctl.penalty_active(200.0)                  # a penalidade de aprendizado continua


# ---------------- comportamento ----------------

def test_na_bagunca_ele_pula_na_cama():
    bounds = (0, 0, 1920, 1080)
    corpo = Body(400.0, 1045.0, 30.0, 35.0)
    corpo.grounded, corpo.surface = True, 1080.0
    comportamento = Behavior(corpo, PetState(), None)
    comportamento.next_roam = 1e12
    comportamento.cama = (94.0, 1e9, "bagunca")
    agora, pulos, perto = 0.0, 0, False
    for _ in range(int(20 / (1 / 60))):
        agora += 1 / 60
        estava = corpo.grounded
        comportamento.tick(1 / 60, agora, (960, 500), bounds, {"righting_after": 1.0, "roam_interval": (5, 10)}, [])
        if estava and not corpo.grounded:
            pulos += 1
            perto = perto or abs(corpo.x - 94.0) < 60
        corpo.step(1 / 60, bounds, [], [bounds], [bounds])
    assert pulos >= 3 and perto
    assert abs(corpo.x - 94.0) < 120                    # pula em volta da cama, não sai passeando


# ---------------- no app ----------------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _montar(tmp_path, monkeypatch, lar):
    from pestinha.app import PestinhaApp
    from pestinha.settings_store import SettingsStore
    monkeypatch.setattr(config, "FRENTES", dict(config.FRENTES, lar=lar))
    monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, rotina=False))
    return PestinhaApp(store, paths)


def _fechar(app):
    app.floats.hidden_by_tray = True
    for janela in list(app.floats.windows.values()):
        janela.close()
    app.mischief.clear()
    for modulo in app.modulos.modulos:
        modulo.cama.close()
    app.tray.icon.hide()


@pytest.fixture
def com_lar(qapp, tmp_path, monkeypatch):
    app = _montar(tmp_path, monkeypatch, True)
    yield app
    _fechar(app)


def test_sem_lar_nada_muda_no_app(qapp, tmp_path, monkeypatch):
    app = _montar(tmp_path, monkeypatch, False)
    try:
        assert app.mischief_ctl.travessura_de_casa is None
        assert all(c.dispensa_e_atencao for c in (app.mischief_ctl, app.protest_ctl, app.sad_ctl))
        app.drives.contact = 0.8
        app.mischief_ctl.on_dismissed(object(), 30.0, app.prof, time.monotonic())
        assert app.drives.contact < 0.8
    finally:
        _fechar(app)


def test_com_lar_dispensa_nao_tira_carencia(com_lar):
    app = com_lar
    assert all(not c.dispensa_e_atencao for c in (app.mischief_ctl, app.protest_ctl, app.sad_ctl))
    app.drives.contact = 0.8
    app.mischief_ctl.on_dismissed(object(), 30.0, app.prof, time.monotonic())
    assert app.drives.contact == 0.8


def test_travessura_de_casa_no_app_nao_poe_nada_na_tela(com_lar, monkeypatch):
    app = com_lar
    lar = app.modulos.modulos[0]
    monkeypatch.setattr("pestinha.mind.mischief_ctl.random.random", lambda: 0.0)
    corpo = app.pet.body
    corpo.grounded, corpo.held = True, False
    app.drives.stimulation = 0.1
    acao = app.mischief_ctl.maybe_act(time.monotonic(), 0.016, app.bounds(), (0, 0), corpo,
                                      motores={"TRAVESSURA": 100.0}, activity="IDLE", emotion="curioso",
                                      perms=app.perms, prof=app.prof, fullscreen=False, asleep=False,
                                      protest_stage=0)
    assert acao == "casa"
    assert app.mischief.things == [] and app.behavior.mission is None
    assert app.drives.stimulation > 0.1
    assert app.behavior.cama[2] == "bagunca" and lar.cama.baguncada
    assert lar.estado()["travessuras_de_casa"] == 1

    app.sleep.relogio = lambda: app.sleep.pico_h        # meio do dia, sem sono: a bagunça continua
    app.drives.pressao = ajustes.PRESSAO_INICIAL
    app.think()
    assert app.behavior.cama is not None and app.behavior.cama[2] == "bagunca"

    antes = lar.bagunca_ate
    lar.deslocar(5.0)
    assert lar.bagunca_ate == antes + 5.0

    corpo.x = lar.cama.centro_x()
    app.sleep.fall_asleep()                             # foi dormir: a cama fica arrumada
    assert not lar.cama.baguncada and lar.bagunca_ate == 0.0
    app.sleep.wake(startled=False)
    app.think()
    assert app.behavior.cama is None


def test_escondido_nao_faz_travessura_de_casa(com_lar):
    app = com_lar
    lar = app.modulos.modulos[0]
    app.toggle_hidden()
    assert lar.travessura(time.monotonic()) is False
    assert lar.estado()["travessuras_de_casa"] == 0 and not lar.cama.baguncada
