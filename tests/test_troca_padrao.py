"""
NE-5 (plano, onda 2; decisão do Cantyll, 2026-11-13, opção B): o padrão do app é o cérebro "bio", com as três chaves
da frente NE ligadas. As duas coisas voltam sem mexer no código: PESTINHA_CEREBRO=lif e PESTINHA_NE=0 no ambiente.

Portão D: voltar para "lif" funciona, e a troca nos dois sentidos não apaga nem corrompe o estado salvo de nenhum
dos dois cérebros (cada um grava o próprio arquivo: core/bio/rede.py, arquivo_do_bio).

Rodar: python -m pytest tests/test_troca_padrao.py -q
"""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from pestinha import ajustes, config
from pestinha.core.bio import BioBrain
from pestinha.core.bio.rede import arquivo_do_bio, neuronios_das_chaves
from pestinha.core.nervous_system import LIFBrain
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore

RAIZ = Path(__file__).resolve().parent.parent


def _no_ambiente(codigo, **variaveis):
    """Roda `codigo` num Python novo com as variáveis dadas (as de PESTINHA_ que não forem dadas saem)."""
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith("PESTINHA_")}
    ambiente.update(variaveis)
    saida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                           check=True)
    return saida.stdout.strip()


VER = ("from pestinha import ajustes, config; "
       "print(config.cerebro_escolhido(), ajustes.NE_INIBIDORES_FS, ajustes.NE_EXCITATORIOS, ajustes.NE_MOTORES)")


def test_padrao_e_bio_com_as_chaves_ne_ligadas():
    assert _no_ambiente(VER) == "bio True True True"


def test_padrao_do_processo_de_teste():
    """Sem PESTINHA_CEREBRO, a suíte roda com o padrão; com ela, com o cérebro pedido (conftest)."""
    assert config.CEREBRO == (os.environ.get("PESTINHA_CEREBRO", "").strip() or "bio")
    if os.environ.get("PESTINHA_NE", "1").strip() != "0":
        assert ajustes.NE_INIBIDORES_FS and ajustes.NE_EXCITATORIOS and ajustes.NE_MOTORES


def test_volta_para_o_lif_pelo_ambiente():
    assert _no_ambiente(VER, PESTINHA_CEREBRO="lif") == "lif True True True"


def test_chaves_ne_desligam_pelo_ambiente():
    """PESTINHA_NE=0: o BioBrain volta aos neurônios LIF (separa o efeito do cérebro do efeito do neurônio)."""
    assert _no_ambiente(VER, PESTINHA_NE="0") == "bio False False False"
    codigo = "from pestinha.core.bio import BioBrain; b = BioBrain(seed=7); print(b.izhikevich is None or b.izhikevich.n)"
    assert _no_ambiente(codigo, PESTINHA_NE="0") in ("True", "0")


def test_chaves_ligadas_poem_todos_os_interneuronios_em_izhikevich():
    tipos, _, _ = neuronios_das_chaves()
    b = BioBrain(seed=7)
    assert b.izhikevich.n == sum(b.pool(name)["n"] for name in tipos) == b.Nl     # nenhum interneurônio no LIF


def test_nome_desconhecido_volta_para_o_lif():
    assert config.cerebro_escolhido("izhikevich") == "lif"


@pytest.mark.parametrize("nome, esperado", [
    ("nervous.json", "nervous_bio.json"),                 # pasta do pet
    ("bryan_nervous.json", "bryan_nervous_bio.json"),     # modo compatível (migração pendente)
    ("rede.json", "rede.json"),                           # testes e ferramentas: o caminho dado
    ("nervous_bio.json", "nervous_bio.json"),
])
def test_arquivo_do_bio(tmp_path, nome, esperado):
    assert arquivo_do_bio(tmp_path / nome) == tmp_path / esperado
    assert arquivo_do_bio(str(tmp_path / nome)) == tmp_path / esperado


# ---------------- a troca no app, nos dois sentidos ----------------

def _abrir(paths, monkeypatch, cerebro):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(config, "CEREBRO", cerebro)
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    app = app_mod.PestinhaApp(SettingsStore(paths), paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    return app


def test_trocar_de_cerebro_nao_apaga_o_estado_do_outro(tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    paths.pets.mkdir()
    paths.definicao("bryan").write_text('{"nome": "Bryan", "seed": 7}', encoding="utf-8")

    # 1) o LIF aprende e grava
    lif = _abrir(paths, monkeypatch, "lif")
    assert isinstance(lif.brain, LIFBrain)
    lif.brain.learned[0, 0] = 0.05
    lif.save()
    arquivo_lif = lif.state_file
    bytes_lif = arquivo_lif.read_bytes()
    arquivo_bio = arquivo_do_bio(arquivo_lif)
    assert not arquivo_bio.exists()

    # 2) troca para o bio: começa sem o aprendizado do LIF (D7), aprende outra coisa e grava ao lado
    bio = _abrir(paths, monkeypatch, "bio")
    assert isinstance(bio.brain, BioBrain) and not bio.brain.learned.any()
    bio.brain.learned[0, 1] = 0.04
    bio.save()
    assert arquivo_lif.read_bytes() == bytes_lif            # o arquivo do LIF não mudou
    bytes_bio = arquivo_bio.read_bytes()

    # 3) volta para o LIF: tudo como ele deixou, e o do bio fica intacto
    de_novo = _abrir(paths, monkeypatch, "lif")
    assert isinstance(de_novo.brain, LIFBrain)
    assert de_novo.brain.learned[0, 0] == pytest.approx(0.05, abs=1e-6)
    assert np.count_nonzero(de_novo.brain.learned) == 1
    de_novo.save()
    assert arquivo_bio.read_bytes() == bytes_bio

    # 4) e de novo o bio: o aprendizado dele voltou
    bio2 = _abrir(paths, monkeypatch, "bio")
    assert bio2.brain.learned[0, 1] == pytest.approx(0.04, abs=1e-6)
    assert np.count_nonzero(bio2.brain.learned) == 1


def test_save_do_bio_estragado_nao_atinge_o_lif(tmp_path, monkeypatch):
    """Um arquivo do bio ilegível só faz o bio começar do zero: o LIF segue com o dele."""
    paths = Paths(root=tmp_path)
    paths.pets.mkdir()
    paths.definicao("bryan").write_text('{"nome": "Bryan", "seed": 7}', encoding="utf-8")
    lif = _abrir(paths, monkeypatch, "lif")
    lif.brain.learned[0, 0] = 0.05
    lif.save()
    arquivo_do_bio(lif.state_file).write_text("{ quebrado", encoding="utf-8")
    bio = _abrir(paths, monkeypatch, "bio")
    assert not bio.brain.learned.any()
    assert _abrir(paths, monkeypatch, "lif").brain.learned[0, 0] == pytest.approx(0.05, abs=1e-6)
