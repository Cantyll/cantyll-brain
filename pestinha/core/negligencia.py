"""
NEGLIGÊNCIA (R1): você está presente, mas não interage com o pet por um tempo.

Diferente da ausência (você saiu do computador, detectado por `AWAY`), aqui a guarda de ausência só liga depois
de `limite_s` segundos de presença sem interação. Interagir zera o tempo: carinho, cutucada, arrasto, arremesso e
dispensa de travessura (controle/interacao.py e App.think).

- O tempo só passa enquanto você está presente. Ausente, ele para: a ausência já segura a rede por conta própria.
- Uma vez ligada, a guarda só desliga com interação. Voltar ao computador, sozinho, não a desliga.
- Na pausa, App.think não chama `tick`, então a pausa não conta.

Puro: sem Qt e sem relógio do sistema. Quem chama passa o dt em segundos.
"""


class Negligencia:
    """Conta quanto tempo você está presente sem interagir com o pet, e diz quando isso vira negligência."""

    def __init__(self, limite_s):
        self.limite_s = float(limite_s)
        self.parado_s = 0.0

    def tick(self, dt_s, presente):
        """Soma dt_s só se você está presente. Ausente, o tempo não passa para a negligência."""
        if presente and dt_s > 0:
            self.parado_s += dt_s

    def interagiu(self):
        """Você interagiu com o pet: a contagem recomeça do zero."""
        self.parado_s = 0.0

    @property
    def ativa(self):
        """True quando já são `limite_s` segundos presente sem interagir."""
        return self.parado_s >= self.limite_s
