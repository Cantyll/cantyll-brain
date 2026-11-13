"""
CONDICIONAMENTO - ele aprende a reagir ANTES do que costuma acontecer com ele.

Cue (sinal antecipador): algo que costuma vir antes de uma interação.
    PRESS      você apertou o botão do mouse em cima dele
    APPROACH   o cursor veio rápido na direção dele
    PLACA      você o carrega perto da placa do cantinho (desfecho: ficar preso)

Desfecho (o que aconteceu de fato): cutucada, arraste ou arremesso.

Regra (Rescorla-Wagner, por episódio):
    cada vez que um cue termina, V += taxa * (λ - V)
    λ = 1 se houve desfecho até WINDOW s depois do fim do cue, senão λ = 0
Então, se você sempre joga ele depois de apertar o mouse em cima, V(PRESS)
sobe, e ele reage ao PRESS sozinho. Se você apertar e soltar sem nada depois,
V cai: é a extinção, e ele volta a não se assustar.

A força antecipada (V do cue ativo) vai para a rede como o canal ANTICIPATE,
que liga em ALERT e STARTLE. Ou seja, o reflexo antecipado sai da rede, não
de um "se apertar, pule".
"""

import math

import numpy as np

from ..store import read_json, write_json

WINDOW = 1.5                # s: desfecho até aqui depois do cue conta como consequência
JANELAS = {"PLACA": 4.0}    # s por pista: a placa espera a queda e o pouso no canto (até 3 s)
MIN_V = 0.0
MAX_V = 1.0


class Conditioning:
    """Condicionamento: aprende que um sinal (ex.: a placa do castigo) anuncia algo, e começa a reagir antes de acontecer."""
    def __init__(self, path=None, rate=0.12):
        """Guarda o arquivo e a taxa de aprendizado (quanto cada repetição muda a associação)."""
        self.path = path
        self.rate = rate
        self.V = {"PRESS": 0.0, "APPROACH": 0.0, "PLACA": 0.0}
        self.active = {}           # cue -> {"start": t, "hit": bool}
        self.ended = []            # [cue, fim, teve_desfecho]; viram aprendizado após WINDOW

    # ---------------- observação ----------------

    def set_cue(self, cue, on, now):
        """Liga ou desliga um sinal (cue); enquanto ele está ligado, espera-se o resultado."""
        if on and cue not in self.active:
            self.active[cue] = {"start": now, "hit": False}
        elif not on and cue in self.active:
            info = self.active.pop(cue)
            self.ended.append([cue, now, info["hit"]])

    def outcome(self, now, cues=("PRESS", "APPROACH")):
        """
        Algo aconteceu com ele: marca os cues desse tipo de desfecho que vieram antes.
        Cutucada, arraste e arremesso são desfechos de PRESS/APPROACH; ficar preso é o da PLACA.
        """
        for cue, info in self.active.items():
            if cue in cues:
                info["hit"] = True
        for ep in self.ended:
            if ep[0] in cues and now - ep[1] <= JANELAS.get(ep[0], WINDOW):
                ep[2] = True

    # ---------------- aprendizado ----------------

    def tick(self, now):
        """Fecha episódios vencidos e atualiza V (Rescorla-Wagner)."""
        still = []
        for ep in self.ended:
            cue, end, hit = ep
            if now - end < JANELAS.get(cue, WINDOW):
                still.append(ep)
                continue
            lam = 1.0 if hit else 0.0
            v = self.V.get(cue, 0.0)
            self.V[cue] = min(MAX_V, max(MIN_V, v + self.rate * (lam - v)))
        self.ended = still

    def deslocar(self, segundos):
        """Desconta uma pausa dos relógios das pistas e dos episódios ainda aguardando desfecho."""
        for info in self.active.values():
            info["start"] += segundos
        for ep in self.ended:
            ep[1] += segundos

    def expectancy(self):
        """Força antecipada agora: V de cada cue que está ativo."""
        return {cue: self.V.get(cue, 0.0) for cue in self.active}

    def strength(self, cues=("PRESS", "APPROACH")):
        """Força antecipada só das pistas pedidas: cada tipo de desfecho vai para o seu canal."""
        return max((v for cue, v in self.expectancy().items() if cue in cues), default=0.0)

    # ---------------- persistência ----------------

    def save(self):
        """Grava o aprendizado em conditioning.json (nada se não houver caminho)."""
        if self.path is None:
            return
        write_json(self.path, {"V": self.V})

    def load(self):
        """Lê o aprendizado salvo, validando os valores (valor inválido volta ao zero)."""
        if self.path is None:
            return
        data = read_json(self.path, default=None)
        if isinstance(data, dict) and isinstance(data.get("V"), dict):
            for cue, v in data["V"].items():
                if cue in self.V and isinstance(v, (int, float)) and math.isfinite(v):
                    self.V[cue] = min(MAX_V, max(MIN_V, float(v)))


# ---------------------------------------------------------------------------
# CRÍTICO (PL-1; decisão D3): o V de δ = r − V para a plasticidade do BioBrain.
# ---------------------------------------------------------------------------

class Critico:
    """
    Quanto de recompensa ele espera daqui para a frente, pelas pistas que sente agora: V = w · x, com x o nível
    de cada canal lido. O erro de predição é o da diferença temporal (TD(0); Schultz, Dayan e Montague, 1997):

        δ = r · dt + γ · V(agora) − V(antes),   γ = e^(−dt / τ_V)

    δ já é uma quantidade de recompensa no passo (não uma taxa). Sem pista nenhuma, V = 0 e δ = r · dt: a regra
    antiga, de recompensa bruta. Com uma pista que sempre vem antes da recompensa, V(pista) aprende a recompensa
    que vem depois dela; quando a pista some e a recompensa chega, uma cancela a outra e δ fica perto de zero
    (R2). Se a recompensa não vier, δ fica negativo quando a pista some (extinção). Como V é a soma das pistas,
    uma pista nova que chega junto com uma já aprendida quase não aprende (bloqueio de Kamin).

    Aprende com w += taxa · δ · z, em que z é o traço de elegibilidade das mesmas pistas (TD(λ)): a recompensa
    que chega até alguns segundos depois de a pista sumir ainda é creditada a ela. A taxa vale por passo de até
    PASSO_REF segundos (um passo mais longo conta como um só) e é dividida por |z|² quando ele passa de 1, para
    não oscilar com muitas pistas juntas. Puro (numpy), sem Qt. O estado é só o vetor de pesos, um número por
    canal (R6).
    """

    PASSO_REF = 0.1             # s: o passo do app (think); passo maior aprende como um

    def __init__(self, n, taxa, limite, tau_v):
        self.w = np.zeros(int(n))
        self.taxa = float(taxa)
        self.limite = float(limite)
        self.tau_v = float(tau_v)
        self.x_antes = None

    def valor(self, x):
        """V para os níveis x."""
        return float(self.w @ x)

    def passo(self, x, z, recompensa, dt):
        """
        Um passo de `dt` segundos com recompensa (taxa) `recompensa`, níveis x agora e o traço z. Devolve δ do passo.
        """
        x = np.asarray(x, dtype=float)
        gama = math.exp(-max(0.0, dt) / self.tau_v) if self.tau_v > 0 else 0.0
        antes = 0.0 if self.x_antes is None else self.valor(self.x_antes)
        delta = float(recompensa) * max(0.0, dt) + gama * self.valor(x) - antes
        if self.taxa > 0.0 and dt > 0.0:
            z = np.asarray(z, dtype=float)
            alfa = self.taxa * min(1.0, dt / self.PASSO_REF) / max(1.0, float(z @ z))   # normalizado: não oscila
            self.w = np.clip(self.w + alfa * delta * z, -self.limite, self.limite)
        self.x_antes = x.copy()
        return delta

    def esquecer_o_passo(self):
        """Corta a ligação com o passo anterior (depois de carregar ou de um salto no tempo)."""
        self.x_antes = None

    def downscaling(self, fracao):
        """O sono desfaz no crítico a mesma fração que o SHY tira das sinapses (decisão D4)."""
        self.w = self.w * (1.0 - float(fracao))

    def estado(self):
        """Pesos como lista (para salvar)."""
        return [round(float(v), 6) for v in self.w]

    def carregar(self, valores):
        """Restaura os pesos. Tamanho errado ou valor não finito: False e nada muda."""
        if not isinstance(valores, list) or len(valores) != len(self.w):
            return False
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in valores):
            return False
        self.w = np.clip(np.array(valores, dtype=float), -self.limite, self.limite)
        self.x_antes = None
        return True
