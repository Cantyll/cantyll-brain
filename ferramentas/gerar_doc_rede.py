"""
Gera docs/REDE_NEURAL.md a partir do código (canais, interneurônios, motores, conexões e limiares).

    python ferramentas/gerar_doc_rede.py

Rode de novo sempre que mexer em pestinha/core/nervous_system.py, nos limiares de pestinha/ajustes.py ou no modelo
de neurônio de cada população (pestinha/core/bio/rede.py, frente NE).
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from pestinha import ajustes  # noqa: E402
from pestinha.core import nervous_system as ns  # noqa: E402
from pestinha.core import emotion  # noqa: E402
from pestinha.core.bio.neuronios import TIPOS, reobase  # noqa: E402
from pestinha.core.bio.rede import gasto_das_chaves, neuronios_das_chaves  # noqa: E402
from pestinha.mind import castigo_ctl  # noqa: E402
from pestinha.ui.rotulos import CANAIS_SENSORIAIS, INTERNEURONIOS, MOTORES  # noqa: E402

CHAVES_NE = ("NE_INIBIDORES_FS", "NE_EXCITATORIOS", "NE_MOTORES")

FONTE = (RAIZ / "pestinha" / "core" / "nervous_system.py").read_text(encoding="utf-8")


def comentarios_sensoriais():
    ini = FONTE.index("SENSORY_SPEC = {")
    bloco = FONTE[ini:FONTE.index("\n}", ini)]
    return dict(re.findall(r'"([A-Z_]+)":\s*\([^)]*\),\s*#\s*(.*)', bloco))


def comentarios_motores():
    ini = FONTE.index("MOTOR_SPEC = [")
    bloco = FONTE[ini:FONTE.index("\n]", ini)]
    return dict(re.findall(r'\("([A-Z_]+)",[^)]*\),\s*#\s*(.*)', bloco))


def entradas_de(pos):
    pares = [(pre, w) for pre, alvo, w, _d in ns.CONNECTIONS if alvo == pos and w != 0]   # peso 0: linha só para manter o sorteio
    return ", ".join(f"{pre} ({'+' if w > 0 else '−'}{abs(w):.2f})" for pre, w in sorted(pares, key=lambda p: -abs(p[1])))


def modelos_com_as_chaves():
    """{população: (tipo Izhikevich, ganho, gasta corrente)} com as chaves da frente NE ligadas."""
    antes = {k: getattr(ajustes, k) for k in CHAVES_NE}
    try:
        for k in CHAVES_NE:
            setattr(ajustes, k, True)
        tipos, ganho, _tau = neuronios_das_chaves()
        gasta = gasto_das_chaves()
    finally:
        for k, v in antes.items():
            setattr(ajustes, k, v)
    return {n: (t, ganho.get(n, 1.0), n in gasta) for n, t in tipos.items()}


def modelo(nome, modelos):
    if nome not in modelos:
        return "LIF"
    tipo, ganho, _ = modelos[nome]
    return f"{tipo} ×{ganho:g}"


def main():
    brain = ns.LIFBrain(seed=7)
    modelos = modelos_com_as_chaves()
    ligadas = [k for k in CHAVES_NE if getattr(ajustes, k)]
    com_s, com_m = comentarios_sensoriais(), comentarios_motores()
    linhas = [
        "# A rede neural do pet",
        "",
        "> Gerado por `ferramentas/gerar_doc_rede.py` a partir do código. Não edite à mão: rode o script.",
        "",
        f"A rede tem **{brain.N} neurônios**, "
        f"**{int(np.count_nonzero(brain.W))} sinapses**, **{len(ns.SENSORY_SPEC)} canais sensoriais**, "
        f"**{len(ns.INTER_SPEC)} populações de interneurônios** e **{len(ns.MOTOR_SPEC)} populações motoras**.",
        "",
        "## Modelo de neurônio",
        "",
        "Há dois cérebros com a mesma rede (as mesmas populações e sinapses): o `BioBrain`, padrão do app desde a "
        "NE-5, e o `LIFBrain` (`PESTINHA_CEREBRO=lif` no ambiente). Cada um grava o próprio arquivo de estado "
        "(`nervous.json` o LIF, `nervous_bio.json` o bio). No `LIFBrain` todo neurônio é de integração e disparo com "
        "vazamento (LIF). No `BioBrain`, as chaves da frente NE em `ajustes.py` passam populações para o modelo de "
        "Izhikevich, uma frente por vez: "
        + ", ".join(f"`{k}`" for k in CHAVES_NE) + ". "
        + (f"Ligadas agora: {', '.join(f'`{k}`' for k in ligadas)}." if ligadas else "Todas desligadas agora.")
        + " `PESTINHA_NE=0` no ambiente desliga as três."
        + " As colunas \"Com as chaves NE\" abaixo dizem o modelo de cada população com as três ligadas "
        "(tipo e ganho sobre a escala de corrente).",
        "",
        "| Tipo | a | b | c (mV) | d | Reobase | Populações com as chaves NE |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for tipo, (a, b, c, d) in TIPOS.items():
        quem = [n for n, (t, *_r) in modelos.items() if t == tipo]
        linhas.append(f"| {tipo} | {a:g} | {b:g} | {c:g} | {d:g} | {reobase(tipo):.2f} | "
                      f"{', '.join(f'`{n}`' for n in quem) or '—'} |")
    linhas += [
        "",
        "- **Correntes sinápticas:** τ = τ_m que a população tinha no LIF (decisão A da NE-1), para a mesma "
        "integração lenta.",
        "- **Gasto:** nas populações excitatórias e motoras, cada pulso tira da corrente um limiar do LIF "
        "(reobase × ganho), como o reset do LIF (NE-3). As inibitórias FS não gastam.",
        "- **Adaptação lenta:** no LIF o limiar sobe a cada pulso e volta em segundos; o u do Izhikevich só adapta em "
        "~50 ms. A `ALERT` e o `STARTLE` levam a adaptação do LIF como corrente (`rede.ADAPTACAO_LENTA`): sem ela o "
        "pet se assusta a mais com estímulo fraco e contínuo. Nas outras populações ela fica de fora (o portão A piora).",
        "- **Ganhos:** ajustados para a taxa de cada população ficar a do LIF "
        "(`python ferramentas/comparar_izhikevich.py --ajustar ne3` e `--ajustar ne4`). Os da `ALERT` e do `STARTLE`, "
        "em CH, igualam o susto do LIF em eventos curtos, não a taxa (`--comportamento ne4`, `tests/test_ne_susto.py`).",
        "",
        "## Como o sinal anda",
        "",
        "```text",
        "computador e você ──► sentidos (0..1) ──► neurônios sensoriais (Poisson, com habituação)",
        "                                               │",
        "                                               ▼",
        "                                   interneurônios (foco, curiosidade, raiva...)",
        "                                               │",
        "                                               ▼",
        "            motores de expressão (corpo, emoção)    motores de decisão (sentar, fugir...)",
        "                     │                                        │",
        "                     ▼                                        ▼",
        "          tom motor, olhar, emoção               limiares em Hz ou frequência = taxa × ganho",
        "```",
        "",
        "- **Habituação:** cada canal perde eficácia a cada disparo (`d`) e recupera em `tau_rec` segundos.",
        "- **Temperamento:** `pets/*.json` multiplica as sinapses que saem dos sentidos (o mesmo estímulo pesa diferente em cada pet).",
        "- **Inibição lateral:** motores competem só dentro do seu grupo (expressão com expressão, decisão com decisão).",
        "- **Ausência (modulador, R1):** com o usuário ausente, FUGIR e TRAVESSURA recebem corrente inibitória "
        "(`ajustes.AUSENCIA_CORRENTE`). Não é canal sensorial e não mexe no sorteio da rede.",
        "- **Aprendizado por carinho:** regra de três fatores entre canais sensoriais e PLAYFUL/CALM/FRUSTRATION/GLOOM, "
        "com recompensa (+ carinho, − dispensa e castigo).",
        "- **Condicionamento:** Rescorla–Wagner fora da rede (`core/conditioning.py`); a força prevista entra como "
        "`ANTICIPATE` (cutucada/arraste) e `ANTECIPA_PLACA` (cantinho).",
        "",
        "## Canais sensoriais",
        "",
        "| Canal | Nome no monitor | Habitua (d / tau_rec) | O que é |",
        "|---|---|---|---|",
    ]
    for nome, (_n, _taxa, d, tau) in ns.SENSORY_SPEC.items():
        hab = "não" if d == 0 else f"{d:g} / {tau:g} s"
        linhas.append(f"| `{nome}` | {CANAIS_SENSORIAIS.get(nome, '')} | {hab} | {com_s.get(nome, '')} |")
    linhas += ["", "## Interneurônios", "",
               "| População | Nome no monitor | Tipo | Neurônios | τ_m (ms) | Com as chaves NE | Entradas (peso) |",
               "|---|---|---|---:|---:|---|---|"]
    for nome, tipo, n, tau_m, *_ in ns.INTER_SPEC:
        linhas.append(f"| `{nome}` | {INTERNEURONIOS.get(nome, '')} | {'excitatória' if tipo == 'exc' else 'inibitória'} "
                      f"| {n} | {tau_m:g} | {modelo(nome, modelos)} | {entradas_de(nome)} |")
    linhas += ["", "## Motores", "",
               "| Motor | Grupo | Nome no monitor | τ_m (ms) | Com as chaves NE | Entradas (peso) | Para que serve |",
               "|---|---|---|---:|---|---|---|"]
    for nome, n, tau_m, *_ in ns.MOTOR_SPEC:
        grupo = "decisão" if nome in ns.DECISION_MOTORS else "expressão"
        linhas.append(f"| `{nome}` | {grupo} | {MOTORES.get(nome, '')} | {tau_m:g} | {modelo(nome, modelos)} | "
                      f"{entradas_de(nome)} | {com_m.get(nome, '')} |")
    linhas += [
        "",
        "## Decisões pela rede",
        "",
        "Os motores de decisão viram comportamento assim (valores em `pestinha/ajustes.py`):",
        "",
        "| Decisão | Regra |",
        "|---|---|",
        f"| Comportamento atual (`MotorDecoder`) | o motor mais ativo, se ≥ {ns.MotorDecoder().threshold:g} Hz; sai "
        f"abaixo de {ns.MotorDecoder().threshold * ns.MotorDecoder().exit_ratio:g} Hz e fica ao menos "
        f"{ns.MotorDecoder().min_dwell:g} s. `STARTLE` ≥ {ns.MotorDecoder().threshold:g} Hz passa na frente. |",
        f"| Susto na cara (`core/emotion.py`) | `STARTLE` ≥ {emotion.STARTLE_HZ:g} Hz na subida; rearma abaixo de "
        f"{0.3 * emotion.STARTLE_HZ:g} Hz. |",
        f"| Sentar no notebook | `SENTAR` ≥ {ajustes.LIMIAR_SENTAR_HZ:g} Hz senta; < {ajustes.LIMIAR_LEVANTAR_HZ:g} Hz levanta (histerese). |",
        f"| Fugir do cantinho | `FUGIR` acima de {ajustes.LIMIAR_FUGA_HZ:g} Hz enche a vontade; {ajustes.CARGA_FUGA_HZ_S:g} Hz·s a enchem (um pico não basta). |",
        f"| Perdoar o castigo | `ACEITAR` ≥ {castigo_ctl.LIMIAR_PERDAO_HZ:g} Hz (`mind/castigo_ctl.py`): sai sozinho, sem contar fuga. |",
        f"| Olhar e virar de costas no castigo | `ANGRY` ≥ {castigo_ctl.COSTAS_HZ:g} Hz vira de costas; senão `WATCH` ≥ "
        f"{castigo_ctl.OLHAR_HZ:g} Hz olha para você. |",
        f"| Ir para o cantinho | `CANTO` ≥ {ajustes.LIMIAR_CANTO_HZ:g} Hz. |",
        f"| Travessuras | por segundo: taxa de `TRAVESSURA` × {ajustes.GANHO_TRAVESSURA:g}. |",
        f"| Cartazes do castigo | por segundo: taxa de `CARTAZ` × {ajustes.GANHO_CARTAZ:g} (cada um fica ao menos 8 s). |",
        f"| Bolinhas de papel | por segundo: taxa de `PAPEL` × {ajustes.GANHO_PAPEL:g} (só na revolução). |",
        "",
        "Regras que ainda não são da rede: as condições do corpo (dormindo, segurado, no ar), os estágios do "
        "protesto (acúmulo com limiar), o sono pela pressão de sono e pelo relógio (`core/ritmo.py`) e a escolha do tipo "
        "de travessura (memória episódica).",
        "",
    ]
    destino = RAIZ / "docs" / "REDE_NEURAL.md"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    print(f"escrito: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
