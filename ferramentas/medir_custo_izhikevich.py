"""
Mede o custo de um passo do M1 (Izhikevich, passo de 0,5 ms) ao lado do LIF atual, na mesma máquina.

    python ferramentas/medir_custo_izhikevich.py

Só mede: não muda a rede. Comparação A/B: os dois modelos passam pelo mesmo `_substep` sintético
(mesmo tamanho, mesma multiplicação densa de entrada, mesma habituação, mesma contagem de pools).
Só o núcleo do neurônio muda: LIF (decaimento, ruído, refratário, adaptação) contra Izhikevich
(v, u, disparo e reset). Assim a razão mede o custo do neurônio, não diferenças de código.

Usa a mesma conta de medir_custo_passo.py: fração de um núcleo, uma thread de BLAS, mediana de RODADAS.
Os valores são sintéticos. O custo de uma multiplicação densa depende das formas, não dos valores.

Não é a referência: rode na máquina de referência (docs/CUSTO_DO_PASSO.md) antes de decidir D2 e M1.
"""
import os

# Uma thread só, como em medir_custo_passo.py: o número é o custo de um núcleo.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import types  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

FERRAMENTAS = Path(__file__).resolve().parent
sys.path.insert(0, str(FERRAMENTAS))
import medir_custo_passo as lif  # noqa: E402  (rede sintética do LIF, ambiente e RODADAS)

from pestinha.core import nervous_system as ns  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402

DT_MS = 0.5                 # passo de integração de D2 (spec, seção 10)
PASSOS_POR_S = 2000         # 1 s simulado a 0,5 ms
AMOSTRAS = 2000             # passos por rodada


def _substep_izhikevich(self):
    """Um passo de 0,5 ms com neurônios Izhikevich. Igual ao LIF em tudo, menos o núcleo do neurônio."""
    rng = self.rng
    Ns = self.Ns

    drive = (self.spikes * self.pre_gain) @ self.W_lif
    I = drive + ns.NOISE_SIGMA * rng.standard_normal(self.Nl)

    v, u = self.v, self.u
    v += DT_MS * (0.04 * v * v + 5.0 * v + 140.0 - u + I)
    u += DT_MS * self.iz_a * (self.iz_b * v - u)
    fired = v >= 30.0
    v[fired] = self.iz_c[fired]                          # reset
    u[fired] += self.iz_d[fired]

    s_fired = rng.random(Ns) < self.s_prob
    self.p[s_fired] *= (1.0 - self.s_d[s_fired])         # habituação, igual ao LIF
    self.p += (1.0 - self.p) * self.s_rec

    self.spikes[:Ns] = s_fired
    self.spikes[Ns:] = fired
    self.trace *= ns.TRACE_DECAY
    self.trace[self.spikes > 0] = 1.0
    self.pool_counts += self.spikes @ self.onehot


def preparar_izhikevich(b, seed=3):
    """Dá à rede sintética os estados do Izhikevich: RS (80%) e FS (20%), e troca o _substep pelo do M1."""
    rng = np.random.default_rng(seed)
    Nl = b.Nl
    fs = rng.random(Nl) < 0.2
    b.iz_a = np.where(fs, 0.1, 0.02)
    b.iz_b = np.full(Nl, 0.2)
    b.iz_c = np.full(Nl, -65.0)
    b.iz_d = np.where(fs, 2.0, 8.0)
    b.v = -65.0 + 5.0 * rng.random(Nl)
    b.u = b.iz_b * b.v
    b._substep = types.MethodType(_substep_izhikevich, b)
    return b


def medir_pareado(b1, b2):
    """Mede duas redes na mesma rodada, uma depois da outra, para o ruído da máquina pesar igual nas duas."""
    for _ in range(200):
        b1._substep()
        b2._substep()
    acc1, acc2 = [], []
    for _ in range(lif.RODADAS):
        for b, acc in ((b1, acc1), (b2, acc2)):
            t0, c0 = time.perf_counter(), time.process_time()
            for _ in range(AMOSTRAS):
                b._substep()
            t1, c1 = time.perf_counter(), time.process_time()
            acc.append((t1 - t0, c1 - c0))
    def resumo(acc):
        wall = statistics.median(t for t, _ in acc) / AMOSTRAS
        cpu = statistics.median(c for _, c in acc) / AMOSTRAS
        return {"us_por_passo": 1e6 * wall, "us_cpu_por_passo": 1e6 * cpu}
    return resumo(acc1), resumo(acc2)


def fracao_nucleo(us_cpu_por_passo):
    """Fração de um núcleo com passo de 0,5 ms (2000 passos por segundo simulado)."""
    return us_cpu_por_passo * PASSOS_POR_S / 1e6


def main():
    base = LIFBrain(seed=7)
    resultados = []
    for N in (base.N, lif.N_ALVO):
        r_lif, r_izh = medir_pareado(lif.rede_sintetica(N, base),
                                     preparar_izhikevich(lif.rede_sintetica(N, base)))
        resultados.append((N, r_lif, r_izh))

    print("Ambiente:", lif.ambiente())
    print()
    print("| Neurônio | Neurônios | dt | µs por passo | fração de 1 núcleo |")
    print("|---|---:|---:|---:|---:|")
    for N, r_lif, r_izh in resultados:
        for nome, r in (("LIF", r_lif), ("Izhikevich", r_izh)):
            print(f"| {nome} | {N} | 0,5 ms | {r['us_por_passo']:.1f} "
                  f"| {100 * fracao_nucleo(r['us_cpu_por_passo']):.1f}% |")
    print()
    for N, r_lif, r_izh in resultados:
        print(f"Razão Izhikevich / LIF com {N} neurônios: "
              f"{r_izh['us_cpu_por_passo'] / r_lif['us_cpu_por_passo']:.2f}")
    print(f"Ns = {base.Ns}. Cada linha é a mediana de {lif.RODADAS} rodadas de {AMOSTRAS} passos, "
          "medidas alternando LIF e Izhikevich.")


if __name__ == "__main__":
    main()
