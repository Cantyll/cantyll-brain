"""
BioBrain, T2.3 (plano, T2, PR 3 de 4): aprendizado, replay, homeostase do sono, salvar e carregar.

A regra de aprendizado é a do LIFBrain, levada para as projeções plásticas: com a mesma semente e o mesmo
ruído, `learned`, os pesos e os pulsos saem iguais aos do LIF. O save é do BioBrain e não lê o do LIF
(decisão D7).

Rodar: python -m pytest tests/test_bio_aprendizado.py -q
"""
import json

import numpy as np
import pytest

from ferramentas.simular_noites import simular
from pestinha.core import nervous_system as ns
from pestinha.core.bio import BioBrain
from pestinha.core.nervous_system import LIFBrain
from pestinha import ajustes


@pytest.fixture(autouse=True)
def _regra_do_lif(monkeypatch):
    """A paridade é com a regra do LIF: o PL-1 (ligado por padrão no bio) muda o aprendizado de propósito."""
    monkeypatch.setattr(ajustes, "PL_DELTA", False)

SEQUENCIA = [
    ({"CARESS": 1.0, "POKE": 0.4}, 1.0),
    ({"DISMISS": 1.0}, -1.0),
    ({"PLAY": 1.0, "BOREDOM": 0.2}, 0.6),
    ({"SILENCE": 0.5, "BOREDOM": 1.0}, -0.4),
]


def _par(seed=7, ruido=5):
    return LIFBrain(seed=seed, seed_ruido=ruido), BioBrain(seed=seed, seed_ruido=ruido)


def _treinar(brain, segundos=12, teto=None):
    for k in range(segundos):
        sentidos, recompensa = SEQUENCIA[k % len(SEQUENCIA)]
        brain.stimulate(sentidos)
        for _ in range(10):
            brain.step(100)
            brain.learn(recompensa, 0.0, 0.1, teto=teto)


def _iguais(lif, bio):
    assert np.array_equal(bio.learned, lif.learned)
    assert np.array_equal(bio.eligibility, lif.eligibility)
    assert np.array_equal(bio.W, lif.W)
    assert np.array_equal(bio.disparos, lif.disparos)


# ---------------- aprendizado ----------------

@pytest.mark.parametrize("teto", [None, 0.6])
def test_aprendizado_igual_ao_do_lif(teto):
    lif, bio = _par()
    _treinar(lif, teto=teto)
    _treinar(bio, teto=teto)
    assert np.abs(bio.learned).max() > 0          # aprendeu de fato, não é 0 == 0
    _iguais(lif, bio)
    assert bio.learned_summary() == lif.learned_summary()


def test_peso_plastico_segue_learned():
    """Peso efetivo = base + learned × unidade, a mesma conta do LIF (W_base + learned × máscara)."""
    bio = BioBrain(seed=7)
    antes = bio.W.copy()
    bio.learned[:] = 0.0
    bio.learned[bio.sensory_names.index("CARESS"), bio.plastic_posts.index("PLAYFUL")] = ns.LEARN_MAX
    bio._apply_learning()
    mudou = bio.W != antes
    assert mudou.any()
    linhas = np.flatnonzero(mudou.any(axis=1))
    assert set(linhas) <= set(range(*bio.pool("CARESS").fatia.indices(bio.N)))


def test_aprendizado_respeita_os_limites():
    bio = BioBrain(seed=7, seed_ruido=1)
    bio.stimulate({"CARESS": 1.0})
    bio.step(100)
    for _ in range(2000):
        bio.learn(50.0, 0.0, 0.1, rate=1.0)
    assert bio.learned.max() <= ns.LEARN_MAX and bio.learned.min() >= ns.LEARN_MIN


def test_contagem_de_sinapses_nao_muda_com_aprendizado():
    """n_synapses conta as sinapses que existem antes do aprendizado, como no LIF."""
    lif, bio = _par()
    _treinar(lif)
    _treinar(bio)
    assert bio.n_synapses == lif.n_synapses == 15808


# ---------------- replay e sono ----------------

def test_replay_e_shy_iguais_ao_lif():
    lif, bio = _par(11, 3)
    for brain in (lif, bio):
        _treinar(brain, segundos=6)
        brain.replay({"CARESS": 1.0, "WORK": 0.3, "NAO_EXISTE": 1.0}, 700, 0.8, teto=0.6)
        brain.replay({"DISMISS": 1.0}, 350, -0.5)
        brain.downscaling_sono(0.2)
    _iguais(lif, bio)


def test_downscaling_encolhe_o_aprendido():
    bio = BioBrain(seed=7, seed_ruido=2)
    _treinar(bio)
    antes = bio.learned.copy()
    bio.downscaling_sono(0.25)
    assert np.allclose(bio.learned, antes * 0.75)


def test_simulacao_de_noites_igual_ao_lif():
    """simular_noites com --cerebro bio dá as mesmas linhas que com o LIF (3 noites, misto)."""
    lif = simular("misto", noites=3, semente=3, cerebro="lif")
    bio = simular("misto", noites=3, semente=3, cerebro="bio")
    assert bio == lif


# ---------------- salvar e carregar ----------------

def test_salvar_e_carregar_devolve_o_mesmo_estado(tmp_path):
    arquivo = tmp_path / "bio.json"
    a = BioBrain(seed=7, seed_ruido=4)
    _treinar(a)
    a.stimulate({"POKE": 1.0})
    for _ in range(10):
        a.step(100)
    a.save(arquivo)

    b = BioBrain(seed=7, seed_ruido=4)
    assert b.load(arquivo) is True
    assert np.allclose(b.learned, a.learned, atol=1e-6)
    assert np.allclose(b.W, a.W, atol=1e-5)
    for nome in b.sensory_names:
        assert b.efficacy()[nome] == pytest.approx(a.efficacy()[nome], abs=0.02)   # recupera um pouco no intervalo


def test_save_do_lif_nao_e_lido(tmp_path):
    arquivo = tmp_path / "lif.json"
    lif = LIFBrain(seed=7, seed_ruido=4)
    _treinar(lif)
    lif.save(arquivo)
    bio = BioBrain(seed=7)
    antes = bio.learned.copy()
    assert bio.load(arquivo) is False
    assert np.array_equal(bio.learned, antes)


@pytest.mark.parametrize("estrago", [
    lambda d: d.update(seed=8),
    lambda d: d.update(version=99),
    lambda d: d["populacoes"].update(PLAYFUL=11),
    lambda d: d["learned"]["CARESS"].update(PLAYFUL="nan"),
    lambda d: d.update(learned=[1, 2]),
])
def test_save_estranho_nao_muda_nada(tmp_path, estrago):
    arquivo = tmp_path / "bio.json"
    a = BioBrain(seed=7, seed_ruido=4)
    _treinar(a)
    a.save(arquivo)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    estrago(dados)
    arquivo.write_text(json.dumps(dados), encoding="utf-8")

    b = BioBrain(seed=7)
    antes, eficacia = b.learned.copy(), b.p.copy()
    assert b.load(arquivo) is False
    assert np.array_equal(b.learned, antes) and np.array_equal(b.p, eficacia)


def test_arquivo_ausente_ou_quebrado(tmp_path):
    bio = BioBrain(seed=7)
    assert bio.load(tmp_path / "nao_existe.json") is False
    quebrado = tmp_path / "quebrado.json"
    quebrado.write_text("{ isso não é json", encoding="utf-8")
    assert bio.load(quebrado) is False
