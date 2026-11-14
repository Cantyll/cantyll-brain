"""
NE-2 (plano, onda 2): os interneurônios inibitórios do BioBrain (QUIET e INHIB) em Izhikevich FS, atrás da chave
ajustes.NE_INIBIDORES_FS, ligada por padrão desde a NE-5 (PESTINHA_NE=0 desliga as três chaves da frente).

Com a chave ligada, as duas populações usam τ sináptico = τ_m do LIF (opção A, 2026-11-13) e os ganhos de
ajustes.py. Os critérios são relativos ao LIF (plano, seção 2, regra 7).

Rodar: python -m pytest tests/test_ne2_inibidores.py -q
"""
import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core import nervous_system as ns
from pestinha.core.bio import BioBrain
from pestinha.core.bio.rede import neuronios_das_chaves


@pytest.fixture
def ne2(monkeypatch):
    _desligar(monkeypatch)
    monkeypatch.setattr(ajustes, "NE_INIBIDORES_FS", True)


def _desligar(monkeypatch):
    """Desde a NE-5 as chaves vêm ligadas (PESTINHA_NE=0 desliga): aqui, desligadas uma a uma."""
    for chave in ("NE_INIBIDORES_FS", "NE_EXCITATORIOS", "NE_MOTORES"):
        monkeypatch.setattr(ajustes, chave, False)


def test_chave_desligada_nada_muda(monkeypatch):
    _desligar(monkeypatch)
    assert neuronios_das_chaves() == ({}, {}, {})
    b = BioBrain(seed=7)
    assert b.tipos == {} and b.izhikevich is None


def test_chave_ligada_poe_quiet_e_inhib_em_fs(ne2):
    b = BioBrain(seed=7)
    assert b.tipos == {"QUIET": "FS", "INHIB": "FS"}
    n = b.pool("QUIET")["n"] + b.pool("INHIB")["n"]
    assert b.izhikevich.n == n and set(b.izhikevich.tipos) == {"FS"}
    assert b.neuronios.n == b.Nl - n
    padrao = BioBrain(seed=7, tipos={})
    assert np.array_equal(b.W, padrao.W)                 # só o neurônio muda: as sinapses são as mesmas


def test_chave_ligada_usa_tau_da_membrana_e_ganhos_de_ajustes(ne2):
    tipos, ganho, tau = neuronios_das_chaves()
    assert tau == {"QUIET": "membrana", "INHIB": "membrana"}
    assert ganho == {"QUIET": ajustes.NE_GANHO_QUIET, "INHIB": ajustes.NE_GANHO_INHIB}
    b = BioBrain(seed=7)
    tau_m = {name: t for name, _k, _n, t, *_ in ns.INTER_SPEC}
    inhib = b._locais_izh + b.Ns >= b.pool("INHIB")["start"]
    assert np.all(np.abs(b.izhikevich.tau_ampa[inhib] / tau_m["INHIB"] - 1) <= 0.1 + 1e-9)
    assert np.all(np.abs(b.izhikevich.tau_ampa[~inhib] / tau_m["QUIET"] - 1) <= 0.1 + 1e-9)


def test_argumentos_explicitos_vencem_a_chave(ne2):
    assert BioBrain(seed=7, tipos={}).izhikevich is None
    assert BioBrain(seed=7, tipos={"QUIET": "FS"}).tipos == {"QUIET": "FS"}


def test_ganhos_fora_do_limite_sao_recusados(monkeypatch):
    monkeypatch.setattr(ajustes, "NE_GANHO_INHIB", 0.0)
    with pytest.raises(ValueError, match="NE_GANHO_INHIB"):
        ajustes.validar()


def _taxas(nivel, **kwargs):
    """Hz médio por população, 3 sementes, todos os canais no nível dado, 3 s depois de 0,5 s de entrada."""
    total = None
    for semente in (3, 7, 11):
        b = BioBrain(seed=semente, seed_ruido=3, **kwargs)
        b.stimulate({c: nivel for c in ns.SENSORY_SPEC})
        for _ in range(5):
            b.step(100)
        b.disparos[:] = 0
        for _ in range(30):
            b.step(100)
        taxa = b.disparos / (3.0 * b.pool_sizes)
        total = taxa if total is None else total + taxa
    return {p["name"]: float(total[i] / 3) for i, p in enumerate(b.pools)}


def test_com_entrada_forte_a_inhib_fica_perto_do_lif(ne2):
    """Calibração: com todos os canais em 1,0, a INHIB em FS dispara a ±30% do LIF, e quem ela inibe a ±10%."""
    lif, fs = _taxas(1.0, tipos={}), _taxas(1.0)
    assert lif["INHIB"] > 10.0                           # a comparação não é 0 contra 0
    assert abs(fs["INHIB"] / lif["INHIB"] - 1) <= 0.30
    for nome in ("ALERT", "FOCUS", "CURIOUS", "PLAYFUL", "WATCH"):
        assert abs(fs[nome] / lif[nome] - 1) <= 0.10, nome


def test_ausencia_continua_valendo_com_a_chave(ne2):
    """FUGIR e TRAVESSURA seguem no LIF; a guarda de ausência (R1) continua cortando as duas."""
    sentidos = {"BOREDOM": 1.0, "DISMISS": 1.0, "POKE": 0.5}
    presente, ausente = BioBrain(seed=7, seed_ruido=9), BioBrain(seed=7, seed_ruido=9)
    ausente.definir_ausencia(True)
    for b in (presente, ausente):
        b.stimulate(sentidos)
        for _ in range(50):
            b.step(100)
    alvos = [presente._pool_index["FUGIR"], presente._pool_index["TRAVESSURA"]]
    assert presente.disparos[alvos].sum() > 0
    assert ausente.disparos[alvos].sum() < 0.5 * presente.disparos[alvos].sum()
