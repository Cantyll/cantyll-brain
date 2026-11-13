"""
Modelos de neurônio do BioBrain (spec, seção 5).

Dois modelos convivem na mesma rede, população por população:

- `Neuronio`: integração e disparo com vazamento (LIF), o mesmo do LIFBrain, com a mesma adaptação e o mesmo
  período refratário. É o padrão de toda população enquanto a frente NE não a migrar.
- `Izhikevich` (NE-1): o modelo de Izhikevich (2003), com os tipos RS, FS, IB, CH e LTS e corrente sináptica
  exponencial (AMPA e GABA). Nenhuma população o usa por padrão: a NE-2 a NE-4 escolhem quais migram.

Dono: T2. Depois do T2, só a frente NE edita este arquivo (plano, seção 5).
"""
import math

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


# ============================================================
# IZHIKEVICH (NE-1; spec, seção 5)
# ============================================================

# Parâmetros (a, b, c, d) de Izhikevich (2003), "Simple model of spiking neurons", IEEE TNN 14(6), fig. 2.
TIPOS = {
    "RS": (0.02, 0.20, -65.0, 8.0),     # disparo regular, com adaptação (excitatório)
    "FS": (0.10, 0.20, -65.0, 2.0),     # disparo rápido, sem adaptação (inibitório)
    "IB": (0.02, 0.20, -55.0, 4.0),     # rajada inicial, depois disparo regular
    "CH": (0.02, 0.20, -50.0, 2.0),     # rajadas repetidas (chattering)
    "LTS": (0.02, 0.25, -65.0, 2.0),    # limiar baixo, com adaptação
}
PICO = 30.0                             # mV: v ≥ PICO é disparo
TAU_AMPA = 5.0                          # ms: corrente sináptica excitatória (spec, seção 5: ≈ 5 ms)
TAU_GABA = 10.0                         # ms: corrente sináptica inibitória (spec, seção 5: ≈ 10 ms)


def repouso(tipo):
    """Tensão de repouso (mV) sem corrente: a raiz estável de 0,04v² + (5 − b)v + 140 = 0 (com u = b·v)."""
    b = TIPOS[tipo][1]
    return (-(5.0 - b) - math.sqrt((5.0 - b) ** 2 - 0.16 * 140.0)) / 0.08


def reobase(tipo):
    """
    Menor corrente constante que mantém o neurônio disparando, a partir do repouso. Com u = b·v no equilíbrio,
    o repouso perde a estabilidade numa bifurcação de Hopf quando o traço do jacobiano zera (0,08v + 5 = a, com
    b > a, o caso dos cinco tipos), em I = −(0,04v² + (5 − b)v + 140) nesse v. Sem Hopf (b ≤ a), é a sela-nó:
    I = (5 − b)² / 0,16 − 140. Vale 3,80 para RS, IB e CH, 3,94 para FS e 0,69 para LTS; a simulação com o
    passo deste módulo dá o mesmo a menos de 4% (test_bio_izhikevich.py). É a referência de `escala_de_corrente`.
    """
    a, b = TIPOS[tipo][:2]
    if b > a:
        v = (a - 5.0) / 0.08
        return -(0.04 * v * v + (5.0 - b) * v + 140.0)
    return (5.0 - b) ** 2 / 0.16 - 140.0


def escala_de_corrente(tipo, tau_m):
    """
    Quanto de corrente do modelo vale 1 unidade de entrada do LIF por ms (peso, ruído e corrente de ausência
    estão em fração do limiar por ms), para um neurônio que tinha constante de membrana τ_m (ms) no LIF.

    No LIF, entrada constante c por ms leva v a c / (1 − e^(−1/τ_m)), e o disparo vem quando isso passa de 1.
    Aqui, a mesma entrada leva a corrente a c × escala (ver Izhikevich), e o disparo vem quando ela passa da
    reobase. Com escala = reobase / (1 − e^(−1/τ_m)), a população que migra começa a disparar com a mesma
    entrada constante mínima do LIF. É o ponto de partida da calibração (NE-2 a NE-4), não a calibração: o
    que acontece com entrada que flutua depende do τ sináptico (ver `Izhikevich`).
    """
    return reobase(tipo) / (1.0 - np.exp(-1.0 / np.asarray(tau_m, dtype=float)))


class Izhikevich:
    """
    Estado e integração de um conjunto de neurônios de Izhikevich, num passo de rede de 1 ms.

    Como no artigo original (e na spec, seção 6), v é integrado em duas metades de 0,5 ms e u uma vez por ms.
    O disparo é conferido no fim do milissegundo, então cada neurônio dá no máximo um pulso por ms.

    Corrente sináptica exponencial: toda entrada em unidades do LIF por ms passa por um de dois filtros, o
    excitatório (AMPA: pesos positivos e o ruído de fundo) e o inibitório (GABA: pesos negativos e a corrente
    de ausência). Cada ms, I ← I·e^(−1/τ) + entrada × escala × (1 − e^(−1/τ)), então uma entrada constante c
    leva a corrente a exatamente c × escala: a média é a mesma do LIF, espalhada no tempo por τ.
    I = I_AMPA + I_GABA + externa.

    Com τ sináptico igual ao τ_m do LIF e a escala de `escala_de_corrente`, I / reobase é a tensão que o LIF
    teria sem o reset (test_bio_izhikevich.py). Com os τ da spec (5 e 10 ms), a entrada que flutua pesa mais
    que no LIF de τ_m longo: é a escolha que a NE-2 a NE-4 fazem por população.

    tipos: um nome de TIPOS por neurônio. escala: corrente por unidade de entrada do LIF, por neurônio.
    tau_ampa, tau_gaba: ms, um valor ou um por neurônio.
    gasto: corrente que cada pulso tira da corrente sináptica (um valor ou um por neurônio; 0 = nada). Com
    gasto = um limiar do LIF em unidades de corrente (reobase × ganho) e τ sináptico = τ_m, a corrente faz o que
    a tensão do LIF faz no reset (v − 1): a carga gasta no disparo some, o excesso fica. O Izhikevich decide
    então quando e como dispara (u, rajadas). Sem gasto, a corrente lenta continua acima da reobase depois do
    pulso e o neurônio dispara em trem enquanto ela durar.
    adapt_b, adapt_tau, limiar: a adaptação lenta do LIF (o limiar sobe adapt_b a cada pulso e volta em
    adapt_tau segundos), levada como corrente: a cada ms, tira-se adaptação × limiar da corrente, com limiar =
    um limiar do LIF em corrente (escala × (1 − e^(−1/τ_m))). O u do Izhikevich adapta em ~50 ms (RS, CH); esta é
    a de segundos que o LIF tinha. adapt_b = 0 (padrão): sem adaptação lenta, bit a bit o de antes.
    """
    modelo = "izhikevich"

    def __init__(self, tipos, escala, tau_ampa=TAU_AMPA, tau_gaba=TAU_GABA, gasto=0.0, adapt_b=0.0, adapt_tau=1.0,
                 limiar=0.0):
        tipos = list(tipos)
        self.n = len(tipos)
        desconhecidos = sorted(set(tipos) - set(TIPOS))
        if desconhecidos:
            raise ValueError(f"tipo de neurônio desconhecido: {desconhecidos}")
        self.tipos = tipos
        params = np.array([TIPOS[t] for t in tipos], dtype=float).reshape(self.n, 4)
        self.a, self.b, self.c, self.d = (params[:, k].copy() for k in range(4))
        self.escala = self._por_neuronio(escala)
        self.tau_ampa = self._por_neuronio(tau_ampa)
        self.tau_gaba = self._por_neuronio(tau_gaba)
        self.gasto = self._por_neuronio(gasto)
        if (self.tau_ampa <= 0).any() or (self.tau_gaba <= 0).any():
            raise ValueError("τ sináptico precisa ser positivo")
        self.adapt_b = self._por_neuronio(adapt_b)
        self.adapt_decay = np.exp(-1.0 / (self._por_neuronio(adapt_tau) * 1000.0))
        self.limiar = self._por_neuronio(limiar)
        self.adapt = np.zeros(self.n)
        self._adapta = bool((self.adapt_b != 0.0).any())
        self.v = np.array([repouso(t) for t in tipos], dtype=float)  # parte do repouso: sem pulso de partida
        self.u = self.b * self.v
        self.i_ampa = np.zeros(self.n)
        self.i_gaba = np.zeros(self.n)
        self.decai_ampa = np.exp(-1.0 / self.tau_ampa)
        self.decai_gaba = np.exp(-1.0 / self.tau_gaba)
        self._salto_ampa = self.escala * (1.0 - self.decai_ampa)
        self._salto_gaba = self.escala * (1.0 - self.decai_gaba)

    def _por_neuronio(self, valor):
        return np.broadcast_to(np.asarray(valor, dtype=float), (self.n,)).copy()

    def passo(self, excitatoria, inibitoria, ruido, inibidos=None, inibicao=0.0, externa=None):
        """
        Integra 1 ms e devolve quem disparou (vetor booleano).
        excitatoria, inibitoria: entrada sináptica deste ms em unidades do LIF (soma dos pesos positivos e dos
        negativos dos pulsos que chegaram). ruido: ruído de fundo em unidades do LIF por ms. inibidos e
        inibicao: como no LIF (corrente de ausência). externa: corrente direta no modelo, para testes e calibração.
        """
        entrada_inh = inibitoria
        if inibidos is not None:
            entrada_inh = np.array(inibitoria, dtype=float, copy=True)
            entrada_inh[inibidos] -= inibicao
        self.i_ampa *= self.decai_ampa
        self.i_ampa += (excitatoria + ruido) * self._salto_ampa
        self.i_gaba *= self.decai_gaba
        self.i_gaba += entrada_inh * self._salto_gaba
        corrente = self.i_ampa + self.i_gaba
        if externa is not None:
            corrente = corrente + externa
        if self._adapta:
            corrente = corrente - self.adapt * self.limiar

        v, u = self.v, self.u
        v += 0.5 * (0.04 * v * v + 5.0 * v + 140.0 - u + corrente)
        ja = v >= PICO                                       # passou do pico na 1ª metade: não integra a 2ª
        np.minimum(v, PICO, out=v)
        v += np.where(ja, 0.0, 0.5 * (0.04 * v * v + 5.0 * v + 140.0 - u + corrente))
        np.minimum(v, PICO, out=v)
        u += self.a * (self.b * v - u)

        disparou = v >= PICO
        v[disparou] = self.c[disparou]
        u[disparou] += self.d[disparou]
        self.i_ampa[disparou] -= self.gasto[disparou]
        if self._adapta:                                     # como no LIF: decai, e o pulso soma adapt_b
            self.adapt *= self.adapt_decay
            self.adapt[disparou] += self.adapt_b[disparou]
        return disparou
