"""
Modelo de neurônio do BioBrain (spec, seção 5).

Nesta fase (T2) todas as populações usam o mesmo neurônio de integração e disparo com vazamento (LIF) do
LIFBrain, com a mesma adaptação e o mesmo período refratário: a paridade com o LIF vem primeiro. A troca para
Izhikevich (tipos RS, FS, IB, CH e LTS) é a frente NE (NE-1 a NE-4), população por população.

Dono: T2. Depois do T2, só a frente NE edita este arquivo (plano, seção 5).
"""
import numpy as np

from ..nervous_system import T_REF


class Neuronio:
    """
    Estado e integração de um conjunto de neurônios LIF, num passo de 1 ms.
    tau_m em ms; adapt_b é o salto do limiar a cada disparo; adapt_tau, em s, o tempo de volta do limiar.
    """
    modelo = "lif"

    def __init__(self, tau_m, adapt_b, adapt_tau):
        tau_m = np.asarray(tau_m, dtype=float)
        self.n = tau_m.size
        self.decay = np.exp(-1.0 / tau_m)
        self.adapt_b = np.asarray(adapt_b, dtype=float)
        self.adapt_decay = np.exp(-1.0 / (np.asarray(adapt_tau, dtype=float) * 1000.0))
        self.v = np.zeros(self.n)
        self.a = np.zeros(self.n)
        self.ref = np.zeros(self.n, dtype=int)

    def passo(self, corrente, ruido, inibidos=None, inibicao=0.0):
        """
        Integra 1 ms e devolve quem disparou (vetor booleano). A ordem das contas é a do LIFBrain:
        vazamento, corrente sináptica, ruído, corrente inibitória dos `inibidos`, refratário, piso de −0,5,
        disparo contra o limiar adaptado (1 + a) e adaptação.
        """
        v = self.v
        v *= self.decay
        v += corrente
        v += ruido
        if inibidos is not None:
            v[inibidos] -= inibicao

        em_refratario = self.ref > 0
        v[em_refratario] = 0.0
        self.ref[em_refratario] -= 1
        np.maximum(v, -0.5, out=v)

        disparou = v >= (1.0 + self.a)
        v[disparou] = 0.0
        self.ref[disparou] = T_REF
        self.a *= self.adapt_decay
        self.a[disparou] += self.adapt_b[disparou]
        return disparou
