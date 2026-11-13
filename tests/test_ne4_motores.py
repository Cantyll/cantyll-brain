"""
NE-4 (plano, onda 2): os 15 motores do BioBrain em Izhikevich, atrás da chave ajustes.NE_MOTORES, desligada por
padrão (R7). Quatorze em RS; o STARTLE em CH (rajadas), porque em RS o reflexo de susto, lido na subida, some.

Com a chave ligada, os motores usam τ sináptico = τ_m do LIF (opção A), os ganhos de ajustes.py e o pulso gasta um
limiar do LIF da corrente (como na NE-3). Os limiares de decisão em Hz não mudam: os critérios são relativos ao LIF
(plano, seção 2, regra 7), nas taxas, no reflexo de susto e no comportamento do MotorDecoder.

Rodar: python -m pytest tests/test_ne4_motores.py -q
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core import nervous_system as ns
from pestinha.core.bio import BioBrain
from pestinha.core.bio.neuronios import reobase
from pestinha.core.bio.rede import EXCITATORIOS_NE3, MOTORES_NE4, TIPO_NE4, gasto_das_chaves, neuronios_das_chaves

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import comparar_izhikevich as ci  # noqa: E402


@pytest.fixture
def ne4(monkeypatch):
    monkeypatch.setattr(ajustes, "NE_INIBIDORES_FS", True)
    monkeypatch.setattr(ajustes, "NE_EXCITATORIOS", True)
    monkeypatch.setattr(ajustes, "NE_MOTORES", True)


def test_chave_desligada_por_padrao():
    assert ajustes.NE_MOTORES is False
    assert all(name not in neuronios_das_chaves()[0] for name in MOTORES_NE4)
    assert not set(MOTORES_NE4) & gasto_das_chaves()


def test_motores_sao_os_da_spec():
    assert MOTORES_NE4 == tuple(m[0] for m in ns.MOTOR_SPEC) and len(MOTORES_NE4) == 15


def test_chave_ligada_poe_14_em_rs_e_o_startle_em_ch(ne4):
    tipos, ganho, tau = neuronios_das_chaves()
    assert {name: tipos[name] for name in MOTORES_NE4} == TIPO_NE4
    assert TIPO_NE4["STARTLE"] == "CH" and {TIPO_NE4[m] for m in MOTORES_NE4 if m != "STARTLE"} == {"RS"}
    assert {tipos[name] for name in EXCITATORIOS_NE3 if name != "ALERT"} == {"RS"} and tipos["ALERT"] == "CH"
    assert tipos["QUIET"] == tipos["INHIB"] == "FS"
    assert set(tau.values()) == {"membrana"}
    assert all(ganho[name] == getattr(ajustes, f"NE_GANHO_{name}") for name in MOTORES_NE4)
    assert set(MOTORES_NE4) <= gasto_das_chaves()
    b = BioBrain(seed=7)
    n = sum(b.pool(name)["n"] for name in tipos)
    assert b.izhikevich.n == n and b.neuronios.n == b.Nl - n
    assert np.array_equal(b.W, BioBrain(seed=7, tipos={}).W)   # só o neurônio muda: as sinapses são as mesmas


def test_motores_sem_as_outras_chaves(monkeypatch):
    """A chave da NE-4 vale sozinha: só os motores saem do LIF."""
    monkeypatch.setattr(ajustes, "NE_MOTORES", True)
    tipos, _, _ = neuronios_das_chaves()
    assert set(tipos) == set(MOTORES_NE4) and gasto_das_chaves() == set(MOTORES_NE4)
    b = BioBrain(seed=7)
    assert b.izhikevich.n == sum(b.pool(name)["n"] for name in MOTORES_NE4)


def test_gasto_dos_motores_e_um_limiar_do_lif(ne4):
    b = BioBrain(seed=7)
    izh, Ns = b.izhikevich, b.Ns
    for name in MOTORES_NE4:
        sl = b.pool(name).fatia
        m = (b._locais_izh + Ns >= sl.start) & (b._locais_izh + Ns < sl.stop)
        assert m.sum() == b.pool(name)["n"]
        esperado = reobase(TIPO_NE4[name]) * getattr(ajustes, f"NE_GANHO_{name}")
        assert np.allclose(izh.gasto[m], esperado), name


@pytest.mark.parametrize("nome", [f"NE_GANHO_{n}" for n in MOTORES_NE4])
def test_ganhos_fora_do_limite_sao_recusados(monkeypatch, nome):
    monkeypatch.setattr(ajustes, nome, 0.0)
    with pytest.raises(ValueError, match=nome):
        ajustes.validar()


CONTEXTOS = {
    "PROGRAMMING": {"WORK": 1.0, "TYPING": 0.6},
    "IDLE": {"SILENCE": 0.3, "BOREDOM": 1.0},
    "DISPENSA": {"DISMISS": 1.0, "BOREDOM": 0.5},
    "CARINHO": {"CARESS": 1.0},
    "PEDIDO": {"PEDIDO": 1.0},
    "PRESO": {"PRESO": 1.0, "DISMISS": 0.5},
    "TOY_TAKEN": {"TOY_TAKEN": 1.0},
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
def test_cada_motor_responde_como_no_lif(ne4, contexto):
    """
    Calibração: em cada contexto, o motor que dispara a mais de 3 Hz no LIF fica a ±25% dele; o que fica calado
    no LIF (< 0,5 Hz) não passa de 1 Hz. O STARTLE fica fora: o critério dele é o reflexo (teste abaixo).
    """
    sentidos = CONTEXTOS[contexto]
    lif, izh = _taxas(sentidos, tipos={}), _taxas(sentidos)
    for nome in MOTORES_NE4:
        if nome == "STARTLE":
            continue
        if lif[nome] > 3.0:
            assert abs(izh[nome] / lif[nome] - 1) <= 0.25, (nome, lif[nome], izh[nome])
        elif lif[nome] < 0.5:
            assert izh[nome] <= 1.0, (nome, lif[nome], izh[nome])


def test_reflexo_de_susto(ne4):
    """
    O susto curto (300 ms de MOTION e IMPACT) passa de Emotion.STARTLE_HZ como no LIF (20 de 20 sementes no LIF;
    medido em --comportamento ne4), e o cutucão longo quase nunca (0 de 20 no LIF).
    """
    k = ci._com_chaves("ne4")
    curto, _ = ci.sustos({"MOTION": 1.0, "IMPACT": 0.5}, 300, sementes=range(1, 11), **k)
    cutucao, _ = ci.sustos({"POKE": 1.0}, 3000, sementes=range(1, 11), **k)
    assert curto >= 9, curto
    assert cutucao <= 3, cutucao


def test_em_rs_o_susto_curto_se_perde(ne4):
    """
    Por que o STARTLE é CH: em RS, com o ganho que iguala a taxa somada (0,653), a troca de janela curta (MOTION 1,0
    por 300 ms) quase não assusta (no LIF assusta em todas as sementes). Vale também com a ALERT já em CH.
    """
    k = ci._com_chaves("ne4")
    lif, _ = ci.sustos({"MOTION": 1.0}, 300, sementes=range(41, 51), tipos={})
    k = {**k, "tipos": {**k["tipos"], "STARTLE": "RS"}, "ganho": {**k["ganho"], "STARTLE": 0.653}}
    curto, _ = ci.sustos({"MOTION": 1.0}, 300, sementes=range(41, 51), **k)
    assert lif == 10 and curto <= 5, (lif, curto)


@pytest.mark.parametrize("contexto", ["PROGRAMMING", "DISPENSA", "CARINHO", "SUSTO", "PEDIDO 1.0", "LEMBRA_FUGA 1.0"])
def test_mesmo_comportamento_do_lif(ne4, contexto):
    """O MotorDecoder escolhe o mesmo comportamento que no LIF em ao menos 90% do tempo (5 sementes, 6 s)."""
    sentidos = dict(ci.CONTEXTOS_NE4)[contexto]
    a = ci.perfil_de_comportamento(sentidos, sementes=range(1, 6), tipos={})
    b = ci.perfil_de_comportamento(sentidos, sementes=range(1, 6), **ci._com_chaves("ne4"))
    principal = max(a, key=a.get)
    assert principal != "-" and a[principal] >= 0.9
    assert b.get(principal, 0.0) >= 0.9, (principal, a, b)


def test_ausencia_continua_valendo_com_a_chave(ne4):
    """FUGIR e TRAVESSURA agora em Izhikevich: a guarda de ausência (R1) continua cortando as duas."""
    sentidos = {"BOREDOM": 1.0, "DISMISS": 1.0, "POKE": 0.5}
    presente, ausente = BioBrain(seed=7, seed_ruido=9), BioBrain(seed=7, seed_ruido=9)
    assert {presente.tipos["FUGIR"], presente.tipos["TRAVESSURA"]} == {"RS"}
    ausente.definir_ausencia(True)
    for b in (presente, ausente):
        b.stimulate(sentidos)
        for _ in range(50):
            b.step(100)
    alvos = [presente._pool_index["FUGIR"], presente._pool_index["TRAVESSURA"]]
    assert presente.disparos[alvos].sum() > 0
    assert ausente.disparos[alvos].sum() < 0.5 * presente.disparos[alvos].sum()


def test_salvar_e_carregar_com_a_chave(ne4, tmp_path):
    """O formato salvo não muda com a chave; carregar reproduz o aprendido (salvo com 6 casas)."""
    a = BioBrain(seed=7, seed_ruido=4)
    a.stimulate({"DISMISS": 1.0})
    for _ in range(10):
        a.step(100)
        a.learn(0.5, 0.0, 0.1)
    caminho = tmp_path / "bio.json"
    a.save(caminho)
    b = BioBrain(seed=7, seed_ruido=4)
    b.load(caminho)
    assert np.abs(a.learned).max() > 0
    assert np.allclose(a.learned, b.learned, atol=1e-6)
