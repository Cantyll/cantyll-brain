"""
ferramentas/medir_custo_bio.py (plano, T2, PR 4 de 4): a medida só vale se as duas redes fazem o mesmo trabalho.

O tempo não é testado (depende da máquina). O que se testa é que a rede sintética esparsa dispara os mesmos
pulsos que a densa, passo a passo, para a comparação de custo ser justa.

Rodar: python -m pytest tests/test_bio_custo.py -q
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))

import medir_custo_bio  # noqa: E402
import medir_custo_passo  # noqa: E402

from pestinha.core.nervous_system import LIFBrain  # noqa: E402


def test_sintetica_esparsa_dispara_igual_a_densa():
    referencia = LIFBrain(seed=7)
    densa = medir_custo_passo.rede_sintetica(630, referencia)
    esparsa = medir_custo_bio.bio_sintetica(medir_custo_passo.rede_sintetica(630, referencia))
    assert len(esparsa.sinapses) == np.count_nonzero(densa.W_lif)
    total = 0
    for _ in range(300):
        densa._substep()
        esparsa._substep()
        assert np.array_equal(densa.spikes, esparsa.spikes)
        total += int(densa.spikes.sum())
    assert total > 0                                     # houve atividade: não é 0 == 0
    assert np.array_equal(densa.pool_counts, esparsa.pool_counts)
