"""
M0 do núcleo biológico (docs/ESPECIFICACAO_NUCLEO_BIOLOGICO.md, seções 11 e 13):
interface Brain com erro de predição em learn(), avancar(), estado(), versionamento e roundtrip.
O comportamento do LIF padrão não muda: estes testes checam isso também.
"""

import json
import math

import numpy as np
import pytest

from pestinha import config
from pestinha.core import nervous_system as ns
from pestinha.core.nervous_system import Brain, LIFBrain, criar_cerebro


def test_expected_zero_reproduz_a_recompensa_bruta_de_antes():
    # Mesma conta do comportamento anterior: rate * reward * dt * outer(elegibilidade, sinal)
    b = LIFBrain(seed=7)
    b.stimulate({"WEB": 1.0, "CARESS": 1.0})
    b.step(100)
    b.learn(1.0, 0.0, 0.1, 0.004)
    k = 1.0 - math.exp(-0.1 / ns.ELIGIBILITY_TAU)
    elegibilidade = b._levels * k                       # partiu de zero
    esperado = np.clip(0.004 * 1.0 * 0.1 * np.outer(elegibilidade, b.post_sign), ns.LEARN_MIN, ns.LEARN_MAX)
    assert np.allclose(b.learned, esperado, rtol=0, atol=1e-12)


def test_erro_de_predicao_zero_nao_muda_o_aprendizado():
    b = LIFBrain(seed=7)
    b.stimulate({"WEB": 1.0, "CARESS": 1.0})
    b.step(100)
    b.learn(1.0, 1.0, 0.1, 0.004)                       # δ = 0: a recompensa era esperada
    assert not b.learned.any()
    assert b.eligibility.any()                          # o rastro continua sendo atualizado


def test_predicao_acima_da_recompensa_inverte_o_sinal():
    b = LIFBrain(seed=7)
    b.stimulate({"WEB": 1.0})
    b.step(100)
    b.learn(0.0, 1.0, 0.1, 0.004)                       # δ = -1
    i = b.sensory_names.index("WEB")
    assert b.learned[i, b.plastic_posts.index("PLAYFUL")] < 0
    assert b.learned[i, b.plastic_posts.index("FRUSTRATION")] > 0


def test_avancar_limita_a_um_segundo_e_informa_o_tempo_simulado():
    b = LIFBrain(seed=7)
    assert b.avancar(0.25) == pytest.approx(0.25)
    assert b.time_ms == 250
    assert b.avancar(5.0) == pytest.approx(1.0)         # teto por chamada (computador que dormiu)
    assert b.time_ms == 1250
    assert b.avancar(0.0) == 0.0
    assert b.avancar(-3.0) == 0.0
    assert b.time_ms == 1250


def test_estado_e_serializavel_e_tem_versao():
    b = LIFBrain(seed=7)
    b.stimulate({"WORK": 0.8})
    b.step(200)
    e = b.estado()
    json.dumps(e)                                       # sem arrays numpy
    assert e["tipo"] == "lif" and e["versao"] == 1
    assert e["neuronios"] == b.N and e["tempo_ms"] == 200.0
    assert set(e["eficacia"]) == set(b.sensory_names)
    assert set(e["aprendido"]) == set(b.sensory_names)


def test_roundtrip_identico_com_relogio_parado(tmp_path, monkeypatch):
    monkeypatch.setattr(ns.time, "time", lambda: 1_000_000.0)   # sem tempo decorrido na recuperação
    a = LIFBrain(seed=7)
    for _ in range(30):
        a.stimulate({"WEB": 1.0, "CARESS": 1.0})
        a.step(100)
        a.learn(1.0, 0.0, 0.1, 0.004)
    assert a.learned.any()
    primeiro, segundo = tmp_path / "a.json", tmp_path / "b.json"
    a.save(str(primeiro))
    b = LIFBrain(seed=7)
    assert b.load(str(primeiro))
    b.save(str(segundo))
    assert json.loads(primeiro.read_text()) == json.loads(segundo.read_text())
    assert np.allclose(a.learned, b.learned, rtol=0, atol=1e-6)


def test_load_rejeita_outro_tipo_sem_mudar_nada(tmp_path):
    caminho = tmp_path / "estado.json"
    LIFBrain(seed=7).save(str(caminho))
    dados = json.loads(caminho.read_text())
    dados["tipo"] = "bio"
    caminho.write_text(json.dumps(dados))
    b = LIFBrain(seed=7)
    antes = b.learned.copy()
    assert b.load(str(caminho)) is False
    assert (b.learned == antes).all()


def test_save_antigo_sem_campo_tipo_continua_carregando(tmp_path):
    caminho = tmp_path / "antigo.json"
    LIFBrain(seed=7).save(str(caminho))
    dados = json.loads(caminho.read_text())
    del dados["tipo"]                                   # formato anterior à M0
    caminho.write_text(json.dumps(dados))
    assert LIFBrain(seed=7).load(str(caminho)) is True


def test_learn_aceita_taxa_padrao():
    b = LIFBrain(seed=7)
    b.stimulate({"WEB": 1.0})
    b.step(100)
    b.learn(1.0, 0.0, 0.1)                              # sem rate: usa LEARN_RATE_PADRAO
    assert b.learned.any()


def test_criar_cerebro_e_escolha_pela_configuracao():
    assert isinstance(criar_cerebro("lif", seed=7), LIFBrain)
    assert isinstance(criar_cerebro(seed=7), Brain)
    with pytest.raises(ValueError):
        criar_cerebro("bio")
    assert config.cerebro_escolhido() == "lif"
    assert config.cerebro_escolhido("lif") == "lif"
    assert config.cerebro_escolhido("bio") == "lif"     # ainda não pronto: volta ao padrão
