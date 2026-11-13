"""
Linha de base do LIF para o portão A do plano (T2): a simulação de noites com várias sementes, por
cenário e por número de sonos, e o resumo de cada população no último dia.

    python ferramentas/linha_de_base.py                       # 20 sementes, duro/misto/carinhoso, 1 sono
    python ferramentas/linha_de_base.py --sementes 5          # sementes 1 a 5
    python ferramentas/linha_de_base.py --cenarios duro --sonos 1 --processos 2
    python ferramentas/linha_de_base.py --json saida.json --md saida.md
    python ferramentas/linha_de_base.py --cerebro bio         # o BioBrain contra o LIF registrado (portão A)

Sem --json e sem --md, grava em docs/linha_de_base_lif.json e docs/LINHA_DE_BASE_LIF.md (os arquivos
registrados no repositório). Com a mesma lista de sementes, o resultado se repete: cada rodada é
ferramentas/simular_noites.py com a mesma semente (rede, ruído, sorteio do dia e relógio).

O que sai, por cenário, número de sonos e população: média, desvio padrão, mínimo e máximo das sementes, e
dois erros-padrão da média (2·dp/√n), em Hz e em % da média. É simulação com uso suposto (as suposições
estão no cabeçalho de simular_noites.py), não medida de uso real.

Por que mais de 5 sementes: com n sementes, uma rodada nova e intercambiável com elas cai entre o mínimo
e o máximo com probabilidade (n−1)/(n+1). Com 5 sementes, 67%; com 20, 90%. A faixa de 5 sementes deixa
passar uma rede errada com frequência demais para servir de portão.

Com --cerebro bio, a ferramenta roda as mesmas simulações com o BioBrain e compara com o registro do LIF pelo
critério do portão A (plano, seção 6): a média de cada população fica a no máximo 2 erros-padrão da média do
LIF, ou a no máximo PISO_HZ quando PISO_HZ for maior, e nenhuma população com média acima do piso no LIF zera.
O piso de 0,05 Hz é um número escolhido, não medido (decidido pelo Cantyll em 2026-11-13). Sai com código 1
se alguma linha não passar. Sem --json e sem --md, não grava nada: o registro do LIF não é sobrescrito.

Por que só 1 sono por noite no padrão: desde o B4 (PR #10), o replay e o SHY são cobrados pela dívida de
sono, e a noite picada em N sonos dá exatamente o mesmo resultado na simulação (tests/test_simulacao_noites.py,
picada == inteira). Rodado com --sonos 1 6, as tabelas de 6 sonos saem idênticas às de 1.

Populações com média perto de zero (FRUSTRATION, GLOOM e SAD nos cenários misto e carinhoso): ali o erro-padrão
em % não tem sentido (a tabela mostra "--" abaixo de PCT_DESDE_HZ), e qualquer comparação tem de ser em Hz.
"""
import argparse
import json
import math
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))

import simular_noites  # noqa: E402

CENARIOS_PADRAO = ("duro", "misto", "carinhoso")
SONOS_PADRAO = (1,)
PCT_DESDE_HZ = 0.05            # abaixo disso, a % da média não tem sentido: a tabela mostra "--"
PISO_HZ = 0.05                 # portão A: tolerância mínima em Hz. Escolhido, não medido (Cantyll, 2026-11-13)
SEMENTES_PADRAO = 20
NOITES_PADRAO = 30
JSON_PADRAO = RAIZ / "docs" / "linha_de_base_lif.json"
MD_PADRAO = RAIZ / "docs" / "LINHA_DE_BASE_LIF.md"
VERSAO = 1


def resumo(valores):
    """Média, desvio padrão (amostral), mínimo, máximo e dois erros-padrão da média de uma lista de taxas."""
    valores = [float(v) for v in valores]
    n = len(valores)
    if n == 0:
        raise ValueError("resumo de lista vazia")
    media = statistics.fmean(valores)
    dp = statistics.stdev(valores) if n > 1 else 0.0
    dois_ep = 2.0 * dp / math.sqrt(n)
    return {
        "n": n,
        "media": media,
        "dp": dp,
        "min": min(valores),
        "max": max(valores),
        "dois_ep": dois_ep,
        "dois_ep_pct": (100.0 * dois_ep / media) if media > 0 else None,
    }


def rodada(cenario, sonos, semente, noites=NOITES_PADRAO, cerebro="lif"):
    """Uma simulação de noites; devolve a taxa de uso de cada população no último dia."""
    linhas = simular_noites.simular(cenario, noites, semente, sonos=sonos, cerebro=cerebro)
    return {pop: float(linhas[-1]["uso_hz"][pop]) for pop in simular_noites.POPULACOES}


def _rodada(args):
    return args, rodada(*args)


def medir(cenarios=CENARIOS_PADRAO, sonos=SONOS_PADRAO, sementes=range(1, SEMENTES_PADRAO + 1),
          noites=NOITES_PADRAO, processos=None, cerebro="lif"):
    """Roda todas as combinações e devolve o dicionário que vai para o JSON."""
    tarefas = [(c, int(s), int(semente), int(noites), cerebro) for c in cenarios for s in sonos for semente in sementes]
    brutos = {}
    if processos == 1:
        resultados = map(_rodada, tarefas)
    else:
        executor = ProcessPoolExecutor(max_workers=processos)
        resultados = executor.map(_rodada, tarefas)
    for (c, s, semente, _n, _cerebro), taxas in resultados:
        brutos.setdefault(c, {}).setdefault(str(s), {})[str(semente)] = taxas
    if processos != 1:
        executor.shutdown()
    resumos = {
        c: {
            s: {pop: resumo([por_semente[k][pop] for k in sorted(por_semente, key=int)])
                for pop in simular_noites.POPULACOES}
            for s, por_semente in por_sonos.items()
        }
        for c, por_sonos in brutos.items()
    }
    return {
        "versao": VERSAO,
        "cerebro": cerebro,
        "noites": int(noites),
        "sementes": [int(x) for x in sementes],
        "populacoes": list(simular_noites.POPULACOES),
        "taxas": brutos,
        "resumo": resumos,
    }


def comparar(dados, referencia):
    """
    Critério do portão A: cada (cenário, sonos, população) de `dados` contra `referencia` (o LIF registrado).
    Devolve uma linha por combinação, com a tolerância usada e se passou.
    """
    linhas = []
    for c, por_sonos in dados["resumo"].items():
        for s, por_pop in por_sonos.items():
            for pop, r in por_pop.items():
                ref = referencia["resumo"][c][s][pop]
                tolerancia = max(ref["dois_ep"], PISO_HZ)
                diferenca = r["media"] - ref["media"]
                zerou = ref["media"] > PISO_HZ and r["max"] == 0.0
                linhas.append({
                    "cenario": c, "sonos": s, "populacao": pop, "media": r["media"], "media_lif": ref["media"],
                    "diferenca": diferenca, "tolerancia": tolerancia,
                    "passou": abs(diferenca) <= tolerancia and not zerou,
                })
    return linhas


def tabela_comparacao(linhas):
    texto = ["| Cenário | Sonos | População | média LIF | média | diferença | tolerância | passou |",
             "|---|---|---|---|---|---|---|---|"]
    for r in linhas:
        texto.append(f"| {r['cenario']} | {r['sonos']} | {r['populacao']} | {_hz(r['media_lif'])} | {_hz(r['media'])} "
                     f"| {r['diferenca']:+.3f} | {_hz(r['tolerancia'])} | {'sim' if r['passou'] else 'NÃO'} |")
    return "\n".join(texto)


def _hz(valor):
    return f"{valor:.3f}"


def markdown(dados, comando):
    """Tabela da linha de base, para docs/LINHA_DE_BASE_LIF.md."""
    sementes = dados["sementes"]
    faixa = f"{sementes[0]} a {sementes[-1]}" if sementes == list(range(sementes[0], sementes[-1] + 1)) else \
        ", ".join(str(s) for s in sementes)
    linhas = [
        f"# Linha de base do {'LIF' if dados['cerebro'] == 'lif' else 'BioBrain'} (T2)",
        "",
        "Arquivo gerado. Não editar à mão: rodar o comando abaixo e fazer commit do resultado.",
        "",
        f"    {comando}",
        "",
        f"Simulação de noites (`ferramentas/simular_noites.py`), {dados['noites']} noites, sementes {faixa} "
        f"({len(sementes)} rodadas por linha). Taxa de uso de cada população no dia {dados['noites']}, em Hz por "
        "neurônio. É simulação com uso suposto, não medida de uso real: as suposições estão no cabeçalho de "
        "`simular_noites.py`.",
        "",
        "Colunas: média, desvio padrão (dp), mínimo e máximo das sementes, e dois erros-padrão da média "
        "(2·dp/√n), em Hz e em % da média. Os valores brutos de cada semente estão em "
        "`docs/linha_de_base_lif.json`. Com média abaixo de "
        f"{PCT_DESDE_HZ} Hz, a % não tem sentido e aparece como --: ali a comparação tem de ser em Hz.",
        "",
    ]
    for c, por_sonos in dados["resumo"].items():
        for s, por_pop in sorted(por_sonos.items(), key=lambda kv: int(kv[0])):
            linhas += [
                f"## {c}, {s} sono(s) por noite",
                "",
                "| População | média | dp | mín | máx | ±2 EP | ±2 EP (%) |",
                "|---|---|---|---|---|---|---|",
            ]
            for pop in dados["populacoes"]:
                r = por_pop[pop]
                pct = "--" if r["dois_ep_pct"] is None or r["media"] < PCT_DESDE_HZ else f"{r['dois_ep_pct']:.1f}%"
                linhas.append(f"| {pop} | {_hz(r['media'])} | {_hz(r['dp'])} | {_hz(r['min'])} | {_hz(r['max'])} "
                              f"| {_hz(r['dois_ep'])} | {pct} |")
            linhas.append("")
    return "\n".join(linhas)


def main():
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    parser = argparse.ArgumentParser(description="Linha de base do LIF: simulação de noites com várias sementes.")
    parser.add_argument("--cenarios", nargs="+", default=list(CENARIOS_PADRAO), choices=sorted(simular_noites.CENARIOS))
    parser.add_argument("--sonos", nargs="+", type=int, default=list(SONOS_PADRAO))
    parser.add_argument("--sementes", type=int, default=SEMENTES_PADRAO, help="usa as sementes 1 a N (padrão: 20)")
    parser.add_argument("--noites", type=int, default=NOITES_PADRAO)
    parser.add_argument("--processos", type=int, default=None, help="processos em paralelo (padrão: um por núcleo)")
    parser.add_argument("--cerebro", default="lif", choices=sorted(simular_noites.CEREBROS),
                        help="lif (padrão: grava o registro) ou bio (compara com o registro do LIF)")
    parser.add_argument("--json", help=f"onde gravar os valores (padrão: {JSON_PADRAO.relative_to(RAIZ)})")
    parser.add_argument("--md", help=f"onde gravar a tabela (padrão: {MD_PADRAO.relative_to(RAIZ)})")
    args = parser.parse_args()

    dados = medir(args.cenarios, args.sonos, range(1, args.sementes + 1), args.noites, args.processos, args.cerebro)
    partes = ["python ferramentas/linha_de_base.py"]
    if args.cerebro != "lif":
        partes.append(f"--cerebro {args.cerebro}")
    if args.sementes != SEMENTES_PADRAO:
        partes.append(f"--sementes {args.sementes}")
    if tuple(args.cenarios) != CENARIOS_PADRAO:
        partes.append("--cenarios " + " ".join(args.cenarios))
    if tuple(args.sonos) != SONOS_PADRAO:
        partes.append("--sonos " + " ".join(str(s) for s in args.sonos))
    if args.noites != NOITES_PADRAO:
        partes.append(f"--noites {args.noites}")
    texto = markdown(dados, " ".join(partes))
    print(texto)

    if args.cerebro == "lif":
        caminho_json = Path(args.json) if args.json else JSON_PADRAO
        caminho_md = Path(args.md) if args.md else MD_PADRAO
    else:
        caminho_json = Path(args.json) if args.json else None
        caminho_md = Path(args.md) if args.md else None
    if caminho_json:
        caminho_json.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Gravado em {caminho_json}")
    if caminho_md:
        caminho_md.write_text(texto, encoding="utf-8")
        print(f"Gravado em {caminho_md}")

    if args.cerebro != "lif":
        referencia = json.loads(JSON_PADRAO.read_text(encoding="utf-8"))
        if referencia["sementes"] != dados["sementes"] or referencia["noites"] != dados["noites"]:
            print("O registro do LIF foi feito com outras sementes ou noites: a comparação do portão A não vale.")
            sys.exit(2)
        linhas = comparar(dados, referencia)
        print(f"\nPortão A: {args.cerebro} contra o LIF registrado (tolerância = máx(2 EP do LIF, {PISO_HZ} Hz))\n")
        print(tabela_comparacao(linhas))
        falhas = [r for r in linhas if not r["passou"]]
        print(f"\n{len(linhas) - len(falhas)} de {len(linhas)} linhas passam.")
        if falhas:
            sys.exit(1)


if __name__ == "__main__":
    main()
