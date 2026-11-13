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

    def __init__(self, origem, destino, pre, pos, peso, plastica=False, receptor=None, limites=None, celula=None):
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
        # plástica: peso é o peso unitário de cada sinapse, e o peso efetivo é valor[celula] × peso, onde valor
        # é o vetor que a regra de aprendizado mantém (no T2, a matriz `learned` achatada)
        if self.plastica and celula is None:
            raise ValueError("projeção plástica precisa da célula de aprendizado")
        self.celula = None if celula is None else int(celula)

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
    Todas as sinapses numa tabela ordenada pelo neurônio pré (CSR). pos é o índice local entre os neurônios
    de destino (global − deslocamento).

    Sinapses fixas repetidas no mesmo par (pré, pós) são somadas no peso de base, e as que somam zero saem.
    Uma sinapse plástica no mesmo par entra como parcela à parte (celula, unidade): o peso efetivo é
    base + valor[celula] × unidade, a mesma conta do LIFBrain (W_base + learned × máscara). Um par tem no
    máximo uma parcela plástica.
    """

    def __init__(self, n_pre, n_pos, deslocamento, pre, pos, peso, celula=None):
        self.n_pre = int(n_pre)
        self.n_pos = int(n_pos)
        self.deslocamento = int(deslocamento)
        pre = np.asarray(pre, dtype=np.int64)
        pos = np.asarray(pos, dtype=np.int64)
        peso = np.asarray(peso, dtype=float)
        celula = np.full(pre.size, -1, dtype=np.int64) if celula is None else np.asarray(celula, dtype=np.int64)
        plastica = celula >= 0
        chave = pre * self.n_pos + (pos - self.deslocamento)
        unicas, inverso = np.unique(chave, return_inverse=True)
        base = np.bincount(inverso[~plastica], weights=peso[~plastica], minlength=unicas.size)
        cel = np.full(unicas.size, -1, dtype=np.int64)
        unidade = np.zeros(unicas.size)
        if np.bincount(inverso[plastica], minlength=unicas.size).max(initial=0) > 1:
            raise ValueError("duas sinapses plásticas no mesmo par (pré, pós)")
        cel[inverso[plastica]] = celula[plastica]
        unidade[inverso[plastica]] = peso[plastica]
        manter = (base != 0.0) | ((cel >= 0) & (unidade != 0.0))
        unicas = unicas[manter]
        self.pre = unicas // self.n_pos
        self.pos = unicas % self.n_pos
        self.base = base[manter]
        self.celula = cel[manter]
        self.unidade = unidade[manter]
        self._plasticas = np.flatnonzero(self.celula >= 0)
        self.peso = self.base.copy()
        self.inicio = np.zeros(self.n_pre + 1, dtype=np.int64)
        np.cumsum(np.bincount(self.pre, minlength=self.n_pre), out=self.inicio[1:])

    def __len__(self):
        return int(self.peso.size)

    @property
    def n_fixas(self):
        """Sinapses com peso de base diferente de zero (as que existem antes de qualquer aprendizado)."""
        return int(np.count_nonzero(self.base))

    def aplicar(self, valores):
        """Recalcula o peso efetivo das sinapses plásticas: base + valores[celula] × unidade."""
        k = self._plasticas
        self.peso = self.base.copy()
        self.peso[k] = self.base[k] + np.asarray(valores, dtype=float)[self.celula[k]] * self.unidade[k]

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

    def propagar_por_sinal(self, atividade, disparou):
        """
        Como `propagar`, mas com a corrente separada por sinal do peso efetivo: (excitatória, inibitória).
        A soma das duas é a corrente de `propagar` (a menos do arredondamento). Usada pelos neurônios de
        Izhikevich, que têm uma corrente sináptica para cada sinal (AMPA e GABA).
        """
        if disparou.size == 0:
            return np.zeros(self.n_pos), np.zeros(self.n_pos)
        comeco = self.inicio[disparou]
        tamanho = self.inicio[disparou + 1] - comeco
        total = int(tamanho.sum())
        if total == 0:
            return np.zeros(self.n_pos), np.zeros(self.n_pos)
        idx = np.repeat(comeco - np.cumsum(tamanho) + tamanho, tamanho) + np.arange(total)
        peso = self.peso[idx]
        valor = peso * atividade[self.pre[idx]]
        alvo = self.pos[idx]
        positivo = peso > 0.0
        excitatoria = np.bincount(alvo[positivo], weights=valor[positivo], minlength=self.n_pos)
        inibitoria = np.bincount(alvo[~positivo], weights=valor[~positivo], minlength=self.n_pos)
        return excitatoria, inibitoria

    def densa(self):
        """Matriz densa (pré × destino) com os pesos efetivos. Só para ferramentas e testes."""
        matriz = np.zeros((self.n_pre, self.n_pos))
        matriz[self.pre, self.pos] = self.peso
        return matriz


def compilar(projecoes, n_pre, n_pos, deslocamento):
    """Junta as projeções (fixas e plásticas) numa TabelaDeSinapses."""
    vazio = np.zeros(0, dtype=np.int64)
    pre = np.concatenate([p.pre for p in projecoes] or [vazio])
    pos = np.concatenate([p.pos for p in projecoes] or [vazio])
    peso = np.concatenate([p.peso for p in projecoes] or [np.zeros(0)])
    celula = np.concatenate([np.full(len(p), p.celula if p.plastica else -1, dtype=np.int64) for p in projecoes] or [vazio])
    if pre.size and (pos.min() < deslocamento or pos.max() >= deslocamento + n_pos or pre.max() >= n_pre):
        raise ValueError("sinapse fora da rede")
    return TabelaDeSinapses(n_pre, n_pos, deslocamento, pre, pos, peso, celula)
