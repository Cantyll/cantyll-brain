# Arquitetura do Pestinha

Este documento explica como as partes conversam. Para o que cada arquivo faz, veja o README de cada
pasta em `pestinha/`; para os detalhes da rede, [REDE_NEURAL.md](REDE_NEURAL.md).

## Visão geral

```text
   o sistema (programa ativo, ocioso,         você (mouse: cutucar, carinho,
   janelas, tela cheia)                     arrastar, arremessar, menu)
            │                                         │
            ▼                                         ▼
   sense/ ─► canais 0..1 ◄──────────── body/pet.py (gestos) e controle/interacao.py
            │
            │   + sinais internos: homeostase (tédio, carência, cansaço), condicionamento,
            │     cantinho (preso, placa, visita, rancor, receio), pedido de trabalho
            ▼
   core/nervous_system.py ── rede LIF: sensores ─► interneurônios ─► motores
            │                                              │
            ▼                                              ▼
   motores de expressão                            motores de decisão
   (tom motor, olhar, emoção)                      (sentar, fugir, cartaz, canto,
            │                                       travessura, papel, aceitar)
            ▼                                              │
   body/ (PetState, Behavior) ◄── mind/ (controladores) ◄──┘
            │                          │
            ▼                          ▼
   janela do pet                  world/ (post-its, memes, cartazes, notebook, fogos, placa)
```

## Camadas

```text
core  <  sense  <  body  <  world  <  mind  <  ui  <  controle  <  app.py
```

Cada camada só importa das que estão à esquerda dela, além dos módulos compartilhados
(`ajustes`, `config`, `paths`, `store`, `log`, `mathutil`, `settings_store`). Isso é verificado por
`tests/test_arquitetura.py`, que também garante que `core/` não usa Qt nem API do sistema.

| Camada | Responsabilidade | Qt | Depende do sistema |
|---|---|:-:|:-:|
| `core/` | Rede neural, emoção, homeostase, homeostase sináptica, memória episódica, condicionamento, física, protesto | não | não |
| `plataforma/` | Tudo que depende do sistema: janelas, teclado, tempo ocioso, atalho (um módulo por sistema) | não | sim |
| `sense/` | O que as leituras significam e registro da rotina | não | não (usa `plataforma/`) |
| `body/` | Janela do pet, estado que ele mostra, comportamento, bolinha | sim | não (usa `plataforma/`) |
| `world/` | Objetos na tela e a janela arrastável base | sim | não |
| `mind/` | Controladores: ligam as decisões da rede à cena | sim | não |
| `ui/` | Telas: permissões, bandeja, passo a passo, monitor, painel de protesto | sim | não (usa `plataforma/`) |
| `controle/` | Mixins de `PestinhaApp`: sessão e interação | sim | não |
| `app.py` | Composição e os três ciclos | sim | sim |

## Os ciclos

Tudo roda na thread do Qt, em relógios (`QTimer`) criados em `PestinhaApp.__init__`:

| A cada | Método | O que faz |
|---|---|---|
| 16 ms | `frame` | Física, comportamento, cantinho, notebook, bolinha, revolução, travessuras, desenho |
| 100 ms | `think` | Sentidos → rede → motores → emoção, protesto, sono, aprendizado, festa, mesa |
| 250 ms | `scan_windows` | Barras de título onde ele pode pousar |
| 500 ms | `sense` | Programa ativo, tempo ocioso, tela cheia |
| 30 s | `save` | Grava rede, homeostase, memória, condicionamento, protesto e cantinho |

`think` integra pelo **tempo real** decorrido (em passos de até 100 ms, com no máximo 2 s por atraso),
então um ciclo atrasado não muda o ritmo da rede nem da homeostase.

## Política de sessão

Fica em `controle/sessao.py`, num lugar só:

- **Pausado, desligado (pânico) ou apagando os dados** (`_congelado`): nada de rede, sentidos, decisões
  ou mudanças de estado por interação. Na retomada, os prazos (episódios, cantinho, pedido) são
  deslocados pelo tempo parado.
- **Escondido ou desligado** (`update_visibility`): nada fica na tela, e qualquer arraste em andamento é
  cancelado.
- **Apagar todos os dados**: para a gravação do log, apaga `memory/` e encerra sem gravar mais nada.

## Decisões: rede ou regra

As decisões de comportamento saem dos motores de decisão da rede (tabela em
[REDE_NEURAL.md](REDE_NEURAL.md)). Continuam como regra explícita:

- condições do corpo (dormindo, segurado, no ar, em missão);
- estágios do protesto (acúmulo de insatisfação com limiar);
- sono pela pressão de sono e pelo relógio (`core/ritmo.py`, `mind/sleep.py`); a energia continua como drive, mas não manda no sono;
- qual travessura fazer (memória episódica com bandit contextual).

**Pendente (decisão D5, spec seção 14):** os gânglios da base podem passar a liberar as ações, no lugar das regras de limiar e sorteio. As guardas continuam fora da rede em qualquer caso. Até a decisão, vale o que está escrito acima.

## Aprendizado

| Mecanismo | Onde | O que aprende |
|---|---|---|
| Habituação | `core/nervous_system.py` | Estímulo repetido perde força e recupera com o tempo |
| Três fatores | `core/nervous_system.py` (`learn`) | Contextos ligados a carinho (+) e a dispensa ou castigo (−) |
| Condicionamento | `core/conditioning.py` | Antecipar cutucada/arraste (`ANTICIPATE`) e ir para o canto (`ANTECIPA_PLACA`) |
| Memória episódica | `core/episodic.py` | Qual travessura dá certo em cada contexto; o castigo pune a última |
| Replay noturno e homeostase sináptica (SHY) | `core/homeostase_sinaptica.py`, `core/episodic.py`, `mind/sleep.py` | Consolida, no sono, os episódios mais marcantes; ao dormir, cada sinapse aprendida perde 20%, e o replay para de empurrar uma sinapse ao chegar a 50% do limite |
| Cantinho | `mind/castigo_ctl.py` | Fugas que deram certo (memória de fuga) ou errado (receio) e rancor |

## Conteúdo de cada pet

Frases, cartazes, memes e imagens vêm de `Paths.conteudo(id)` (`ConteudoPaths`), que procura cada item
primeiro em `pets/<id>/` e depois em `assets/comum/`. Sem nenhum dos dois, o caminho devolvido é o da
pasta do pet, que não existe: os cartazes usam as frases neutras de `core/protesto.py` (`DEFAULT_SIGNS`)
e as travessuras que dependem de memes ou post-its não são oferecidas. Nenhum caminho leva à pasta de
outro pet. Os cartazes do cantinho do castigo são as seções `[castigo]` e `[xingamento]` do mesmo
`cartazes.txt`, relidas a cada cartaz.

## Persistência

Todos os arquivos ficam na pasta de dados (veja [PRIVACIDADE.md](../PRIVACIDADE.md)): `memory/` ao lado do
programa ou, no executável do Windows sem uma `memory/` já existente, `%LOCALAPPDATA%\Pestinha`
(`paths.pasta_de_dados`). Os caminhos saem só de
`paths.py`: `Paths` tem o que é global (permissões, rotina, painéis, log) e `Paths.pet(id)` devolve um
`PetPaths` com os oito arquivos de estado de um personagem, em `memory/pets/<id>/`. O id passa por
`pet_id_valido` antes de virar nome de pasta.

A versão antiga gravava tudo solto em `memory/`. Ao abrir, `migracao.py` leva esses arquivos para a pasta
do pet: copia (temporário e troca), confere byte a byte e no formato real (JSON e JSONL), e só então move
os originais para `memory/legado/<pet>/` e grava o marcador `.migrado`. Conflito ou erro param tudo
daquele pet sem sobrescrever nada; o app abre em modo compatível (`Paths.pet_legado`, os arquivos antigos)
e avisa na bandeja. `migracao.restaurar` desfaz. Pastas de memória não criam personagens: os pets
selecionáveis vêm só de `pets/*.json`.

Toda leitura e escrita passa por `store.py`:

- escrita atômica (arquivo temporário e troca);
- leitura tolerante: arquivo ausente ou ilegível vira o valor padrão, e o ilegível é guardado como
  `.corrompido`;
- `NaN` e infinito são recusados na leitura e na escrita;
- cada modelo valida tipos e domínio ao carregar e, se algo estiver errado, não aplica nada.

## Como acrescentar um comportamento

1. **Sinal novo para a rede:** acrescente o canal em `SENSORY_SPEC` e as conexões em `CONNECTIONS`
   (`core/nervous_system.py`), e alimente o valor em `PestinhaApp.think`.
2. **Decisão nova:** crie um motor de decisão em `MOTOR_SPEC`, inclua em `DECISION_MOTORS` e leia a
   taxa no controlador (`mind/`), com o limiar em `ajustes.py`.
3. **Objeto novo na tela:** em `world/`, usando `overlay_flags()` e `set_no_activate()` para não
   roubar o foco.
4. **Números de ajuste:** em `ajustes.py`, com o intervalo válido em `_LIMITES`.
5. **Testes:** um teste para o comportamento e, se houver estado salvo, um para dados inválidos.
6. **Documentação:** rode `python ferramentas/gerar_readmes.py` e `python ferramentas/gerar_doc_rede.py`.

## Regras do projeto

- Nenhum pet move nem clica o cursor de verdade.
- Ele nunca tira o foco da janela que você está usando.
- Fechar, dispensar, pausar e o pânico sempre funcionam.
- Nada de ler conteúdo ou título de janela.
- Nada de culpar, pressionar ou bloquear a pessoa para ela usar mais o app.

## Regras do núcleo biológico (R1 a R7)

Cópia da seção 1 da [especificação do núcleo biológico](ESPECIFICACAO_NUCLEO_BIOLOGICO.md). Nenhum teste compara as duas cópias; esse teste não é deste PR.

- **R1. Sem culpa.** Nenhum estado cresce ou decai para pressionar a pessoa a voltar. Carência leva a sono ou repouso, nunca a tristeza ativa. Vale para carência em geral, nos dois casos: ausência (você fora do computador) e negligência (você presente, ignorando o pet). Decidido pelo Cantyll em 2026-11-11. Base: a seção «Regras do projeto», acima neste arquivo.
- **R2. Reforço só por erro de predição.** Recompensa bruta não reforça comportamentos que chamam atenção, como `PEDIDO`.
- **R3. Crescimento não é disparado por recompensa bruta.** Vale para sinaptogênese e neurogênese.
- **R4. Segurança fica fora da rede.** Tela cheia, usuário ausente e limites de execução continuam em código de regras (guardas), que podem vetar qualquer ação da rede.
- **R5. Biologia como fonte de fenômenos testáveis, não como cópia.** Cada parte tem nome biológico, função e teste.
- **R6. Privacidade.** A rede recebe as mesmas categorias que `sense/senses.py` já produz. O estado salvo tem contagens e pesos, nunca títulos ou conteúdo. Base: `PRIVACIDADE.md`.
- **R7. Mudança por fase, reversível.** Cada fase é ligada por configuração. O LIF continua disponível até o novo núcleo passar nos testes.

## Como a decisão funciona

A rede neural decide **a tendência**; as regras decidem **as opções e a execução**. Em resumo:

**O que é decidido pela rede** (em `core/nervous_system.py`, com a semente e o temperamento do pet):
- Qual dos 15 motores está mais forte: sentar no notebook, fugir do canto, colar cartaz, ir para o canto,
  aprontar, atirar papel na revolução, aceitar o castigo, expressões (alegria, raiva, tristeza...).
- A intensidade de cada motor (taxa de disparo em Hz). Essa taxa vira probabilidade: a chance de colar um
  cartaz e de aprontar uma travessura é a taxa do motor, não um sorteio fixo. Fugir e aceitar o perdão
  dependem de a taxa passar de um limiar.
- A emoção, a insatisfação (raiva e tristeza acumulam com a taxa dos motores) e os gestos (pular, girar,
  balançar) são calculados a partir dessas taxas (`core/motor.py`, `core/emotion.py`, `core/protesto.py`).

**O que é aprendido**
- As sinapses de sentidos para a rede mudam com a experiência (aprendizado de três fatores).
- Condicionamento: o pet aprende a antecipar sinais (a placa do castigo, o cursor chegando), `core/conditioning.py`.
- Memória de travessuras: escolhe, por tentativa e erro, entre as ações que são permitidas naquele momento,
  guardando o que deu certo em cada situação (`core/episodic.py`).

**O que é regra escrita à mão** (são limiares e limites, não decisões do pet):
- Como os sentidos viram números: quais programas contam como trabalho, o que é ocioso, o que é tela cheia.
- Os limiares de disparo (ex.: a raiva precisa passar de um valor para virar cartaz; a fuga precisa encher uma
  carga) e os estágios de insatisfação (quanta raiva para cada estágio).
- O que pode acontecer: não aprontar durante o castigo, não dormir em protesto forte, a lista de travessuras
  permitidas pelas suas permissões.
- A execução física: para onde ele anda, por quanto tempo, a velocidade e a física da queda e do pouso.
- O conteúdo que aparece (frases e memes), que vem dos arquivos do personagem.

Na prática: a rede decide quando e com que vontade o pet quer fazer algo; as regras decidem o que é possível
e como isso acontece na tela.

