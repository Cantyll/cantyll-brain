"""
A linha de base do LIF (T2 do plano, PR 1 de 4): docs/linha_de_base_lif.json é o que
ferramentas/linha_de_base.py produz, e uma rodada refeita agora dá o mesmo número.

Rodar: python -m pytest tests/test_linha_de_base.py -q
"""
import json
import math
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))
import linha_de_base  # noqa: E402
import simular_noites  # noqa: E402


def _registrada():
    return json.loads(linha_de_base.JSON_PADRAO.read_text(encoding="utf-8"))


def test_resumo_calcula_media_dp_e_dois_erros_padrao():
    r = linha_de_base.resumo([1.0, 2.0, 3.0, 4.0])
    assert r["n"] == 4
    assert r["media"] == pytest.approx(2.5)
    assert r["dp"] == pytest.approx(math.sqrt(5.0 / 3.0))
    assert r["dois_ep"] == pytest.approx(2.0 * math.sqrt(5.0 / 3.0) / 2.0)
    assert r["dois_ep_pct"] == pytest.approx(100.0 * r["dois_ep"] / 2.5)
    assert (r["min"], r["max"]) == (1.0, 4.0)


def test_resumo_de_media_zero_nao_divide():
    r = linha_de_base.resumo([0.0, 0.0])
    assert r["dois_ep_pct"] is None
    with pytest.raises(ValueError):
        linha_de_base.resumo([])


def test_registro_tem_todas_as_combinacoes_e_resumo_coerente():
    dados = _registrada()
    assert dados["versao"] == linha_de_base.VERSAO and dados["cerebro"] == "lif"
    assert dados["sementes"] == list(range(1, linha_de_base.SEMENTES_PADRAO + 1))
    assert dados["populacoes"] == list(simular_noites.POPULACOES)
    for c in linha_de_base.CENARIOS_PADRAO:
        for s in linha_de_base.SONOS_PADRAO:
            por_semente = dados["taxas"][c][str(s)]
            assert sorted(por_semente, key=int) == [str(x) for x in dados["sementes"]]
            for pop in dados["populacoes"]:
                esperado = linha_de_base.resumo([por_semente[k][pop] for k in sorted(por_semente, key=int)])
                assert dados["resumo"][c][str(s)][pop] == pytest.approx(esperado)


def test_tabela_registrada_e_a_gerada_do_json():
    dados = _registrada()
    texto = linha_de_base.markdown(dados, "python ferramentas/linha_de_base.py")
    assert linha_de_base.MD_PADRAO.read_text(encoding="utf-8") == texto


def test_uma_rodada_refeita_bate_com_o_registro():
    """
    Semente 7, duro, 1 sono: a simulação de agora reproduz o número registrado (leva uns 15 s).
    Na máquina que gerou o registro (Linux) o número sai idêntico. A folga de 5% cobre a aritmética de ponto
    flutuante de outro sistema (Windows, macOS), que pode trocar um pulso de lugar; uma mudança na rede, no
    sono ou na simulação que mova a taxa mais que isso faz o teste falhar e pede gerar o registro de novo.
    """
    agora = linha_de_base.rodada("duro", 1, 7)
    registrado = _registrada()["taxas"]["duro"]["1"]["7"]
    for pop in simular_noites.POPULACOES:
        assert agora[pop] == pytest.approx(registrado[pop], rel=0.05, abs=0.02), pop
