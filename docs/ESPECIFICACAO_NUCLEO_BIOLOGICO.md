# Especificação: núcleo neural biológico do Pestinha

**Versão:** 0.1 (rascunho para decisão)
**Estado:** nenhum código foi alterado. Este documento define o que construir, em que ordem e como testar.
**Origem:** decisões tiradas das conversas sobre SNN, neurônios biológicos e humanos, neuromoduladores, sinaptogênese e neurogênese.

## 0. Objetivo e critério de sucesso

- **Objetivo:** aproximar a rede de propriedades observáveis de sistemas biológicos: habituação, condicionamento com bloqueio e extinção, ritmo diário, sono com consolidação e respiração.
- **Restrição:** sem perder segurança e sem cobrar o usuário (regras R1 a R7).
- **Fora de escopo:** fidelidade biofísica, conectoma humano e escala humana.
- **Critério:** todo fenômeno tem teste automatizado (seção 10). O que não tem teste não entra.

## 1. Regras de projeto

- **R1. Sem culpa.** Nenhum estado cresce ou decai para pressionar a pessoa a voltar. Carência leva a sono ou repouso, nunca a tristeza ativa. Vale para carência em geral, nos dois casos: ausência (você fora do computador) e negligência (você presente, ignorando o pet). Decidido pelo Cantyll em 2026-11-11. Base: `ARQUITETURA.md`.
- **R2. Reforço só por erro de predição.** Recompensa bruta não reforça comportamentos que chamam atenção, como `PEDIDO`.
- **R3. Crescimento não é disparado por recompensa bruta.** Vale para sinaptogênese e neurogênese.
- **R4. Segurança fica fora da rede.** Tela cheia, usuário ausente e limites de execução continuam em código de regras (guardas), que podem vetar qualquer ação da rede.
- **R5. Biologia como fonte de fenômenos testáveis, não como cópia.** Cada parte tem nome biológico, função e teste.
- **R6. Privacidade.** A rede recebe as mesmas categorias que `sense/senses.py` já produz. O estado salvo tem contagens e pesos, nunca títulos ou conteúdo. Base: `PRIVACIDADE.md`.
- **R7. Mudança por fase, reversível.** Cada fase é ligada por configuração. O LIF continua disponível até o novo núcleo passar nos testes.

## 2. Fronteira do sistema

**Entradas (vindas do app):**
- intensidades sensoriais (`sense/senses.py`);
- sinais de interação: carinho, dispensa, `PEDIDO`, brinquedo, castigo e recusa;
- recompensa `r` e valor esperado `V` (de `core/conditioning.py`, decisão D3);
- hora local, usada só para o relógio circadiano.

**Saídas (para o app):**
- atividade motora, que alimenta `MotorTone`;
- taxas por população, para a mesa de depuração;
- estado dos moduladores, que alimenta `homeostasis.py`, `mind/sleep.py` e `core/protesto.py`.

**Tempo:** a rede avança com `step(dt_real)`, não com passos fixos de 100 ms.

## 3. Glossário: termo biológico → nome no código

| Termo biológico | Nome proposto | Papel |
|---|---|---|
| Neurônio de pulso | `Neuronio` (Izhikevich) | unidade de disparo |
| Núcleo ou população | `Pool` | agrupamento funcional |
| Sinapse | `Projecao` (listas de pré, pós e peso) | conexão com peso e sinal |
| Dopamina fásica | `delta` em `Neuromod` | erro de predição |
| Noradrenalina | `arousal` | ganho global |
| Acetilcolina | `ach` | atenção e plasticidade |
| Serotonina | `serot` | estado lento |
| Adenosina | `pressao_sono` | pressão de sono |
| Relógio circadiano | `circ` | ritmo de 24 h |
| Tálamo (porta) | `PortaTalamica` | ganho sensorial |
| Gânglios da base | `Estriado` (D1, D2) e `GPi` | seleção de ação |
| Gerador central de padrão | `Respiracao` | ritmo gerado |

## 4. Mapa de regiões

| Região | Neurônios | Tipo | Origem no código atual |
|---|---|---|---|
| Relé sensorial | 180 | RS, entrada Poisson | `SENSORY_SPEC` (mantém) |
| Via rápida de susto (SUSTO) | 20 | RS, com ganho de entrada maior | novo |
| Córtex: pools excitatórios e inibitórios | 140 (10 pools) | RS (E), FS (I) | `INTER_SPEC` (recebe tipos) |
| Gânglios da base | 210 (7 ações × D1, D2, GPi de 10) | RS, RS, FS | substitui o grupo de decisão de `MOTOR_SPEC` (70) |
| Expressão motora | 80 (8 pools × 10) | RS | expressão de `MOTOR_SPEC` (mantém) |
| **Total** | **630** | | hoje 470 |

Relógio, sono, pressão de sono, serotonina, arousal, acetilcolina e δ são variáveis globais, não neurônios.

## 5. Neurônios

- **Modelo:** Izhikevich (2003). dv/dt = 0,04v² + 5v + 140 − u + I; du/dt = a(bv − u). Se v ≥ 30 mV: v ← c e u ← u + d.
- **Tipos** (valores canônicos do artigo de 2003; conferir antes de usar):
  - RS (disparo regular, excitatório): a = 0,02; b = 0,2; c = −65; d = 8.
  - FS (disparo rápido, inibitório): a = 0,1; b = 0,2; c = −65; d = 2.
  - IB (rajadas intrínsecas): a = 0,02; b = 0,2; c = −55; d = 4.
  - CH (chattering): a = 0,02; b = 0,2; c = −50; d = 2.
- **Uso:** córtex excitatório = RS; córtex inibitório = FS; SUSTO = RS com ganho de entrada maior; D1 e D2 = RS; GPi = FS com entrada tônica; expressão motora = RS.
- **Sinapses:** corrente exponencial, com τ ≈ 5 ms para o tipo AMPA e ≈ 10 ms para o tipo GABA (valores típicos, ajustar).
- **Adaptação:** a variável u substitui `adapt_b` e `adapt_tau`.
- **Escala de pesos:** deve ser recalibrada, porque a corrente é em unidades do modelo.
- **Implementação:** estado dos neurônios em arrays numpy, e propagação de disparos pelas listas de índices das sinapses. Um loop Python por neurônio provavelmente não cabe no passo de 0,5 ms; medir em M1.

## 6. Tempo

- **Passo de integração:** 0,5 ms (decisão D2). Em cada milissegundo, v é atualizado em duas metades, como no artigo original.
- **`step(dt_real)`:** o número de passos é `dt_real / 0,5 ms`, com teto de 1 s por chamada, para o caso de o computador ter dormido.
- **Pausa do pet:** a rede não avança, e todo o estado, incluindo P, A, ACh e S, fica congelado. O relógio circadiano segue a hora local e continua andando durante a pausa.
- **Custo:** o LIF atual integra a cada 1 ms (`nervous_system.py`, linhas 589 e 590). Com passo de 0,5 ms e 630 neurônios, a multiplicação densa atual custaria cerca de 3,6 vezes mais por segundo simulado (2 × (630/470)²). Por isso o critério de custo da seção 10 é obrigatório.
- **Replay noturno** pode rodar mais rápido que o tempo real, porque o pet está dormindo.

## 7. Conexões e plasticidade

### 7.1 Projeções
Cada `Projecao` tem: populações de origem e destino, lista de sinapses (índices de pré, de pós e peso), sinal (excitatório ou inibitório), indicação de plasticidade, receptor (nenhum, D1 ou D2) e limites de peso. As sinapses ficam em listas, não em matriz densa, para escalar.

### 7.2 Regra de três fatores explícita
- **Traço de elegibilidade** e_ij: marca coincidência entre pré e pós dentro de uma janela de cerca de 20 ms, e decai com τ_e. Hoje `ELIGIBILITY_TAU = 4.0`; conferir a unidade no código.
- **Atualização:** Δw_ij = η · δ · e_ij · g, em que g = +1 para sinapses plásticas gerais e para receptor D1, e g = −1 para receptor D2.
- **Limites:** `LEARN_MIN` e `LEARN_MAX`, por projeção.
- **Fim do sinal fixo por população** (`PLASTIC_POSTS`). O sinal passa a vir do receptor.

### 7.3 Escalonamento homeostático
Cada população tem uma taxa-alvo r*, em Hz por neurônio, definida pela taxa medida na fase M1. A cada hora acordado, e também durante o sono, os pesos de entrada são escalados em até ±5% por ajuste.

### 7.4 Acetilcolina
Taxa de aprendizado efetiva: η_eff = η · (0,5 + ACh).

### 7.5 Sinaptogênese e poda (fase M6)
- **Criar:** um par pré e pós com coincidência acumulada acima de um limiar, numa janela de 1 h, e com δ médio positivo no mesmo período (R3). Peso inicial: 0,01.
- **Podar:** peso com |w| < 0,002 por 6 h de uso, ou sinapse sem disparo pré por 24 h.
- **Limite:** no máximo o dobro do grau médio inicial, cerca de 34 entradas por neurônio.

### 7.6 Neurogênese (fase M7, opcional; decisão D9)
- **Gatilho:** erro persistente em contexto novo (novidade) e pool saturado, com taxa média acima de 0,8 do máximo.
- **Teto:** 800 neurônios.
- **Entrada:** o neurônio novo recebe sinapses de parceiros co-ativos, com peso de saída pequeno (0,2 vez a média) e uma janela de maturação de 48 h de uso acordado. Durante a maturação, ele é mais excitável e mais plástico.
- **Morte:** se não atingir taxa mínima ao fim da maturação, é removido.
- **Custo:** a pressão de sono cresce mais rápido com mais neurônios. Fórmula: k_w = 0,1/h × (N / 630).

## 8. Moduladores (variáveis globais)

| Variável | Faixa | Fonte | Efeito | Constante inicial |
|---|---|---|---|---|
| δ (dopamina fásica) | real | r − V | plasticidade (terceiro fator) e ganho de D1 e D2 | instantânea |
| A (noradrenalina, arousal) | 0 a 1 | tédio e sons aumentam; fadiga reduz | ganho global de (0,8 + 0,4·A); limiares de `ajustes.py` multiplicados por (1 + 0,2·(A − 0,5)) | τ = 60 s |
| ACh (acetilcolina, atenção) | 0 a 1 | atividade média do pool FOCUS | taxa de aprendizado e porta talâmica | τ = 30 s |
| S (serotonina, estado lento) | −1 a 1 | média de δ ao longo do tempo | sensibilidade a punição; substitui o acumulador de queixa de `protesto.py` | τ = 2 h |
| P (pressão de sono, adenosina) | 0 a 1 | tempo acordado | gatilho do sono | sobe com k_w; cai com k_s = 0,35/h dormindo |
| C (relógio circadiano) | −1 a 1 | C = cos(2π(h − h_pico)/24) | limiar do sono | h_pico configurável |

**Regras dos moduladores:**
- Durante a carência (ausência ou negligência), S relaxa para o neutro e nunca sobe (R1).
- O termo fixo `0,15 * repressions` em `protesto.py` sai do código e passa para `ajustes.py`.

**Dinâmica de P:** acordado, P' = k_w · (1 − P); dormindo, P' = −k_s · P. Com k_w = 0,1/h, P chega a 0,80 depois de 16 h acordado, valor usado no teste de sono da seção 10.

### 8.1 Sono: flip-flop com histerese
- Dorme se (P > 0,75 e C < 0,2) ou se P > 0,95.
- Acorda se P < 0,25, ou se (C > 0,6 e P < 0,5).
- A energia de `homeostasis.py` continua como drive interoceptivo. O gatilho de sono passa a ser P (decisão D6).
- Carinho do usuário acorda o pet, independentemente de P e C. Sem essa regra, o pet dorme enquanto você está com ele.

### 8.2 Porta talâmica
- **Ganho por canal:** g = clip(0,3 + 0,5·ACh + 0,2·A − 0,6·dormindo, 0, 1), aplicado à taxa sensorial.
- **Via rápida:** intensidade acima de 0,9 passa com fator 0,8 direto para SUSTO, sem o ganho da porta.

## 9. Módulos de comportamento

### 9.1 Via rápida e via lenta de susto
SUSTO recebe o sensorial direto (via rápida). O pool ALERT modula o ganho de SUSTO (via lenta). A saída vai para STARTLE.

### 9.2 Gânglios da base
Para cada ação a em SENTAR, FUGIR, CARTAZ, CANTO, TRAVESSURA, PAPEL e ACEITAR:
- D1_a (10 RS) e D2_a (10 RS) recebem entrada do córtex, por projeções plásticas com receptor D1 ou D2.
- D1_a inibe GPi_a (desinibição, via direta). D2_a excita GPi_a (via indireta).
- GPi_a é FS, com atividade tônica. A ação é liberada quando GPi_a fica abaixo de um limiar de liberação.
- Entre as ações liberadas, vence a de GPi mais baixo, com inibição lateral entre canais.
- As guardas (R4) podem vetar a ação antes da execução.

Esta é a mudança de fronteira mais importante do projeto (decisão D5). Hoje os sete motores de decisão já competem por inibição lateral (peso −0,05, 70% das conexões; `nervous_system.py`, linhas 453–458), e cada um vira ação por regra própria: limiar, sorteio com ganho ou ambos, espalhados por `ajustes.py` e `mind/`. A BG muda quem libera a ação, não a existência de competição. A escolha de *qual* travessura (meme, foto, bilhete, atravessar, nada) continua em `episodic.py`; a BG decide só se TRAVESSURA vence.

### 9.3 Respiração (gerador de padrão)
Oscilador de fase φ, com frequência f = 0,25 Hz + 0,5·A. Saída: escala corporal s = 1 + 0,03·sen(φ), enviada ao `MotorTone`.

### 9.4 Replay noturno
Durante o sono, são escolhidos 50 episódios de `episodic.py`, por prioridade de |δ| e recência. Cada episódio reativa o padrão pré-sináptico por 0,5 s, com δ_replay = 0,5 · δ registrado. `consolidate()` continua atualizando a tabela do bandit. Downscaling sináptico no sono (hipótese SHY) fica ligado (decisão D4, Cantyll, 2026-11-11): ao adormecer, cada sinapse aprendida perde 20% (`HOMEOSTASE_SHY`), e o replay para de empurrar uma sinapse ao chegar a 50% do seu limite (`HOMEOSTASE_TETO`). Sem isso, a tristeza de episódios negativos subia ao teto e ficava lá (medido: 4,8 Hz em 30 noites de uso misto).

### 9.5 Opcionais, fora do escopo inicial
- Codificação esparsa tipo giro denteado (k-WTA, com k = 5%).
- Memória tipo CA3 (Hopfield) para episódios.
- Modelo direto cerebelar (previsão do efeito do próprio movimento).

## 10. Testes de aceitação

Os critérios são valores iniciais, para calibrar.

| Fenômeno | Como testar | Critério inicial |
|---|---|---|
| Habituação | 20 estímulos repetidos | resposta cai ≥ 50%; recupera ≥ 50% após 1 min sem estímulo |
| Aprendizado por erro de predição | cue seguido de recompensa, 20 vezes | δ na recompensa cai para < 20% do inicial |
| Bloqueio (Kamin) | treina A→R; depois AB→R | aprendizado de B < 20% do aprendizado de A isolado |
| Extinção | 30 tentativas sem recompensa | resposta cai ≥ 70% |
| Surpresa | recompensa inesperada vs. esperada | plasticidade ≥ 2× na inesperada |
| Ritmo diário | mesma entrada às 10 h e às 23 h | atividade motora difere ≥ 15% |
| Sono por pressão | 16 h simuladas acordado | P ≈ 0,8; sono só começa com P > 0,75 e C < 0,2 |
| Replay | sono com episódios marcados | probabilidade da ação preferida muda ≥ 10 pontos |
| Porta talâmica | sono reduz a entrada sensorial | entrada cai ≥ 50%; estímulo acima de 0,9 passa |
| Respiração | 60 s parado, com A fixo | frequência ≈ 0,25 Hz; amplitude estável |
| Retenção (M6) | aprende um padrão; faz 5 aprendizados novos; testa o primeiro | ≥ 80% de reprodução |
| Determinismo | save → load → step, com semente fixa | spikes idênticos |
| Guarda: tela cheia | estado de tela cheia | travessura bloqueada |
| Guarda: sem reforço bruto | recompensa com δ = 0 | PEDIDO não cresce |
| Guarda: ausência (R1) | 3 dias sem usuário | S não sobe; CARTAZ e FUGIR não sobem; o pet dorme em vez de chamar atenção |
| Guarda: negligência (R1) | você presente e sem interagir por dias (tempo a definir) | S não sobe; nenhuma tristeza ativa; o pet repousa. Pendente: FUGIR e TRAVESSURA ainda sobem com você presente (medido: 4 a 5 Hz e 16 a 18 Hz). Decidir se a guarda de ausência vale aqui |
| Não regressão | suíte atual | passa; só as contagens 470 e 15.939 são atualizadas |
| Custo por passo | 630 neurônios, passo de 0,5 ms, máquina de referência | menos de 0,5 ms por passo para acompanhar o tempo real; fração de CPU medida (estimativa inicial: até 25% de um núcleo). Se não couber, revisar D2 e o tamanho das populações |
| Valor percebido | uma semana de uso real, com o LIF e com a versão nova | a variação do comportamento (intervalos entre ações e distribuição das ações) aumenta, sem sair da faixa de segurança |

## 11. Persistência e configuração

- **Versão:** `BIO_VERSION = 1`. O save guarda tipos e tamanhos de pools, listas de projeções, pesos, estado dos moduladores e a versão.
- **Saves do LIF:** não são convertidos (decisão D7). A memória episódica é separada e continua valendo.
- **Determinismo:** a semente é registrada, e o teste de roundtrip é obrigatório.
- **`config.py`:**
  - `"cerebro": "lif"` ou `"bio"` (padrão `"lif"` até M2 passar nos testes);
  - `"cerebro_debug": false` (painel de moduladores).
- **`pets/*.json`:**
  - `"pico_vigilia_h"` (exemplo: 23; decisão D8);
  - temperamento: os multiplicadores atuais continuam valendo sobre as entradas. Novos multiplicadores podem agir sobre η e sobre A.

## 12. Arquivos afetados

Com a ordem da seção 13, M2 a M6 podem ser feitas no `LIFBrain` antes de existir `BioBrain`. `bio_brain.py` só é necessário para M1 (decisão D10).

- `pestinha/core/bio_brain.py` (novo): `BioBrain(Brain)`, `Neuronio`, `Pool`, `Projecao`, `Neuromod`, `PortaTalamica`, `Estriado`, `Respiracao`.
- `pestinha/core/nervous_system.py`: a interface `Brain` ganha `estado()` e uma nova assinatura de `learn`. `LIFBrain` fica como base de comparação.
- `pestinha/core/conditioning.py`: expõe o V esperado do cue ativo.
- `pestinha/core/episodic.py`: API de replay, com seleção por |δ| e recência.
- `pestinha/mind/sleep.py`: gatilho por P e C, com histerese.
- `pestinha/core/homeostasis.py`: a energia continua; P passa a ser o gatilho de sono.
- `pestinha/core/protesto.py`: o acumulador vira S, e o termo fixo `0,15 * repressions` sai.
- `pestinha/core/motor.py`: recebe a escala do CPG.
- `pestinha/ajustes.py`: novos parâmetros, validados em `_LIMITES`. Também recebe `LIMIAR_PERDAO_HZ` e `ALTURA_CANTO`, que hoje estão em `mind/castigo_ctl.py`.
- `pestinha/app.py`: passa δ, A e ACh; usa o dt real; congela a rede durante a pausa.
- `pestinha/config.py`: chaves `cerebro` e `cerebro_debug`.
- `pets/bryan.json`: `pico_vigilia_h` e temperamento.
- `PRIVACIDADE.md`: atualizar antes de M6.
- `ARQUITETURA.md`: registrar R1 a R7 e a decisão D5.
- `docs/REDE_NEURAL.md`: regenerar com `ferramentas/gerar_doc_rede.py`.
- Testes: os novos da seção 10, e a atualização das contagens.

Cada fase entra como pull requests pequenos, validados no CI que já roda em Windows, macOS e Linux.

## 13. Fases

| Fase | Conteúdo | Esforço | Pronto quando |
|---|---|---|---|
| M0 | Interface `Brain` nova (tempo real, `learn(reward, expected, dt)`, `estado()`), versionamento e roundtrip | baixo | testes atuais passam; roundtrip idêntico |
| M1 | Izhikevich, passo de 0,5 ms, tipos RS e FS | alto (recalibra todos os limiares) | padrões RS, FS e IB reproduzidos; atividade calibrada; custo por passo dentro do orçamento |
| M2 | Moduladores, regra de três fatores explícita, ACh | médio | habituação, aprendizado por δ, bloqueio, extinção e surpresa passam |
| M3 | Sono por P, relógio circadiano, replay noturno | médio | testes de ritmo, sono e replay passam |
| M4 | Gânglios da base (D1 e D2) e guardas | alto | a seleção surge do balanço D1 e D2; guardas vetam tela cheia |
| M5 | Porta talâmica, via rápida de susto e respiração | médio | testes de porta, via rápida e respiração passam |
| M6 | Sinaptogênese, poda, teste de retenção e atualização de `PRIVACIDADE.md` | médio-alto | retenção ≥ 80% após 5 aprendizados novos |
| M7 | Neurogênese com maturação e teto (opcional) | alto | neurônios novos sobrevivem só quando recrutados; teto respeitado |

**Ordem recomendada:** M0, M3, M2, M5 e M6, todas sobre o LIF atual. M3 vem antes de M1 porque `sleep.py`, `homeostasis.py` e `episodic.py` não referenciam o modelo de neurônio, e M3 é o que a pessoa percebe primeiro. Só M1 troca o neurônio. Decida M1 depois de ver o resultado de M3 e M2: se a diferença já aparecer, M1 pode nem ser necessária. M4 exige aprovação de D5. M7 fica fora do plano inicial.

## 14. Decisões pendentes

| ID | Decisão | Padrão adotado | Alternativa | Impacto |
|---|---|---|---|---|
| D1 | Neurônio padrão | Izhikevich | CAdEx só no córtex | calibração |
| D2 | Passo de integração | 0,5 ms | 0,25 ms (mais estável, mais caro) | custo por passo |
| D3 | Crítico do δ | V de `conditioning.py` | crítico próprio na rede | acoplamento |
| D4 | Downscaling no sono (hipótese SHY) | ligado, decidido pelo Cantyll em 2026-11-11: −20% por sono, replay com teto de 50% do limite | desligado | ciência contestada |
| D5 | A BG (D1 e D2) passa a liberar as ações, no lugar das regras atuais de limiar e sorteio; guardas continuam | sim, em M4 | manter as regras; a rede já compete por inibição lateral | previsibilidade (ex.: travessura) e a regra de `ARQUITETURA.md` |
| D6 | Gatilho do sono | pressão P com relógio C | manter a energia | ritmo |
| D7 | Saves do LIF | não convertidos; memória episódica preservada | conversão | o pet começa a rede do zero |
| D8 | Pico circadiano | configurável por pet; exemplo 23 h | fixo | personalização |
| D9 | Neurogênese | desligada por padrão; teto de 800 | ligada desde o início | risco de inchaço |
| D10 | Onde vivem M2 a M6 | no `LIFBrain` atual (recomendado) | no `BioBrain`, junto com M1 | evita refazer a calibração duas vezes |

D5 muda a fronteira do projeto. Hoje a rede dá a tendência, e as regras escolhem as opções e a execução (`ARQUITETURA.md`). Precisa de aprovação explícita antes de M4.

## 15. Riscos

- **Fronteira (D5):** com a seleção na rede, a previsibilidade cai, e travessura e execução ficam mais difíceis de controlar. As guardas mitigam, mas não eliminam.
- **Calibração:** todos os limiares em Hz, hoje em `ajustes.py`, precisam ser refeitos a cada troca de neurônio ou de passo.
- **Estado:** mais estado significa mais bugs de save e load. Mitigação: versionamento e roundtrip obrigatório.
- **Escala:** com matriz densa, o custo cresce com o quadrado do número de neurônios. A poda só economiza se as sinapses forem esparsas; essa escolha de representação deve ser feita antes de M6.
- **Culpa disfarçada:** S, P e `PEDIDO` podem, juntos, criar pressão para voltar. Mitigação: R1, R2 e o teste de ausência. A negligência ainda não tem teste próprio.
- **Ciência contestada:** dopamina como erro de predição é a hipótese mais sustentada, mas há debate sobre saliência e vigor. Downscaling no sono e serotonina são hipóteses. Cada escolha fica registrada no código.
- **Privacidade:** em M6, os pesos sinápticos passam a registrar padrões de uso. Mitigação: `PRIVACIDADE.md` atualizado antes.
- **Valor percebido:** os testes fenomenológicos não dizem se o pet parece mais vivo para quem usa. Mitigação: o critério de valor percebido (seção 10) e a ordem da seção 13, que testa o barato antes do caro.

## 16. Fora de escopo

- Conectoma humano ou de qualquer outro organismo.
- Neurônios multicompartimentais com parâmetros humanos.
- Cerebelo, CA3 e giro denteado (opcionais, em fase posterior).
- Qualquer mecanismo que transforme carência (ausência ou negligência) em cobrança.
