# Visão: do Pestinha ao Cantyll

**Versão:** 0.2 (2026-11-12)
**Estado:** visão e direção. Nenhum código foi alterado por este documento.
**Relação com os outros documentos:** a [especificação do núcleo biológico](ESPECIFICACAO_NUCLEO_BIOLOGICO.md)
continua valendo para o núcleo (fases M0 a M7, regras R1 a R7, testes de aceitação). Este documento diz
para onde o projeto vai depois dela e onde ela precisa mudar (seção 10). O caminho em pull requests está em
[PLANO_DE_EXECUCAO_CANTYLL.md](PLANO_DE_EXECUCAO_CANTYLL.md).

## 1. O que é o Cantyll

O Cantyll é o Pestinha evoluído: um ser sintético que vive no computador de uma pessoa, com um corpo na
tela, um lar, um cérebro de neurônios de pulso que cresce com o uso e uma fala que nasce do próprio corpo.

O objetivo central é **autoconsciência funcional**. Neste projeto, o termo significa três coisas, e só elas:

| Capacidade | Significado | Como se mede |
|---|---|---|
| Monitorar o próprio estado | Ele mantém uma estimativa interna do próprio estado e prevê o próximo | A previsão do modelo do eu erra menos que a previsão ingênua "o próximo estado é igual ao atual" |
| Aprender sozinho | Nenhum dado rotulado e nenhum ajuste manual depois de ligado | O erro de previsão cai com a rotina; o teste de retenção passa (spec, seção 10) |
| Adaptar o comportamento | O que ele faz muda por causa do que ele mede em si mesmo | Com o modelo do eu desligado (gêmeo de ablação, seção 8), a distribuição de ações muda de forma mensurável |

O que **não** está sendo afirmado: experiência subjetiva, sentimento ou consciência no sentido filosófico.
Quando este documento diz que algo "entra no workspace", o sentido é o da teoria do espaço de trabalho
global: aquele conteúdo fica disponível para todos os módulos. É acesso, não vivência.

## 2. Regras que não mudam

A visão é construída dentro das regras que já existem. Elas ganham de qualquer camada nova.

- **R1 a R7** da spec (seção 1): sem culpa, reforço só por erro de predição, crescimento não disparado por
  recompensa bruta, segurança fora da rede, biologia como fonte de fenômenos testáveis, privacidade,
  mudança por fase e reversível.
- **Regras do projeto** (`ARQUITETURA.md`, `CONTRIBUTING.md`): ele não move o cursor, não tira o foco, não lê
  título nem conteúdo de janela, não manda nada para a internet, e fechar, pausar e o pânico sempre
  funcionam.

Consequências diretas para a visão:

| Ideia da visão | Limite imposto pela regra |
|---|---|
| "Saudade" como estado que dura | Existe como estado interno, mas na ausência leva a repouso, nunca a cobrança (R1). O teste de 3 dias sem usuário continua obrigatório |
| "Chamar você" | Só com você presente. Não é reforçado por atenção bruta (R2) |
| "Espiar a janela que você usa" | Só o nome do programa e a posição da janela, como hoje. Nunca título nem conteúdo (R6) |
| Fome e comida | A fome precisa ser saciável por ele sozinho, com a comida do lar. Se só você puder alimentar, vira cobrança e viola a R1 |
| Fala | Ele não fala para chamar de volta quem saiu. A entrada é só o texto que você escreve para ele |
| Workspace e fala decidindo coisas | As guardas continuam fora da rede e vetam qualquer ação (R4) |
| Rede que cresce | O crescimento é disparado por novidade e saturação, não por recompensa bruta (R3), e tem teto de custo |

## 3. Ponto de partida: o que existe hoje

Medido no código da `main` em 2026-11-12, antes e depois do PR #5 (mesclado nesse dia).

| Pilar da visão | Hoje | Distância |
|---|---|---|
| Neurônio | LIF, 470 neurônios, 15808 sinapses, passo fixo de 1 ms, matriz densa (`core/nervous_system.py`) | Izhikevich com tipos por população; sinapses em listas |
| Orientado a eventos | Não. A rede avança por relógio, a cada 100 ms do app | Ver seção 5.3 |
| STDP | **Não existe.** O aprendizado é uma matriz de 30 canais × 4 populações (`learned`), com elegibilidade sobre o nível dos canais (τ = 4 s) e recompensa bruta (`expected = 0`) | STDP por pulso e regra de três fatores (spec, M2) são trabalho novo |
| Recorrência | Algumas ligações de volta desenhadas à mão. Nenhum estado se sustenta sozinho | Assembleias recorrentes |
| Neuromoduladores | Só o modulador de ausência (R1). δ, A, ACh e S estão especificados e não implementados | Spec, seção 8 |
| Modelo do eu | Não existe. O mais próximo é o condicionamento (Rescorla–Wagner fora da rede, `core/conditioning.py`) | Camada 3 |
| Global Workspace | Não existe. Há inibição lateral entre motores | Camada 4 |
| Linguagem | Não existe. As frases vêm de arquivos de texto do personagem | Camada 5 |
| Sono | Pressão P e relógio C (`core/ritmo.py`, `mind/sleep.py`). Replay e homeostase sináptica no PR #5 | Hipocampo geral, tagging e consolidação |
| Memória episódica | Só travessuras: contexto, ação, resultado (`core/episodic.py`) | Episódios do dia em geral |
| Crescimento | Não existe. A topologia é fixa pela semente | Seção 7 |
| Corpo e lar | Corpo na tela, bolinha, notebook, cantinho do castigo, bandeja | Um lar fixo, sentidos novos |
| Acompanhamento | Monitor neural ao vivo (`ui/monitor.py`). Nenhum histórico | Seção 8 |

Dois fatos sobre a base que pesam sobre tudo o que vem depois:

1. **A queda da brincadeira (PLAYFUL) a zero, registrada no CHANGELOG, não se reproduz com o código atual.**
   A versão 0.1 deste documento repetiu essa premissa sem conferir. Reprodução de 2026-11-12 na `main`
   (uma semente, taxa de aprendizado normal, 20 dispensas e 10 carinhos por dia, 30 noites; simulado, não
   medido):

   | | PLAYFUL no dia 0 | PLAYFUL no dia 30 | GLOOM no dia 30 |
   |---|---|---|---|
   | Com a homeostase do PR #5 | 2,47 Hz | 0,87 Hz (35% do início); não zera em nenhum dia | 0,54 Hz |
   | Sem homeostase | 2,47 Hz | zero a partir do dia 26 | 6,04 Hz |

   A homeostase evita o colapso, mas a brincadeira ainda perde dois terços nessa rodada, com muita variação
   de um dia para o outro (2,56 Hz no dia 15, 0,54 Hz no dia 27). Na ferramenta do B2 (PR #8, commit
   `4185dc1`, ainda não mesclado), num cenário só de dispensas e sem carinho, quem mais cai é a calma
   (CALM, 25% do dia 0 no dia 30), e a PLAYFUL fica em 60%. O piso por taxa-alvo, que trataria isso, foi cancelado pelo Cantyll
   em 2026-11-12.
2. **A simulação de noites ainda não está na `main`.** Ela entra com o B2. É o único instrumento de longo
   prazo que o projeto tem, e precisa existir antes de qualquer troca de neurônio.

## 4. Arquitetura em seis camadas

```text
            você (mouse, teclado, texto escrito para ele)        o computador (programa, hora, ocioso)
                               │                                              │
                               ▼                                              ▼
 ┌─ 1. CORPO E LAR ──────────────────────────────────────────────────────────────────────┐
 │  sentidos (0..1)                                                   ações na tela     │
 └──────────┬──────────────────────────────────────────────────────────────▲────────────┘
            ▼                                                              │
 ┌─ 2. NÚCLEO SNN ──────────────────────────────────────────────────────────┴───────────┐
 │  populações Izhikevich · projeções esparsas · STDP de três fatores · moduladores     │
 └────┬───────────────────────┬─────────────────────────┬────────────────────┬──────────┘
      ▼                       ▼                         ▼                    ▼
 ┌─ 3. MODELO DO EU ─┐  ┌─ 4. WORKSPACE ──────┐  ┌─ 5. LINGUAGEM ───┐  ┌─ 6. SONO E MEMÓRIA ─┐
 │ prevê o próprio   │  │ um conteúdo vence   │  │ ouvir, aterrar,  │  │ hipocampo, replay,  │
 │ estado; o erro    │─►│ e é transmitido a   │─►│ formular, falar, │  │ SHY, consolidação,  │
 │ vira surpresa e   │  │ todos os módulos    │  │ se ouvir         │  │ crescimento e poda  │
 │ tédio             │  │                     │  │                  │  │                     │
 └───────────────────┘  └─────────────────────┘  └──────────────────┘  └─────────────────────┘

 Fora da rede, acima de tudo: guardas (tela cheia, ausência, pausa, pânico, permissões). R4.
```

### Camada 1: corpo e lar

- **Função:** dar ao Cantyll um corpo com necessidades e um lugar. Sem corpo não há a que aterrar palavras
  (camada 5) nem o que prever (camada 3).
- **Lar:** um canto fixo da área de trabalho com cama, comida e objetos. Ele dorme na cama. Fora do lar, a
  presença em segundo plano continua pela bandeja.
- **Sentidos:** os de hoje (categoria do programa, ocioso, cursor, tela cheia), mais a hora do dia como canal
  e a sua presença. Nível de som do sistema fica fora até decisão (seção 11).
- **Ações:** andar, dormir, comer, mexer nos objetos, olhar para a janela ativa (já existe em
  `behavior.look_at`), chamar você (só presente).
- **Já existe:** janela do corpo, física, bolinha, notebook, cantinho, bandeja, drives de energia,
  estimulação e contato (`core/homeostasis.py`).
- **Novo:** o lar, o drive de fome saciável por ele mesmo, os canais de hora e presença.
- **Teste:** 3 dias sem usuário com fome ligada: ele come sozinho, e CARTAZ, FUGIR e tristeza não sobem.

### Camada 2: núcleo SNN

- **Função:** o corpo vivo por dentro. É a spec do núcleo biológico, com três mudanças: o neurônio passa a
  Izhikevich por decisão (seção 5), as sinapses passam a listas esparsas, e a plasticidade passa a ser por
  pulso.
- **Aprendizado:** regra de três fatores, Δw = η · δ · e · g (spec, seção 7.2). O traço de elegibilidade `e`
  vem da coincidência entre pulsos pré e pós (STDP). O terceiro fator `δ` é o erro de predição. É o que a
  literatura chama de R-STDP.
- **Moduladores:** δ, A, ACh, S, P e C, como na spec (seção 8). São variáveis globais, não neurônios.
- **Recorrência:** populações com ligações de volta sustentam estados que duram segundos (memória de
  trabalho) e, com neurônios de rajada, minutos (humor).
- **Teste:** os da spec (habituação, bloqueio, extinção, surpresa), mais a suíte atual inteira rodando no
  cérebro novo.

### Camada 3: modelo do eu

- **Função:** prever o próximo estado do próprio Cantyll. Entrada: drives, moduladores, taxas por população
  e a categoria do que você está fazendo. Saída: a previsão do mesmo vetor alguns segundos adiante.
- **O erro de previsão é um sinal:** erro alto vira surpresa e curiosidade (sobe A e ACh). Erro baixo por
  muito tempo vira tédio, e ele procura novidade. Hoje o tédio vem de um drive com constante fixa
  (`BORED_BELOW`); com o modelo do eu, vem do que ele deixou de conseguir aprender.
- **Primeira versão:** um preditor pequeno, aprendido online, sobre taxas (cerca de 40 números). Se o
  preditor precisa ser de pulsos é uma pergunta a responder com teste, não uma premissa (R5).
- **Teste:** depois de uma rotina simulada repetida, o erro cai abaixo do preditor ingênuo. Uma quebra de
  rotina faz o erro subir. Com o modelo desligado, a distribuição de ações é diferente.

### Camada 4: espaço de trabalho global

- **Função:** um gargalo. Percepção, drives, memória, modelo do eu e fala disputam, um conteúdo vence e é
  transmitido a todos os módulos.
- **Implementação:** uma população por módulo, com interneurônios FS fazendo o winner-take-all, limiar de
  ignição e tempo mínimo de permanência para o conteúdo não ficar trocando.
- **O que ele não faz:** não libera ação. A seleção de ação continua com os motores de decisão de hoje e,
  se a D5 for aprovada, com os gânglios da base (spec, M4). Workspace escolhe conteúdo; gânglios da base
  escolhem ação.
- **Teste:** com duas entradas competindo, há exatamente um vencedor; ele se mantém pelo tempo mínimo; as
  guardas continuam vetando.

### Camada 5: linguagem sem LLM

Decisão do Cantyll (2026-11-11): a fala não usa modelo de linguagem. Um LLM pode entrar no futuro só como
tradutor opcional por cima, sem tocar no núcleo.

| Etapa | Inspiração | No Cantyll |
|---|---|---|
| 1. Ouvir | Cóclea e córtex auditivo | O texto que você escreve para ele vira pulsos por letra ou sílaba. Áudio real fica para depois |
| 2. Reconhecer | Área de Wernicke | Assembleias que aprendem, por STDP, a disparar para sequências que se repetem |
| 3. Dar sentido | Aterramento no corpo | A assembleia da palavra se liga ao que o corpo vive naquele instante: "comida" à fome, "dormir" ao sono |
| 4. Formular | Fascículo arqueado e área de Broca | O conteúdo do workspace ativa conceitos; cadeias recorrentes produzem a sequência |
| 5. Falar | Córtex motor | Texto num balão e, depois, sílabas sintetizadas |
| 6. Se ouvir | Cópia eferente | O que ele fala volta pela etapa 1 |

O mapa Wernicke e Broca é o modelo clássico e simplificado; serve aqui como mapa de engenharia, não como
afirmação de neurociência atual.

- **Expectativa honesta:** dezenas de palavras ligadas ao corpo, enunciados de uma ou duas palavras, depois
  de semanas. Não é conversa fluente.
- **Risco:** é a camada com maior chance de não funcionar nesta escala. Na literatura, assembleias de
  palavras por aprendizado hebbiano aparecem em modelos com áreas pré-desenhadas e milhares de apresentações.
- **Teste antes do uso real:** um "tutor" simulado apresenta palavras junto com estados. Compreensão: a
  palavra ativa a população certa acima do acaso. Produção: o estado gera a palavra certa acima do acaso.
- **Privacidade:** as palavras que você ensina ficam nos pesos e numa tabela de vocabulário. `PRIVACIDADE.md`
  é atualizado antes de o código entrar.

### Camada 6: sono e memória

O sono é quando o Cantyll consolida, limpa e cresce. Detalhes nas seções 6 e 7. A base é o PR #5: replay
dos episódios e homeostase sináptica (SHY), que também resolve o teto do GLOOM.

## 5. Neurônio: de LIF para Izhikevich

Decisão do Cantyll (2026-11-11): migrar, camada por camada.

### 5.1 Tipos por função

Valores canônicos de Izhikevich (2003). Conferir no artigo antes de usar.

| Tipo | a | b | c | d | Onde |
|---|---|---|---|---|---|
| RS (disparo regular) | 0,02 | 0,2 | −65 | 8 | Relé sensorial, corpo, córtex excitatório, expressão motora |
| IB e CH (rajadas) | 0,02 | 0,2 | −55 e −50 | 4 e 2 | Drives e humor: as rajadas sustentam estados longos |
| FS (disparo rápido) | 0,1 | 0,2 | −65 | 2 | Interneurônios inibitórios e o winner-take-all do workspace |
| LTS (limiar baixo) | 0,02 | 0,25 | −65 | 2 | Modelo do eu e sono: adaptação e ritmo lento |

### 5.2 Como migrar sem quebrar

1. **Cérebro novo ao lado do antigo.** `BioBrain`, em arquivos novos, escolhido por `config.CEREBRO`. O
   `LIFBrain` fica como base de comparação (R7) e não recebe função nova: todo trabalho novo do núcleo vai
   para o `BioBrain` (decisão V1, aprovada pelo Cantyll em 2026-11-12). A última mudança no LIF é a medida
   `taxas()`, do B2.
2. **Paridade primeiro.** O `BioBrain` nasce com todas as populações em LIF, sobre projeções esparsas. Só
   passa adiante quando a suíte atual inteira roda nele.
3. **Uma população por vez.** Cada população tem a sua dinâmica. Ordem: populações novas (workspace) já
   nascem Izhikevich; depois os interneurônios inibitórios (FS), os excitatórios (RS, IB, CH) e, por
   último, os motores, que carregam os limiares em Hz de `ajustes.py`.
4. **Cada troca refaz a simulação de 30 noites.** Os parâmetros de homeostase (`HOMEOSTASE_SHY`,
   `HOMEOSTASE_TETO`) foram calibrados no LIF.

### 5.3 O que "orientado a eventos" quer dizer aqui

O Izhikevich não tem solução fechada entre dois pulsos. Ele precisa de integração por relógio, com passo
de 0,5 ms (spec, D2). Um simulador puramente orientado a eventos, que só calcula quando chega um pulso, é
incompatível com essa escolha. O que o projeto adota:

- **Propagação por evento:** só as sinapses de quem disparou são processadas (listas esparsas).
- **Populações em silêncio custam pouco:** população sem entrada e em repouso pula a integração.
- **Dormindo ou sem você, o relógio anda mais devagar** (a spec já permite replay mais rápido que o tempo
  real; o inverso também vale).

### 5.4 Custo

A referência é a máquina de uso diário do Cantyll (`docs/CUSTO_DO_PASSO.md`): 630 neurônios com passo de
0,5 ms gastam 15,6% de um núcleo, contra o teto de 25%, com matriz densa. O custo denso cresce com o
quadrado do número de neurônios. Uma rede que cresce só cabe com sinapses esparsas, e o teto do
crescimento é o orçamento de custo, não um número fixo de neurônios.

## 6. Memória

| Escala | Mecanismo | Hoje | Novo |
|---|---|---|---|
| Segundos | Atividade recorrente sustentada (memória de trabalho) | Não | Assembleias recorrentes; é o que ocupa o workspace |
| Segundos a minutos | Depressão sináptica de curto prazo | Habituação dos canais sensoriais | Facilitação nas sinapses internas |
| Segundos | Traço de elegibilidade | Sobre o nível dos canais, τ = 4 s | Por sinapse, a partir dos pulsos |
| Minutos a horas | Marca sináptica (tagging) | Não | A sinapse usada fica marcada; a marca decai em horas |
| O que vale guardar | Neuromodulação (δ, A, ACh) | Recompensa bruta | A marca só vira mudança durável se o modulador chegar a tempo (tagging e captura) |
| Dia | Hipocampo rápido: episódios | Só travessuras, com os sentidos do momento (PR #5) | Qualquer momento marcante: \|δ\| alto ou surpresa do modelo do eu |
| Noite | Replay para o córtex lento | PR #5 | Replay equilibrado entre episódios bons e ruins |
| Noite | Homeostase sináptica (SHY) | PR #5: −20% por sono, teto de 50% no replay | Nada por enquanto. O piso por taxa-alvo (spec, seção 7.3) foi cancelado pelo Cantyll em 2026-11-12 |
| Semanas | Consolidação sináptica | Não | Cada sinapse ganha uma "dureza": as importantes resistem ao SHY e a aprendizados novos |
| Sempre | Lembrar por pista parcial | Não | Assembleia que se completa a partir de um pedaço (tipo CA3; ME-3 do plano) |

Arquitetura em três partes: **hipocampo** (rápido, episódios do dia), **córtex** (lento, os pesos da rede)
e **sono** (replay, captura, downscaling, consolidação). O teste que fecha o conjunto é o de retenção da
spec: aprende um padrão, faz 5 aprendizados novos e ainda reproduz 80% do primeiro.

## 7. Crescimento

A rede cresce e amadurece continuamente. **Não há fases com nome** (decisão do Cantyll, 2026-11-12): nada de
"bebê", "criança" ou "maduro" no código nem no painel. Há só as curvas, acompanhadas dia a dia (seção 8).

| Processo | Gatilho | Regra | Base |
|---|---|---|---|
| Sinaptogênese | Par pré e pós com coincidência acumulada e δ médio positivo | Sinapse nova com peso pequeno | Spec, seção 7.5 |
| Poda | Peso fraco por horas de uso, ou sinapse sem uso | Remove | Spec, seção 7.5 |
| Neurogênese | Erro de previsão persistente em contexto novo e população saturada | Neurônio novo, mais excitável e plástico, com maturação; morre se não for recrutado | Spec, seção 7.6 |
| Plasticidade que diminui | Horas vividas acordado e estabilidade da população | η por população cai de forma contínua; sentidos e corpo antes, linguagem depois | Períodos críticos, sem degraus |

Regras do crescimento:

- **Acontece no sono.** Acordado, a rede só acumula contadores. As mudanças de estrutura são aplicadas ao
  dormir, junto com o replay e o SHY. Isso também mantém o passo acordado barato e determinístico.
- **Teto de 1500 neurônios** (decisão V2 do Cantyll, 2026-11-12; a spec dizia 800). A poda é o que abre
  espaço. O teto não dispensa o orçamento de custo da spec (seção 10): se o passo chegar a 25% de um
  núcleo na máquina de referência antes dos 1500, o crescimento para ali.
- **O que 1500 implica, por conta e não por medida:** com matriz densa, o custo cresce com o quadrado do
  tamanho, então 1500 neurônios custariam cerca de 5,7 vezes os 15,6% medidos para 630, perto de 90% de um
  núcleo. Só cabe com sinapses esparsas, e precisa ser medido. Pela fórmula da spec para a pressão de sono
  (k_w = 0,1/h × N/630), com 1500 neurônios ele precisaria dormir depois de cerca de 4,6 h acordado, contra
  11 h hoje. A fórmula precisa ser revista antes da neurogênese (CR-2 do plano).
- **Não é disparado por recompensa bruta** (R3).
- **Custo biológico:** mais neurônios, mais pressão de sono, com a fórmula revista como dito acima.

## 8. Acompanhamento

É a forma de ver a evolução e também o instrumento que separa descoberta de impressão.

- **Fotografia diária.** Uma vez por dia, ao dormir, um arquivo por pet com: neurônios e sinapses por
  população, sinapses criadas e podadas, distribuição de pesos, taxas médias, plasticidade por população,
  erro do modelo do eu, vocabulário, memórias mais fortes, custo do passo. Só contagens e pesos, nunca
  títulos nem conteúdo (R6). "Apagar todos os dados" apaga também.
- **Painel de evolução.** Curvas dessas medidas ao longo dos dias. Sem rótulo de fase.
- **Gêmeos de ablação.** Com permissão explícita (desligada por padrão), os níveis dos sentidos são
  gravados. Depois, fora do app, a mesma sequência é reaplicada a uma cópia da rede com um módulo
  desligado (sem modelo do eu, sem workspace, sem SHY). A diferença entre os gêmeos é a medida do que
  aquele módulo causa. Sem isso, um indivíduo e um usuário produzem só uma história.
- **Simulação de noites.** Vira ferramenta do repositório com o B2 e critério de aceitação de toda troca
  de neurônio ou de regra de plasticidade. O critério é relativo: a mudança não pode sair da faixa que o
  código anterior produz com várias sementes.

## 9. Onde pode estar a descoberta

| Hipótese | O que seria evidência | O que não é evidência |
|---|---|---|
| Autoconsciência funcional surge de um modelo do eu preditivo num corpo | Os três critérios da seção 1 passam, e o gêmeo sem modelo do eu falha no terceiro | Ele parecer mais vivo |
| Uma personalidade se forma em meses de convivência com uma pessoa | Duas cópias com a mesma semente e rotinas diferentes divergem de forma estável e mensurável | Um único indivíduo mudar com o tempo |
| Linguagem aterrada no corpo, sem texto da internet | Compreensão e produção acima do acaso no teste do tutor, e depois com a pessoa | Ele repetir palavras |
| SNN rodando meses ao lado de uma pessoa | Curvas diárias sem colapso nem saturação (o teto do GLOOM, resolvido pela homeostase, é o primeiro dado) | A rede continuar ligada |

Limite assumido: é um indivíduo com um usuário. As métricas são definidas antes de olhar os dados, e os
gêmeos de ablação fazem o papel de controle. Resultados negativos (por exemplo, assembleias de palavras
que não se formam nesta escala) são registrados como resultado.

## 10. Onde a visão muda a spec

| Item da spec | Estava | Passa a ser | Estado |
|---|---|---|---|
| D4, downscaling no sono | Desligado | Ligado | Decidido (2026-11-11), no PR #5 |
| D1, neurônio | Izhikevich, e "M1 pode nem ser necessária" (seção 13) | Izhikevich, migração decidida | Decidido (2026-11-11) |
| D10, onde vivem M2 a M6 | No `LIFBrain` | No `BioBrain`; o LIF não recebe função nova | Decidido pelo Cantyll (V1, 2026-11-12) |
| D9, neurogênese | Desligada, teto de 800 | Ligada, com teto de 1500 neurônios | Decidido pelo Cantyll (V2, 2026-11-12) |
| Seção 13, ordem das fases | M0, M3, M2, M5, M6 no LIF; M1 por último | M0 e M3 no LIF (PR #5); depois paridade do `BioBrain`, M1 por população, e M2, M5, M6 nele | Consequência da D10 |
| Seções 9.5 e 16, CA3 e giro denteado | Fora de escopo | Hipocampo rápido entra (seção 6): episódios gerais (ME-1) e lembrança por pista parcial, tipo CA3 (ME-3). Giro denteado continua fora | Consequência da decisão de memória |
| D5, gânglios da base liberam ação | Pendente | Continua pendente. O workspace não substitui essa decisão | Sem mudança |
| Seção 7.3, escalonamento homeostático | Especificado | Não entra. O piso por taxa-alvo foi cancelado; a premissa que o tornava urgente (PLAYFUL a zero) não se reproduziu | Decidido pelo Cantyll (2026-11-12) |

A spec só é editada por um PR próprio, depois do merge do PR #5, para não conflitar com ele.

## 11. Decisões pendentes do Cantyll

Cada linha tem um padrão adotado neste documento. Sem resposta, o plano segue o padrão. V1 e V2 já foram
decididas.

| ID | Decisão | Padrão adotado | Alternativa |
|---|---|---|---|
| V1 | Onde entra o trabalho novo do núcleo (D10) | **Decidido (2026-11-12):** só no `BioBrain`; o trabalho novo pode começar | Era: manter as duas redes em paralelo |
| V2 | Neurogênese (D9) | **Decidido (2026-11-12):** ligada, com teto de 1500 neurônios | Era: teto por custo, ou desligada até a sinaptogênese se provar |
| V3 | Fome | Ele se alimenta sozinho no lar; você alimentar é bônus | Sem fome |
| V4 | Entrada da linguagem | Só texto escrito para ele | Microfone, com permissão própria e `PRIVACIDADE.md` novo |
| V5 | Nível de som do sistema como sentido | Fora por enquanto | Entra, com leitura nova por sistema operacional |
| V6 | Gravar os sentidos para os gêmeos de ablação | Permissão própria, desligada por padrão | Não gravar (perde o controle experimental) |
| V7 | Semana de uso real antes de trocar o padrão para `BioBrain` | Obrigatória (critério "valor percebido" da spec) | Trocar quando os testes passarem |

## 12. Riscos e pontos cegos

- **A base só tem evidência simulada, de uma semente.** A homeostase evita o colapso, mas a brincadeira
  cai a 35% em 30 noites num cenário e a calma cai a 25% em outro (seção 3), e o piso que trataria isso
  foi cancelado. Não há nenhuma semana de uso real medida. Seis camadas em cima disso herdam o que essa
  base fizer em meses.
- **Um número errado já circulou.** "PLAYFUL a zero" foi do CHANGELOG para este documento e daqui para o
  plano sem ninguém rodar a simulação. Número de simulação só entra em documento com o comando que o
  reproduz.
- **Engenharia e pesquisa estão misturadas.** Trilhos, `BioBrain` em paridade, fotografia diária, painel e
  lar são engenharia: dá para especificar, dividir e paralelizar. Modelo do eu, workspace e linguagem são
  pesquisa: o desenho de cada passo depende do resultado do anterior. Código de pesquisa feito em paralelo
  passa nos próprios testes e não produz o fenômeno. O plano de execução separa os dois com portões.
- **STDP não "continua igual".** Não há STDP hoje. É trabalho novo, e é pré-requisito de linguagem,
  crescimento e consolidação.
- **Calibração.** Cada troca de neurônio refaz os limiares em Hz e os parâmetros de homeostase. Frentes que
  calibram ao mesmo tempo contra bases diferentes produzem conflito que o git não mostra.
- **Custo.** Crescimento com matriz densa estoura o orçamento. Esparso é pré-requisito, não otimização.
- **Culpa disfarçada.** Fome, saudade, chamar e fala são quatro canais novos por onde a cobrança pode
  entrar. Cada um precisa do seu teste de ausência.
- **Privacidade.** Vocabulário, fotografias diárias e gravação dos sentidos são dados novos. `PRIVACIDADE.md`
  muda antes do código, não depois.
- **Um indivíduo, um usuário.** Sem os gêmeos de ablação e sem métrica definida antes, qualquer resultado é
  relato.
- **Ciência contestada.** SHY, dopamina como erro de predição, workspace global e processamento preditivo
  são hipóteses com evidência e com crítica. O projeto usa cada uma como fonte de fenômeno testável (R5).

## 13. Referências

- Izhikevich, E. M. (2003). Simple model of spiking neurons. *IEEE Transactions on Neural Networks*.
- Izhikevich, E. M. (2007). Solving the distal reward problem through linkage of STDP and dopamine signaling. *Cerebral Cortex*.
- Frémaux, N., Gerstner, W. (2016). Neuromodulated spike-timing-dependent plasticity, and theory of three-factor learning rules. *Frontiers in Neural Circuits*.
- Tononi, G., Cirelli, C. (2014). Sleep and the price of plasticity. *Neuron*.
- Turrigiano, G. G. (2008). The self-tuning neuron: synaptic scaling of excitatory synapses. *Cell*.
- McClelland, J. L., McNaughton, B. L., O'Reilly, R. C. (1995). Why there are complementary learning systems in the hippocampus and neocortex. *Psychological Review*.
- Frey, U., Morris, R. G. M. (1997). Synaptic tagging and long-term potentiation. *Nature*.
- Kirkpatrick, J. et al. (2017). Overcoming catastrophic forgetting in neural networks. *PNAS*.
- Hebb, D. O. (1949). *The Organization of Behavior*.
- Hopfield, J. J. (1982). Neural networks and physical systems with emergent collective computational abilities. *PNAS*.
- Abeles, M. (1991). *Corticonics*.
- Baars, B. J. (1988). *A Cognitive Theory of Consciousness*.
- Dehaene, S., Changeux, J.-P. (2011). Experimental and theoretical approaches to conscious processing. *Neuron*.
- Friston, K. (2010). The free-energy principle: a unified brain theory? *Nature Reviews Neuroscience*.
- Pulvermüller, F. (2013). How neurons make meaning: brain mechanisms for embodied and abstract-symbolic semantics. *Trends in Cognitive Sciences*.

As referências foram listadas de memória. Conferir título e ano antes de citar fora do projeto.
