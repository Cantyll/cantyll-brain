"""
BioBrain, NE-1 (plano, onda 2): o neurônio de Izhikevich, os cinco tipos e a corrente sináptica exponencial.

Nenhuma população muda nesta frente: com `tipos` vazio (o padrão) a rede é a do T2, e a paridade com o LIF
continua coberta por test_bio_dinamica.py e test_bio_aprendizado.py. Aqui se testa o que o NE-1 traz:

- os padrões de disparo de cada tipo, com corrente direta, como na fig. 2 de Izhikevich (2003);
- a corrente sináptica (AMPA e GABA) e a escala que liga as unidades do LIF às do modelo;
- uma rede com populações em Izhikevich: mesmas sinapses, determinismo, ausência (R1), salvar e carregar.

Rodar: python -m pytest tests/test_bio_izhikevich.py -q
"""
import math

import numpy as np
import pytest

from pestinha.core.bio import BioBrain
from pestinha.core.bio.neuronios import (PICO, Neuronio, TAU_AMPA, TAU_GABA, TIPOS, Izhikevich, escala_de_corrente,
                                         reobase, repouso)
from pestinha.core.bio.projecoes import compilar, projecao_de_bloco


def _disparos(tipo, corrente, ms=1000):
    """Instantes (ms) dos pulsos de um neurônio do tipo, com corrente direta constante e sem ruído."""
    n = Izhikevich([tipo], 1.0)
    zero = np.zeros(1)
    externa = np.array([float(corrente)])
    return np.array([k for k in range(ms) if n.passo(zero, zero, zero, externa=externa)[0]])


# ---------------- padrões de disparo (Izhikevich 2003, fig. 2; corrente de 10) ----------------

def test_rs_dispara_regular_com_adaptacao():
    isi = np.diff(_disparos("RS", 10))
    assert len(isi) >= 10
    assert isi[0] < 0.7 * isi[-1]                        # o intervalo cresce: adaptação
    assert isi[-5:].max() - isi[-5:].min() <= 2          # depois, regular
    assert (isi > 10).all()                              # sem rajada


def test_fs_dispara_rapido_e_sem_adaptacao():
    fs, rs = _disparos("FS", 10), _disparos("RS", 10)
    assert len(fs) >= 3 * len(rs)                        # bem mais rápido com a mesma corrente
    isi = np.diff(fs)
    assert isi[2:].max() - isi[2:].min() <= 2            # regular desde o terceiro intervalo
    assert (isi[1:] < 15).all()


def test_ib_comeca_com_rajada_e_segue_regular():
    isi = np.diff(_disparos("IB", 10))
    assert (isi[:2] < 10).all()                          # rajada inicial
    assert (isi[3:] > 25).all()                          # depois, pulsos isolados
    assert isi[-5:].max() - isi[-5:].min() <= 2


def test_ch_dispara_em_rajadas_repetidas():
    isi = np.diff(_disparos("CH", 10))
    curtos, longos = (isi < 8).sum(), (isi > 20).sum()
    assert longos >= 5                                   # várias rajadas, não uma só
    assert curtos >= 2 * longos                          # cada rajada tem pelo menos 3 pulsos


def test_lts_tem_limiar_baixo_e_adapta():
    assert len(_disparos("RS", 2.0)) == 0
    assert len(_disparos("LTS", 2.0)) >= 5               # dispara onde o RS fica parado
    isi = np.diff(_disparos("LTS", 10))
    assert isi[0] * 3 <= isi[-1]                         # começa rápido e desacelera


@pytest.mark.parametrize("tipo", sorted(TIPOS))
def test_reobase_separa_parado_de_disparando(tipo):
    """Disparo sustentado (no último segundo de 3) a partir do repouso: 5% abaixo da reobase, nada; 5% acima, sim."""
    r = reobase(tipo)
    assert ((_disparos(tipo, 0.95 * r, ms=3000)) >= 2000).sum() == 0
    assert ((_disparos(tipo, 1.05 * r, ms=3000)) >= 2000).sum() > 0


def test_reobase_e_repouso_analiticos():
    assert reobase("RS") == reobase("IB") == reobase("CH") == pytest.approx(3.7969, abs=1e-3)
    assert reobase("FS") == pytest.approx(3.9375, abs=1e-3)
    assert reobase("LTS") == pytest.approx(0.6844, abs=1e-3)
    assert repouso("RS") == pytest.approx(-70.0) and repouso("LTS") == pytest.approx(-64.41, abs=0.01)


@pytest.mark.parametrize("tipo", sorted(TIPOS))
def test_parte_do_repouso_sem_pulso(tipo):
    n = Izhikevich([tipo], 1.0)
    zero = np.zeros(1)
    assert not any(n.passo(zero, zero, zero)[0] for _ in range(2000))
    assert n.v[0] == pytest.approx(repouso(tipo), abs=1e-6)


def test_um_pulso_por_ms_no_maximo_e_tensao_finita():
    n = Izhikevich(["FS"] * 3, 1.0)
    zero = np.zeros(3)
    for _ in range(200):
        disparou = n.passo(zero, zero, zero, externa=np.array([1e3, 1e4, 1e5]))
        assert disparou.dtype == bool and disparou.shape == (3,)
        assert np.isfinite(n.v).all() and np.isfinite(n.u).all() and (n.v < PICO).all()


def test_tipo_desconhecido_e_recusado():
    with pytest.raises(ValueError):
        Izhikevich(["RS", "XX"], 1.0)


# ---------------- corrente sináptica ----------------

@pytest.mark.parametrize("sinal,tau", [(+1, TAU_AMPA), (-1, TAU_GABA)])
def test_corrente_exponencial_decai_com_tau(sinal, tau):
    n = Izhikevich(["RS"], 2.0)
    um, zero = np.ones(1), np.zeros(1)
    n.passo(um * (sinal > 0), -um * (sinal < 0), zero)
    corrente = n.i_ampa if sinal > 0 else n.i_gaba
    inicio = float(corrente[0])
    assert inicio == pytest.approx(sinal * 2.0 * (1 - math.exp(-1 / tau)))
    for _ in range(int(tau)):
        n.passo(zero, zero, zero)
    assert float(corrente[0]) == pytest.approx(inicio * math.exp(-1.0), rel=1e-9)


def test_entrada_constante_vira_corrente_media_igual_a_do_lif():
    """Entrada c por ms (unidades do LIF) leva a corrente a c × escala: a média é a do LIF."""
    n = Izhikevich(["RS"], 3.0)
    c, zero = np.array([0.4]), np.zeros(1)
    for _ in range(300):
        n.passo(c, -c / 2, zero)
    assert n.i_ampa[0] == pytest.approx(0.4 * 3.0)
    assert n.i_gaba[0] == pytest.approx(-0.2 * 3.0)


def test_escala_iguala_a_entrada_minima_de_disparo_do_lif():
    """No LIF, entrada constante (1 − e^(−1/τ_m)) por ms leva ao limiar; aqui, a mesma entrada vira a reobase."""
    for tipo in TIPOS:
        for tau_m in (10.0, 20.0, 400.0):
            limiar_lif = 1.0 - math.exp(-1.0 / tau_m)
            assert limiar_lif * escala_de_corrente(tipo, tau_m) == pytest.approx(reobase(tipo))


def test_com_tau_da_membrana_a_corrente_e_a_tensao_do_lif():
    """
    Com τ sináptico = τ_m e a escala de escala_de_corrente, I / reobase segue a tensão do LIF passo a passo
    (abaixo do limiar, onde o LIF não reinicia), com a mesma entrada excitatória, inibitória e ruído.
    """
    rng = np.random.default_rng(5)
    tau_m = np.array([10.0, 60.0, 400.0])
    lif = Neuronio(tau_m, np.zeros(3), np.ones(3))
    tipos = ["RS", "CH", "LTS"]
    izh = Izhikevich(tipos, [escala_de_corrente(t, m) for t, m in zip(tipos, tau_m)], tau_m, tau_m)
    reo = np.array([reobase(t) for t in tipos])
    limiar = 1.0 - np.exp(-1.0 / tau_m)                # entrada constante que leva o LIF ao limiar
    for _ in range(3000):
        exc = rng.uniform(0, 1.2, 3) * limiar            # média de 0,5 do limiar, sem chegar a ele
        inh = -rng.uniform(0, 0.2, 3) * limiar
        ruido = 0.002 * rng.standard_normal(3)
        assert not lif.passo(exc + inh, ruido).any()
        izh.passo(exc, inh, ruido)
        assert np.allclose((izh.i_ampa + izh.i_gaba) / reo, lif.v, rtol=1e-9, atol=1e-12)
    assert lif.v.min() > 0.2                             # a conta não foi feita só perto de zero


def test_propagar_por_sinal_soma_igual_a_propagar():
    rng = np.random.default_rng(3)
    bloco = rng.normal(0, 0.1, (30, 20)) * (rng.random((30, 20)) < 0.4)
    tabela = compilar([projecao_de_bloco("a", "b", 0, 30, bloco)], 30, 20, 30)
    atividade = rng.random(30)
    disparou = np.flatnonzero(rng.random(30) < 0.5)
    exc, inh = tabela.propagar_por_sinal(atividade, disparou)
    assert (exc >= 0).all() and (inh <= 0).all()
    assert np.allclose(exc + inh, tabela.propagar(atividade, disparou))
    vazio = np.empty(0, dtype=np.int64)
    assert all((x == 0).all() for x in tabela.propagar_por_sinal(atividade, vazio))


# ---------------- a rede com populações em Izhikevich ----------------

TIPOS_TESTE = {"QUIET": "FS", "INHIB": "FS", "ALERT": "RS", "STARTLE": "RS", "FUGIR": "RS", "TRAVESSURA": "CH"}


def _rodar(brain, segundos, sentidos):
    brain.stimulate(sentidos)
    for _ in range(segundos * 10):
        brain.step(100)


def test_padrao_e_nenhuma_populacao_em_izhikevich():
    b = BioBrain(seed=7)
    assert b.tipos == {} and b.izhikevich is None and b.neuronios.n == b.Nl


def test_mesmas_sinapses_e_populacoes_com_qualquer_tipo():
    """Trocar o neurônio não sorteia nada: sinapses, populações e posições saem iguais."""
    padrao, misto = BioBrain(seed=7), BioBrain(seed=7, tipos=TIPOS_TESTE)
    assert misto.pools == padrao.pools
    assert np.array_equal(misto.W, padrao.W)
    assert np.array_equal(misto.pos, padrao.pos)
    n_izh = sum(misto.pool(name)["n"] for name in TIPOS_TESTE)
    assert misto.izhikevich.n == n_izh and misto.neuronios.n == misto.Nl - n_izh
    assert sorted(set(misto.izhikevich.tipos)) == ["CH", "FS", "RS"]


def test_rede_mista_e_deterministica_e_ativa():
    a = BioBrain(seed=7, seed_ruido=4, tipos=TIPOS_TESTE)
    b = BioBrain(seed=7, seed_ruido=4, tipos=TIPOS_TESTE)
    for sentidos in ({"WORK": 1.0, "TYPING": 0.6}, {"POKE": 1.0, "DRAG": 1.0}, {"PLAY": 1.0}):
        _rodar(a, 2, sentidos)
        _rodar(b, 2, sentidos)
    assert np.array_equal(a.disparos, b.disparos)
    assert a.pool_rates() == b.pool_rates()
    assert all(math.isfinite(x) for x in a.pool_rates().values())
    assert a.disparos[[a._pool_index[n] for n in TIPOS_TESTE]].sum() > 0     # as populações novas disparam


def test_ganho_escala_a_corrente_da_populacao():
    um = BioBrain(seed=7, tipos={"QUIET": "FS"})
    dobro = BioBrain(seed=7, tipos={"QUIET": "FS"}, ganho={"QUIET": 2.0})
    assert np.allclose(dobro.izhikevich.escala, 2.0 * um.izhikevich.escala)


def test_tau_sinaptico_por_populacao():
    b = BioBrain(seed=7, tipos={"QUIET": "FS", "GLOOM": "RS", "INHIB": "FS"},
                 tau_sinaptico={"QUIET": 8.0, "GLOOM": "membrana"})
    izh, Ns = b.izhikevich, b.Ns
    quiet, gloom, inhib = (np.isin(b._locais_izh + Ns, np.arange(b.N)[b.pool(n).fatia])
                           for n in ("QUIET", "GLOOM", "INHIB"))
    assert (izh.tau_ampa[quiet] == 8.0).all() and (izh.tau_gaba[quiet] == 8.0).all()
    assert (izh.tau_ampa[inhib] == TAU_AMPA).all() and (izh.tau_gaba[inhib] == TAU_GABA).all()
    assert 360.0 <= izh.tau_ampa[gloom].min() and izh.tau_ampa[gloom].max() <= 440.0   # τ_m de 400 ms ± 10%


@pytest.mark.parametrize("kwargs", [
    {"tipos": {"WORK": "RS"}},                                   # sensorial não tem neurônio para trocar
    {"tipos": {"NAO_EXISTE": "RS"}},
    {"tipos": {"QUIET": "XX"}},
    {"tipos": {"QUIET": "FS"}, "ganho": {"INHIB": 2.0}},         # só para população em Izhikevich
    {"tipos": {"QUIET": "FS"}, "tau_sinaptico": {"INHIB": 5.0}},
    {"tipos": {"QUIET": "FS"}, "tau_sinaptico": {"QUIET": 0.0}},
    {"tipos": {"QUIET": "FS"}, "tau_sinaptico": {"QUIET": "lento"}},
])
def test_configuracao_invalida_e_recusada(kwargs):
    with pytest.raises(ValueError):
        BioBrain(seed=7, **kwargs)


def test_ausencia_inibe_fugir_e_travessura_em_izhikevich():
    """R1 vale para a população que migrou: a corrente de ausência entra na escala do modelo."""
    tipos = {"FUGIR": "RS", "TRAVESSURA": "RS"}
    sentidos = {"BOREDOM": 1.0, "DISMISS": 1.0, "POKE": 0.5}
    presente = BioBrain(seed=7, seed_ruido=9, tipos=tipos)
    ausente = BioBrain(seed=7, seed_ruido=9, tipos=tipos)
    ausente.definir_ausencia(True)
    _rodar(presente, 5, sentidos)
    _rodar(ausente, 5, sentidos)
    alvos = [presente._pool_index["FUGIR"], presente._pool_index["TRAVESSURA"]]
    assert presente.disparos[alvos].sum() > 0
    assert ausente.disparos[alvos].sum() < 0.5 * presente.disparos[alvos].sum()


def test_salvar_e_carregar_com_populacoes_em_izhikevich(tmp_path):
    a = BioBrain(seed=7, seed_ruido=1, tipos=TIPOS_TESTE)
    _rodar(a, 1, {"WORK": 1.0})
    for _ in range(20):
        a.learn(1.0, 0.0, 0.1)
    caminho = tmp_path / "bio.json"
    a.save(caminho)
    b = BioBrain(seed=7, tipos=TIPOS_TESTE)
    assert b.load(caminho)
    assert np.allclose(b.learned, a.learned, atol=1e-6)
