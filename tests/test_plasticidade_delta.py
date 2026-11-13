"""
PL-1, parte 1: plasticidade do BioBrain com δ = r − V (crítico de core/conditioning.py) e ACh na taxa.

Os fenômenos da spec, seção 10: aprendizado por erro de predição, bloqueio, extinção, surpresa e a guarda
"sem reforço bruto" (PEDIDO não cresce). A habituação já é dos receptores e tem teste próprio
(test_bio_dinamica.py); aqui só se confere que a plasticidade nova não mexe nela.

Sem Qt: só o BioBrain. Os testes não passam pulsos pela rede, porque o aprendizado depende dos níveis
sensoriais, da elegibilidade e de δ. A ACh e a média dela ficam fixas em 0,5 (fator 1) onde o teste não é sobre ela.
"""
import numpy as np
import pytest

from pestinha import ajustes
from pestinha.core.bio import BioBrain
from pestinha.core.conditioning import Critico

TAXA = 0.004
PASSO = 0.1


@pytest.fixture
def pl1(monkeypatch):
    monkeypatch.setattr(ajustes, "PL_DELTA", True)


@pytest.fixture
def ach_ligada(monkeypatch):
    monkeypatch.setattr(ajustes, "PL_ACH", True)


def _cerebro(ach=0.5):
    brain = BioBrain(seed=7, seed_ruido=1)
    if brain.plasticidade is not None:
        brain.plasticidade.neuromod.ach_fixa = ach
        brain.plasticidade.neuromod.ach_media_fixa = 0.5     # fator = (0,5 + ACh) / 1
    return brain


def _segundos(brain, niveis, recompensa, segundos, taxa=TAXA):
    """Fica `segundos` com os níveis e a recompensa dados. Devolve os δ de cada passo."""
    deltas = []
    for _ in range(int(round(segundos / PASSO))):
        brain.stimulate(niveis)
        brain.learn(recompensa, 0.0, PASSO, taxa)
        if brain.plasticidade is not None:
            deltas.append(brain.plasticidade.ultimo_delta)
    return deltas


def _tentativa(brain, pistas, recompensa=1.0, contexto=None):
    """
    Uma tentativa: a pista por 2 s, depois a recompensa por 1 s (a pista já saiu), e 8 s sem nada (a
    elegibilidade volta perto de zero). `contexto` fica ligado o tempo todo. Devolve a soma de δ desde que a
    pista sai até o fim da recompensa: é o quanto da recompensa ainda era surpresa.
    """
    contexto = dict(contexto or {})
    _segundos(brain, dict(contexto, **pistas), 0.0, 2.0)
    na_recompensa = _segundos(brain, contexto, recompensa, 1.0)
    _segundos(brain, contexto, 0.0, 8.0)
    return float(np.sum(na_recompensa))


def _peso(brain, canal, post="PLAYFUL"):
    return float(brain.learned[brain.sensory_names.index(canal), brain.plastic_posts.index(post)])


# ---------------- desligado: igual ao LIF ----------------

def test_desligado_por_padrao_e_aprende_como_antes():
    """R7: sem a chave, nada muda. A mesma sequência dá o mesmo aprendizado de antes (recompensa bruta)."""
    assert ajustes.PL_DELTA is False
    brain = _cerebro()
    assert brain.plasticidade is None
    for _ in range(5):
        _tentativa(brain, {"PEDIDO": 1.0})
    # recompensa bruta: cada tentativa soma; o PEDIDO puxa para PLAYFUL
    assert _peso(brain, "PEDIDO") > 0
    assert "plasticidade" not in brain.estado()


# ---------------- crítico sozinho ----------------

def test_critico_passo_longo_nao_diverge():
    """Uma hora de uma vez, sem recompensa (a simulação faz isso): V cai, sem trocar de sinal nem explodir."""
    critico = Critico(3, taxa=0.5, limite=5.0, tau_v=30.0)
    x = np.array([1.0, 0.0, 0.5])
    critico.w[:] = [1.0, 0.0, 1.0]
    antes = critico.valor(x)
    critico.passo(x, x, 0.0, 0.1)
    for _ in range(5):
        critico.passo(x, x, 0.0, 3600.0)
    assert 0.0 <= critico.valor(x) < antes
    assert np.all(np.abs(critico.w) <= 5.0)


def test_critico_carregar_recusa_lixo():
    critico = Critico(2, 1.0, 5.0, 10.0)
    critico.w[:] = [0.3, -0.1]
    for ruim in (None, [1.0], [1.0, float("nan")], [True, 0.0], "x"):
        assert critico.carregar(ruim) is False
    assert critico.w.tolist() == [0.3, -0.1]


# ---------------- fenômenos da spec, seção 10 ----------------

def test_aprendizado_por_erro_de_predicao(pl1):
    """Pista seguida de recompensa, 20 vezes: δ na recompensa cai para menos de 20% do inicial."""
    brain = _cerebro()
    deltas = [_tentativa(brain, {"PEDIDO": 1.0}) for _ in range(20)]
    assert deltas[0] > 0.5
    assert deltas[-1] < 0.2 * deltas[0]


def test_bloqueio_de_kamin(pl1):
    """Treina A→R; depois AB→R. B aprende menos de 20% do que A aprende sozinho."""
    a, b = "PEDIDO", "ANTICIPATE"
    sozinho = _cerebro()
    for _ in range(20):
        _tentativa(sozinho, {a: 1.0})
    aprendido_a = _peso(sozinho, a)

    bloqueado = _cerebro()
    for _ in range(20):
        _tentativa(bloqueado, {a: 1.0})
    antes = _peso(bloqueado, b)
    for _ in range(20):
        _tentativa(bloqueado, {a: 1.0, b: 1.0})
    aprendido_b = _peso(bloqueado, b) - antes
    assert aprendido_a > 0
    assert aprendido_b < 0.2 * aprendido_a


def test_extincao(pl1):
    """Depois de aprender, 30 tentativas sem recompensa: a resposta (o peso aprendido da pista) cai 70% ou mais."""
    brain = _cerebro()
    for _ in range(20):
        _tentativa(brain, {"PEDIDO": 1.0})
    aprendido = _peso(brain, "PEDIDO")
    for _ in range(30):
        _tentativa(brain, {"PEDIDO": 1.0}, recompensa=0.0)
    assert _peso(brain, "PEDIDO") <= 0.3 * aprendido


def test_surpresa(pl1):
    """A mesma recompensa muda as sinapses pelo menos 2 vezes mais quando é inesperada."""
    esperada = _cerebro()
    for _ in range(20):
        _tentativa(esperada, {"PEDIDO": 1.0})
    inesperada = _cerebro()
    for cerebro in (esperada, inesperada):
        cerebro._antes = cerebro.learned.copy()
        _tentativa(cerebro, {"PEDIDO": 1.0})
    mudou = {nome: float(np.abs(c.learned - c._antes).sum()) for nome, c in
             (("esperada", esperada), ("inesperada", inesperada))}
    assert mudou["inesperada"] >= 2.0 * mudou["esperada"]


def test_guarda_sem_reforco_bruto(pl1):
    """
    R2: com a recompensa toda prevista (δ = 0), o PEDIDO não cresce. Depois que o carinho depois do pedido virou
    rotina, mais 20 rotinas não aumentam o peso do PEDIDO; na regra antiga, ele seguiria subindo.
    """
    brain = _cerebro()
    for _ in range(40):
        _tentativa(brain, {"PEDIDO": 1.0})
    estavel = _peso(brain, "PEDIDO")
    for _ in range(20):
        _tentativa(brain, {"PEDIDO": 1.0})
    assert _peso(brain, "PEDIDO") <= estavel * 1.02

    ajustes.PL_DELTA = False
    try:
        antigo = BioBrain(seed=7, seed_ruido=1)
    finally:
        ajustes.PL_DELTA = True
    for _ in range(40):
        _tentativa(antigo, {"PEDIDO": 1.0})
    meio = _peso(antigo, "PEDIDO")
    for _ in range(20):
        _tentativa(antigo, {"PEDIDO": 1.0})
    assert _peso(antigo, "PEDIDO") > meio * 1.2


def test_recompensa_sem_pista_ensina_o_contexto(pl1):
    """O crítico só lê as pistas: carinho sem pista nenhuma ensina o contexto como antes (e não some com a repetição)."""
    brain = _cerebro()
    for _ in range(20):
        _tentativa(brain, {}, contexto={"WORK": 1.0})
    ajustes.PL_DELTA = False
    try:
        antigo = BioBrain(seed=7, seed_ruido=1)
    finally:
        ajustes.PL_DELTA = True
    for _ in range(20):
        _tentativa(antigo, {}, contexto={"WORK": 1.0})
    assert _peso(brain, "WORK") > 0
    assert _peso(brain, "WORK") == pytest.approx(_peso(antigo, "WORK"), rel=1e-9)


def test_habituacao_nao_muda(pl1):
    """A habituação é dos receptores: a plasticidade nova não mexe nela."""
    ligado, desligado = _cerebro(), None
    ajustes.PL_DELTA = False
    try:
        desligado = BioBrain(seed=7, seed_ruido=1)
    finally:
        ajustes.PL_DELTA = True
    for cerebro in (ligado, desligado):
        cerebro.stimulate({"POKE": 1.0})
        cerebro.step(500)
    assert ligado.efficacy() == desligado.efficacy()


# ---------------- ACh ----------------

def test_ach_muda_a_taxa(pl1, ach_ligada):
    """η_eff = η · (0,5 + ACh): com ACh 1 o mesmo evento ensina 3 vezes o que ensina com ACh 0."""
    pesos = {}
    for ach in (0.0, 1.0):
        brain = _cerebro(ach=ach)
        _tentativa(brain, {}, contexto={"WORK": 1.0})
        pesos[ach] = _peso(brain, "WORK")
    assert pesos[1.0] == pytest.approx(3.0 * pesos[0.0], rel=1e-9)


def test_ach_desligada_por_padrao_nao_muda_a_taxa(pl1):
    """PL_ACH desligada (padrão): a ACh é medida, mas o fator é 1, com ACh 0 ou 1."""
    assert ajustes.PL_ACH is False
    for ach in (0.0, 1.0):
        assert _cerebro(ach=ach).plasticidade.neuromod.fator_aprendizado() == 1.0


def test_ach_segue_o_focus(pl1):
    """Sem ACh fixa, ela sobe com o FOCUS disparando e cai com ele parado (τ = PL_ACH_TAU_S)."""
    brain = BioBrain(seed=7, seed_ruido=1)
    neuromod = brain.plasticidade.neuromod
    neuromod.atualizar(ajustes.PL_ACH_REF_HZ, 10 * ajustes.PL_ACH_TAU_S)
    assert neuromod.ach == pytest.approx(1.0, abs=1e-3)
    neuromod.atualizar(0.0, ajustes.PL_ACH_TAU_S)
    assert neuromod.ach == pytest.approx(np.exp(-1.0), rel=1e-3)


def test_ach_normalizada_pela_media_nao_muda_o_quanto_aprende_no_dia(pl1, ach_ligada):
    """
    A média lenta divide a taxa: um dia com 30% programando (ACh 1) e 70% à toa (ACh 0) aprende, na soma, o
    mesmo que um dia de ACh constante. Muda quando ele aprende, não quanto (regra 8).
    """
    brain = BioBrain(seed=7, seed_ruido=1)
    neuromod = brain.plasticidade.neuromod
    neuromod.ach_media = 0.3
    soma = 0.0
    for _ in range(1000):
        for focus, fracao in ((ajustes.PL_ACH_REF_HZ, 0.3), (0.0, 0.7)):
            neuromod.atualizar(focus, fracao * 60.0)
            soma += neuromod.fator_aprendizado() * fracao
    assert soma / 1000 == pytest.approx(1.0, abs=0.1)


def test_media_da_ach_vai_e_volta_no_save(pl1, tmp_path):
    brain = _cerebro()
    brain.plasticidade.neuromod.ach_media_fixa = None
    brain.plasticidade.neuromod.ach_media = 0.42
    brain.save(tmp_path / "rede.json")
    outro = BioBrain(seed=7, seed_ruido=1)
    assert outro.load(tmp_path / "rede.json")
    assert outro.plasticidade.neuromod.ach_media == pytest.approx(0.42)


def test_replay_nao_usa_a_ach(pl1, ach_ligada):
    """No replay a taxa não depende da ACh."""
    pesos = {}
    for ach in (0.0, 1.0):
        brain = _cerebro(ach=ach)
        brain.replay({"WORK": 1.0}, 2000, 0.5)
        pesos[ach] = _peso(brain, "WORK")
    assert pesos[0.0] == pytest.approx(pesos[1.0], rel=1e-9)


# ---------------- sono e persistência ----------------

def test_shy_tira_o_mesmo_do_critico(pl1):
    """O sono desfaz no crítico a mesma fração que nas sinapses; sem isso, o SHY apagaria o aprendido."""
    brain = _cerebro()
    for _ in range(20):
        _tentativa(brain, {"PEDIDO": 1.0})
    w = brain.plasticidade.critico.w.copy()
    brain.downscaling_sono(0.2)
    assert np.allclose(brain.plasticidade.critico.w, 0.8 * w)


def test_sono_e_dia_seguinte_devolvem_o_aprendido(pl1):
    """
    Com a mesma rotina, o que o SHY tira de noite o dia seguinte devolve: depois de 10 dias e noites, o peso
    da pista fica perto do de 1 dia (não vai a zero).
    """
    brain = _cerebro()
    for _ in range(20):
        _tentativa(brain, {"PEDIDO": 1.0})
    um_dia = _peso(brain, "PEDIDO")
    for _ in range(10):
        brain.downscaling_sono(0.2)
        for _ in range(20):
            _tentativa(brain, {"PEDIDO": 1.0})
    assert _peso(brain, "PEDIDO") == pytest.approx(um_dia, rel=0.1)


def test_salvar_e_carregar(pl1, tmp_path):
    brain = _cerebro()
    for _ in range(5):
        _tentativa(brain, {"PEDIDO": 1.0})
    brain.save(tmp_path / "rede.json")
    outro = _cerebro()
    assert outro.load(tmp_path / "rede.json")
    assert np.allclose(outro.plasticidade.critico.w, brain.plasticidade.critico.w, atol=1e-6)
    assert outro.plasticidade.neuromod.ach == pytest.approx(brain.plasticidade.neuromod.ach)


def test_carregar_save_sem_pl1(pl1, tmp_path):
    """Save sem o campo (gravado com a chave desligada): carrega, com o crítico do zero."""
    ajustes.PL_DELTA = False
    try:
        antigo = BioBrain(seed=7, seed_ruido=1)
        _tentativa(antigo, {"WORK": 1.0})
        antigo.save(tmp_path / "rede.json")
    finally:
        ajustes.PL_DELTA = True
    novo = _cerebro()
    assert novo.load(tmp_path / "rede.json")
    assert not novo.plasticidade.critico.w.any()
    assert _peso(novo, "WORK") == pytest.approx(_peso(antigo, "WORK"), abs=1e-6)


def test_carregar_plasticidade_invalida_nao_muda_nada(pl1, tmp_path):
    from pestinha.store import read_json, write_json
    brain = _cerebro()
    _tentativa(brain, {"PEDIDO": 1.0})
    brain.save(tmp_path / "rede.json")
    dados = read_json(tmp_path / "rede.json")
    dados["plasticidade"]["critico"][0] = "lixo"
    write_json(tmp_path / "rede.json", dados)
    outro = _cerebro()
    assert outro.load(tmp_path / "rede.json") is False
    assert not outro.learned.any()
    assert not outro.plasticidade.critico.w.any()
