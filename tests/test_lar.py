"""
O lar (LAR-1): a cama no canto e ir para ela quando o sono chega. Frente desligada por padrão.

Critério do plano: a cama não rouba foco, some em tela cheia, e pausa e pânico funcionam.
Mais: com sono chegando ele anda até a cama e dorme nela; sem o lar renovar o pedido, ele esquece.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from pestinha import ajustes, config  # noqa: E402
from pestinha.body.behavior import Behavior  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402
from pestinha.mind.lar_ctl import ARQUIVO, deitado, sonolento  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.world.lar import CAMA_H, CAMA_W, MARGEM_TELA, no_chao, posicao_padrao  # noqa: E402

BOUNDS = (0, 0, 1920, 1080)
PROF = {"righting_after": 1.0, "roam_interval": (5.0, 10.0)}
DT = 1 / 60


# ---------------- regras puras ----------------

def test_sonolento_um_pouco_antes_do_ritmo_mandar_dormir():
    margem_p, margem_c = ajustes.LAR_MARGEM_PRESSAO, ajustes.LAR_MARGEM_C
    noite = ajustes.LIMIAR_DORME_C - margem_c / 2               # ainda não é noite para o ritmo
    perto = ajustes.LIMIAR_DORME_PRESSAO - margem_p / 2         # pressão ainda abaixo do limiar
    assert sonolento(perto, noite)
    assert not sonolento(ajustes.LIMIAR_DORME_PRESSAO - 2 * margem_p, noite)
    assert not sonolento(perto, ajustes.LIMIAR_DORME_C + 2 * margem_c)
    assert sonolento(ajustes.LIMIAR_DORME_FORCADO - margem_p / 2, 1.0)    # sono forçado chegando, de dia
    assert not sonolento(ajustes.PRESSAO_INICIAL, -1.0)


def test_cama_comeca_no_canto_esquerdo_com_a_base_no_chao():
    assert posicao_padrao((0, 0, 1920, 1040), (CAMA_W, CAMA_H)) == (MARGEM_TELA, 1040 - CAMA_H)
    assert posicao_padrao((1920, 100, 1280, 900), (CAMA_W, CAMA_H)) == (1920 + MARGEM_TELA, 1000 - CAMA_H)


def test_cama_solta_no_ar_desce_ao_chao_da_tela_dela():
    telas = [(0, 0, 1920, 1040), (1920, 0, 1280, 1000)]
    assert no_chao(500, 300, (CAMA_W, CAMA_H), telas) == (500, 1040 - CAMA_H)
    assert no_chao(2500, 10, (CAMA_W, CAMA_H), telas) == (2500, 1000 - CAMA_H)
    assert no_chao(1910, 10, (CAMA_W, CAMA_H), telas) == (1920, 1000 - CAMA_H)   # o centro está na segunda: entra inteira nela
    x, y = no_chao(9000, 9000, (CAMA_W, CAMA_H), telas)                    # fora de tudo: a tela mais perto
    assert (x, y) == (1920 + 1280 - CAMA_W, 1000 - CAMA_H)
    assert no_chao(10, 20, (CAMA_W, CAMA_H), []) == (10, 20)


def test_deitado_so_no_chao_perto_do_meio_da_cama():
    corpo = Body(100.0, 1000.0, 30.0, 35.0)
    corpo.grounded = True
    assert deitado(corpo, 100.0 + ajustes.LAR_CHEGOU_CAMA - 1)
    assert not deitado(corpo, 100.0 + ajustes.LAR_CHEGOU_CAMA + 1)
    corpo.platform = 42
    assert not deitado(corpo, 100.0)                         # numa janela em cima da cama não vale
    corpo.platform, corpo.held = None, True
    assert not deitado(corpo, 100.0)


# ---------------- comportamento ----------------

def _no_chao(x):
    corpo = Body(x, BOUNDS[3] - 35.0, 30.0, 35.0)
    corpo.grounded, corpo.surface = True, float(BOUNDS[3])
    comportamento = Behavior(corpo, PetState(), None)
    comportamento.next_roam = 1e12
    comportamento.emotion = "observando"
    return corpo, comportamento


def _andar(corpo, comportamento, segundos, cama_x=None, plataformas=(), agora=0.0, areas=None):
    for _ in range(int(segundos / DT)):
        agora += DT
        if cama_x is not None:
            comportamento.cama = (cama_x, agora + ajustes.LAR_VALIDADE_CAMA)
        comportamento.tick(DT, agora, (960, 500), BOUNDS, PROF, list(plataformas))
        corpo.step(DT, BOUNDS, list(plataformas), areas or [BOUNDS], areas or [BOUNDS])
    return agora


def test_com_sono_ele_anda_ate_a_cama_e_fica_la():
    corpo, comportamento = _no_chao(900.0)
    _andar(corpo, comportamento, 15.0, cama_x=94.0)
    assert abs(corpo.x - 94.0) < ajustes.LAR_CHEGOU_CAMA
    assert corpo.vx == 0.0 and corpo.grounded and deitado(corpo, 94.0)


def test_vai_devagar_para_a_cama():
    corpo, comportamento = _no_chao(900.0)
    _andar(corpo, comportamento, 1.0, cama_x=94.0)
    assert corpo.x < 900.0
    assert abs(corpo.vx) <= ajustes.LAR_VELOCIDADE_CAMA + 1e-9


def test_pedido_que_o_lar_nao_renova_vence():
    corpo, comportamento = _no_chao(900.0)
    comportamento.cama = (94.0, 0.5)
    _andar(corpo, comportamento, 1.0)
    assert comportamento.cama is None
    x = corpo.x
    _andar(corpo, comportamento, 3.0, agora=1.0)
    assert abs(corpo.x - x) < 1.0                            # passeio normal (sem destino): não segue para a cama


@pytest.mark.parametrize("emocao", ["dormindo", "assustado"])
def test_parado_por_emocao_nao_vai_para_a_cama(emocao):
    corpo, comportamento = _no_chao(900.0)
    comportamento.emotion = emocao
    _andar(corpo, comportamento, 2.0, cama_x=94.0)
    assert abs(corpo.x - 900.0) < 1.0


def test_em_protesto_o_protesto_vem_primeiro():
    corpo, comportamento = _no_chao(900.0)
    comportamento.state.protest_stage = 1                     # reclamação: parado encarando você
    _andar(corpo, comportamento, 2.0, cama_x=94.0)
    assert abs(corpo.x - 900.0) < 1.0


@pytest.mark.parametrize("janela_x, corpo_x, cama_x, sentido", [
    ((100.0, 600.0), 200.0, 150.0, -1),        # a beirada esquerda é a mais perto
    ((0.0, 400.0), 120.0, 94.0, +1),           # janela encostada na borda da tela: só dá para descer pela direita
])
def test_numa_janela_em_cima_da_cama_desce_pela_beirada_e_deita(janela_x, corpo_x, cama_x, sentido):
    topo = 700.0
    janela = (7, janela_x[0], janela_x[1], topo)               # a cama está embaixo desta barra de título
    corpo = Body(corpo_x, topo - 35.0, 30.0, 35.0)
    corpo.grounded, corpo.surface, corpo.platform = True, topo, 7
    comportamento = Behavior(corpo, PetState(), None)
    comportamento.next_roam = 1e12
    _andar(corpo, comportamento, 0.5, cama_x=cama_x, plataformas=[janela])
    assert corpo.vx * sentido > 0
    _andar(corpo, comportamento, 20.0, cama_x=cama_x, plataformas=[janela], agora=0.5)
    assert corpo.platform is None and deitado(corpo, cama_x)


def test_cama_em_monitor_sem_passagem_nao_vira_destino():
    corpo, comportamento = _no_chao(900.0)
    _andar(corpo, comportamento, 2.0, cama_x=5000.0)
    assert abs(corpo.x - 900.0) < 1.0


# ---------------- no app ----------------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def app_com_lar(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    from pestinha.settings_store import SettingsStore
    monkeypatch.setattr(config, "FRENTES", dict(config.FRENTES, lar=True))
    monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, rotina=False))
    app = PestinhaApp(store, paths)
    yield app
    app.floats.hidden_by_tray = True
    for janela in list(app.floats.windows.values()):
        janela.close()
    app.mischief.clear()
    for modulo in app.modulos.modulos:
        modulo.cama.close()
    app.tray.icon.hide()


def _lar(app):
    assert app.modulos.nomes() == ["lar"] and app.modulos.erros == []
    return app.modulos.modulos[0]


def test_cama_nao_rouba_foco_e_nao_vira_barra_de_pouso(app_com_lar):
    from PySide6.QtCore import Qt
    cama = _lar(app_com_lar).cama
    flags = cama.windowFlags()
    assert flags & Qt.WindowDoesNotAcceptFocus and flags & Qt.Tool and flags & Qt.WindowStaysOnTopHint
    assert cama.testAttribute(Qt.WA_ShowWithoutActivating)


def test_cama_aparece_e_some_com_o_pet_tela_cheia_e_panico(app_com_lar):
    app = app_com_lar
    cama = _lar(app).cama
    assert app.pet.isVisible() and cama.isVisible()
    app.fullscreen = True
    app.update_visibility()
    assert not app.pet.isVisible() and not cama.isVisible()
    app.fullscreen = False
    app.update_visibility()
    assert cama.isVisible()
    app.toggle_hidden()
    assert not cama.isVisible()
    app.toggle_hidden()
    assert cama.isVisible()
    app.panic()
    assert not app.pet.isVisible() and not cama.isVisible()


def test_sono_chegando_pede_a_cama_e_a_pausa_congela(app_com_lar):
    app = app_com_lar
    lar = _lar(app)
    app.sleep.relogio = lambda: app.sleep.pico_h              # meio do dia: o ritmo não manda dormir
    app.drives.pressao = ajustes.PRESSAO_INICIAL
    app.think()
    assert app.behavior.cama is None
    app.toggle_pause()
    app.drives.pressao = ajustes.LIMIAR_DORME_FORCADO - ajustes.LAR_MARGEM_PRESSAO / 2
    app.think()                                               # pausado: o lar não é chamado
    assert app.behavior.cama is None
    app.toggle_pause()
    app.think()
    assert not app.asleep
    assert app.behavior.cama is not None and app.behavior.cama[0] == lar.cama.centro_x()


def test_conta_sonos_na_cama_e_fora_e_guarda(app_com_lar):
    from pestinha.mind.lar_ctl import LarModulo
    app = app_com_lar
    lar = _lar(app)
    corpo = app.pet.body
    corpo.x, corpo.grounded, corpo.platform, corpo.held = lar.cama.centro_x(), True, None, False
    app.sleep.fall_asleep()
    assert lar.cama.ocupada
    app.sleep.wake(startled=False)
    assert not lar.cama.ocupada
    corpo.x = lar.cama.centro_x() + 400
    app.sleep.fall_asleep()
    assert not lar.cama.ocupada
    app.sleep.wake(startled=False)
    assert lar.estado() == {"sonos_na_cama": 1, "sonos_fora": 1, "travessuras_de_casa": 0}
    app.save()
    pasta = app.pet_paths.modulo("lar")
    assert (pasta / ARQUIVO).exists()
    outro = LarModulo(app, cama=lar.cama)
    outro.carregar(pasta)
    assert outro.estado() == {"sonos_na_cama": 1, "sonos_fora": 1, "travessuras_de_casa": 0}


@pytest.mark.parametrize("conteudo", ['{"sonos_na_cama": -1, "sonos_fora": true, "travessuras_de_casa": 1.5}',
                                      '[1, 2]', 'lixo'])
def test_arquivo_ruim_comeca_do_zero(app_com_lar, conteudo):
    from pestinha.mind.lar_ctl import LarModulo
    app = app_com_lar
    pasta = app.pet_paths.modulo("lar")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ARQUIVO).write_text(conteudo, encoding="utf-8")
    outro = LarModulo(app, cama=_lar(app).cama)
    outro.carregar(pasta)
    assert outro.estado() == {"sonos_na_cama": 0, "sonos_fora": 0, "travessuras_de_casa": 0}
