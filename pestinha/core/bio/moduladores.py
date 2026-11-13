"""
Neuromoduladores globais: `Neuromod` (spec, seção 8). Donos: PL-1 (ACh na taxa de aprendizado) e PL-2 (A e S, com S no lugar do acumulador de queixa).

PL-1 (parte 1) preenche só a acetilcolina. ACh vai de 0 a 1 e segue a atividade do pool FOCUS com τ = PL_ACH_TAU_S:
programando, ela sobe perto de 1; à toa, cai perto de 0. A taxa de aprendizado efetiva acordado é
η · (0,5 + ACh) / (0,5 + Ā), em que Ā é a média lenta da ACh (τ = PL_ACH_MEDIA_H). A spec (seção 7.4) diz
η · (0,5 + ACh); a divisão pela média faz a ACh mudar QUANDO ele aprende (mais com atenção, menos à toa), sem
mudar QUANTO ele aprende no dia. Sem ela, quem passa pouco tempo programando aprende a metade (regra 8).

Mesmo normalizada, a ACh tira PLAYFUL e CALM da faixa da regra 8 no misto e no carinhoso (o aprendizado se
concentra no contexto de programação, e o efeito no comportamento não é linear). Por isso ela fica atrás de
ajustes.PL_ACH, desligada: a ACh segue sendo medida, mas o fator é 1 até a parte 2 do PL-1 trazer um
critério próprio. Variável global, não neurônio (spec, seção 4).

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
        self.ach_media = ajustes.PL_ACH_MEDIA_INICIAL
        self.ach_media_fixa = None      # simulação: a média do dia, dada de fora (None no app)

    def atualizar(self, focus_hz, dt):
        """Um passo de `dt` segundos com o FOCUS disparando a `focus_hz` (Hz por neurônio)."""
        if self.ach_fixa is not None:
            self.ach = self.ach_fixa
        else:
            alvo = min(1.0, max(0.0, float(focus_hz) / ajustes.PL_ACH_REF_HZ))
            if dt > 0.0:
                self.ach += (alvo - self.ach) * (1.0 - math.exp(-dt / ajustes.PL_ACH_TAU_S))
        if self.ach_media_fixa is not None:
            self.ach_media = self.ach_media_fixa
        elif dt > 0.0:
            self.ach_media += (self.ach - self.ach_media) * (1.0 - math.exp(-dt / (ajustes.PL_ACH_MEDIA_H * 3600.0)))

    def fator_aprendizado(self):
        """η_eff / η = (0,5 + ACh) / (0,5 + Ā). Com ajustes.PL_ACH desligado, 1 (a ACh é medida, mas não muda a taxa)."""
        if not ajustes.PL_ACH:
            return 1.0
        return (0.5 + self.ach) / (0.5 + self.ach_media)

    def estado(self):
        return {"ach": round(float(self.ach), 6), "ach_media": round(float(self.ach_media), 6)}

    def carregar(self, dados):
        """Restaura a ACh e a média. Valor inválido: False e nada muda. Média ausente (save antigo): a inicial."""
        if not isinstance(dados, dict):
            return False
        ach = dados.get("ach")
        media = dados.get("ach_media", ajustes.PL_ACH_MEDIA_INICIAL)
        if not (_fracao(ach) and _fracao(media)):
            return False
        self.ach, self.ach_media = float(ach), float(media)
        return True


def _fracao(valor):
    """Número finito de 0 a 1 (não bool)."""
    return (not isinstance(valor, bool) and isinstance(valor, (int, float)) and math.isfinite(valor)
            and 0.0 <= valor <= 1.0)
