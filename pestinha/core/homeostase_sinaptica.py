"""
HOMEOSTASE SINÁPTICA (spec, seção 9.4; decisão D4, hipótese SHY): o sono desfaz uma parte do
aprendizado, na medida do sono cumprido, e o replay só empurra uma sinapse até uma fração do seu
limite.

Nada aqui depende do modelo de neurônio. As funções trabalham sobre a matriz de sinapses aprendidas
(linhas: canais sensoriais; colunas: populações plásticas), e `HomeostaseDoSono` fala com a rede só
pela interface `Brain` (`downscaling_sono`). O que muda entre LIF, Izhikevich ou outro modelo é a
calibração de HOMEOSTASE_TETO e HOMEOSTASE_SHY em ajustes.py, se os números de aprendizado mudarem.
"""

import numpy as np

from .. import ajustes


def downscaling(aprendido, fracao):
    """SHY: cada sinapse aprendida perde `fracao` do seu valor. O sinal e o zero se mantêm."""
    if not 0.0 <= fracao < 1.0:
        raise ValueError("fração de downscaling fora de [0, 1)")
    return aprendido * (1.0 - fracao)


def saturacao(variacao, aprendido, teto, limite_max, limite_min):
    """
    Fator de 0 a 1 que o replay aplica a cada variação. Empurrar uma sinapse para longe de zero,
    no mesmo sentido do valor atual, perde força conforme ela chega a `teto` do limite. Puxar de
    volta para zero não é freado.
    """
    if not 0.0 < teto <= 1.0:
        raise ValueError("teto fora de (0, 1]")
    alvo = np.where(variacao > 0, teto * limite_max, teto * -limite_min)
    mesmo_sentido = (np.sign(variacao) == np.sign(aprendido)) & (aprendido != 0)
    return np.where(mesmo_sentido, np.clip(1.0 - np.abs(aprendido) / alvo, 0.0, 1.0), 1.0)


class HomeostaseDoSono:
    """
    Reparte o SHY pelo sono cumprido. A medida é a pressão de sono descarregada (o mesmo P que decide
    dormir e acordar): uma noite inteira descarrega de LIMIAR_DORME_PRESSAO a LIMIAR_ACORDA_PRESSAO.
    Um cochilo descarrega pouco e desfaz pouco; vários sonos curtos somam o mesmo que um longo.
    Adormecer e acordar sem ter dormido não desfaz nada.

    A noite é dividida em HOMEOSTASE_AJUSTES_NOITE parcelas. A cada parcela cumprida, a rede desfaz a
    parte dela de HOMEOSTASE_SHY (a noite inteira dá HOMEOSTASE_SHY).
    """

    def __init__(self):
        """Começa sem sono acumulado."""
        self.pressao = None             # última pressão vista dormindo (None: acordado)
        self.sono = 0.0                 # fração de noite cumprida e ainda não usada (sobra de um sono vale para o seguinte)

    @staticmethod
    def noite():
        """Pressão descarregada numa noite inteira."""
        return max(0.05, ajustes.LIMIAR_DORME_PRESSAO - ajustes.LIMIAR_ACORDA_PRESSAO)

    def adormecer(self, pressao):
        """Começo de um sono: a conta parte da pressão deste instante."""
        self.pressao = float(pressao)

    def acordar(self):
        """Fim do sono. A fração de noite que sobrou fica para o próximo sono."""
        self.pressao = None

    def passo(self, brain, pressao):
        """Chamar a cada quadro dormindo. Aplica o SHY das parcelas cumpridas desde a última chamada."""
        if self.pressao is None:
            self.adormecer(pressao)
        self.sono += max(0.0, self.pressao - pressao) / self.noite()
        self.pressao = float(pressao)
        parcela = 1.0 / ajustes.HOMEOSTASE_AJUSTES_NOITE
        while self.sono >= parcela:
            self.sono -= parcela
            brain.downscaling_sono(1.0 - (1.0 - ajustes.HOMEOSTASE_SHY) ** parcela)
