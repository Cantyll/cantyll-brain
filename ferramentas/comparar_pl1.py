"""
Compara o BioBrain com e sem a plasticidade do PL-1 na simulação de noites: 5 sementes, 4 cenários, dia 30.
É o comando que reproduz os números da descrição do PR do PL-1 (regra 8 do plano e critério da GLOOM).

    python ferramentas/comparar_pl1.py                         # sementes 3 a 7, 4 processos
    python ferramentas/comparar_pl1.py --sementes 7 --json saida.json

Cada linha é a faixa (mínimo–máximo) das sementes. "%" compara com o dia 0 da mesma semente. Simulado, não
medido: as suposições estão no cabeçalho de simular_noites.py.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

CENARIOS = ("duro", "misto", "carinhoso", "so_o_lar")


def _uma(args):
    import simular_noites
    cenario, semente, pl1, noites = args
    linhas = simular_noites.simular(cenario, noites, semente, dias=(0, noites), cerebro="bio", pl1=pl1)
    fim = linhas[-1]
    return {"cenario": cenario, "semente": semente, "pl1": pl1, "uso_hz": fim["uso_hz"],
            "uso_relativo": fim["uso_relativo"], "peso_gloom_max": fim["peso_gloom_max"]}


def _faixa(valores, fmt):
    return f"{fmt(min(valores))}–{fmt(max(valores))}"


def main():
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    parser = argparse.ArgumentParser(description="BioBrain com e sem o PL-1 na simulação de noites.")
    parser.add_argument("--sementes", type=int, nargs="+", default=[3, 4, 5, 6, 7])
    parser.add_argument("--noites", type=int, default=30)
    parser.add_argument("--processos", type=int, default=4)
    parser.add_argument("--json", help="grava os resultados neste arquivo")
    args = parser.parse_args()

    tarefas = [(c, s, p, args.noites) for c in CENARIOS for s in args.sementes for p in (False, True)]
    with ProcessPoolExecutor(args.processos) as ex:
        resultados = list(ex.map(_uma, tarefas))

    print(f"Dia {args.noites}, sementes {args.sementes}, cérebro bio.")
    print("  cenário    | PL-1 | GLOOM (Hz)   | FRUSTRATION (Hz) | PLAYFUL (% dia 0) | CALM (% dia 0)")
    for cenario in CENARIOS:
        for pl1 in (False, True):
            linhas = [r for r in resultados if r["cenario"] == cenario and r["pl1"] == pl1]
            hz = lambda pop: _faixa([r["uso_hz"][pop] for r in linhas], lambda v: f"{v:.2f}")  # noqa: E731
            pc = lambda pop: _faixa([100 * r["uso_relativo"][pop] for r in linhas], lambda v: f"{v:.0f}%")  # noqa: E731
            print(f"  {cenario:10s} | {'sim' if pl1 else 'não':4s} | {hz('GLOOM'):12s} | {hz('FRUSTRATION'):16s} | "
                  f"{pc('PLAYFUL'):17s} | {pc('CALM')}")
    if args.json:
        Path(args.json).write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Resultados gravados em {args.json}")


if __name__ == "__main__":
    main()
