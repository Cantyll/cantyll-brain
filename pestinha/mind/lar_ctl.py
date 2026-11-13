"""
LAR_CTL - o lar como módulo de frente (LAR-1): a cama no canto, e ir para ela quando o sono chega.

Entra pelo registro de módulos (core/modulos.py) com a chave config.FRENTES["lar"], desligada por
padrão. Desligada, nada disto existe: nem a cama, nem a pasta, nem o pedido de ir para a cama.

O que faz:
    - mostra a cama (world/lar.py) junto com o pet e a esconde junto com ele: tela cheia, esconder
      e pânico escondem a cama também, porque ela segue a janela do pet, não o relógio da rede;
    - com sono chegando (perto dos limiares de core/ritmo.py), pede ao comportamento que vá até a
      cama, devagar. Ele dorme quando o ritmo mandar, como antes: o lar não decide o sono, só onde.
      Se o sono vier antes de ele chegar (sono forçado, a cama em outro monitor sem passagem),
      ele dorme onde estiver;
    - conta quantos sonos começaram na cama e fora dela (fotografia diária e modulos/lar/lar.json).

A parte de necessidades da opção A (lazer no lar, decidida pelo Cantyll em 2026-11-12):
    - a travessura que vem do tédio, em paz, vira travessura de casa (mind/mischief_ctl.py chama
      `travessura`): ele vai até a cama, pula nela por LAR_DURACAO_BAGUNCA e a deixa bagunçada
      até ir dormir. Tira o tédio como a travessura da tela, sem nada na sua tela;
    - dispensar uma travessura ou arrancar um cartaz deixa de contar como atenção (carência).

Não toca a rede: nenhum canal novo, nenhuma recompensa (o reforço do lar espera o PL-1, regra R2).
Na pausa e no pânico o app não chama o módulo; o pedido de ir para a cama vence em
LAR_VALIDADE_CAMA e ele volta ao passeio normal se o módulo sair do registro por defeito.
"""

import time

from PySide6.QtCore import QEvent, QObject

from .. import ajustes
from ..core.modulos import Modulo
from ..core.ritmo import circadiano, quer_dormir
from ..store import read_json, write_json
from ..world.lar import Cama

ARQUIVO = "lar.json"


def sonolento(pressao, c):
    """Diz se o sono está chegando: o ritmo mandaria dormir com a pressão e o relógio um pouco à frente."""
    return quer_dormir(pressao + ajustes.LAR_MARGEM_PRESSAO, c - ajustes.LAR_MARGEM_C)


def deitado(body, x_cama):
    """Diz se o corpo está na cama: no chão (não numa janela), apoiado, e perto do meio dela."""
    return (body.grounded and body.platform is None and not body.held
            and abs(body.x - x_cama) < ajustes.LAR_CHEGOU_CAMA)


class _SegueOPet(QObject):
    """Mostra a cama quando a janela do pet aparece e a esconde quando ela some."""

    def __init__(self, cama, pet):
        super().__init__(pet)
        self.cama = cama
        self.pet = pet

    def eventFilter(self, obj, event):
        """Show e Hide da janela do pet valem também para a cama. Não consome o evento."""
        if obj is self.pet:
            if event.type() == QEvent.Show:
                self.cama.show()
                self.pet.raise_()           # o pet fica na frente da cama, deitado nela
            elif event.type() == QEvent.Hide:
                self.cama.hide()
        return False


class LarModulo(Modulo):
    """A frente lar: a cama e o caminho até ela."""
    nome = "lar"

    def __init__(self, app, cama=None):
        """Cria a cama (escondida até o pet aparecer) e liga a visibilidade dela à do pet."""
        self.app = app
        self.cama = cama if cama is not None else Cama(app)
        self.filtro = _SegueOPet(self.cama, app.pet)
        app.pet.installEventFilter(self.filtro)
        self.cama.setVisible(app.pet.isVisible())
        self.sonos = {"na_cama": 0, "fora": 0}
        self.baguncas = 0               # travessuras de casa desde sempre
        self.bagunca_ate = 0.0          # até quando dura a travessura de casa em andamento (relógio monotônico)
        app.mischief_ctl.travessura_de_casa = self.travessura
        for controlador in (app.mischief_ctl, app.protest_ctl, app.sad_ctl):
            controlador.dispensa_e_atencao = False

    def travessura(self, now):
        """Começa uma travessura de casa: vai até a cama e pula nela. False se ele não está na tela."""
        if not self.app.pet.isVisible():
            return False
        self.bagunca_ate = now + ajustes.LAR_DURACAO_BAGUNCA
        self.baguncas += 1
        self.cama.set_baguncada(True)
        self.app.behavior.cama = (self.cama.centro_x(), self.bagunca_ate, "bagunca")
        return True

    # ---------------- encaixes ----------------

    def depois_do_passo(self, cerebro, drives, dt):
        """Com sono chegando (ou dormindo), pede ao comportamento que vá até a cama; senão, retira o pedido."""
        app = self.app
        sono = app.sleep
        x_cama = self.cama.centro_x()
        if not app.pet.isVisible():
            app.behavior.cama = None
        elif sono.asleep or sonolento(drives.pressao, circadiano(sono.relogio(), sono.pico_h)):
            app.behavior.cama = (x_cama, time.monotonic() + ajustes.LAR_VALIDADE_CAMA, "deitar")
        elif time.monotonic() < self.bagunca_ate:
            ate = min(self.bagunca_ate, time.monotonic() + ajustes.LAR_VALIDADE_CAMA)
            app.behavior.cama = (x_cama, ate, "bagunca")
        else:
            app.behavior.cama = None
        self.cama.set_ocupada(sono.asleep and deitado(app.pet.body, x_cama))

    def ao_dormir(self, cerebro):
        """Conta onde o sono começou."""
        na_cama = deitado(self.app.pet.body, self.cama.centro_x())
        self.sonos["na_cama" if na_cama else "fora"] += 1
        self.cama.set_ocupada(na_cama)
        self.cama.set_baguncada(False)          # foi dormir: a cama fica arrumada
        self.bagunca_ate = 0.0

    def ao_acordar(self, cerebro):
        """Acordou: o cobertor volta."""
        self.cama.set_ocupada(False)

    def deslocar(self, segundos):
        """Volta da pausa: a travessura de casa em andamento continua de onde parou."""
        if self.bagunca_ate:
            self.bagunca_ate += segundos

    def estado(self):
        """Quantos sonos começaram na cama e fora dela, e quantas travessuras de casa."""
        return {"sonos_na_cama": self.sonos["na_cama"], "sonos_fora": self.sonos["fora"],
                "travessuras_de_casa": self.baguncas}

    def salvar(self, pasta):
        """Grava as contagens em modulos/lar/lar.json."""
        write_json(pasta / ARQUIVO, self.estado())

    def carregar(self, pasta):
        """Lê as contagens. Arquivo ausente ou valor inválido: começa do zero naquele campo."""
        dados = read_json(pasta / ARQUIVO, default={})
        if not isinstance(dados, dict):
            return
        for chave, campo in (("na_cama", "sonos_na_cama"), ("fora", "sonos_fora")):
            valor = dados.get(campo)
            if _contagem_valida(valor):
                self.sonos[chave] = valor
        if _contagem_valida(dados.get("travessuras_de_casa")):
            self.baguncas = dados["travessuras_de_casa"]


def _contagem_valida(valor):
    """Inteiro (não bool) maior ou igual a zero."""
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def criar(app):
    """Fábrica da frente lar (config.MODULOS_DAS_FRENTES["lar"])."""
    return LarModulo(app)
