"""
Neuromoduladores globais: `Neuromod` (spec, seção 8). Donos: PL-1 (ACh na taxa de aprendizado) e PL-2 (A e S, com S no lugar do acumulador de queixa).

PL-1 (parte 1) preenche só a acetilcolina. ACh vai de 0 a 1 e segue a atividade do pool FOCUS com τ = PL_ACH_TAU_S:
programando, ela sobe perto de 1; à toa, cai perto de 0. A taxa de aprendizado efetiva acordado é
η · (0,5 + ACh) (spec, seção 7.4). Variável global, não neurônio (spec, seção 4).

O replay da noite não usa a ACh: no sono de ondas lentas ela é baixa e o replay já tem a própria taxa
(REPLAY_FATOR). Fica registrado como escolha desta parte, não como medida.
"""
import math

from ... import ajustes


class Neuromod:
    """Estado dos moduladores. Nesta parte, só `ach`."""

    def __init__(self):
        self.ach = 0.0
        self.ach_fixa = None            # simulação sem pulsos: a ACh do contexto, dada de fora (None no app)

    def atualizar(self, focus_hz, dt):
        """Um passo de `dt` segundos com o FOCUS disparando a `focus_hz` (Hz por neurônio)."""
        if self.ach_fixa is not None:
            self.ach = self.ach_fixa
            return
        alvo = min(1.0, max(0.0, float(focus_hz) / ajustes.PL_ACH_REF_HZ))
        if dt > 0.0:
            self.ach += (alvo - self.ach) * (1.0 - math.exp(-dt / ajustes.PL_ACH_TAU_S))

    def fator_aprendizado(self):
        """η_eff / η = 0,5 + ACh."""
        return 0.5 + self.ach

    def estado(self):
        return {"ach": round(float(self.ach), 6)}

    def carregar(self, dados):
        """Restaura a ACh. Valor ausente ou inválido: False e nada muda."""
        if not isinstance(dados, dict):
            return False
        ach = dados.get("ach")
        if isinstance(ach, bool) or not isinstance(ach, (int, float)) or not math.isfinite(ach) or not 0.0 <= ach <= 1.0:
            return False
        self.ach = float(ach)
        return True
