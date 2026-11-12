"""
HABITUAÇÃO - dispensas repetidas no mesmo dia pesam cada vez menos no aprendizado.

Sem ela, cada dispensa ensina a mesma tristeza que a anterior, e 20 dispensas num dia ensinam 20
vezes mais que uma. Com ela, a resposta ao castigo repetido decai, como a habituação de um animal a
um estímulo que se repete, e volta com o tempo (recuperação espontânea).

Só o peso no aprendizado (a recompensa negativa da penalidade) habitua. O pulso DISMISS, a
frustração, o drama e a memória do episódio continuam inteiros: ele fica chateado em toda dispensa,
mas não é castigado em espiral (R1: sem culpa e sem cobrança).

O modelo é uma carga que vaza:
- cada dispensa soma 1 à carga;
- entre uma dispensa e outra, a carga vaza com constante de tempo `recuperacao_s` (exp(-Δt/τ));
- o peso de uma dispensa é 0,5 ** (carga / meia_vida): com carga igual a `meia_vida`, vale a metade.

Daí o teto: numa rajada, as dispensas somam no máximo 1 / (1 - 0,5 ** (1 / meia_vida)) dispensas
inteiras, por mais que sejam (com meia_vida 10, são 14,9; com 5, são 7,7). Ao longo de um dia, a
recuperação devolve um pouco desse peso, na proporção da duração do dia sobre `recuperacao_s`.

Desabituação: um estímulo bom e diferente devolve a resposta. Cada carinho tira uma fração da carga
(DESABITUACAO_CARINHO em ajustes.py). Quem dispensa e também faz carinho continua ensinando com a
dispensa quase inteira; quem só dispensa encontra o teto. Sem isso, o cenário misto (20 dispensas e
10 carinhos por dia) também mudaria, porque tem tantas dispensas quanto o duro.

`meia_vida` igual a 0 desliga a habituação: toda dispensa pesa 1, como antes.
O estado vive só na memória do processo: se o app fecha, a carga volta a zero e a próxima dispensa
pesa inteira (o erro, se houver, é para o lado do comportamento antigo).
"""
import math


class Habituacao:
    """Carga de dispensas recentes; diz quanto a próxima pesa no aprendizado."""

    def __init__(self, meia_vida, recuperacao_s):
        """meia_vida: dispensas seguidas para o peso cair à metade (0 desliga). recuperacao_s: τ da volta, em s."""
        if recuperacao_s <= 0:
            raise ValueError("recuperacao_s precisa ser positiva")
        self.meia_vida = float(meia_vida)
        self.recuperacao_s = float(recuperacao_s)
        self.carga = 0.0
        self.ultimo = None

    @property
    def ligada(self):
        return self.meia_vida > 0.0

    def _carga_em(self, agora):
        if self.ultimo is None:
            return 0.0
        passou = max(0.0, float(agora) - self.ultimo)
        return self.carga * math.exp(-passou / self.recuperacao_s)

    def peso(self, agora):
        """Quanto uma dispensa agora pesaria (1 = inteira), sem registrá-la."""
        if not self.ligada:
            return 1.0
        return 0.5 ** (self._carga_em(agora) / self.meia_vida)

    def registrar(self, agora):
        """Uma dispensa aconteceu agora: devolve o peso dela e soma 1 à carga."""
        valor = self.peso(agora)
        if self.ligada:
            self.carga = self._carga_em(agora) + 1.0
            self.ultimo = float(agora)
        return valor

    def desabituar(self, fracao):
        """Um estímulo bom e diferente (carinho) devolve a resposta: tira esta fração da carga (desabituação)."""
        if self.ultimo is not None:
            self.carga *= 1.0 - min(1.0, max(0.0, float(fracao)))

    def teto_rajada(self):
        """Soma máxima dos pesos de uma rajada infinita, sem tempo para recuperar (inf se desligada)."""
        if not self.ligada:
            return math.inf
        return 1.0 / (1.0 - 0.5 ** (1.0 / self.meia_vida))
