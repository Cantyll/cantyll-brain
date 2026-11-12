"""
SLEEP - quando ele dorme, quando acorda, e o que acontece ao adormecer.

Dormir é decisão do ritmo (core/ritmo.py): a pressão de sono P sobe acordado e o relógio
C marca a noite. Ele dorme à noite, quando P está alta; acorda de manhã, quando P caiu.
A energia (homeostase) continua valendo como sentido interno, mas não manda no sono.

Ele só adormece apoiado, sem ser segurado, sem voar, sem missão e fora de protesto ativo
(indignado não dorme). Carinho acorda na hora, de qualquer jeito. Ao adormecer,
consolida a memória episódica e monta a fila de replay (spec, seção 9.4): os episódios
mais marcantes da memória voltam à rede, um pedaço por quadro, até ele acordar. Ao longo do
sono, a rede desfaz uma parte do aprendizado (homeostase sináptica, SHY) na medida do sono
cumprido: uma noite inteira desfaz HOMEOSTASE_SHY, um cochilo desfaz a parte dele. O replay
para de empurrar cada sinapse perto do seu limite, e uma população que ficou muda tem as
entradas escaladas para cima (piso por taxa-alvo). A conta é de core/homeostase_sinaptica.py.
"""

from ..log import log
from ..core.emotion import PRIORITY
from ..core.homeostase_sinaptica import HomeostaseDoSono
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
        self.replay_fila = []       # episódios ainda não reaplicados nesta noite: {sentidos, delta, restante}
        self.homeostase = HomeostaseDoSono()   # SHY e piso, repartidos pela pressão de sono descarregada

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
        """Adormece, consolida e monta a fila de replay: refaz as preferências a partir dos episódios."""
        self.asleep = True
        prefs = self.memory.consolidate()
        self.replay_fila = [{"sentidos": sentidos, "delta": delta, "restante": ajustes.REPLAY_MS}
                            for sentidos, delta in self.memory.escolher_replay()]
        self.homeostase.adormecer(self.drives.pressao, [item["sentidos"] for item in self.replay_fila])
        if self.debug():
            log(f"[sono] dormiu ({self.drives.describe()}), replay de {len(self.replay_fila)} episódios")
            for ctx, action, mean, n in prefs:
                log(f"[sono]   {ctx} -> {action}: {mean:+.2f} ({n:.0f} episódios)")

    def replay_passo(self, brain, orcamento_ms, rate):
        """
        Usa até `orcamento_ms` de simulação no replay da noite, um episódio por vez, na ordem da fila. Devolve o tempo usado.
        Antes, a homeostase do sono faz a parte dela: o SHY do sono cumprido desde a última chamada e, com o
        replay já terminado, o ensaio do piso (que gasta do mesmo orçamento).
        """
        usado = self.homeostase.passo(brain, self.drives.pressao, orcamento_ms, replay_pendente=bool(self.replay_fila))
        while self.replay_fila and usado < orcamento_ms:
            item = self.replay_fila[0]
            n = min(orcamento_ms - usado, item["restante"])
            brain.replay(item["sentidos"], n, item["delta"], rate, ajustes.HOMEOSTASE_TETO)
            item["restante"] -= n
            usado += n
            if item["restante"] <= 0:
                self.replay_fila.pop(0)
        return usado

    def wake(self, startled):
        """Acorda: se foi um susto, ele fica assustado; senão, acorda calmo. Replay que não acabou fica para a próxima noite."""
        self.asleep = False
        self.replay_fila = []
        self.homeostase.acordar()
        if startled:
            self.emotion.force("assustado", 1.2, priority=PRIORITY["assustado"])    # acordou no susto
        if self.debug():
            how = "no susto" if startled else "descansado"
            log(f"[sono] acordou {how} ({self.drives.describe()})")
