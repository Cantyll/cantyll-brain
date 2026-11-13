"""
O passo de 1 ms do BioBrain compilado com Numba (decisão do Cantyll, 2026-11-13, opção C: "Numba já").

O Numba é dependência opcional (requirements-numba.txt). Sem ele, ou com PESTINHA_NUMBA=0 no ambiente, ou com
ajustes.NE_NUMBA = False, o BioBrain usa o caminho em numpy de sempre. Com ele, os dois caminhos dão os mesmos
pulsos, bit a bit: cada conta é feita na mesma ordem e com os mesmos arredondamentos do numpy (sem fastmath), e
o ruído continua saindo do mesmo gerador numpy, na mesma ordem (tests/test_ne_numba.py).

Por que ajuda: com 470 neurônios o passo em numpy é feito de ~60 chamadas pequenas, e o custo de cada chamada
(1 a 2 µs) pesa mais que a conta. Aqui são quatro chamadas: propagar, LIF, Izhikevich e o fechamento do passo.

Na primeira vez a compilação leva alguns segundos; o resultado fica em cache (__pycache__ ao lado deste
arquivo, ou em NUMBA_CACHE_DIR) e as próximas partidas só carregam.

Dono: frente NE.
"""
import os

DISPONIVEL = False
MOTIVO = ""
if os.environ.get("PESTINHA_NUMBA", "1") == "0":
    MOTIVO = "PESTINHA_NUMBA=0"
else:
    try:
        import numba
    except Exception as erro:                                   # sem Numba: o numpy segue valendo
        MOTIVO = f"Numba indisponível ({type(erro).__name__}: {erro})"
    else:
        DISPONIVEL = True
        VERSAO = numba.__version__

if DISPONIVEL:
    _jit = numba.njit(cache=True, nogil=True, fastmath=False, error_model="numpy")

    @_jit
    def propagar(inicio, pre, pos, peso, spikes, pre_gain, corrente):
        """Como TabelaDeSinapses.propagar, somando em `corrente` (zerada) na mesma ordem do np.bincount."""
        for i in range(spikes.size):
            if spikes[i] != 0.0:
                for k in range(inicio[i], inicio[i + 1]):
                    j = pre[k]
                    corrente[pos[k]] += peso[k] * (spikes[j] * pre_gain[j])

    @_jit
    def propagar_por_sinal(inicio, pre, pos, peso, spikes, pre_gain, exc, inh):
        """Como TabelaDeSinapses.propagar_por_sinal: peso > 0 vai para `exc`, o resto para `inh` (zerados)."""
        for i in range(spikes.size):
            if spikes[i] != 0.0:
                for k in range(inicio[i], inicio[i + 1]):
                    j = pre[k]
                    w = peso[k]
                    if w > 0.0:
                        exc[pos[k]] += w * (spikes[j] * pre_gain[j])
                    else:
                        inh[pos[k]] += w * (spikes[j] * pre_gain[j])

    @_jit
    def lif(locais, corrente, outra, somar_outra, normal, sigma, inibido, ausente, inibicao,
            v, decay, ref, a, adapt_b, adapt_decay, t_ref, disparou):
        """Neuronio.passo para os neurônios `locais` (índices em Nl), escrevendo em `disparou[locais]`."""
        for n in range(locais.size):
            g = locais[n]
            c = corrente[g] + outra[g] if somar_outra else corrente[g]
            x = v[n] * decay[n]
            x = x + c
            x = x + sigma * normal[g]
            if ausente and inibido[n]:
                x = x - inibicao
            if ref[n] > 0:
                x = 0.0
                ref[n] -= 1
            if x < -0.5:
                x = -0.5
            dispara = x >= (1.0 + a[n])
            if dispara:
                x = 0.0
                ref[n] = t_ref
            v[n] = x
            an = a[n] * adapt_decay[n]
            if dispara:
                an = an + adapt_b[n]
            a[n] = an
            disparou[g] = dispara

    @_jit
    def izhikevich(locais, exc, inh, normal, sigma, inibido, ausente, inibicao,
                   v, u, i_ampa, i_gaba, decai_ampa, decai_gaba, salto_ampa, salto_gaba,
                   pa, pb, pc, pd, gasto, pico, disparou):
        """Izhikevich.passo (sem `externa`) para os neurônios `locais`, escrevendo em `disparou[locais]`."""
        for n in range(locais.size):
            g = locais[n]
            entrada_inh = inh[g]
            if ausente and inibido[n]:
                entrada_inh = entrada_inh - inibicao
            ia = i_ampa[n] * decai_ampa[n]
            ia = ia + (exc[g] + sigma * normal[g]) * salto_ampa[n]
            ig = i_gaba[n] * decai_gaba[n]
            ig = ig + entrada_inh * salto_gaba[n]
            corrente = ia + ig
            x = v[n]
            un = u[n]
            x = x + 0.5 * (0.04 * x * x + 5.0 * x + 140.0 - un + corrente)
            ja = x >= pico
            if x > pico:
                x = pico
            if not ja:
                x = x + 0.5 * (0.04 * x * x + 5.0 * x + 140.0 - un + corrente)
            if x > pico:
                x = pico
            un = un + pa[n] * (pb[n] * x - un)
            dispara = x >= pico
            if dispara:
                x = pc[n]
                un = un + pd[n]
                ia = ia - gasto[n]
            v[n] = x
            u[n] = un
            i_ampa[n] = ia
            i_gaba[n] = ig
            disparou[g] = dispara

    @_jit
    def fechar(uniforme, s_prob, p, s_d, s_rec, disparou, spikes, trace, trace_decay, pool_de, pool_counts):
        """Receptores sensoriais e habituação, pulsos do passo, rastro e contagem por população."""
        ns_ = uniforme.size
        for i in range(ns_):
            dispara = uniforme[i] < s_prob[i]
            pi = p[i]
            if dispara:
                pi = pi * (1.0 - s_d[i])
            p[i] = pi + (1.0 - pi) * s_rec[i]
            spikes[i] = 1.0 if dispara else 0.0
        for i in range(disparou.size):
            spikes[ns_ + i] = 1.0 if disparou[i] else 0.0
        for i in range(spikes.size):
            t = trace[i] * trace_decay
            if spikes[i] != 0.0:
                t = 1.0
                pool_counts[pool_de[i]] += 1.0
            trace[i] = t
