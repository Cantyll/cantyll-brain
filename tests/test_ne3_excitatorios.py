"""
NE-3 (plano, onda 2): os 8 interneurônios excitatórios do BioBrain (ALERT, FOCUS, CURIOUS, PLAYFUL, CALM, TIRED,
FRUSTRATION, GLOOM) em Izhikevich, atrás da chave ajustes.NE_EXCITATORIOS, desligada por padrão (R7). Sete em RS;
a ALERT em CH, com a adaptação lenta do LIF (tests/test_ne_susto.py).

Com a chave ligada, as 8 populações usam τ sináptico = τ_m do LIF (opção A, 2026-11-13), os ganhos de ajustes.py,
e o pulso gasta um limiar do LIF da corrente sináptica (gasta_corrente), como o reset do LIF. Os critérios são
relativos ao LIF (plano, seção 2, regra 7).

Rodar: python -m pytest tests/test_ne3_excitatorios.py -q
"""
import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core import nervous_system as ns
from pestinha.core.bio import BioBrain
from pestinha.core.bio.neuronios import Izhikevich, Neuronio, escala_de_corrente, reobase
from pestinha.core.bio.rede import EXCITATORIOS_NE3, gasto_das_chaves, neuronios_das_chaves

TAU_M = {name: t for name, _k, _n, t, *_ in ns.INTER_SPEC}


@pytest.fixture
def ne3(monkeypatch):
    monkeypatch.setattr(ajustes, "NE_INIBIDORES_FS", True)
    monkeypatch.setattr(ajustes, "NE_EXCITATORIOS", True)


def test_chave_desligada_por_padrao():
    assert ajustes.NE_EXCITATORIOS is False
    assert gasto_das_chaves() == set()
    assert all(name not in neuronios_das_chaves()[0] for name in EXCITATORIOS_NE3)


def test_chave_ligada_poe_7_excitatorios_em_rs_e_a_alert_em_ch(ne3):
    tipos, ganho, tau = neuronios_das_chaves()
    esperado = {name: "RS" for name in EXCITATORIOS_NE3} | {"ALERT": "CH"}
    assert {name: tipos[name] for name in EXCITATORIOS_NE3} == esperado
    assert tipos["QUIET"] == tipos["INHIB"] == "FS"
    assert set(tau.values()) == {"membrana"}
    assert all(ganho[name] == getattr(ajustes, f"NE_GANHO_{name}") for name in EXCITATORIOS_NE3)
    assert gasto_das_chaves() == set(EXCITATORIOS_NE3)
    b = BioBrain(seed=7)
    n = sum(b.pool(name)["n"] for name in tipos)
    assert b.izhikevich.n == n and b.neuronios.n == b.Nl - n
    assert np.array_equal(b.W, BioBrain(seed=7, tipos={}).W)   # só o neurônio muda: as sinapses são as mesmas


def test_gasto_e_um_limiar_do_lif_so_nos_excitatorios(ne3):
    b = BioBrain(seed=7)
    izh, Ns = b.izhikevich, b.Ns
    for name in ("QUIET", "INHIB", *EXCITATORIOS_NE3):
        sl = b.pool(name).fatia
        m = (b._locais_izh + Ns >= sl.start) & (b._locais_izh + Ns < sl.stop)
        if name in EXCITATORIOS_NE3:
            esperado = reobase(b.tipos[name]) * getattr(ajustes, f"NE_GANHO_{name}")
            assert np.allclose(izh.gasto[m], esperado), name
        else:
            assert np.all(izh.gasto[m] == 0.0), name


def test_gasto_devolve_a_integracao_lenta_do_lif():
    """
    Entrada constante acima do limiar, um neurônio, τ sináptico = τ_m. Nas membranas lentas (τ_m de 100 e 400 ms),
    sem gasto o RS dispara no ritmo da própria curva f-I, várias vezes o LIF; com gasto, fica a ±30% do LIF até
    2 vezes o limiar. Acima disso a dinâmica rápida do RS limita a taxa (τ_m 100 ms, 3 vezes o limiar: 15 Hz
    contra 23 do LIF, medido).
    """
    for tau in (100.0, 400.0):
        limiar = 1.0 - np.exp(-1.0 / tau)
        for k in (1.2, 1.5, 2.0):
            c, zero = np.array([k * limiar]), np.zeros(1)
            esc = escala_de_corrente("RS", tau)
            lif = Neuronio(np.array([tau]), zero, np.ones(1))
            com = Izhikevich(["RS"], esc, tau, tau, gasto=esc * limiar)
            sem = Izhikevich(["RS"], esc, tau, tau)
            n_lif = n_com = n_sem = 0
            for _ in range(5000):
                n_lif += int(lif.passo(c, zero).sum())
                n_com += int(com.passo(c, zero, zero).sum())
                n_sem += int(sem.passo(c, zero, zero).sum())
            assert n_lif > 0
            assert abs(n_com / n_lif - 1) <= 0.30, (tau, k, n_lif, n_com)
            if tau == 400.0:
                assert n_sem >= 2.5 * n_lif, (tau, k, n_lif, n_sem)


def test_sem_gasto_nada_muda_no_neuronio():
    """gasto = 0 é o Izhikevich do NE-1, bit a bit."""
    rng = np.random.default_rng(2)
    a, b = Izhikevich(["RS", "FS"], 40.0, 60.0, 60.0), Izhikevich(["RS", "FS"], 40.0, 60.0, 60.0, gasto=0.0)
    for _ in range(2000):
        e, i, r = rng.uniform(0, 0.3, 2), -rng.uniform(0, 0.1, 2), 0.01 * rng.standard_normal(2)
        assert np.array_equal(a.passo(e, i, r), b.passo(e, i, r))
    assert np.array_equal(a.v, b.v) and np.array_equal(a.i_ampa, b.i_ampa)


def test_argumentos_explicitos_vencem_a_chave(ne3):
    assert BioBrain(seed=7, tipos={}).izhikevich is None
    b = BioBrain(seed=7, tipos={"GLOOM": "RS"}, tau_sinaptico={"GLOOM": "membrana"})
    assert b.tipos == {"GLOOM": "RS"} and np.all(b.izhikevich.gasto == 0.0)


def test_gasta_corrente_so_vale_para_populacao_em_izhikevich():
    with pytest.raises(ValueError, match="gasta_corrente"):
        BioBrain(seed=7, tipos={"GLOOM": "RS"}, gasta_corrente={"CALM"})


@pytest.mark.parametrize("nome", [f"NE_GANHO_{n}" for n in EXCITATORIOS_NE3])
def test_ganhos_fora_do_limite_sao_recusados(monkeypatch, nome):
    monkeypatch.setattr(ajustes, nome, 0.0)
    with pytest.raises(ValueError, match=nome):
        ajustes.validar()


CONTEXTOS = {
    "PROGRAMMING": {"WORK": 1.0, "TYPING": 0.6},
    "IDLE": {"SILENCE": 0.3, "BOREDOM": 1.0},
    "DISPENSA": {"DISMISS": 1.0, "BOREDOM": 0.5},
    "CARINHO": {"CARESS": 1.0},
    "SUSTO": {"MOTION": 1.0, "IMPACT": 0.5},
}


def _taxas(sentidos, **kwargs):
    """Hz médio por população, sementes 3, 7 e 11, 1,5 s depois de 0,3 s de entrada."""
    total = None
    for semente in (3, 7, 11):
        b = BioBrain(seed=semente, seed_ruido=99, **kwargs)
        b.stimulate(sentidos)
        for _ in range(3):
            b.step(100)
        b.disparos[:] = 0
        for _ in range(15):
            b.step(100)
        taxa = b.disparos / (1.5 * b.pool_sizes)
        total = taxa if total is None else total + taxa
    return {p["name"]: float(total[i] / 3) for i, p in enumerate(b.pools)}


@pytest.mark.parametrize("contexto", sorted(CONTEXTOS))
def test_cada_populacao_responde_como_no_lif(ne3, contexto):
    """
    Calibração: em cada contexto, quem dispara a mais de 3 Hz no LIF fica a ±25% dele em Izhikevich; quem fica
    calado no LIF (< 0,5 Hz) não passa de 1 Hz.
    """
    sentidos = CONTEXTOS[contexto]
    lif, izh = _taxas(sentidos, tipos={}), _taxas(sentidos)
    for nome in EXCITATORIOS_NE3:
        if lif[nome] > 3.0:
            assert abs(izh[nome] / lif[nome] - 1) <= 0.25, (nome, lif[nome], izh[nome])
        elif lif[nome] < 0.5:
            assert izh[nome] <= 1.0, (nome, lif[nome], izh[nome])


def test_ausencia_continua_valendo_com_a_chave(ne3):
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


def test_salvar_e_carregar_com_a_chave(ne3, tmp_path):
    """O estado salvo é o mesmo com e sem a chave (o formato não muda); carregar reproduz a rede."""
    a = BioBrain(seed=7, seed_ruido=4)
    a.stimulate({"DISMISS": 1.0})
    for _ in range(10):
        a.step(100)
    caminho = tmp_path / "bio.json"
    a.save(caminho)
    b = BioBrain(seed=7, seed_ruido=4)
    b.load(caminho)
    assert np.array_equal(a.learned, b.learned)
