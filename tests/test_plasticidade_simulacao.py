"""
PL-1 na simulação de noites (regra 8 do plano): o reforço do lar ensina no cenário "só o lar", e o critério da
GLOOM no dia 30 (decisão do Cantyll, 2026-11-13: duro até 2,0 Hz) vale com o PL-1 ligado.

Sem Qt. Comando que reproduz: python ferramentas/simular_noites.py --pl1 --cenario <cenário> --semente <n>
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))

import simular_noites  # noqa: E402

from pestinha import ajustes  # noqa: E402


def _dia(linhas, dia):
    return next(linha for linha in linhas if linha["dia"] == dia)


def test_so_o_lar_sem_pl1_nao_aprende():
    """O controle do PR #27: sem o PL-1, as bagunças não têm recompensa e nada é aprendido."""
    linhas = simular_noites.simular("so_o_lar", 3, 7, dias=(0, 3), cerebro="bio")
    assert not any(any(v != 0.0 for v in fila) for fila in _dia(linhas, 3)["aprendido"])


def test_so_o_lar_com_pl1_aprende_pelo_tedio():
    """Com o PL-1, o alívio do tédio ensina: o tédio passa a puxar para brincar e para a calma."""
    linhas = simular_noites.simular("so_o_lar", 3, 7, dias=(0, 3), cerebro="bio", pl1=True)
    rel = _dia(linhas, 3)["uso_relativo"]
    assert rel["PLAYFUL"] > 1.05 and rel["CALM"] > 1.05
    assert _dia(linhas, 3)["uso_hz"]["GLOOM"] == pytest.approx(0.0, abs=0.05)


def test_pl1_so_existe_no_bio():
    with pytest.raises(ValueError):
        simular_noites.simular("duro", 1, 7, dias=(0, 1), cerebro="lif", pl1=True)


def test_pl1_nao_fica_ligado_depois_da_simulacao():
    simular_noites.simular("so_o_lar", 1, 7, dias=(0, 1), cerebro="bio", pl1=True)
    assert ajustes.PL_DELTA is False


def test_criterio_da_gloom_no_duro_com_pl1():
    """Critério absoluto da GLOOM (spec, seção 10): no cenário duro, até 2,0 Hz no dia 30, semente 7."""
    linhas = simular_noites.simular("duro", 30, 7, dias=(0, 30), cerebro="bio", pl1=True)
    assert _dia(linhas, 30)["uso_hz"]["GLOOM"] <= 2.0
