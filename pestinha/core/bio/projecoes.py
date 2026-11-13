"""
Projeções do BioBrain (spec, seção 7.1): uma lista de sinapses entre duas populações, não uma matriz densa.

Cada Projecao guarda os índices de pré e de pós, o peso de cada sinapse, o sinal, se é plástica, o
receptor (nenhum, D1 ou D2) e os limites de peso. `compilar` junta todas as projeções numa tabela única
ordenada pelo neurônio pré (CSR), que é o que o passo da rede usa: a cada milissegundo, só as sinapses
dos neurônios que dispararam entram na conta.

Dono: T2. Depois do T2, só a frente NE edita este arquivo (plano, seção 5).
"""
import numpy as np

RECEPTORES = (None, "D1", "D2")


class Projecao:
    """Sinapses de uma população para outra. pre e pos são índices globais de neurônio."""

    def __init__(self, origem, destino, pre, pos, peso, plastica=False, receptor=None, limites=None):
        if receptor not in RECEPTORES:
            raise ValueError(f"receptor desconhecido: {receptor!r}")
        self.origem = origem
        self.destino = destino
        self.pre = np.asarray(pre, dtype=np.int64)
        self.pos = np.asarray(pos, dtype=np.int64)
        self.peso = np.asarray(peso, dtype=float)
        if not (self.pre.shape == self.pos.shape == self.peso.shape) or self.pre.ndim != 1:
            raise ValueError("pre, pos e peso precisam ser listas do mesmo tamanho")
        self.plastica = bool(plastica)
        self.receptor = receptor
        self.limites = limites

    @property
    def sinal(self):
        """+1 excitatória, −1 inibitória, 0 sem sinapse (ou pesos que se anulam)."""
        total = float(self.peso.sum())
        return 0 if total == 0.0 else (1 if total > 0 else -1)

    def __len__(self):
        return int(self.pre.size)

    def __repr__(self):
        return f"Projecao({self.origem}->{self.destino}, {len(self)} sinapses)"


def projecao_de_bloco(origem, destino, inicio_pre, inicio_pos, bloco, **kwargs):
    """Projeção a partir de um bloco denso (pré × pós) de pesos: só as entradas diferentes de zero viram sinapse."""
    i, j = np.nonzero(bloco)
    return Projecao(origem, destino, inicio_pre + i, inicio_pos + j, bloco[i, j], **kwargs)


class TabelaDeSinapses:
    """
    Todas as sinapses numa tabela ordenada pelo neurônio pré (CSR). Sinapses repetidas no mesmo par
    (pré, pós) são somadas, e as que somam zero saem. pos é o índice local entre os neurônios de destino
    (global − deslocamento).
    """

    def __init__(self, n_pre, n_pos, deslocamento, pre, pos, peso):
        self.n_pre = int(n_pre)
        self.n_pos = int(n_pos)
        self.deslocamento = int(deslocamento)
        chave = pre * self.n_pos + (pos - self.deslocamento)
        unicas, inverso = np.unique(chave, return_inverse=True)
        soma = np.bincount(inverso, weights=peso, minlength=unicas.size)
        manter = soma != 0.0
        unicas, soma = unicas[manter], soma[manter]
        self.pre = unicas // self.n_pos
        self.pos = unicas % self.n_pos
        self.peso = soma
        self.inicio = np.zeros(self.n_pre + 1, dtype=np.int64)
        np.cumsum(np.bincount(self.pre, minlength=self.n_pre), out=self.inicio[1:])

    def __len__(self):
        return int(self.peso.size)

    def propagar(self, atividade, disparou):
        """
        Corrente em cada neurônio de destino: soma de peso × atividade do pré, só para os pré que dispararam.
        atividade: vetor por neurônio pré (pulso × eficácia); disparou: índices dos pré com pulso.
        """
        if disparou.size == 0:
            return np.zeros(self.n_pos)
        comeco = self.inicio[disparou]
        tamanho = self.inicio[disparou + 1] - comeco
        total = int(tamanho.sum())
        if total == 0:
            return np.zeros(self.n_pos)
        idx = np.repeat(comeco - np.cumsum(tamanho) + tamanho, tamanho) + np.arange(total)
        return np.bincount(self.pos[idx], weights=self.peso[idx] * atividade[self.pre[idx]], minlength=self.n_pos)

    def densa(self):
        """Matriz densa (pré × destino) com os mesmos pesos. Só para ferramentas e testes."""
        matriz = np.zeros((self.n_pre, self.n_pos))
        matriz[self.pre, self.pos] = self.peso
        return matriz


def compilar(projecoes, n_pre, n_pos, deslocamento):
    """Junta as projeções numa TabelaDeSinapses."""
    if projecoes:
        pre = np.concatenate([p.pre for p in projecoes])
        pos = np.concatenate([p.pos for p in projecoes])
        peso = np.concatenate([p.peso for p in projecoes])
    else:
        pre = pos = np.zeros(0, dtype=np.int64)
        peso = np.zeros(0)
    if pre.size and (pos.min() < deslocamento or pos.max() >= deslocamento + n_pos or pre.max() >= n_pre):
        raise ValueError("sinapse fora da rede")
    return TabelaDeSinapses(n_pre, n_pos, deslocamento, pre, pos, peso)
