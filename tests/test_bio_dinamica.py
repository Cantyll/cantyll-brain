"""
BioBrain, T2.2 (plano, T2, PR 2 de 4): estrutura e dinâmica, sem aprendizado.

Nesta fase o BioBrain é o LIFBrain em outra forma: populações explícitas e projeções em listas de
sinapses. Com a mesma semente, as sinapses saem iguais às do LIF; com a mesma semente de ruído, os pulsos
também. Aprendizado, replay, SHY, salvar e carregar estão em test_bio_aprendizado.py (T2.3).

Rodar: python -m pytest tests/test_bio_dinamica.py -q
"""
import importlib

import numpy as np
import pytest

from pestinha.core.bio import BIO_VERSION, BioBrain
from pestinha.core.bio.projecoes import Projecao, compilar, projecao_de_bloco
from pestinha.core.nervous_system import LIFBrain

TEMPERAMENTO = {"PLAYFUL": 1.3, "DRAG->ALERT": 0.5}
SEQUENCIA = [
    {"WORK": 1.0, "TYPING": 0.6},
    {"PLAY": 1.0, "BOREDOM": 0.3},
    {"DISMISS": 1.0},
    {"SILENCE": 0.3, "BOREDOM": 1.0},
    {"CARESS": 1.0, "POKE": 0.5},
]


def _par(seed=7, temperament=None, ruido=5):
    return (LIFBrain(seed=seed, temperament=temperament, seed_ruido=ruido),
            BioBrain(seed=seed, temperament=temperament, seed_ruido=ruido))


# ---------------- estrutura ----------------

@pytest.mark.parametrize("seed,temperament", [(7, None), (11, TEMPERAMENTO)])
def test_mesmas_populacoes_sinapses_e_posicoes_que_o_lif(seed, temperament):
    lif, bio = _par(seed, temperament)
    assert bio.pools == lif.pools
    assert (bio.N, bio.Ns, bio.Nl) == (lif.N, lif.Ns, lif.Nl)
    assert bio.sensory_names == lif.sensory_names and bio.motor_names == lif.motor_names
    assert bio.n_synapses == lif.n_synapses
    assert np.array_equal(bio.W, lif.W)
    assert np.array_equal(bio.pos, lif.pos) and np.array_equal(bio.kind, lif.kind)
    assert np.array_equal(bio.neuronios.decay, lif.decay)
    assert np.array_equal(bio.neuronios.adapt_b, lif.adapt_b)
    assert np.array_equal(bio.neuronios.adapt_decay, lif.adapt_decay)


def test_contagem_da_semente_7():
    """A contagem que a spec cita (seção 10, não regressão): 470 neurônios e 15.808 sinapses."""
    bio = BioBrain(seed=7)
    assert (bio.N, bio.n_synapses) == (470, 15808)
    assert bio.describe().startswith("Bio 470 neurônios, 15808 sinapses")


def test_outra_semente_e_outro_individuo():
    assert not np.array_equal(BioBrain(seed=7).W, BioBrain(seed=8).W)


# ---------------- dinâmica ----------------

def test_mesmos_pulsos_que_o_lif_com_o_mesmo_ruido():
    """20 s com estímulos trocando a cada segundo e a ausência ligada no meio: pulsos idênticos aos do LIF."""
    lif, bio = _par(11, TEMPERAMENTO)
    lif.recording = bio.recording = True
    for k in range(20):
        sentidos = SEQUENCIA[k % len(SEQUENCIA)]
        lif.stimulate(sentidos)
        bio.stimulate(sentidos)
        if k == 10:
            lif.definir_ausencia(True)
            bio.definir_ausencia(True)
        for _ in range(10):
            lif.step(100)
            bio.step(100)
    assert np.array_equal(bio.disparos, lif.disparos)
    assert bio.pool_rates() == lif.pool_rates()
    assert np.array_equal(bio.p, lif.p)
    assert np.array_equal(bio.trace, lif.trace)
    assert [b.tolist() for b in bio.raster] == [b.tolist() for b in lif.raster]
    assert bio.time_ms == lif.time_ms


def test_ausencia_cala_fugir_e_travessura():
    """R1: com o modulador de ausência, FUGIR e TRAVESSURA ficam abaixo do controle com você presente."""
    def rodar(ausente):
        bio = BioBrain(seed=7, seed_ruido=3)
        bio.definir_ausencia(ausente)
        bio.stimulate({"BOREDOM": 1.0, "SILENCE": 0.3})
        for _ in range(30):
            bio.step(100)
        return bio.disparos[bio._pool_index["TRAVESSURA"]], bio.disparos[bio._pool_index["FUGIR"]]

    presente, ausente = rodar(False), rodar(True)
    assert presente[0] > 0
    assert ausente[0] < presente[0] and ausente[1] <= presente[1]


def test_mesma_semente_de_ruido_repete():
    a, b = BioBrain(seed=7, seed_ruido=9), BioBrain(seed=7, seed_ruido=9)
    for bio in (a, b):
        bio.stimulate({"PLAY": 1.0})
        for _ in range(10):
            bio.step(100)
    assert np.array_equal(a.disparos, b.disparos)


def test_habituacao_e_reset():
    bio = BioBrain(seed=7, seed_ruido=1)
    bio.stimulate({"POKE": 1.0})
    for _ in range(20):
        bio.step(100)
    assert bio.efficacy()["POKE"] < 0.99
    bio.reset_habituation()
    assert bio.efficacy()["POKE"] == 1.0


# ---------------- interface ----------------

def test_interface_igual_a_do_lif():
    lif, bio = _par()
    for brain in (lif, bio):
        brain.stimulate({"WORK": 1.0})
        brain.step(200)
    assert set(bio.snapshot()) == set(lif.snapshot())
    assert set(bio.taxas()) == set(lif.taxas()) == {p["name"] for p in bio.pools}
    assert set(bio.motor_activity()) == set(lif.motor_activity())
    assert set(bio.efficacy()) == set(lif.efficacy())
    estado_bio, estado_lif = bio.estado(), lif.estado()
    assert set(estado_bio) - {"plasticidade"} == set(estado_lif)   # o crítico do PL-1 é só do bio
    assert estado_bio["tipo"] == "bio" and estado_bio["versao"] == BIO_VERSION
    assert estado_bio["aprendido"] == estado_lif["aprendido"]
    assert bio.learned_summary() == []
    assert bio.avancar(0.25) == 0.25


@pytest.mark.parametrize("nome", [
    "plasticidade", "moduladores", "consolidacao", "assembleias", "crescimento", "workspace", "talamo",
    "spec_base", "spec_corpo", "spec_eu", "spec_workspace", "spec_linguagem",
])
def test_arquivos_das_frentes_existem(nome):
    modulo = importlib.import_module(f"pestinha.core.bio.{nome}")
    assert "Dono" in modulo.__doc__   # "Dono:" ou "Donos:"


# ---------------- projeções ----------------

def test_tabela_soma_repetidas_e_tira_as_que_se_anulam():
    a = Projecao("A", "B", [0, 0, 1], [3, 4, 3], [0.5, 0.2, 0.1])
    b = Projecao("A", "B", [0, 1], [3, 3], [0.25, -0.1])
    tabela = compilar([a, b], n_pre=3, n_pos=2, deslocamento=3)
    assert len(tabela) == 2                                  # (0,3) somada; (1,3) zerou e saiu; (0,4) fica
    assert np.allclose(tabela.densa(), [[0.75, 0.2], [0.0, 0.0], [0.0, 0.0]])


def test_propagar_e_o_produto_denso():
    rng = np.random.default_rng(0)
    bloco = rng.normal(size=(40, 25)) * (rng.random((40, 25)) < 0.3)
    tabela = compilar([projecao_de_bloco("A", "B", 0, 40, bloco)], n_pre=40, n_pos=25, deslocamento=40)
    for _ in range(20):
        pulsos = (rng.random(40) < 0.2).astype(float)
        ganho = rng.uniform(0.5, 1.0, 40)
        esperado = (pulsos * ganho) @ bloco
        obtido = tabela.propagar(pulsos * ganho, np.flatnonzero(pulsos))
        assert np.allclose(obtido, esperado, atol=1e-12)
    assert np.array_equal(tabela.propagar(np.zeros(40), np.zeros(0, dtype=int)), np.zeros(25))


def test_projecao_recusa_dado_invalido():
    with pytest.raises(ValueError):
        Projecao("A", "B", [0, 1], [2], [0.1, 0.2])
    with pytest.raises(ValueError):
        Projecao("A", "B", [0], [2], [0.1], receptor="D3")
    with pytest.raises(ValueError):
        compilar([Projecao("A", "B", [0], [9], [0.1])], n_pre=2, n_pos=2, deslocamento=2)
    assert Projecao("A", "B", [0], [2], [-0.1]).sinal == -1
