"""
Plasticidade do BioBrain com erro de predição (PL-1, parte 1; spec, seções 7.2 e 7.4; decisão D3). Dono: PL-1.

Desligada (ajustes.PL_DELTA = False), o BioBrain aprende como o LIF: δ = r − expected com expected = 0 no app,
ou seja, recompensa bruta. Ligada, δ é o erro de diferença temporal do crítico (core/conditioning.py, decisão
D3): δ = r·dt + γ·V(agora) − V(antes). Com ajustes.PL_ACH (desligada por padrão), a taxa acordado também segue a
acetilcolina (core/bio/moduladores.py).
O que muda no pet:

- recompensa prevista deixa de ensinar (R2): se ele sempre ganha carinho depois de um pedido, o carinho depois
  do pedido para de reforçar o pedido;
- recompensa que não vem quando era esperada ensina para o outro lado (δ < 0), como na extinção;
- o crítico lê só as pistas (ajustes.PL_CANAIS_CRITICO), não o contexto nem a sensação da própria recompensa.
  Lendo o contexto, o crítico aprenderia a recompensa média de cada contexto, e o aprendido ficaria preso a
  ela: o que um carinho ensina, as horas seguintes no mesmo contexto sem carinho desensinam. Carinho e bagunça
  são raros no dia, então quase nada ficaria aprendido. Lendo só as pistas, recompensa sem pista ensina o
  contexto exatamente como antes (V = 0, δ = r·dt), e recompensa anunciada por uma pista deixa de ensinar;
- o crítico perde a mesma fração que o SHY tira das sinapses a cada sono. Sem isso, o crítico continuaria
  prevendo tudo, δ ficaria em zero, e o SHY apagaria o aprendido noite após noite. Com isso, o que o sono
  tira o dia seguinte devolve, se a recompensa continuar vindo.

A regra ainda é por níveis: a elegibilidade de cada canal sensorial (τ = ELIGIBILITY_TAU) vezes δ, aplicada à
matriz `learned` (canal × população plástica), como no LIF. A STDP por pulso (traço de 20 ms por sinapse) é a
parte 2 do PL-1, depois do NE-1 na main, porque depende do modelo de neurônio que o NE-1 está trocando.

Puro (numpy), sem Qt.
"""
import numpy as np

from ... import ajustes
from ..conditioning import Critico
from .moduladores import Neuromod


class PlasticidadeDelta:
    """Crítico e moduladores do aprendizado de um BioBrain."""

    def __init__(self, canais):
        canais = list(canais)
        lidos = ajustes.PL_CANAIS_CRITICO
        self.mascara = np.array([1.0 if lidos is None or c in lidos else 0.0 for c in canais])
        self.critico = Critico(len(canais), ajustes.PL_CRITICO_TAXA, ajustes.PL_CRITICO_LIMITE, ajustes.PL_CRITICO_TAU_S)
        self.neuromod = Neuromod()
        self.ultimo_delta = 0.0         # δ do último passo (no começo dele), para o monitor e os testes
        self.ultimo_valor = 0.0         # V do último passo

    def passo(self, niveis, elegibilidade, recompensa, esperado, dt, focus_hz, em_replay=False):
        """
        Um passo de aprendizado com os níveis sensoriais de agora. Devolve (δ do passo, já em recompensa × tempo,
        e o fator da taxa). A rede multiplica isso pela taxa e pela elegibilidade de cada canal. `esperado` (de um
        módulo, decisão D3) é uma taxa que sai da recompensa antes do crítico.
        """
        if not em_replay:
            self.neuromod.atualizar(focus_hz, dt)
        x = np.asarray(niveis, dtype=float) * self.mascara
        self.ultimo_valor = self.critico.valor(x)
        z = np.asarray(elegibilidade, dtype=float) * self.mascara
        self.ultimo_delta = self.critico.passo(x, z, float(recompensa) - float(esperado), dt)
        fator = 1.0 if em_replay else self.neuromod.fator_aprendizado()
        return self.ultimo_delta, fator

    def downscaling(self, fracao):
        """SHY: o crítico perde a mesma fração que as sinapses (ver o cabeçalho)."""
        self.critico.downscaling(fracao)

    def estado(self):
        return {"critico": self.critico.estado(), "moduladores": self.neuromod.estado()}

    def carregar(self, dados):
        """Restaura crítico e moduladores. Algo inválido: False e nada muda."""
        if not isinstance(dados, dict):
            return False
        critico = Critico(len(self.critico.w), self.critico.taxa, self.critico.limite, self.critico.tau_v)
        neuromod = Neuromod()
        if not critico.carregar(dados.get("critico")) or not neuromod.carregar(dados.get("moduladores")):
            return False
        self.critico, self.neuromod = critico, neuromod
        return True


def criar(canais):
    """A plasticidade do PL-1 (canais: nomes dos canais sensoriais) se a chave estiver ligada; senão None."""
    return PlasticidadeDelta(canais) if ajustes.PL_DELTA else None


__all__ = ["PlasticidadeDelta", "criar"]
