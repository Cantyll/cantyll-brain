"""
Piso por taxa-alvo, SHY repartido pelo sono cumprido e a simulação de noites (B2 do plano; spec,
seções 7.3 e 9.4). A simulação de 30 noites é critério de aceitação de toda mudança em dinâmica de
neurônio, plasticidade, replay ou homeostase.

Os testes de aceitação usam réguas relativas: a fração HOMEOSTASE_PISO de ajustes.py e a comparação
com a mesma simulação sem piso. Os números absolutos da seção 10 da spec são decisão pendente.

Rodar: python -m pytest tests/test_simulacao_noites.py -q
Só os rápidos: python -m pytest tests/test_simulacao_noites.py -q -k "not trinta_noites"
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core import nervous_system as ns
from pestinha.core.homeostase_sinaptica import HomeostaseDoSono, escalonamento_piso, escolher_padroes
from pestinha.core.nervous_system import Brain, LIFBrain

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import simular_noites  # noqa: E402

NOITE = ajustes.LIMIAR_DORME_PRESSAO - ajustes.LIMIAR_ACORDA_PRESSAO
PADROES = [{"PLAY": 1.0, "BOREDOM": 0.3}, {"SOUND": 1.0, "BOREDOM": 0.6}, {"SILENCE": 0.3, "BOREDOM": 1.0}]


class _RedeFalsa:
    """Rede que só anota o que a homeostase do sono pede. `respostas`: o que cada ensaio devolve, em ordem."""

    def __init__(self, respostas=()):
        self.restou = 1.0                   # fração das sinapses que sobrou depois dos downscalings
        self.respostas = list(respostas)
        self.ensaios = 0
        self.escalonamentos = []

    def downscaling_sono(self, fracao):
        self.restou *= 1.0 - fracao

    def ensaio_piso(self, padroes, orcamento_ms):
        self.ensaios += 1
        return 10, (self.respostas.pop(0) if self.respostas else {})      # sem resposta combinada: nenhuma população a medir

    def escalonar_piso(self, razoes, piso, passo):
        self.escalonamentos.append((dict(razoes), piso, passo))


def _dorme(homeostase, rede, de, ate, quadros=200, replay_pendente=False, padroes=PADROES):
    """Um sono: a pressão cai de `de` até `ate` em `quadros` chamadas, e ele acorda."""
    homeostase.adormecer(de, padroes)
    for k in range(1, quadros + 1):
        homeostase.passo(rede, de + (ate - de) * k / quadros, 100, replay_pendente=replay_pendente)
    homeostase.acordar()


def _noites_desfeitas(rede):
    """Quantas noites inteiras de SHY a rede falsa recebeu."""
    return math.log(rede.restou) / math.log(1.0 - ajustes.HOMEOSTASE_SHY)


# ---------------- SHY pelo sono cumprido ----------------

def test_noite_inteira_desfaz_o_shy_de_uma_noite():
    rede, sono = _RedeFalsa(), HomeostaseDoSono()
    _dorme(sono, rede, ajustes.LIMIAR_DORME_PRESSAO, ajustes.LIMIAR_ACORDA_PRESSAO)
    parcela = 1.0 / ajustes.HOMEOSTASE_AJUSTES_NOITE
    assert abs(_noites_desfeitas(rede) - 1.0) <= parcela + 1e-9      # a sobra de menos de uma parcela fica para o próximo sono


def test_cochilo_desfaz_so_a_parte_dele_e_cochilos_somam_uma_noite():
    rede, sono = _RedeFalsa(), HomeostaseDoSono()
    _dorme(sono, rede, 0.6, 0.6 - NOITE / 5)                         # um quinto de noite
    um_cochilo = _noites_desfeitas(rede)
    assert 0.05 < um_cochilo < 0.35
    for _ in range(4):
        _dorme(sono, rede, 0.6, 0.6 - NOITE / 5)
    assert abs(_noites_desfeitas(rede) - 1.0) <= 1.0 / ajustes.HOMEOSTASE_AJUSTES_NOITE + 1e-9


def test_adormecer_e_acordar_sem_dormir_nao_desfaz_nada():
    rede, sono = _RedeFalsa(), HomeostaseDoSono()
    for _ in range(20):                                             # acordado com carinho vinte vezes na mesma noite
        _dorme(sono, rede, 0.8, 0.8, quadros=5)
    assert rede.restou == 1.0


def test_pressao_que_sobe_dormindo_nao_conta_como_sono():
    rede, sono = _RedeFalsa(), HomeostaseDoSono()
    _dorme(sono, rede, 0.5, 0.9)
    assert rede.restou == 1.0


# ---------------- piso: quando ensaia e quando escala ----------------

def test_piso_espera_o_replay_acabar_e_para_quando_esta_em_dia():
    abaixo, acima = {"PLAYFUL": 0.2, "CALM": 0.9}, {"PLAYFUL": 0.7, "CALM": 0.9}
    rede, sono = _RedeFalsa([abaixo, abaixo, acima]), HomeostaseDoSono()
    sono.adormecer(0.8, PADROES)
    for k in range(1, 6):                                           # replay em curso: o sono anda, o ensaio espera
        sono.passo(rede, 0.8 - 0.3 * NOITE * k / 5, 100, replay_pendente=True)
    assert rede.ensaios == 0 and rede.restou < 1.0
    for k in range(1, 201):
        sono.passo(rede, 0.8 - 0.3 * NOITE - 0.7 * NOITE * k / 200, 100)
    assert rede.ensaios == 3                                        # dois abaixo do piso, um acima; depois, nenhum
    assert len(rede.escalonamentos) == 2 == sono.ajustes_piso
    assert rede.escalonamentos[0] == (abaixo, ajustes.HOMEOSTASE_PISO, ajustes.HOMEOSTASE_PISO_PASSO)
    assert sono.piso_em_dia and sono.razoes == acima


def test_ensaio_inacabado_segue_no_quadro_seguinte():
    rede, sono = _RedeFalsa([None, None, {"PLAYFUL": 0.9}]), HomeostaseDoSono()
    sono.adormecer(0.8, PADROES)
    sono.passo(rede, 0.8 - NOITE / 5, 100)
    sono.passo(rede, 0.8 - NOITE / 5, 100)
    assert not sono.piso_em_dia
    sono.passo(rede, 0.8 - NOITE / 5, 100)
    assert sono.piso_em_dia and rede.ensaios == 3 and rede.escalonamentos == []


def test_piso_desligado_ou_sem_padroes_nao_ensaia(monkeypatch):
    rede, sono = _RedeFalsa(), HomeostaseDoSono()
    _dorme(sono, rede, 0.8, 0.3, padroes=[])                        # pet novo: nenhum episódio para ensaiar
    assert rede.ensaios == 0
    monkeypatch.setattr(ajustes, "HOMEOSTASE_PISO", 0.0)            # aceitar o colapso: o SHY segue, o piso não
    _dorme(sono, rede, 0.8, 0.3)
    assert rede.ensaios == 0 and rede.restou < 1.0


def test_escolher_padroes_espalha_pela_lista():
    assert escolher_padroes([1, 2, 3], 10) == [1, 2, 3]
    assert escolher_padroes(list(range(50)), 10) == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]


# ---------------- piso: a conta do escalonamento ----------------

def test_escalonamento_so_mexe_na_populacao_abaixo_do_piso():
    aprendido = np.array([[-0.02, -0.02], [0.01, 0.01], [0.0, 0.0], [-0.03, -0.03]])
    base = np.array([[0.10, 0.10], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    out = escalonamento_piso(aprendido, base, [0.3, 0.9], piso=0.5, passo=0.05, limite_max=0.08, limite_min=-0.05)
    assert np.array_equal(out[:, 1], aprendido[:, 1])               # acima do piso: intocada
    assert np.isclose(out[0, 0], -0.02 + 0.05 * 0.08)               # excitatória (inato + aprendido > 0): cresce 5%
    assert np.isclose(out[1, 0], 0.01 * 1.05)                       # excitatória aprendida: cresce 5%
    assert out[2, 0] == 0.0                                         # onde não há sinapse, nada é criado
    assert np.isclose(out[3, 0], -0.03 * 0.95)                      # inibitória: encolhe 5%


def test_escalonamento_respeita_os_limites_e_recusa_parametro_invalido():
    out = escalonamento_piso(np.array([[0.079]]), np.array([[0.5]]), [0.0], 0.5, 0.05, 0.08, -0.05)
    assert out[0, 0] == 0.08
    with pytest.raises(ValueError):
        escalonamento_piso(np.zeros((1, 1)), np.zeros((1, 1)), [0.0], 0.0, 0.05, 0.08, -0.05)
    with pytest.raises(ValueError):
        escalonamento_piso(np.zeros((1, 1)), np.zeros((1, 1)), [0.0], 0.5, 1.5, 0.08, -0.05)


# ---------------- piso: o ensaio no LIFBrain ----------------

def _ensaia(brain, orcamento=10 ** 6):
    while True:
        _, razoes = brain.ensaio_piso(PADROES, orcamento)
        if razoes is not None:
            return razoes


def test_interface_brain_tem_taxas_e_o_piso_sem_efeito_por_padrao():
    class _Minimo(Brain):
        def stimulate(self, intensities): pass
        def step(self, dt_ms): pass
        def motor_activity(self): return {}
        def snapshot(self): return {}
        def learn(self, reward, expected, dt, rate=0.0, teto=None): pass
        def estado(self): return {}

    minimo = _Minimo()
    assert minimo.taxas() == {} and minimo.ensaio_piso(PADROES, 100) == (0, {})
    minimo.escalonar_piso({"PLAYFUL": 0.1}, 0.5, 0.05)              # cérebro sem plasticidade: não faz nada, não quebra
    brain = LIFBrain(seed=7, seed_ruido=42)
    assert set(brain.taxas()) == {p["name"] for p in brain.pools}


def test_ensaio_sem_nada_aprendido_da_um_e_nao_toca_a_rede_acordada():
    brain = LIFBrain(seed=7, seed_ruido=42)
    brain.stimulate({"WORK": 0.8, "TYPING": 0.3})
    brain.step(300)
    antes = (brain.v.copy(), brain.p.copy(), brain.learned.copy(), brain.time_ms, brain.rng.bit_generator.state)
    razoes = _ensaia(brain)
    assert razoes and all(razao == 1.0 for razao in razoes.values())
    assert "PLAYFUL" in razoes                                      # recém-nascida, ela responde a esses padrões
    assert np.array_equal(brain.v, antes[0]) and np.array_equal(brain.p, antes[1])
    assert np.array_equal(brain.learned, antes[2]) and brain.time_ms == antes[3]
    assert brain.rng.bit_generator.state == antes[4]


def test_ensaio_cai_com_inibicao_aprendida_e_o_escalonamento_recupera():
    brain = LIFBrain(seed=7, seed_ruido=42)
    j = brain.plastic_posts.index("PLAYFUL")
    brain.learned[:, j] = ns.LEARN_MIN                               # tudo o que chega à PLAYFUL virou inibição
    brain._apply_learning()
    caiu = _ensaia(brain)["PLAYFUL"]
    assert caiu < 0.5
    outras = brain.learned[:, [k for k in range(len(brain.plastic_posts)) if k != j]].copy()
    razao = caiu
    for _ in range(40):
        if razao >= 0.5:
            break
        brain.escalonar_piso({"PLAYFUL": razao}, 0.5, 0.05)
        razao = _ensaia(brain)["PLAYFUL"]
    assert razao >= 0.5 > caiu
    assert np.array_equal(brain.learned[:, [k for k in range(len(brain.plastic_posts)) if k != j]], outras)


def test_ensaio_nao_depende_do_orcamento_por_quadro():
    a, b = LIFBrain(seed=7, seed_ruido=1), LIFBrain(seed=7, seed_ruido=2)
    for brain in (a, b):
        brain.learned[:, 0] = -0.02
        brain.learned[:, 1] = 0.01
        brain._apply_learning()
    assert _ensaia(a, orcamento=37) == _ensaia(b)                    # outro ruído na rede acordada, outro orçamento: mesma medida


# ---------------- a ferramenta ----------------

def test_replay_sem_pulsos_da_as_mesmas_sinapses_que_o_replay_do_app():
    rapido = simular_noites.simular("misto", noites=2, semente=3, dias=(2,))
    com_pulsos = simular_noites.simular("misto", noites=2, semente=3, dias=(2,), pulsos=True)
    assert rapido[-1]["aprendido"] == com_pulsos[-1]["aprendido"]
    assert np.abs(np.array(rapido[-1]["aprendido"])).max() > 0       # a simulação ensinou alguma coisa


def test_simular_devolve_os_ajustes_ao_que_eram():
    antes = ajustes.HOMEOSTASE_PISO
    simular_noites.simular("duro", noites=1, semente=3, piso=0.0, dias=())
    assert ajustes.HOMEOSTASE_PISO == antes


# ---------------- aceitação: 30 noites ----------------

DIAS = (0, 10, 20, 30)


@pytest.fixture(scope="module")
def trinta_noites_com_piso():
    return simular_noites.simular("duro", noites=30, semente=7, dias=DIAS)


@pytest.fixture(scope="module")
def trinta_noites_sem_piso():
    return simular_noites.simular("duro", noites=30, semente=7, piso=0.0, dias=DIAS)


def _media_relativa(linhas, populacao):
    """Média, dos dias 10 a 30, da taxa no uso dividida pela do dia 0."""
    return float(np.mean([linha["uso_relativo"][populacao] for linha in linhas if linha["dia"] >= 10]))


def test_trinta_noites_com_piso_nenhuma_populacao_fica_abaixo_do_piso(trinta_noites_com_piso):
    """Só dispensas, nenhum carinho: PLAYFUL e CALM seguem acima da fração HOMEOSTASE_PISO do dia 0."""
    assert [linha["dia"] for linha in trinta_noites_com_piso] == list(DIAS)
    assert _media_relativa(trinta_noites_com_piso, "PLAYFUL") >= ajustes.HOMEOSTASE_PISO
    assert _media_relativa(trinta_noites_com_piso, "CALM") >= ajustes.HOMEOSTASE_PISO
    assert trinta_noites_com_piso[-1]["ajustes_piso"] > 0            # o piso agiu


def test_trinta_noites_sem_piso_a_calma_cai_abaixo_e_o_piso_faz_diferenca(trinta_noites_com_piso, trinta_noites_sem_piso):
    """O controle: sem piso, a CALM fica abaixo da fração que o piso garante. É o que o piso muda."""
    assert trinta_noites_sem_piso[-1]["ajustes_piso"] == 0
    assert _media_relativa(trinta_noites_sem_piso, "CALM") < ajustes.HOMEOSTASE_PISO
    assert _media_relativa(trinta_noites_com_piso, "CALM") > 1.5 * _media_relativa(trinta_noites_sem_piso, "CALM")


def test_trinta_noites_tristeza_fica_abaixo_do_limite(trinta_noites_com_piso, trinta_noites_sem_piso):
    """A maior sinapse aprendida da GLOOM não chega ao limite LEARN_MAX, com ou sem piso, e o piso não a aumenta."""
    for linhas in (trinta_noites_com_piso, trinta_noites_sem_piso):
        assert max(linha["peso_gloom_max"] for linha in linhas) < 1.0
    assert trinta_noites_com_piso[-1]["peso_gloom_max"] <= trinta_noites_sem_piso[-1]["peso_gloom_max"] * 1.2
