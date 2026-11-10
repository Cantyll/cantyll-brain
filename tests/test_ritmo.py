"""
Ritmo e sono (core/ritmo.py e homeostasis.Drives): vigília de dia, sono à noite, com a pressão de sono da spec.
"""

import pytest

from pestinha import ajustes
from pestinha.core.homeostasis import Drives
from pestinha.core.ritmo import avancar_pressao, circadiano, quer_acordar, quer_dormir
from pestinha.config import PROFILES


def simular(dias, hora_inicial=7.0, pressao=0.25, passo_s=60.0):
    """Roda o relógio por `dias` dias, de um pet acordado às 7 h. Devolve [(tipo, hora)] de cada troca."""
    dormindo = False
    eventos = []
    t = 0.0
    while t < dias * 86400.0:
        hora = (hora_inicial + t / 3600.0) % 24.0
        c = circadiano(hora)
        if dormindo and quer_acordar(pressao, c):
            dormindo = False
            eventos.append(("acorda", hora))
        elif not dormindo and quer_dormir(pressao, c):
            dormindo = True
            eventos.append(("dorme", hora))
        pressao = avancar_pressao(pressao, passo_s, dormindo)
        t += passo_s
    return eventos


def test_pico_de_vigilia_e_o_maximo_do_relogio():
    assert circadiano(ajustes.PICO_VIGILIA_H) == pytest.approx(1.0)
    assert circadiano(ajustes.PICO_VIGILIA_H + 12) == pytest.approx(-1.0)


def test_janela_de_sono_comeca_perto_de_21h15_com_pico_em_16h():
    # C = 0,2 marca o começo da janela em que o relógio deixa dormir (pico 16 h: ~21h14)
    assert circadiano(21.23, 16.0) == pytest.approx(0.2, abs=0.01)
    assert circadiano(10.77, 16.0) == pytest.approx(0.2, abs=0.01)


def test_pressao_chega_a_0_8_em_16_horas_acordado():
    pressao = 0.0
    for _ in range(16 * 60):
        pressao = avancar_pressao(pressao, 60.0, dormindo=False)
    assert pressao == pytest.approx(0.80, abs=0.01)           # spec, seção 8: P ≈ 0,8


def test_de_dia_com_pressao_alta_nao_dorme_e_so_dorme_no_limite_forcado():
    assert not quer_dormir(0.9, circadiano(14.0, 16.0))      # dia: C > 0,2
    assert quer_dormir(0.9, circadiano(22.0, 16.0))          # noite: C < 0,2
    assert quer_dormir(0.96, circadiano(14.0, 16.0))         # limite forçado: P > 0,95


def test_acordar_tem_histerese():
    assert not quer_acordar(0.4, circadiano(2.0, 16.0))      # madrugada, P ainda média: continua dormindo
    assert quer_acordar(0.2, circadiano(2.0, 16.0))          # P caiu abaixo de 0,25
    assert quer_acordar(0.45, circadiano(13.0, 16.0))        # pico de vigília e P abaixo de 0,5


def test_ciclo_de_quatro_dias_dorme_de_noite_e_acorda_de_manha():
    eventos = simular(4)
    dormidas = [h for tipo, h in eventos if tipo == "dorme"]
    acordadas = [h for tipo, h in eventos if tipo == "acorda"]
    assert len(dormidas) >= 3 and len(acordadas) >= 3
    assert all(21.0 <= h <= 23.0 for h in dormidas), dormidas
    assert all(6.0 <= h <= 8.0 for h in acordadas), acordadas


def test_noite_dura_o_que_se_espera():
    eventos = simular(4)
    duracoes = []
    for (tipo_a, h_a), (tipo_b, h_b) in zip(eventos, eventos[1:]):
        if tipo_a == "dorme" and tipo_b == "acorda":
            duracoes.append((h_b - h_a) % 24.0)
    assert duracoes
    assert all(8.5 <= d <= 10.5 for d in duracoes), duracoes


def test_pressao_sobrevive_a_fechar_o_programa(tmp_path):
    caminho = tmp_path / "drives.json"
    d = Drives()
    d.pressao = 0.6
    d.save(str(caminho))
    e = Drives()
    assert e.load(str(caminho), PROFILES["teste"]) is True
    assert e.pressao == pytest.approx(0.6)


def test_pressao_nao_avanca_com_o_programa_fechado(tmp_path):
    # a pausa congela P (spec, seção 6): dez horas fechado não mudam a pressão salva
    import json
    import time

    caminho = tmp_path / "drives.json"
    caminho.write_text(json.dumps({"energy": 0.5, "stimulation": 0.5, "contact": 0.1,
                                   "pressao": 0.5, "saved_at": time.time() - 36000}))
    e = Drives()
    assert e.load(str(caminho), PROFILES["teste"]) is True
    assert e.pressao == pytest.approx(0.5)
