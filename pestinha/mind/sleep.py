"""
SLEEP - quando ele dorme, quando acorda, e o que acontece ao adormecer.

Dormir é decisão do ritmo (core/ritmo.py): a pressão de sono P sobe acordado e o relógio
C marca a noite. Ele dorme à noite, quando P está alta; acorda de manhã, quando P caiu.
A energia (homeostase) continua valendo como sentido interno, mas não manda no sono.

Ele só adormece apoiado, sem ser segurado, sem voar, sem missão e fora de protesto ativo
(indignado não dorme). Carinho acorda na hora, de qualquer jeito. Ao adormecer,
consolida a memória episódica.
"""

from ..log import log
from ..core.emotion import PRIORITY
from ..core.ritmo import circadiano, hora_local, quer_acordar, quer_dormir
from .. import ajustes


class SleepController:
    """Quando ele dorme e acorda: pela pressão de sono e pelo relógio (dia e noite), sem estar em protesto ou em missão."""
    def __init__(self, emotion, drives, memory, debug, pico_h=None, relogio=hora_local):
        """Guarda a emoção, as necessidades, a memória, o pico de vigília do pet e o relógio (função que devolve a hora local)."""
        self.emotion = emotion
        self.drives = drives
        self.memory = memory
        self.debug = debug          # função -> bool: imprime no terminal só no modo teste
        self.pico_h = ajustes.PICO_VIGILIA_H if pico_h is None else pico_h
        self.relogio = relogio
        self.asleep = False

    def can_sleep(self, body, in_flight, protest_stage, mission):
        """Diz se ele pode dormir agora (no chão, sem ser segurado, sem voar, sem protesto forte e sem missão)."""
        return (body.grounded and not body.held and not in_flight
                and protest_stage < 2 and not mission
                and self.emotion.current not in ("assustado", "dramatico"))

    def tick(self, now, body, in_flight, protest_stage, mission, caressing=False):
        """Um passo: dorme quando a pressão e o relógio pedem e ele pode; acorda quando pedem ou se você fizer carinho."""
        c = circadiano(self.relogio(), self.pico_h)
        pressao = self.drives.pressao
        if self.asleep:
            if caressing or quer_acordar(pressao, c):
                self.wake(startled=False)
            else:
                self.emotion.force("dormindo", 0.3, now, PRIORITY["dormindo"])
        elif not caressing and quer_dormir(pressao, c) and self.can_sleep(body, in_flight, protest_stage, mission):
            self.fall_asleep()

    def fall_asleep(self):
        """Adormece e consolida: refaz as preferências a partir dos episódios."""
        self.asleep = True
        prefs = self.memory.consolidate()
        if self.debug():
            log(f"[sono] dormiu ({self.drives.describe()})")
            for ctx, action, mean, n in prefs:
                log(f"[sono]   {ctx} -> {action}: {mean:+.2f} ({n:.0f} episódios)")

    def wake(self, startled):
        """Acorda: se foi um susto, ele fica assustado; senão, acorda calmo."""
        self.asleep = False
        if startled:
            self.emotion.force("assustado", 1.2, priority=PRIORITY["assustado"])    # acordou no susto
        if self.debug():
            how = "no susto" if startled else "descansado"
            log(f"[sono] acordou {how} ({self.drives.describe()})")
