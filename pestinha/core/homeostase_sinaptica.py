"""
HOMEOSTASE SINÁPTICA (spec, seção 9.4; decisão D4, hipótese SHY): o sono desfaz uma parte do
aprendizado, e o replay só empurra uma sinapse até uma fração do seu limite.

Funções puras sobre a matriz de sinapses aprendidas (linhas: canais sensoriais; colunas: populações
plásticas). Não dependem do modelo de neurônio: qualquer rede que aprenda por essa matriz usa estas
funções, seja LIF, Izhikevich ou outra. O que muda entre modelos é a calibração de HOMEOSTASE_TETO
e HOMEOSTASE_SHY em ajustes.py, se os números de aprendizado mudarem.
"""

import numpy as np


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
