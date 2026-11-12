"""
HOMEOSTASE SINÁPTICA (spec, seções 7.3 e 9.4; decisão D4, hipótese SHY): o sono desfaz uma parte do
aprendizado, o replay só empurra uma sinapse até uma fração do seu limite, e nenhuma população
plástica fica muda: se a resposta dela cai abaixo de um piso, as entradas dela são escaladas para
cima (piso por taxa-alvo).

Nada aqui depende do modelo de neurônio. As funções trabalham sobre a matriz de sinapses aprendidas
(linhas: canais sensoriais; colunas: populações plásticas), e `HomeostaseDoSono` fala com a rede só
pela interface `Brain` (`downscaling_sono`, `ensaio_piso`, `escalonar_piso`). O que muda entre LIF,
Izhikevich ou outro modelo é como a rede mede a própria resposta, e a calibração de HOMEOSTASE_TETO,
HOMEOSTASE_SHY e HOMEOSTASE_PISO em ajustes.py, se os números de aprendizado mudarem.

A taxa-alvo não é um número em Hz. O ensaio usa momentos que ele viveu (o padrão sensorial dos
episódios que o replay da noite escolheu) e compara duas respostas a eles: a da rede como está e a
da mesma rede sem nada aprendido. O piso é uma fração da segunda. Assim o critério vale para
qualquer modelo de neurônio, qualquer temperamento e qualquer rotina de uso.
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


def escalonamento_piso(aprendido, base, razoes, piso, passo, limite_max, limite_min):
    """
    Escalonamento homeostático para cima (spec, seção 7.3), só nas populações abaixo do piso. Cada
    entrada da população é escalada em `passo`: a excitatória cresce e a inibitória encolhe. A conta é
    sobre o peso total (inato + aprendido), e o resultado volta para a matriz aprendida:
    aprendido += passo · |base + aprendido|. Onde não há sinapse (base e aprendido zero), nada é
    criado. As diferenças entre sinapses, que são o que ele aprendeu, se mantêm em proporção.

    razoes: por coluna, resposta atual dividida pela de referência. base: mesma forma de `aprendido`.
    """
    if not 0.0 < piso <= 1.0:
        raise ValueError("piso fora de (0, 1]")
    if not 0.0 <= passo <= 1.0:
        raise ValueError("passo fora de [0, 1]")
    fator = np.where(np.asarray(razoes, dtype=float) < piso, passo, 0.0)      # por coluna
    return np.clip(aprendido + fator * np.abs(base + aprendido), limite_min, limite_max)


def escolher_padroes(padroes, quantos):
    """Até `quantos` padrões, espalhados por igual na lista (que vem em ordem de prioridade do replay)."""
    padroes = list(padroes)
    if len(padroes) <= quantos:
        return padroes
    return [padroes[(i * len(padroes)) // quantos] for i in range(quantos)]


class HomeostaseDoSono:
    """
    Reparte a homeostase do sono pelo sono cumprido. A medida é a pressão de sono descarregada (o mesmo
    P que decide dormir e acordar): uma noite inteira descarrega de LIMIAR_DORME_PRESSAO a
    LIMIAR_ACORDA_PRESSAO. Um cochilo descarrega pouco e desfaz pouco; vários sonos curtos somam o
    mesmo que um longo.

    A noite é dividida em HOMEOSTASE_AJUSTES_NOITE parcelas. A cada parcela cumprida:
      1. SHY: a rede desfaz a parte dela de HOMEOSTASE_SHY (a noite inteira dá HOMEOSTASE_SHY).
      2. Piso: depois que o replay acabou, a rede ensaia a própria resposta aos padrões da noite.
         População abaixo do piso tem as entradas escaladas em HOMEOSTASE_PISO_PASSO. Com todas
         acima do piso, os ensaios param até o próximo sono.
    """

    def __init__(self):
        """Começa sem sono acumulado."""
        self.pressao = None             # última pressão vista dormindo (None: acordado)
        self.sono = 0.0                 # fração de noite cumprida e ainda não usada (sobra de um sono vale para o seguinte)
        self.padroes = []               # padrões sensoriais do ensaio deste sono
        self.ensaio_pendente = False    # há um ajuste de piso a fazer
        self.piso_em_dia = False        # o último ensaio deste sono deu todas as populações acima do piso
        self.razoes = {}                # último ensaio: {população: resposta / referência}
        self.ajustes_piso = 0           # quantas vezes o piso escalou alguma população (para o log e a simulação)

    @staticmethod
    def noite():
        """Pressão descarregada numa noite inteira."""
        return max(0.05, ajustes.LIMIAR_DORME_PRESSAO - ajustes.LIMIAR_ACORDA_PRESSAO)

    def adormecer(self, pressao, padroes=()):
        """Começo de um sono: a conta parte da pressão deste instante. padroes: os padrões sensoriais do replay desta noite."""
        self.pressao = float(pressao)
        self.padroes = escolher_padroes(padroes, ajustes.HOMEOSTASE_PISO_PADROES)
        self.ensaio_pendente = False
        self.piso_em_dia = False

    def acordar(self):
        """Fim do sono: ensaio pela metade é abandonado. A fração de noite que sobrou fica para o próximo sono."""
        self.pressao = None
        self.ensaio_pendente = False

    def passo(self, brain, pressao, orcamento_ms, replay_pendente=False):
        """
        Chamar a cada quadro dormindo. Aplica o SHY das parcelas cumpridas desde a última chamada e avança
        o ensaio do piso com até `orcamento_ms` de simulação. Devolve os milissegundos usados.
        """
        if self.pressao is None:
            self.adormecer(pressao)
        self.sono += max(0.0, self.pressao - pressao) / self.noite()
        self.pressao = float(pressao)
        parcela = 1.0 / ajustes.HOMEOSTASE_AJUSTES_NOITE
        while self.sono >= parcela:
            self.sono -= parcela
            brain.downscaling_sono(1.0 - (1.0 - ajustes.HOMEOSTASE_SHY) ** parcela)
            if ajustes.HOMEOSTASE_PISO > 0 and self.padroes and not self.piso_em_dia:
                self.ensaio_pendente = True
        if not self.ensaio_pendente or replay_pendente or orcamento_ms <= 0:
            return 0
        usado, razoes = brain.ensaio_piso(self.padroes, orcamento_ms)
        if razoes is not None:
            self.ensaio_pendente = False
            self.razoes = dict(razoes)
            if not razoes or min(razoes.values()) >= ajustes.HOMEOSTASE_PISO:
                self.piso_em_dia = True
            else:
                brain.escalonar_piso(razoes, ajustes.HOMEOSTASE_PISO, ajustes.HOMEOSTASE_PISO_PASSO)
                self.ajustes_piso += 1
        return usado
