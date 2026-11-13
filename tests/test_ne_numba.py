"""
Passo do BioBrain compilado com Numba (core/bio/acelerado.py; decisão do Cantyll, 2026-11-13, opção C).

O critério é a igualdade bit a bit com o caminho em numpy: os mesmos pulsos, passo a passo, e o mesmo estado
(tensões, correntes, adaptação, habituação, rastro). Sem o Numba instalado, estes testes são pulados e só o
teste do caminho de reserva roda.

Rodar: python -m pytest tests/test_ne_numba.py -q
"""
import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core import nervous_system as ns
from pestinha.core.bio import BioBrain, acelerado
from pestinha.core.bio.rede import adaptacao_das_chaves, gasto_das_chaves, neuronios_das_chaves

precisa_numba = pytest.mark.skipif(not acelerado.DISPONIVEL, reason=f"sem Numba: {acelerado.MOTIVO}")


def _config(nome, monkeypatch):
    if nome == "lif":
        return {"tipos": {}}
    monkeypatch.setattr(ajustes, "NE_INIBIDORES_FS", True)
    monkeypatch.setattr(ajustes, "NE_EXCITATORIOS", nome in ("ne3", "ne4"))
    monkeypatch.setattr(ajustes, "NE_MOTORES", nome == "ne4")              # NE-4: motores em RS e o STARTLE em CH
    tipos, ganho, tau = neuronios_das_chaves()
    return {"tipos": tipos, "ganho": ganho, "tau_sinaptico": tau, "gasta_corrente": gasto_das_chaves(),
            "adaptacao_lenta": adaptacao_das_chaves()}


def _par(kwargs, monkeypatch, seed=7, seed_ruido=5):
    monkeypatch.setattr(ajustes, "NE_NUMBA", False)
    numpy_ = BioBrain(seed=seed, seed_ruido=seed_ruido, **kwargs)
    monkeypatch.setattr(ajustes, "NE_NUMBA", True)
    compilado = BioBrain(seed=seed, seed_ruido=seed_ruido, **kwargs)
    assert not numpy_.numba and compilado.numba
    return numpy_, compilado


def _estado(b):
    partes = [b.spikes, b.trace, b.pre_gain, b.pool_counts, b.disparos, b.neuronios.v, b.neuronios.a,
              b.neuronios.ref.astype(float)]
    if b.izhikevich is not None:
        z = b.izhikevich
        partes += [z.v, z.u, z.i_ampa, z.i_gaba, z.adapt]
    return partes


def _iguais(a, b):
    for x, y in zip(_estado(a), _estado(b)):
        assert np.array_equal(x, y)


ROTEIRO = [
    ({"WORK": 0.8, "TYPING": 0.3}, False),
    ({"DISMISS": 1.0, "BOREDOM": 0.6, "POKE": 0.5}, False),
    ({"DISMISS": 1.0, "BOREDOM": 1.0}, True),                   # ausência (R1) ligada
    ({c: 1.0 for c in ns.SENSORY_SPEC}, False),               # tudo no máximo: muitos pulsos
    ({"CARESS": 1.0, "SOUND": 0.5}, False),
]


@precisa_numba
@pytest.mark.parametrize("nome", ["lif", "ne2", "ne3", "ne4"])
def test_mesmos_pulsos_passo_a_passo(nome, monkeypatch):
    a, b = _par(_config(nome, monkeypatch), monkeypatch)
    total = 0
    for sentidos, ausente in ROTEIRO:
        for x in (a, b):
            x.stimulate(sentidos)
            x.definir_ausencia(ausente)
        for _ in range(400):
            a._substep()
            b._substep()
            assert np.array_equal(a.spikes, b.spikes)
            total += int(a.spikes.sum())
        for x in (a, b):
            x.pool_counts[:] = 0.0
        _iguais(a, b)
    assert total > 500                                          # a comparação não foi feita só com silêncio


@precisa_numba
@pytest.mark.parametrize("nome", ["lif", "ne3", "ne4"])
def test_mesmo_aprendizado_e_mesmas_taxas(nome, monkeypatch):
    """Com aprendizado (pesos plásticos mudam) e step(), as taxas e a matriz aprendida saem iguais."""
    a, b = _par(_config(nome, monkeypatch), monkeypatch, seed=11, seed_ruido=3)
    for x in (a, b):
        x.stimulate({"PLAY": 1.0, "BOREDOM": 0.4})
    for _ in range(30):
        for x in (a, b):
            x.step(100)
            x.learn(1.0, 0.2, 0.1, rate=1.0)
    assert np.abs(a.learned).max() > 0                         # aprendeu algo
    assert np.array_equal(a.learned, b.learned)
    assert np.array_equal(a.pool_rate, b.pool_rate)
    _iguais(a, b)


def test_sem_numba_fica_o_numpy(monkeypatch):
    monkeypatch.setattr(ajustes, "NE_NUMBA", False)
    b = BioBrain(seed=7, tipos={})
    assert b.numba is False
    b.step(50)                                                  # o caminho de reserva roda
