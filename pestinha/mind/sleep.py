"""
SLEEP - quando ele dorme, quando acorda, e o que acontece ao adormecer.

Dormir é decisão do ritmo (core/ritmo.py): a pressão de sono P sobe acordado e o relógio
C marca a noite. Ele dorme à noite, quando P está alta; acorda de manhã, quando P caiu.
A energia (homeostase) continua valendo como sentido interno, mas não manda no sono.

Ele só adormece apoiado, sem ser segurado, sem voar, sem missão e fora de protesto ativo
(indignado não dorme). Carinho acorda na hora, de qualquer jeito. Ao adormecer,
consolida a memória episódica e monta a fila de replay (spec, seção 9.4): os episódios
mais marcantes da memória voltam à rede, um pedaço por quadro, até ele acordar. Logo que
adormece, a rede desfaz uma parte do aprendizado (homeostase sináptica, SHY), e o replay
para de empurrar cada sinapse perto do seu limite.

Replay e SHY valem pela dívida de sono, não por adormecer. A dívida é a pressão de sono que
subiu desde o ponto mais baixo do último sono (`pressao_quitada`, guardada em drives.json).
Uma noite inteira de dívida (LIMIAR_DORME_PRESSAO − LIMIAR_ACORDA_PRESSAO) vale um sono
completo: os REPLAY_EPISODIOS episódios e HOMEOSTASE_SHY. Uma dívida menor vale a parte dela;
a maior vale um sono completo, como antes. Acordar no meio da noite (carinho, susto, o app
fechado e reaberto) e dormir de novo não cobra outra noite: só o que a pressão subiu acordado.

O trabalho da noite é feito no começo do sono, de uma vez, como antes, e não espalhado pela
noite: a elegibilidade dura ~4 s, e um replay em pedaços separados por horas ensinaria os
sentidos da noite em vez dos do episódio.
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
        self.replay_fila = []       # episódios ainda não reaplicados nesta noite: {sentidos, delta, restante}
        self._reduzir_pendente = 0.0     # fração do SHY deste sono ainda não aplicada (0: nada pendente)
        self.cota = 0.0             # fração de um sono completo que este sono cobra (pela dívida de sono)
        self.ao_dormir = None       # função sem argumentos chamada ao adormecer (o app liga os módulos, T1)
        self.ao_acordar = None      # função sem argumentos chamada ao acordar de um sono

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
            self._quitar(pressao)
            if caressing or quer_acordar(pressao, c):
                self.wake(startled=False)
            else:
                self.emotion.force("dormindo", 0.3, now, PRIORITY["dormindo"])
        elif not caressing and quer_dormir(pressao, c) and self.can_sleep(body, in_flight, protest_stage, mission):
            self.fall_asleep()

    @staticmethod
    def noite():
        """Dívida de uma noite inteira, em pressão de sono: a distância entre dormir e acordar."""
        return max(0.05, ajustes.LIMIAR_DORME_PRESSAO - ajustes.LIMIAR_ACORDA_PRESSAO)

    def divida(self):
        """
        Fração de um sono completo que adormecer agora cobra, de 0 a 1: a pressão que subiu desde o
        ponto mais baixo do último sono, sobre a de uma noite inteira. Sem sono anterior, vale 1.
        """
        quitada = getattr(self.drives, "pressao_quitada", None)
        if quitada is None:
            return 1.0
        return min(1.0, max(0.0, (self.drives.pressao - quitada) / self.noite()))

    def _quitar(self, pressao):
        """Dormindo: a dívida fica paga até a pressão deste instante (o ponto mais baixo do sono)."""
        quitada = getattr(self.drives, "pressao_quitada", None)
        self.drives.pressao_quitada = pressao if quitada is None else min(quitada, pressao)

    def fall_asleep(self):
        """
        Adormece, consolida e monta a fila de replay: refaz as preferências a partir dos episódios.
        A fila e o SHY deste sono são a parte da dívida de sono (`divida`), não um sono completo a cada vez.
        """
        self.asleep = True
        self.cota = self.divida()
        self.drives.pressao_quitada = self.drives.pressao
        self._reduzir_pendente = self.cota
        prefs = self.memory.consolidate()
        self.replay_fila = self._fila(self.memory.escolher_replay(), self.cota)
        if self.ao_dormir is not None:
            self.ao_dormir()
        if self.debug():
            log(f"[sono] dormiu ({self.drives.describe()}), dívida {self.cota:.2f} de uma noite, "
                f"replay de {len(self.replay_fila)} episódios")
            for ctx, action, mean, n in prefs:
                log(f"[sono]   {ctx} -> {action}: {mean:+.2f} ({n:.0f} episódios)")

    @staticmethod
    def _fila(escolhidos, cota):
        """
        A fila de replay de um sono que cobra `cota` de um sono completo: os episódios na ordem de
        prioridade até somar cota · (episódios escolhidos) · REPLAY_MS; o último pode ficar mais curto.
        """
        total = int(round(cota * len(escolhidos) * ajustes.REPLAY_MS))
        fila = []
        for sentidos, delta in escolhidos:
            if total <= 0:
                break
            ms = min(ajustes.REPLAY_MS, total)
            fila.append({"sentidos": sentidos, "delta": delta, "restante": ms})
            total -= ms
        return fila

    def replay_passo(self, brain, orcamento_ms, rate):
        """
        Usa até `orcamento_ms` de simulação no replay da noite, um episódio por vez, na ordem da fila. Devolve o tempo usado.
        Na primeira chamada do sono, antes do replay, a rede faz o downscaling da parte do SHY que este sono
        cobra: 1 − (1 − HOMEOSTASE_SHY)^cota. Somadas, as partes de uma noite picada dão o SHY de uma noite.
        """
        self._quitar(self.drives.pressao)
        if self._reduzir_pendente > 0.0:
            cota = self._reduzir_pendente
            brain.downscaling_sono(ajustes.HOMEOSTASE_SHY if cota >= 1.0 else 1.0 - (1.0 - ajustes.HOMEOSTASE_SHY) ** cota)
            self._reduzir_pendente = 0.0
        usado = 0
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
        estava_dormindo = self.asleep
        if self.asleep:
            self._quitar(self.drives.pressao)
        self.asleep = False
        self.replay_fila = []
        self._reduzir_pendente = 0.0
        if startled:
            self.emotion.force("assustado", 1.2, priority=PRIORITY["assustado"])    # acordou no susto
        if estava_dormindo and self.ao_acordar is not None:
            self.ao_acordar()
        if self.debug():
            how = "no susto" if startled else "descansado"
            log(f"[sono] acordou {how} ({self.drives.describe()})")
