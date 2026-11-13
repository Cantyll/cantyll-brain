"""
Guarda de negligência (R1): você presente e sem interagir com o pet por 10 minutos liga a guarda de ausência.
Decisão do Cantyll, 2026-11-13. A lógica é pura (core/negligencia.py); a ligação com a app fica em App.think
e nos gatilhos de interação (controle/interacao.py).
"""
from pestinha import ajustes
from pestinha.core.negligencia import Negligencia


def test_limite_de_negligencia_sao_dez_minutos():
    assert ajustes.NEGLIGENCIA_S == 600.0


def test_liga_so_depois_do_limite_com_voce_presente():
    n = Negligencia(600.0)
    for _ in range(1199):
        n.tick(0.5, presente=True)           # 599,5 s
    assert not n.ativa
    n.tick(0.5, presente=True)               # 600 s
    assert n.ativa


def test_ausente_nao_conta_para_negligencia():
    n = Negligencia(600.0)
    for _ in range(10000):
        n.tick(0.5, presente=False)          # 5000 s fora: não é negligência; a ausência já segura a rede
    assert not n.ativa
    assert n.parado_s == 0.0


def test_interagir_zera_e_a_contagem_recomeca():
    n = Negligencia(600.0)
    for _ in range(1200):
        n.tick(0.5, presente=True)
    assert n.ativa
    n.interagiu()
    assert not n.ativa
    n.tick(0.5, presente=True)
    assert n.parado_s == 0.5


def test_ligada_continua_ligada_ao_voltar_ate_interagir():
    """Uma vez ligada, a guarda só desliga com interação: voltar ao computador, sozinho, não a desliga."""
    n = Negligencia(600.0)
    for _ in range(1200):
        n.tick(0.5, presente=True)
    for _ in range(100):
        n.tick(0.5, presente=False)
    assert n.ativa
    n.interagiu()
    assert not n.ativa


def test_dt_zero_ou_negativo_nao_conta():
    n = Negligencia(600.0)
    n.tick(0.0, presente=True)
    n.tick(-5.0, presente=True)
    assert n.parado_s == 0.0
