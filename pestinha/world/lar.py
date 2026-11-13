"""
LAR - o canto do pet na tela: por enquanto, a cama (frente lar, LAR-1).

A cama fica no chão, no canto inferior esquerdo da tela principal no primeiro uso (o notebook
fica no direito). Dá para arrastar com o botão esquerdo: ao soltar, ela desce até o chão da tela
onde caiu, para ele conseguir deitar. A posição é lembrada em memory/panels.json (chave "lar").

Não tira o foco do seu programa, não vira barra de título onde ele pousa (é janela de ferramenta)
e aparece e some junto com o pet (tela cheia, esconder, pânico): quem cuida disso é mind/lar_ctl.py.
Aqui só o desenho e a posição. Quem decide quando ir para a cama também é o lar_ctl.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen

from .arrastavel import FloatingWidget, save_position

CAMA_W, CAMA_H = 140, 42        # tamanho da cama (desenho)
MARGEM_TELA = 24                # px da borda esquerda da tela no primeiro uso


def posicao_padrao(tela, tamanho):
    """Canto inferior esquerdo da área útil `tela` (x, y, largura, altura), com a base no chão."""
    x, y, _largura, altura = tela
    return x + MARGEM_TELA, y + altura - tamanho[1]


def no_chao(x, y, tamanho, telas):
    """
    (x, y) com a base da cama no chão da tela que contém o centro dela. `telas`: áreas úteis
    [(x, y, largura, altura)]. Fora de todas, usa a tela mais perto na horizontal.
    """
    if not telas:
        return int(x), int(y)
    cx, cy = x + tamanho[0] / 2, y + tamanho[1] / 2
    dentro = [t for t in telas if t[0] <= cx < t[0] + t[2] and t[1] <= cy < t[1] + t[3]]
    if dentro:
        tela = dentro[0]
    else:
        tela = min(telas, key=lambda t: min(abs(cx - t[0]), abs(cx - (t[0] + t[2]))))
    tx, ty, tw, th = tela
    x = min(max(x, tx), tx + tw - tamanho[0])
    return int(x), int(ty + th - tamanho[1])


def _telas_uteis():
    """Áreas úteis de todos os monitores, como (x, y, largura, altura)."""
    return [(g.x(), g.y(), g.width(), g.height())
            for g in (s.availableGeometry() for s in QGuiApplication.screens())]


class Cama(FloatingWidget):
    """A cama do pet: desenhada, no chão, arrastável na horizontal (ao soltar, desce até o chão)."""

    def __init__(self, app):
        """Cria a cama na posição salva (ou no canto inferior esquerdo) e a encosta no chão. Começa escondida."""
        tamanho = (CAMA_W, CAMA_H)
        g = QGuiApplication.primaryScreen().availableGeometry()
        padrao = posicao_padrao((g.x(), g.y(), g.width(), g.height()), tamanho)
        super().__init__(app, "lar", f"Cama do {app.nome}", tamanho, tamanho, padrao)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.move(*no_chao(self.x(), self.y(), tamanho, _telas_uteis()))
        self.ocupada = False            # ele está deitado nela (só muda o desenho do cobertor)

    def centro_x(self):
        """x do meio da cama, onde ele deita."""
        return self.x() + self.width() / 2

    def set_ocupada(self, ocupada):
        """Puxa o cobertor quando ele deita, e redesenha só se mudou."""
        if ocupada != self.ocupada:
            self.ocupada = ocupada
            self.update()

    def mouseReleaseEvent(self, event):
        """Ao soltar, a cama desce até o chão da tela onde caiu e a posição fica salva."""
        if self._grab is not None and event.button() == getattr(self, "_botao", Qt.LeftButton):
            self._grab = None
            self.move(*no_chao(self.x(), self.y(), (self.width(), self.height()), _telas_uteis()))
            save_position(self.app.paths.panels, self.key, self.x(), self.y())

    def paintEvent(self, _event):
        """Cabeceira, colchão, travesseiro e cobertor."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = float(self.width()), float(self.height())
        madeira = QColor("#8a5a3b")
        p.setPen(QPen(QColor("#5e3b25"), 1.2))
        p.setBrush(madeira)
        p.drawRoundedRect(QRectF(2, 2, 12, h - 4), 4, 4)                 # cabeceira
        p.drawRoundedRect(QRectF(6, h - 12, w - 8, 10), 3, 3)            # estrado
        p.setBrush(QColor("#f3efe6"))
        p.setPen(QPen(QColor("#c9c1b0"), 1.0))
        p.drawRoundedRect(QRectF(12, h - 22, w - 16, 12), 5, 5)          # colchão
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(15, h - 30, 30, 12), 6, 6)              # travesseiro
        inicio = w * (0.34 if self.ocupada else 0.55)                     # deitado: cobertor puxado
        cobertor = QPainterPath()
        cobertor.addRoundedRect(QRectF(inicio, h - 25, w - inicio - 4, 15), 6, 6)
        p.setBrush(QColor("#6b8fd6"))
        p.setPen(QPen(QColor("#4a6db3"), 1.0))
        p.drawPath(cobertor)
        p.end()
