"""
Configuração comum dos testes (pasta tests/).

- Qt sem janela: os testes rodam em qualquer máquina, sem abrir nada na tela.
- Isolamento: apps e janelas criados num teste não continuam rodando nos seguintes.
- Cérebro: PESTINHA_CEREBRO=bio roda a suíte com o BioBrain (plano, T2 e portão A). Muda só config.CEREBRO,
  então vale para o que passa pelo app ou por criar_cerebro(config.cerebro_escolhido()); os testes que
  constroem LIFBrain direto seguem no LIF. Sem a variável, o padrão de config.py.
"""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pestinha import config

_CEREBRO = os.environ.get("PESTINHA_CEREBRO", "").strip()
if _CEREBRO:
    if _CEREBRO not in config.CEREBROS_PRONTOS:
        raise pytest.UsageError(f"PESTINHA_CEREBRO={_CEREBRO!r}: os prontos são {config.CEREBROS_PRONTOS}")
    config.CEREBRO = _CEREBRO


def pytest_report_header(config):
    from pestinha import config as cfg
    return f"cérebro: {cfg.cerebro_escolhido()}"


@pytest.fixture(autouse=True)
def _encerrar_apps_e_janelas():
    from PySide6.QtWidgets import QApplication
    qt = QApplication.instance()
    antes = set(qt.topLevelWidgets()) if qt else set()
    yield
    from PySide6.QtCore import QTimer
    from pestinha.app import PestinhaApp
    for obj in gc.get_objects():
        if isinstance(obj, PestinhaApp):
            for timer in obj.findChildren(QTimer):
                timer.stop()
    qt = QApplication.instance()
    if qt:
        for widget in set(qt.topLevelWidgets()) - antes:
            for timer in widget.findChildren(QTimer):
                timer.stop()
            widget.close()
