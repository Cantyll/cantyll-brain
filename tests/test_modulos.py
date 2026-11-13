"""
Trilhos do app (T1): o registro de módulos (core/modulos.py), as chaves das frentes (config.FRENTES),
as permissões escondidas de cada frente, a pasta de estado por módulo e as seções reservadas de ajustes.py.

O critério do plano: com todas as chaves desligadas, nada muda (a suíte passa sem teste alterado e as
taxas motoras ficam idênticas com a mesma semente), e um módulo de teste recebe todos os encaixes na ordem.
"""
import os
import re
import sys
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.core.modulos import Modulo, RegistroDeModulos, criar_registro  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402
from pestinha.paths import Paths  # noqa: E402

AJUSTES = ROOT / "pestinha" / "ajustes.py"


class Espiao(Modulo):
    """Módulo de teste: anota cada encaixe chamado, com o nome, na ordem."""
    nome = "lar"

    def __init__(self, v=None):
        self.chamadas = []
        self.v = v
        self.pastas = []

    def sentir(self, intensidades, dt):
        self.chamadas.append("sentir")
        intensidades["CANAL_DO_ESPIAO"] = 0.5

    def depois_do_passo(self, cerebro, drives, dt):
        self.chamadas.append("depois_do_passo")

    def ajustar_recompensa(self, recompensa, fontes, dt):
        self.chamadas.append("ajustar_recompensa")
        self.fontes = fontes
        return None

    def valor_esperado(self):
        self.chamadas.append("valor_esperado")
        return self.v

    def ao_dormir(self, cerebro):
        self.chamadas.append("ao_dormir")

    def ao_acordar(self, cerebro):
        self.chamadas.append("ao_acordar")

    def deslocar(self, segundos):
        self.chamadas.append("deslocar")

    def estado(self):
        self.chamadas.append("estado")
        return {"chamadas": len(self.chamadas)}

    def salvar(self, pasta):
        self.chamadas.append("salvar")
        self.pastas.append(pasta)

    def carregar(self, pasta):
        self.chamadas.append("carregar")
        self.pastas.append(pasta)


class Quebrado(Modulo):
    nome = "modelo_eu"

    def sentir(self, intensidades, dt):
        raise RuntimeError("defeito de propósito")


class OutroV(Modulo):
    nome = "hipocampo"

    def valor_esperado(self):
        return 0.1


# ---------------- chaves e seções ----------------

def test_toda_frente_comeca_desligada():
    assert config.FRENTES and not any(config.FRENTES.values())
    assert config.frentes_ligadas() == []


def test_toda_frente_tem_caminho_e_secao_em_ajustes():
    texto = AJUSTES.read_text(encoding="utf-8")
    assert set(config.MODULOS_DAS_FRENTES) == set(config.FRENTES)
    for nome in config.FRENTES:
        # uma seção no corpo do arquivo e outra dentro de _LIMITES, cada uma aberta e fechada uma vez
        assert len(re.findall(rf"^# >>> frente {nome}\b", texto, re.M)) == 1, nome
        assert len(re.findall(rf"^# <<< frente {nome}$", texto, re.M)) == 1, nome
        assert len(re.findall(rf"^    # >>> frente {nome}$", texto, re.M)) == 1, nome
        assert len(re.findall(rf"^    # <<< frente {nome}$", texto, re.M)) == 1, nome
    assert len(re.findall(r"^# >>> decisões", texto, re.M)) == 1
    assert len(re.findall(r"^    # >>> decisões$", texto, re.M)) == 1


def test_permissao_de_frente_some_com_a_frente_desligada():
    base_perms = config.permissoes_padrao({nome: False for nome in config.FRENTES})
    assert config.DEFAULT_PERMISSIONS == base_perms
    assert "gravar_sentidos" not in config.DEFAULT_PERMISSIONS
    assert "conversa" not in config.DEFAULT_PERMISSIONS
    titulos = [titulo for titulo, _itens in config.PERMISSION_GROUPS]
    assert "Gravação" not in titulos and "Conversa" not in titulos
    assert config.permissoes_validas({"gravar_sentidos": True}) == {}


def test_permissao_de_frente_ligada_aparece_desligada_antes_do_teste():
    frentes = dict(config.FRENTES, gravador=True)
    perms = config.permissoes_padrao(frentes)
    assert perms["gravar_sentidos"] is False
    grupos = config.grupos_de_permissao(frentes)
    titulos = [titulo for titulo, _itens in grupos]
    assert titulos[-1] == "Teste" and titulos[-2] == "Gravação"
    chaves = [chave for _t, itens in grupos for chave, _r, _d in itens]
    assert set(chaves) <= set(perms)


def test_pasta_de_modulo_fica_dentro_do_pet_e_recusa_nome_ruim(tmp_path):
    pet = Paths(root=tmp_path).pet("bryan")
    assert pet.modulo("lar") == pet.base / "modulos" / "lar"
    assert pet.modulos not in pet.todos()           # a migração continua com os oito arquivos de antes
    for ruim in ("..", "a/b", "Lar", "", "1x", None):
        with pytest.raises(ValueError):
            pet.modulo(ruim)


# ---------------- registro ----------------

def test_registro_vazio_nao_muda_nada(tmp_path):
    registro = RegistroDeModulos(pasta_de=lambda nome: tmp_path / nome)
    entrada = {"WORK": 1.0, "TYPING": 0.6}
    saida = registro.sentir(entrada, 0.1)
    assert saida is entrada and saida == {"WORK": 1.0, "TYPING": 0.6}
    assert registro.valor_esperado() is None
    r = 0.123456789
    assert registro.ajustar_recompensa(r, {"carinho": r}, 0.1) is r
    assert registro.estado() == {}
    registro.depois_do_passo(None, None, 0.1)
    registro.ao_dormir(None)
    registro.ao_acordar(None)
    registro.deslocar(10.0)
    registro.salvar()
    assert list(tmp_path.iterdir()) == []           # nenhuma pasta criada


def test_registro_recusa_nome_ruim_repetido_e_dois_valores():
    registro = RegistroDeModulos()
    ruim = Modulo()
    ruim.nome = "../fora"
    with pytest.raises(ValueError):
        registro.registrar(ruim)
    with pytest.raises(TypeError):
        registro.registrar(object())
    registro.registrar(Espiao(v=0.2))
    with pytest.raises(ValueError):
        registro.registrar(Espiao())
    with pytest.raises(ValueError):                 # dois módulos dando o V do aprendizado
        registro.registrar(OutroV())


def test_modulo_com_defeito_sai_e_os_outros_seguem():
    registro = RegistroDeModulos()
    quebrado = registro.registrar(Quebrado())
    espiao = registro.registrar(Espiao())
    entrada = {}
    registro.sentir(entrada, 0.1)
    assert registro.nomes() == ["lar"]
    assert registro.erros[0][:2] == ("modelo_eu", "sentir")
    assert entrada == {"CANAL_DO_ESPIAO": 0.5} and espiao.chamadas == ["sentir"]
    registro.sentir({}, 0.1)                        # o quebrado não é chamado de novo
    assert quebrado not in registro.modulos


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), "0.2", True])
def test_valor_esperado_invalido_vale_nada(valor):
    registro = RegistroDeModulos()
    registro.registrar(Espiao(v=valor))
    assert registro.valor_esperado() is None


def test_criar_registro_so_com_frentes_ligadas_e_sem_quebrar():
    fabricas = {
        "pestinha.mind.lar_ctl": types.SimpleNamespace(criar=lambda app: Espiao()),
        "pestinha.core.modelo_eu": types.SimpleNamespace(criar=lambda app: Espiao()),   # nome errado
    }
    importar = fabricas.__getitem__
    desligado = criar_registro(config.FRENTES, config.MODULOS_DAS_FRENTES, None, importar=importar)
    assert len(desligado) == 0 and desligado.erros == []
    frentes = dict(config.FRENTES, lar=True, modelo_eu=True, hipocampo=True, bandeja_estado=True)
    registro = criar_registro(frentes, config.MODULOS_DAS_FRENTES, None, importar=importar)
    assert registro.nomes() == ["lar"]
    erros = {nome for nome, _encaixe, _texto in registro.erros}
    assert erros == {"modelo_eu", "hipocampo"}      # nome errado e fábrica que não existe; bandeja não tem módulo


def test_taxas_motoras_iguais_com_o_registro_vazio():
    """Mesma semente e mesmo ruído: passar as intensidades pelo registro vazio dá as mesmas taxas, bit a bit."""
    registro = RegistroDeModulos()
    a = LIFBrain(seed=7, seed_ruido=3)
    b = LIFBrain(seed=7, seed_ruido=3)
    sentidos = [{"WORK": 1.0, "TYPING": 0.6}, {"PLAY": 1.0, "BOREDOM": 0.8}, {"SILENCE": 0.3, "LONELY": 0.7}]
    for k in range(30):
        entrada = dict(sentidos[k % 3])
        a.stimulate(dict(entrada))
        b.stimulate(registro.sentir(dict(entrada), 0.1))
        a.step(100)
        b.step(100)
        a.learn(0.5 if k % 5 == 0 else 0.0, 0.0, 0.1)
        v = registro.valor_esperado()
        r = registro.ajustar_recompensa(0.5 if k % 5 == 0 else 0.0, {}, 0.1)
        b.learn(r, 0.0 if v is None else v, 0.1)
    assert a.motor_activity() == b.motor_activity()
    assert (a.learned == b.learned).all()


class Teto(Modulo):
    """Corta o carinho pela metade; não responde o V."""
    nome = "lar"

    def ajustar_recompensa(self, recompensa, fontes, dt):
        fontes["carinho"] = 99.0                    # mexer na cópia não muda nada para os outros
        return recompensa - 0.5 * fontes.get("dispensa", 0.0)


class Dobro(Modulo):
    nome = "diario"

    def ajustar_recompensa(self, recompensa, fontes, dt):
        return 2 * recompensa


class Ruim(Modulo):
    nome = "gravador"

    def __init__(self, resposta):
        self.resposta = resposta

    def ajustar_recompensa(self, recompensa, fontes, dt):
        if self.resposta == "erro":
            raise RuntimeError("defeito de propósito")
        return self.resposta


def test_recompensa_passa_pelos_modulos_em_cadeia():
    registro = RegistroDeModulos()
    registro.registrar(Teto())
    registro.registrar(Dobro())
    fontes = {"dispensa": -0.6}
    assert registro.ajustar_recompensa(-0.6, fontes, 0.1) == pytest.approx(2 * (-0.6 + 0.3))
    assert fontes == {"dispensa": -0.6}


@pytest.mark.parametrize("resposta", [None, float("nan"), float("inf"), "1.0", True, "erro"])
def test_resposta_invalida_deixa_a_recompensa_como_estava(resposta):
    registro = RegistroDeModulos()
    registro.registrar(Ruim(resposta))
    registro.registrar(Dobro())
    assert registro.ajustar_recompensa(0.25, {}, 0.1) == 0.5
    assert registro.nomes() == (["diario"] if resposta == "erro" else ["gravador", "diario"])


# ---------------- no app ----------------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _montar_app(tmp_path):
    from pestinha.app import PestinhaApp
    from pestinha.settings_store import SettingsStore
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))
    return PestinhaApp(store, paths)


def _fechar(app):
    app.floats.hidden_by_tray = True
    for janela in list(app.floats.windows.values()):
        janela.close()
    app.mischief.clear()
    app.tray.icon.hide()


def test_app_com_frentes_desligadas_nao_tem_modulo_nem_pasta(qapp, tmp_path):
    app = _montar_app(tmp_path)
    try:
        assert len(app.modulos) == 0
        app.think()
        app.save()
        assert not app.pet_paths.modulos.exists()
    finally:
        _fechar(app)


def test_modulo_recebe_todos_os_encaixes_na_ordem(qapp, tmp_path, monkeypatch):
    espiao = Espiao(v=0.25)
    fabrica = types.ModuleType("espiao_t1")
    fabrica.criar = lambda app: espiao
    monkeypatch.setitem(sys.modules, "espiao_t1", fabrica)
    monkeypatch.setattr(config, "FRENTES", dict(config.FRENTES, lar=True))
    monkeypatch.setattr(config, "MODULOS_DAS_FRENTES", dict(config.MODULOS_DAS_FRENTES, lar="espiao_t1"))
    app = _montar_app(tmp_path)
    try:
        assert app.modulos.nomes() == ["lar"]
        esperados = []
        original = app.brain.learn
        app.brain.learn = lambda reward, expected, *a, **k: (esperados.append(expected), original(reward, expected, *a, **k))
        app.think()
        assert app.intensities["CANAL_DO_ESPIAO"] == 0.5       # o canal do módulo chegou à entrada da rede
        assert esperados == [0.25]                              # o V do módulo chegou ao aprendizado
        app.sleep.fall_asleep()
        app.sleep.wake(startled=False)
        app.sleep.wake(startled=False)                          # acordado, acordar de novo não chama o módulo
        app.toggle_pause()
        app.think()                                             # pausado: nenhum encaixe
        app.toggle_pause()
        estado = app.modulos.estado()
        app.save()
        assert espiao.chamadas == ["carregar", "sentir", "depois_do_passo", "ajustar_recompensa", "valor_esperado",
                                   "ao_dormir", "ao_acordar", "deslocar", "estado", "salvar"]
        assert estado == {"lar": {"chamadas": 9}}
        assert "castigo" in espiao.fontes
        assert espiao.pastas == [app.pet_paths.modulo("lar")] * 2
    finally:
        _fechar(app)
