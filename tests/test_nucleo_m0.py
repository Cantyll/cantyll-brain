"""
M0 do núcleo biológico (docs/ESPECIFICACAO_NUCLEO_BIOLOGICO.md, seções 11 e 13):
interface Brain com erro de predição em learn(), avancar(), estado(), versionamento e roundtrip.
O comportamento do LIF padrão não muda: estes testes checam isso também.
"""

import json
import math
import os

import numpy as np
import pytest

from pestinha import config
from pestinha.core import nervous_system as ns
from pestinha.core.nervous_system import Brain, LIFBrain, criar_cerebro
from pestinha.core.homeostasis import Drives


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
    from pestinha.core.bio import BioBrain
    assert isinstance(criar_cerebro("lif", seed=7), LIFBrain)
    assert isinstance(criar_cerebro("bio", seed=7), BioBrain)
    assert isinstance(criar_cerebro(seed=7), Brain)
    with pytest.raises(ValueError):
        criar_cerebro("izhikevich")
    # o padrão do app é o bio desde a NE-5 (V7, opção B); PESTINHA_CEREBRO troca (tests/test_troca_padrao.py)
    assert config.CEREBRO == (os.environ.get("PESTINHA_CEREBRO", "").strip() or "bio")
    assert config.CEREBROS_PRONTOS == ("lif", "bio")
    assert config.cerebro_escolhido("lif") == "lif"
    assert config.cerebro_escolhido("bio") == "bio"
    assert config.cerebro_escolhido("izhikevich") == "lif"   # não pronto: volta ao LIF


def test_mesma_semente_de_ruido_mesmo_estado():
    # determinismo: compara o estado (estado()), não os spikes
    a = LIFBrain(seed=7, seed_ruido=42)
    b = LIFBrain(seed=7, seed_ruido=42)
    for brain in (a, b):
        for _ in range(50):
            brain.stimulate({"WORK": 0.8, "TYPING": 0.3})
            brain.step(100)
            brain.learn(1.0, 0.0, 0.1, 0.004)
    assert a.estado() == b.estado()


def test_sem_semente_de_ruido_o_padrao_continua_aleatorio():
    a, b = LIFBrain(seed=7), LIFBrain(seed=7)
    for brain in (a, b):
        brain.stimulate({"WORK": 0.8, "TYPING": 0.3})
        brain.step(500)
    assert a.estado() != b.estado()


def _rodar_ausencia(seed, ausente):
    """Ausência longa, com carência e tédio no máximo e silêncio total. Devolve a média dos últimos 3 s (após 8 s de aquecimento)."""
    b = LIFBrain(seed=seed, seed_ruido=42)
    b.definir_ausencia(ausente)
    d = Drives()
    d.contact, d.stimulation, d.energy = 1.0, 0.0, 0.5
    soma, n = {}, 0
    for t in range(110):
        ch = d.channels()
        ch["SILENCE"] = 1.0
        b.stimulate(ch)
        b.step(100)
        if t >= 80:
            for k, v in b.motor_activity().items():
                soma[k] = soma.get(k, 0.0) + v
            n += 1
    return {k: v / n for k, v in soma.items()}


def test_ausencia_segura_fugir_e_travessura_sem_mexer_no_repouso():
    # R1: sem você, FUGIR e TRAVESSURA quase param na rede; o repouso continua subindo; ninguém fica triste
    for seed in (7, 1729):
        com = _rodar_ausencia(seed, True)
        sem = _rodar_ausencia(seed, False)
        assert sem["FUGIR"] > 2.0                       # sem o modulador, a fuga passa do limiar (como antes)
        assert com["FUGIR"] < 0.5
        assert com["TRAVESSURA"] < 0.2 * sem["TRAVESSURA"]
        assert com["DROWSE"] >= 0.9 * sem["DROWSE"]
        assert com["SAD"] == 0.0 and com["CANTO"] == 0.0


def test_modulador_de_ausencia_desligado_e_o_padrao():
    b = LIFBrain(seed=7)
    assert b.ausente is False
    b.definir_ausencia(False)
    assert b.ausente is False
