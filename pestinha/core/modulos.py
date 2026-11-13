"""
MODULOS - o registro de módulos: os pontos de encaixe fixos por onde uma frente nova entra no app.

Cada frente do plano (docs/PLANO_DE_EXECUCAO_CANTYLL.md) é um `Modulo`, ligado por uma chave em
`config.FRENTES` e desligado por padrão (R7). O app chama o registro sempre nos mesmos lugares, e o
registro chama cada módulo ligado, na ordem em que foram registrados:

    carregar(pasta)                   ao abrir, com a pasta de estado do módulo
    sentir(intensidades, dt)          a cada `think`, antes do passo da rede; pode acrescentar canais
    depois_do_passo(cerebro, drives, dt)  logo depois do passo da rede
    valor_esperado()                  V de δ = r − V no aprendizado; no máximo um módulo responde
    ao_dormir(cerebro) / ao_acordar(cerebro)   quando ele adormece e quando acorda
    deslocar(segundos)                na volta da pausa: os prazos do módulo andam junto
    estado()                          resumo para a fotografia diária
    salvar(pasta)                     junto com o resto, a cada 30 s e ao fechar

Sem nenhum módulo ligado, o registro não faz nada: as intensidades passam iguais, o valor esperado é
None (o app usa 0, como antes) e nenhuma pasta é criada.

Um módulo que levanta erro num encaixe é desligado na hora e o erro fica em `erros`: uma frente com
defeito não derruba o pet, não impede o pânico, a pausa nem o fechamento.

Puro (sem Qt): a fábrica de cada frente recebe o app, mas só usa o que precisar.
"""

import importlib
import re

from ..log import log

NOME_DE_MODULO = re.compile(r"^[a-z][a-z0-9_]{0,39}$")     # vira nome de pasta

ENCAIXES = ("carregar", "sentir", "depois_do_passo", "valor_esperado", "ao_dormir", "ao_acordar",
            "deslocar", "estado", "salvar")


class Modulo:
    """Contrato de uma frente. Cada método padrão não faz nada; a frente sobrescreve só o que usa."""
    nome = ""                                      # igual à chave em config.FRENTES

    def sentir(self, intensidades, dt):
        """Antes do passo da rede. Pode acrescentar ou mudar canais em `intensidades` (dict, no lugar)."""

    def depois_do_passo(self, cerebro, drives, dt):
        """Logo depois do passo da rede, com o cérebro e a homeostase."""

    def valor_esperado(self):
        """V de δ = r − V. None = este módulo não responde. No máximo um módulo ligado sobrescreve isto."""
        return None

    def ao_dormir(self, cerebro):
        """Ele acabou de adormecer."""

    def ao_acordar(self, cerebro):
        """Ele acabou de acordar."""

    def deslocar(self, segundos):
        """Volta da pausa: empurra os prazos do módulo pelo tempo parado."""

    def estado(self):
        """Resumo serializável para a fotografia diária (só contagens, taxas e pesos; R6)."""
        return {}

    def salvar(self, pasta):
        """Grava o estado do módulo dentro de `pasta` (use store.write_json)."""

    def carregar(self, pasta):
        """Lê o estado de `pasta`. Dado inválido: não aplica nada."""


def _responde_valor(modulo):
    """Diz se o módulo sobrescreve valor_esperado (é quem dá o V do aprendizado)."""
    return type(modulo).valor_esperado is not Modulo.valor_esperado


class RegistroDeModulos:
    """Os módulos ligados, na ordem de registro, e as chamadas de cada encaixe."""

    def __init__(self, pasta_de=None):
        """pasta_de: função nome -> pasta de estado do módulo (Paths.pet(id).modulo). None: sem estado em disco."""
        self.modulos = []
        self.pasta_de = pasta_de
        self.erros = []                            # (módulo, encaixe, texto do erro)

    def __len__(self):
        return len(self.modulos)

    def nomes(self):
        """Nomes dos módulos ativos, na ordem."""
        return [m.nome for m in self.modulos]

    def registrar(self, modulo):
        """Acrescenta um módulo. Recusa nome inválido, nome repetido e um segundo módulo que responda o V."""
        if not isinstance(modulo, Modulo):
            raise TypeError(f"não é um Modulo: {modulo!r}")
        if not NOME_DE_MODULO.match(modulo.nome or ""):
            raise ValueError(f"nome de módulo inválido: {modulo.nome!r}")
        if modulo.nome in self.nomes():
            raise ValueError(f"módulo repetido: {modulo.nome}")
        if _responde_valor(modulo):
            outro = next((m.nome for m in self.modulos if _responde_valor(m)), None)
            if outro:
                raise ValueError(f"{modulo.nome} e {outro} respondem o valor esperado: só um pode")
        self.modulos.append(modulo)
        return modulo

    def _chamar(self, encaixe, *args):
        """Chama `encaixe` em cada módulo. Quem falhar sai do registro e o erro fica guardado."""
        resultados = []
        for modulo in list(self.modulos):
            try:
                resultados.append((modulo, getattr(modulo, encaixe)(*args)))
            except Exception as erro:          # uma frente com defeito não derruba o pet
                self.modulos.remove(modulo)
                self.erros.append((modulo.nome, encaixe, repr(erro)))
                log(f"[modulos] {modulo.nome} desligado: erro em {encaixe}: {erro!r}")
        return resultados

    def _pasta(self, modulo):
        return None if self.pasta_de is None else self.pasta_de(modulo.nome)

    # ---------------- encaixes ----------------

    def carregar(self):
        for modulo in list(self.modulos):
            pasta = self._pasta(modulo)
            if pasta is None:
                continue
            try:
                modulo.carregar(pasta)
            except Exception as erro:
                self.modulos.remove(modulo)
                self.erros.append((modulo.nome, "carregar", repr(erro)))
                log(f"[modulos] {modulo.nome} desligado: erro em carregar: {erro!r}")

    def sentir(self, intensidades, dt):
        """Passa as intensidades por cada módulo, no lugar. Devolve o mesmo dict."""
        self._chamar("sentir", intensidades, dt)
        return intensidades

    def depois_do_passo(self, cerebro, drives, dt):
        self._chamar("depois_do_passo", cerebro, drives, dt)

    def valor_esperado(self):
        """O V do único módulo que responde, ou None. Valor não numérico ou não finito vale None."""
        for _modulo, valor in self._chamar("valor_esperado"):
            if valor is None:
                continue
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor \
                    or valor in (float("inf"), float("-inf")):
                return None
            return float(valor)
        return None

    def ao_dormir(self, cerebro):
        self._chamar("ao_dormir", cerebro)

    def ao_acordar(self, cerebro):
        self._chamar("ao_acordar", cerebro)

    def deslocar(self, segundos):
        self._chamar("deslocar", segundos)

    def estado(self):
        """{nome: estado()} de cada módulo ativo."""
        return {modulo.nome: valor for modulo, valor in self._chamar("estado")}

    def salvar(self):
        for modulo in list(self.modulos):
            pasta = self._pasta(modulo)
            if pasta is None:
                continue
            try:
                modulo.salvar(pasta)
            except Exception as erro:          # não para: os outros módulos e o resto do app gravam
                self.erros.append((modulo.nome, "salvar", repr(erro)))
                log(f"[modulos] {modulo.nome} não salvou: {erro!r}")


def criar_registro(frentes, caminhos, app, pasta_de=None, importar=importlib.import_module):
    """
    Monta o registro com as frentes ligadas em `frentes` ({nome: bool}). `caminhos` diz onde mora a
    fábrica de cada frente ({nome: "pestinha.x.y"}); o módulo Python precisa ter `criar(app)`, que
    devolve um Modulo (ou None, se não houver nada a fazer). Frente ligada sem fábrica, ou com fábrica
    que falha, fica de fora com um aviso no log: o app abre do mesmo jeito.
    """
    registro = RegistroDeModulos(pasta_de)
    for nome, ligada in frentes.items():
        if not ligada:
            continue
        caminho = caminhos.get(nome)
        if not caminho:
            log(f"[modulos] frente {nome} ligada, mas sem módulo no app")
            continue
        try:
            modulo = importar(caminho).criar(app)
            if modulo is None:
                continue
            if modulo.nome != nome:
                raise ValueError(f"o módulo se chama {modulo.nome!r}, a chave é {nome!r}")
            registro.registrar(modulo)
        except Exception as erro:
            registro.erros.append((nome, "criar", repr(erro)))
            log(f"[modulos] frente {nome} não entrou: {erro!r}")
    registro.carregar()
    return registro
