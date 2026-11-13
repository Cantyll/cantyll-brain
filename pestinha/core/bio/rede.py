"""
BioBrain: o núcleo novo (plano, T2; spec, seção 12). Implementa a interface Brain com populações que têm o
próprio modelo de neurônio (core/bio/neuronios.py) e projeções em listas de sinapses (core/bio/projecoes.py),
em vez da matriz densa do LIFBrain.

Paridade (T2): nesta fase a rede é a mesma do LIFBrain. Mesmas populações, mesmas conexões, o mesmo neurônio
LIF e o mesmo sorteio, na mesma ordem: com a mesma semente, as sinapses saem iguais às do LIFBrain, e com a
mesma semente de ruído os pulsos também. As tabelas de populações e de conexões vêm de core/nervous_system.py,
que fica congelado (decisão V1), então não há cópia para sair de sincronia.

O aprendizado também é o do LIFBrain: a matriz `learned` (canal sensorial × população plástica) com
elegibilidade sobre os níveis sensoriais e δ = r − V, aplicada a projeções plásticas (uma por par canal ×
população). O peso efetivo de cada sinapse plástica é base + learned × unidade, a mesma conta do LIF. A troca
para STDP por pulso é a frente PL-1, em core/bio/plasticidade.py.

Está em config.CEREBROS_PRONTOS desde o T2.4; o padrão segue "lif" até o Cantyll decidir a troca (V7).

Dono: T2. Depois do T2, só a frente NE edita este arquivo (plano, seção 5).
"""
import math
import time
from collections import deque

import numpy as np

from ...ajustes import AUSENCIA_CORRENTE
from ...log import log
from ...mathutil import valor_real
from ...store import read_json, write_json
from .. import nervous_system as ns
from ..homeostase_sinaptica import downscaling, saturacao
from ..nervous_system import Brain, LEARN_MAX, LEARN_MIN, LEARN_RATE_PADRAO
from .neuronios import Neuronio
from . import plasticidade as pl
from .projecoes import compilar, projecao_de_bloco

BIO_VERSION = 1


class Pool(dict):
    """
    Uma população: nome, grupo (sensory, inter ou motor), tipo (sens, exc ou inh), onde começa na lista de
    neurônios, quantos são e o centro no monitor. É um dict com as mesmas chaves do LIFBrain, porque o monitor,
    a sessão e as ferramentas leem as populações assim.
    """

    def __init__(self, name, group, kind, start, n, center):
        super().__init__(name=name, group=group, kind=kind, start=start, n=n, center=center)

    @property
    def fatia(self):
        return slice(self["start"], self["start"] + self["n"])


class BioBrain(Brain):
    """Rede neural pulsada com populações e projeções explícitas. Mesma estrutura do LIFBrain nesta fase."""
    SEED = ns.LIFBrain.SEED

    def __init__(self, seed=None, temperament=None, seed_ruido=None):
        """Mesmos argumentos do LIFBrain: seed (o indivíduo), temperament (ganhos) e seed_ruido (ruído reprodutível)."""
        self.seed = self.SEED if seed is None else seed
        self.temperament = dict(temperament or {})
        rng = np.random.default_rng(self.seed)
        self.rng = np.random.default_rng(seed_ruido)

        # ---------------- populações ----------------
        self.pools = []
        self._pool_index = {}
        cursor = 0

        def nova(name, group, n, kind, center):
            nonlocal cursor
            pool = Pool(name, group, kind, cursor, n, center)
            self._pool_index[name] = len(self.pools)
            self.pools.append(pool)
            cursor += n

        for i, (name, (n, *_)) in enumerate(ns.SENSORY_SPEC.items()):
            nova(name, "sensory", n, "sens", (0.05, 0.06 + i * 0.0933))
        for name, kind, n, _tau, _b, _bt, center in ns.INTER_SPEC:
            nova(name, "inter", n, kind, center)
        for i, (name, n, *_) in enumerate(ns.MOTOR_SPEC):
            nova(name, "motor", n, "exc", (0.95, 0.10 + i * 0.16))

        self.N = cursor
        self.Ns = sum(p["n"] for p in self.pools if p["group"] == "sensory")
        self.Nl = self.N - self.Ns
        Ns = self.Ns
        self.sensory_names = list(ns.SENSORY_SPEC)
        self.motor_names = [m[0] for m in ns.MOTOR_SPEC]
        self._pool_de = np.zeros(self.N, dtype=np.int64)       # população de cada neurônio
        for i, p in enumerate(self.pools):
            self._pool_de[p.fatia] = i
        self.pool_sizes = np.array([p["n"] for p in self.pools], dtype=float)

        # R1: com o usuário ausente, FUGIR e TRAVESSURA recebem corrente inibitória (índices locais).
        self.ausente = False
        self._idx_ausencia = np.concatenate([
            np.arange(p["start"] - Ns, p["start"] - Ns + p["n"]) for p in (self.pool("FUGIR"), self.pool("TRAVESSURA"))
        ])

        # ---------------- neurônios ----------------
        tau_m = np.full(self.N, 20.0)
        adapt_b = np.zeros(self.N)
        adapt_tau = np.full(self.N, 1.0)
        for name, _kind, _n, tau, b, bt, _c in ns.INTER_SPEC:
            sl = self.pool(name).fatia
            tau_m[sl], adapt_b[sl], adapt_tau[sl] = tau, b, bt
        for name, _n, tau, b, bt in ns.MOTOR_SPEC:
            sl = self.pool(name).fatia
            tau_m[sl], adapt_b[sl], adapt_tau[sl] = tau, b, bt
        tau_m *= rng.uniform(0.9, 1.1, self.N)                  # heterogeneidade (o 1º sorteio, como no LIF)
        self.neuronios = Neuronio(tau_m[Ns:], adapt_b[Ns:], adapt_tau[Ns:])

        # ---------------- receptores sensoriais ----------------
        self.s_rate = np.zeros(Ns)
        self.s_d = np.zeros(Ns)
        self.s_tau_rec = np.ones(Ns)
        for name, (_n, rate, d, rec) in ns.SENSORY_SPEC.items():
            sl = self.pool(name).fatia
            self.s_rate[sl], self.s_d[sl], self.s_tau_rec[sl] = rate, d, rec
        self.s_rec = 0.001 / self.s_tau_rec
        self.s_prob = np.zeros(Ns)

        # ---------------- projeções ----------------
        self.projecoes = []

        def ligar(pre, post, weight, density):
            a, b = self.pool(pre), self.pool(post)
            mask = rng.random((a["n"], b["n"])) < density
            strength = rng.lognormal(0.0, 0.25, (a["n"], b["n"]))
            strength /= np.exp(0.25 ** 2 / 2)
            self.projecoes.append(projecao_de_bloco(pre, post, a["start"], b["start"], weight * strength * mask))

        for pre, post, weight, density in ns.CONNECTIONS:
            if pre in ns.SENSORY_SPEC:
                weight *= self.temperament.get(f"{pre}->{post}", self.temperament.get(post, 1.0))
            ligar(pre, post, weight, density)
        for a in self.motor_names:
            for b in self.motor_names:
                if a != b and (a in ns.DECISION_MOTORS) == (b in ns.DECISION_MOTORS):
                    ligar(a, b, -(ns.STARTLE_INHIBITION if a == "STARTLE" else ns.LATERAL_INHIBITION), 0.7)

        # projeções plásticas canal sensorial -> população plástica (sorteio próprio, como no LIF: não muda o resto)
        plastic_rng = np.random.default_rng(self.seed + 1)
        self.plastic_posts = list(ns.PLASTIC_POSTS)
        self.post_sign = np.array([ns.PLASTIC_POSTS[name] for name in self.plastic_posts])
        P = len(self.plastic_posts)
        for i, c in enumerate(self.sensory_names):
            a = self.pool(c)
            for j, post in enumerate(self.plastic_posts):
                b = self.pool(post)
                mask = plastic_rng.random((a["n"], b["n"])) < ns.PLASTIC_DENSITY
                strength = plastic_rng.lognormal(0.0, 0.25, (a["n"], b["n"])) / np.exp(0.25 ** 2 / 2)
                self.projecoes.append(projecao_de_bloco(c, post, a["start"], b["start"], mask * strength, plastica=True,
                                                        celula=i * P + j, limites=(LEARN_MIN, LEARN_MAX)))
        self.learned = np.zeros((len(self.sensory_names), P))
        self.eligibility = np.zeros(len(self.sensory_names))
        self._levels = np.zeros(len(self.sensory_names))

        self.sinapses = compilar(self.projecoes, self.N, self.Nl, Ns)
        self.n_synapses = self.sinapses.n_fixas                 # como no LIF: as que existem sem aprendizado

        # ---------------- estado ----------------
        self.spikes = np.zeros(self.N)
        self.pre_gain = np.ones(self.N)
        self.p = self.pre_gain[:Ns]                             # eficácia dos receptores (habituação)
        self.trace = np.zeros(self.N)
        self.pool_counts = np.zeros(len(self.pools))
        self.pool_rate = np.zeros(len(self.pools))
        self.disparos = np.zeros(len(self.pools))

        # ---------------- posições para o monitor (último sorteio, como no LIF) ----------------
        pos = np.zeros((self.N, 2))
        for p in self.pools:
            cx, cy = p["center"]
            idx = np.arange(p["start"], p["start"] + p["n"])
            if p["group"] == "sensory":
                for k, i in enumerate(idx):
                    pos[i] = (cx + (k % 2) * 0.022, cy - 0.028 + (k // 2) * 0.028)
            else:
                pos[idx, 0] = cx + rng.normal(0, 0.022, p["n"])
                pos[idx, 1] = cy + rng.normal(0, 0.026, p["n"])
        self.pos = np.clip(pos, 0.01, 0.99)
        kind = np.zeros(self.N, dtype=int)                      # 0 sens 1 exc 2 inh 3 motor
        for p in self.pools:
            if p["group"] == "motor":
                kind[p.fatia] = 3
            elif p["group"] == "inter":
                kind[p.fatia] = 2 if p["kind"] == "inh" else 1
        self.kind = kind

        self.time_ms = 0.0
        self.recording = False
        self.raster = deque(maxlen=ns.RASTER_BINS)
        self._bin = np.zeros(self.N, dtype=bool)

        # PL-1: δ = r − V e ACh (core/bio/plasticidade.py). None com ajustes.PL_DELTA desligado: aprende como o LIF.
        self.plasticidade = pl.criar(self.sensory_names)
        self._em_replay = False

    # ---------------- populações ----------------

    def pool(self, name):
        """A população pelo nome."""
        return self.pools[self._pool_index[name]]

    @property
    def W(self):
        """Matriz densa (N × N) das sinapses, montada na hora. Só para ferramentas que contam ou conferem pesos."""
        matriz = np.zeros((self.N, self.N))
        matriz[:, self.Ns:] = self.sinapses.densa()
        return matriz

    # ---------------- interface ----------------

    def definir_ausencia(self, ausente):
        """R1: com o usuário ausente, FUGIR e TRAVESSURA recebem corrente inibitória (AUSENCIA_CORRENTE)."""
        self.ausente = bool(ausente)

    def stimulate(self, intensities):
        """Intensidade (0 a 1) de cada canal sensorial vira probabilidade de disparo dos receptores."""
        self.s_prob[:] = 0.0
        for k, name in enumerate(self.sensory_names):
            level = float(intensities.get(name, 0.0))
            level = 0.0 if level < 0 else 1.0 if level > 1 else level
            self._levels[k] = level
            sl = self.pool(name).fatia
            self.s_prob[sl] = self.s_rate[sl] * level * 0.001

    def _substep(self):
        """Um passo de 1 ms: propaga os pulsos do passo anterior pelas sinapses, integra, dispara e habitua."""
        rng = self.rng
        Ns = self.Ns
        corrente = self.sinapses.propagar(self.spikes * self.pre_gain, np.flatnonzero(self.spikes))
        ruido = ns.NOISE_SIGMA * rng.standard_normal(self.Nl)
        disparou = self.neuronios.passo(corrente, ruido, self._idx_ausencia if self.ausente else None,
                                        AUSENCIA_CORRENTE)

        s_fired = rng.random(Ns) < self.s_prob
        self.p[s_fired] *= (1.0 - self.s_d[s_fired])           # habituação: depressão sináptica...
        self.p += (1.0 - self.p) * self.s_rec                  # ...e recuperação lenta

        self.spikes[:Ns] = s_fired
        self.spikes[Ns:] = disparou
        self.trace *= ns.TRACE_DECAY
        ativos = np.flatnonzero(self.spikes)
        self.trace[ativos] = 1.0
        self.pool_counts += np.bincount(self._pool_de[ativos], minlength=len(self.pools))

    def step(self, dt_ms):
        """Avança a rede `dt_ms` milissegundos (em passos de 1 ms, no máximo 400 por chamada)."""
        n = int(max(1, min(400, round(dt_ms))))
        for i in range(n):
            self._substep()
            if self.recording:
                self._bin |= self.spikes > 0
                if (self.time_ms + i + 1) % ns.RASTER_BIN_MS == 0:
                    self.raster.append(self._bin)
                    self._bin = np.zeros(self.N, dtype=bool)
        dt_s = n * 0.001
        rate = self.pool_counts / (dt_s * self.pool_sizes)
        alpha = 1.0 - math.exp(-dt_s / ns.READ_TAU)
        self.pool_rate += alpha * (rate - self.pool_rate)
        self.disparos += self.pool_counts
        self.pool_counts[:] = 0.0
        self.time_ms += n

    def motor_activity(self):
        """Atividade atual (Hz) de cada motor."""
        return {name: float(self.pool_rate[self._pool_index[name]]) for name in self.motor_names}

    def pool_rates(self):
        """Atividade atual (Hz) de cada população."""
        return {p["name"]: float(self.pool_rate[i]) for i, p in enumerate(self.pools)}

    def taxas(self):
        """Taxa atual (Hz por neurônio) de cada população: sensores, interneurônios e motores."""
        return self.pool_rates()

    def efficacy(self):
        """Eficácia média (1 = sem habituação) por canal sensorial."""
        return {name: float(self.p[self.pool(name).fatia].mean()) for name in self.sensory_names}

    def reset_habituation(self):
        """Zera a habituação: todo estímulo volta a ser novidade."""
        self.p[:] = 1.0

    def learned_summary(self, top=5):
        """As associações mais fortes aprendidas: [(canal, alvo, peso)]."""
        pairs = [
            (c, post, float(self.learned[i, j]))
            for i, c in enumerate(self.sensory_names)
            for j, post in enumerate(self.plastic_posts)
            if abs(self.learned[i, j]) > 1e-4
        ]
        return sorted(pairs, key=lambda x: -abs(x[2]))[:top]

    def snapshot(self):
        """Foto do estado da rede para o monitor e para testes (as mesmas chaves do LIFBrain)."""
        return {
            "pos": self.pos,
            "trace": self.trace,
            "kind": self.kind,
            "pools": self.pools,
            "motor": self.motor_activity(),
            "efficacy": self.efficacy(),
            "pool_rate": self.pool_rates(),
        }

    def describe(self):
        """Resumo da rede: quantos neurônios e sinapses."""
        plasticas = sum(1 for p in self.projecoes if p.plastica)
        return (f"Bio {self.N} neurônios, {self.n_synapses} sinapses em {len(self.projecoes) - plasticas} projeções "
                f"fixas e {plasticas} plásticas")

    def estado(self):
        """Resumo serializável: versão, tempo simulado, habituação por canal, aprendizado e taxas por população."""
        return {
            "tipo": "bio",
            "versao": BIO_VERSION,
            "semente": self.seed,
            "neuronios": self.N,
            "sinapses": self.n_synapses,
            "tempo_ms": float(self.time_ms),
            "eficacia": self.efficacy(),
            "aprendido": {
                c: {post: float(self.learned[i, j]) for j, post in enumerate(self.plastic_posts)}
                for i, c in enumerate(self.sensory_names)
            },
            "taxas": self.pool_rates(),
            **({"plasticidade": self.plasticidade.estado()} if self.plasticidade is not None else {}),
        }

    # ---------------- aprendizado ----------------

    def learn(self, reward, expected, dt_s, rate=LEARN_RATE_PADRAO, teto=None):
        """
        Chamar a cada passo: atualiza a elegibilidade (o que estava ativo nos últimos segundos) e, se o erro de
        predição δ = reward − expected não for zero, ajusta as sinapses plásticas. A regra é a do LIFBrain.
        teto: com fração dada, o empurrão perde força perto desse limite (replay homeostático).
        """
        k = 1.0 - math.exp(-dt_s / ns.ELIGIBILITY_TAU)
        self.eligibility += (self._levels - self.eligibility) * k
        if self.plasticidade is not None:
            # PL-1: δ = r − V, com V do crítico (somado ao expected de um módulo) e a taxa vezes (0,5 + ACh)
            focus = self.pool_rate[self._pool_index["FOCUS"]]
            delta, fator = self.plasticidade.passo(self._levels, self.eligibility, reward, expected, dt_s, focus, self._em_replay)
            if delta == 0.0:
                return
            change = rate * fator * delta * np.outer(self.eligibility, self.post_sign)
        else:
            delta_predicao = reward - expected
            if delta_predicao == 0.0:
                return
            change = rate * delta_predicao * dt_s * np.outer(self.eligibility, self.post_sign)
        if teto is not None:
            change = change * saturacao(change, self.learned, teto, LEARN_MAX, LEARN_MIN)
        self.learned = np.clip(self.learned + change, LEARN_MIN, LEARN_MAX)
        self._apply_learning()

    def _apply_learning(self):
        """Leva a matriz `learned` para o peso das sinapses plásticas."""
        self.sinapses.aplicar(self.learned.ravel())

    def replay(self, sentidos, ms, delta, rate=LEARN_RATE_PADRAO, teto=None):
        """
        Replay noturno (M3, spec seção 9.4): reativa o padrão sensorial de um episódio por `ms` milissegundos,
        com δ = delta no aprendizado. Só os canais sensoriais contam; os que faltam valem 0.
        """
        entrada = {k: v for k, v in sentidos.items() if k in self.sensory_names}
        restante = int(ms)
        self._em_replay = True                  # PL-1: no replay, a ACh não muda a taxa (core/bio/moduladores.py)
        try:
            while restante > 0:
                chunk = min(100, restante)
                self.stimulate(entrada)
                self.step(chunk)
                self.learn(delta, 0.0, chunk / 1000.0, rate, teto)
                restante -= chunk
        finally:
            self._em_replay = False

    def downscaling_sono(self, fracao):
        """Homeostase sináptica (SHY, decisão D4): o sono desfaz `fracao` de todas as sinapses aprendidas."""
        self.learned = downscaling(self.learned, fracao)
        self._apply_learning()
        if self.plasticidade is not None:
            self.plasticidade.downscaling(fracao)   # PL-1: o crítico perde o mesmo (core/bio/plasticidade.py)

    # ---------------- persistência ----------------

    def save(self, path):
        """
        Grava habituação, aprendizado e o tamanho das populações (escrita atômica). As sinapses não vão para o
        arquivo: com a mesma semente elas saem iguais. Quando o crescimento mudar a estrutura (CR-1), as
        projeções passam a ser gravadas.
        """
        data = {
            "tipo": "bio",
            "version": BIO_VERSION,
            "seed": self.seed,
            "saved_at": time.time(),
            "populacoes": {p["name"]: p["n"] for p in self.pools},
            "efficacy": {name: [round(float(x), 5) for x in self.p[self.pool(name).fatia]] for name in self.sensory_names},
            "learned": {
                c: {post: round(float(self.learned[i, j]), 6) for j, post in enumerate(self.plastic_posts)}
                for i, c in enumerate(self.sensory_names)
            },
        }
        if self.plasticidade is not None:
            data["plasticidade"] = self.plasticidade.estado()     # PL-1: crítico e ACh (campo opcional)
        write_json(path, data)

    def load(self, path):
        """
        Restaura habituação e aprendizado. Tudo é validado antes de aplicar: tipo, versão, semente, populações,
        valores finitos e dentro do domínio. Se algo falhar, nada muda. Save do LIF não é lido (decisão D7).
        """
        data = read_json(path, default=None)
        if not isinstance(data, dict):
            return False
        try:
            if data.get("tipo") != "bio" or data.get("version") != BIO_VERSION or data.get("seed") != self.seed:
                return False
            if data.get("populacoes") != {p["name"]: p["n"] for p in self.pools}:
                return False
            elapsed = max(0.0, time.time() - valor_real(data["saved_at"], 0.0, 1e13))

            saved_learned = data.get("learned", {})
            if not isinstance(saved_learned, dict):
                return False
            learned = np.array(self.learned, copy=True)
            for i, c in enumerate(self.sensory_names):
                por_canal = saved_learned.get(c, {})
                if not isinstance(por_canal, dict):
                    return False
                for j, post in enumerate(self.plastic_posts):
                    learned[i, j] = valor_real(por_canal.get(post, 0.0), LEARN_MIN, LEARN_MAX)

            saved_eff = data.get("efficacy", {})
            if not isinstance(saved_eff, dict):
                return False
            recuperado = {}
            for name in self.sensory_names:
                if name not in saved_eff:
                    continue
                sl = self.pool(name).fatia
                saved = np.array(saved_eff[name], dtype=float)
                if saved.shape != (self.pool(name)["n"],) or not np.isfinite(saved).all() or ((saved < 0) | (saved > 1)).any():
                    return False
                recuperado[name] = np.clip(1.0 - (1.0 - saved) * np.exp(-elapsed / self.s_tau_rec[sl]), 0.0, 1.0)

            if self.plasticidade is not None and "plasticidade" in data:
                # PL-1: crítico e ACh. Inválido: nada muda (nem o resto). Ausente (save sem PL-1): crítico do zero.
                if not self.plasticidade.carregar(data["plasticidade"]):
                    return False
            self.learned[:] = learned
            self._apply_learning()
            for name, valores in recuperado.items():
                self.p[self.pool(name).fatia] = valores
            self.restored_after = elapsed
            return True
        except Exception as error:
            log(f"[bio] estado ilegível ({error}); começando do zero")
            return False
