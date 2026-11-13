# Plano de execução do Cantyll em pull requests

**Versão:** 0.4 (2026-11-13: critério de paridade do portão A)
**Para quê:** dividir a [visão do Cantyll](VISAO_CANTYLL.md) em pull requests que threads diferentes possam
fazer ao mesmo tempo sem se atrapalhar. Diz, para cada PR: os arquivos de que ele é dono, do que depende, a
ordem de merge e o critério de pronto.

**Rótulos:** `pesado` = código difícil, calibração ou revisão. `fácil` = bem orientado, com padrão já
existente no repositório para copiar. Todo PR, inclusive os fáceis, passa por conferência de código antes
de sair de rascunho.

## 1. O que dá e o que não dá para paralelizar

- **Engenharia (ondas 0 a 2):** trilhos, `BioBrain` em paridade, fotografia diária, painel, lar. O resultado
  é conhecido antes de começar. Paraleliza bem.
- **Pesquisa (ondas 3 e 4):** modelo do eu ligado ao núcleo, workspace, linguagem, neurogênese. O desenho de
  cada passo depende do resultado do anterior. Aqui o plano dá a ordem e os portões (seção 6), não promete
  paralelismo. Abrir essas frentes antes do portão produz código que passa nos próprios testes e não produz
  o fenômeno.
- **Dois tipos de conflito.** O git mostra o conflito de texto. Ele não mostra o conflito de calibração:
  duas frentes ajustando limiares contra bases diferentes. As regras 7 e 8 da seção 2 existem para o segundo.

## 2. Regras para os PRs não se atrapalharem

1. **Cada arquivo tem um dono por vez.** A lista está em cada PR (seção 4) e nos arquivos quentes (seção 5).
   Tocar arquivo fora da própria lista exige combinar com o dono e escrever isso na descrição do PR.
2. **Função nova vai em arquivo novo.** Os trilhos (onda 1) criam os pontos de encaixe e os arquivos vazios
   de cada frente. Depois deles, cada frente só preenche o próprio arquivo.
3. **Tudo atrás de configuração, desligado por padrão (R7).** O PR de uma frente nunca muda o padrão de uma
   chave. Os testes ligam a chave por fixture. Ligar por padrão é um PR à parte, de uma linha, decidido pelo
   Cantyll.
4. **Arquivos gerados e compartilhados ficam fora dos PRs de frente:** `CHANGELOG.md`, `PRIVACIDADE.md`,
   `docs/REDE_NEURAL.md`, `docs/ESPECIFICACAO_NUCLEO_BIOLOGICO.md`, `pestinha/*/README.md`, `tests/README.md`
   e `ferramentas/README.md`. Cada PR escreve a sua entrada de changelog na descrição, sob o título
   "Changelog". O PR de fechamento da onda junta as entradas e roda os geradores.
5. **`PRIVACIDADE.md` muda antes do código.** Um PR de documentação por onda (`DOC-P`) entra primeiro e cobre
   todos os dados novos daquela onda.
6. **Um merge por vez.** Antes do merge: rebase na `main`, CI verde nos três sistemas, e a conferência de
   sobreposição da seção 7.
7. **Critérios relativos.** Teste de frente nova usa razão e porcentagem, como a seção 10 da spec ("cai 50%",
   "2 vezes maior"), nunca Hz absoluto. Só a frente NE mexe em limiares absolutos.
8. **A simulação de noites é critério de aceitação** de todo PR que muda dinâmica de neurônio, plasticidade,
   replay ou homeostase. O critério é relativo à linha de base registrada pelo B2: a taxa de cada população
   plástica no dia 30 não sai da faixa das 5 sementes, a não ser que o PR diga por que deveria e o Cantyll
   aceite a linha de base nova.
9. **Testes:** cada PR cria arquivos de teste próprios (`tests/test_<frente>_*.py`). Teste existente só é
   editado pelo dono indicado.
10. **Ramos:** `claude/<id>-<assunto>`, por exemplo `claude/t1-trilhos`. Um PR por ramo.

## 3. Mapa de dependências

```text
ONDA 0   #5 (replay + SHY) ──► B2 (simulação de noites; piso cancelado) ──► B3 (spec e arquitetura)
         B4 (conserto do sono: replay e SHY pela dívida de sono) ◄─ B2
         B1 (este PR, só documentos)

ONDA 1   T1 (trilhos do app) ──┐
         T2 (BioBrain em paridade) ──► portão A

ONDA 2   NE-1 ─► NE-2 ─► NE-3 ─► NE-4            (em série, uma thread)
         PL-1        EU-1        ME-1
         AC-1   AC-2   AC-3      LAR-1   LAR-2   LAR-4      LI-0      TA-1
         DOC-P2 (antes) ............................................. F2 (fechamento)

ONDA 3   PL-2 ◄─ PL-1          ME-2 ◄─ PL-1         CR-1 ◄─ PL-1
         WS-1 ◄─ NE-1, EU-1    TA-2 ◄─ PL-2, NE-1   LAR-3 ◄─ LAR-1
         DOC-P3 (antes) ............................................. F3 (fechamento)

ONDA 4   EU-2 ◄─ EU-1, PL-2    CR-2 ◄─ CR-1, EU-1   CR-3 ◄─ CR-1
         LI-1 ◄─ PL-1, NE-1 ─► LI-2 ◄─ WS-1 ─► WS-2 ◄─ ME-1 ─► LI-3
         ME-3 ◄─ ME-1, ME-2, NE-1
         NE-5 (trocar o padrão para BioBrain) ◄─ NE-4, suíte e simulação de noites (portão D)
```

## 4. Os pull requests

### Onda 0: base (em série)

| ID | Rótulo | Conteúdo | Arquivos de que é dono | Depende de | Pronto quando |
|---|---|---|---|---|---|
| #5 | pesado | Replay noturno e homeostase sináptica (SHY). Mesclado em 2026-11-12 | `core/homeostase_sinaptica.py`, `core/nervous_system.py`, `core/episodic.py`, `mind/sleep.py`, `app.py`, `ajustes.py`, `CHANGELOG.md`, `PRIVACIDADE.md`, spec | nada | Testes do PR passam |
| B1 | fácil | Visão e este plano | `docs/VISAO_CANTYLL.md`, `docs/PLANO_DE_EXECUCAO_CANTYLL.md`, `docs/README.md` | nada (não toca arquivo do #5) | Revisado pelo Cantyll |
| B2 | pesado | Simulação de noites como ferramenta e `taxas()` na interface `Brain` (opcional; devolve `{}` por padrão). **O piso por taxa-alvo foi cancelado pelo Cantyll em 2026-11-12**, e o SHY repartido pelo sono saiu do PR. É o PR #8 | `core/nervous_system.py` (só `taxas()`), `ferramentas/simular_noites.py` (novo), `tests/test_simulacao_noites.py` (novo) | #5 | Um comando reproduz as 30 noites com semente fixa. A linha de base do LIF (taxa de cada população plástica no dia 30, por cenário, com 5 sementes) fica registrada aqui ou, se o #8 entrar sem ela, no T2 |
| B3 | fácil | Spec e arquitetura alinhadas com a visão: D9, D10, seções 13 e 16; R1 a R7 em `ARQUITETURA.md` | `docs/ESPECIFICACAO_NUCLEO_BIOLOGICO.md`, `docs/ARQUITETURA.md` | #5 e as decisões V1 e V2 da visão | Tabela da seção 10 da visão refletida na spec |
| B4 | pesado | Conserto na `main`: replay e SHY cobrados pela dívida de sono, não a cada adormecer (uma noite picada em N sonos valia N noites de replay e de SHY). Aprovado pelo Cantyll em 2026-11-12. Ramo empilhado sobre o B2; não muda a interface `Brain` | `mind/sleep.py`, `core/homeostasis.py` (`pressao_quitada` em `drives.json`), `ajustes.py` (só comentários de duas constantes), `tests/test_homeostase_sinaptica.py`, `tests/test_replay.py`, `tests/test_simulacao_noites.py`, e a própria entrada no `CHANGELOG.md` | B2 | Critério relativo, decidido pelo Cantyll em 2026-11-12. Com 1 sono por noite: a taxa de cada população plástica no dia 30 fica dentro da faixa das 5 sementes da `main`. Com 6 sonos por noite: PLAYFUL, CALM e GLOOM ficam a no máximo 15% do valor de 1 sono |

Fora da contagem: o PR #9 corrige uma linha do `CHANGELOG.md` (a premissa da PLAYFUL) e não toca mais nada.

B2 é a última mudança no `LIFBrain`. O B4 mexe no controle do sono, não na rede. Depois dele, `core/nervous_system.py` congela (só correção de bug), e
todo trabalho novo do núcleo vai para o `BioBrain` (decisão V1, aprovada pelo Cantyll em 2026-11-12).

**Correção da versão 0.1:** o plano dizia que o B2 existia "para a PLAYFUL não cair a zero". Essa queda não
se reproduz com o código atual (visão, seção 3): com a homeostase do PR #5, a PLAYFUL vai de 2,47 Hz para
0,87 Hz em 30 noites e não zera.

### Onda 1: trilhos

Dois PRs desenvolvidos em paralelo, com arquivos disjuntos. Merge: T1, depois T2.

| ID | Rótulo | Conteúdo | Arquivos de que é dono | Depende de | Pronto quando |
|---|---|---|---|---|---|
| T1 | pesado | Trilhos do app: registro de módulos com pontos de encaixe fixos, chaves de configuração por frente, pasta de estado por módulo, seções reservadas | `core/modulos.py` (novo), `app.py`, `controle/sessao.py`, `mind/sleep.py`, `config.py`, `paths.py`, `ajustes.py`, `ferramentas/gerar_readmes.py`, `tests/test_modulos.py` (novo) | #5, B2 | Com todas as chaves desligadas, a suíte passa sem nenhum teste alterado e, com semente fixa, as taxas motoras são idênticas às de antes. Um módulo de teste recebe todos os encaixes na ordem |
| T2 | pesado | `BioBrain` em paridade: populações com dinâmica própria (todas em LIF nesta fase), projeções esparsas, e os arquivos vazios de cada frente com a interface já definida | `core/bio/` (pacote novo): `rede.py`, `neuronios.py`, `projecoes.py`, e vazios `plasticidade.py`, `moduladores.py`, `consolidacao.py`, `assembleias.py`, `crescimento.py`, `workspace.py`, `talamo.py`, `spec_base.py`, `spec_corpo.py`, `spec_eu.py`, `spec_workspace.py`, `spec_linguagem.py`. Mais: `criar_cerebro` em `core/nervous_system.py`, `CEREBROS_PRONTOS` em `config.py`, `conftest.py`, `.github/workflows/testes.yml`, `tests/test_bio_paridade.py`, `ferramentas/medir_custo_bio.py` | #5, B2 | O `BioBrain` implementa a interface `Brain` inteira da `main` depois do B2: o que já existe (replay e SHY do #5) e `taxas()`. Não há `ensaio_piso` nem `escalonar_piso`: saíram com o piso. A suíte inteira passa com `cerebro = "bio"`. Ida e volta de salvar e carregar determinística. Paridade com o LIF pelo critério do portão A (seção 6). Custo de 630 neurônios não maior que o denso |

**Contrato dos módulos (proposta; o T1 fecha).** Quem começar uma frente antes do merge do T1 programa contra isto:

```python
class Modulo:
    nome = ""                                      # igual à chave em config.FRENTES
    def sentir(self, intensidades, dt): ...        # antes do passo da rede; pode acrescentar canais
    def depois_do_passo(self, cerebro, drives, dt): ...
    def valor_esperado(self): return None          # V de δ = r − V; no máximo um módulo responde
    def ao_dormir(self, cerebro): ...
    def ao_acordar(self, cerebro): ...
    def deslocar(self, segundos): ...              # pausa: os prazos andam junto
    def estado(self): return {}                    # entra na fotografia diária
    def salvar(self, pasta): ...
    def carregar(self, pasta): ...                 # dado inválido: não aplica nada
```

Depois do T1, nenhuma frente edita `app.py`, `config.py` nem `paths.py`. Depois do T2, só a frente NE edita
`core/bio/rede.py`.

Exceção aceita pelo Cantyll em 2026-11-13 (opção A): o PR #18 (gatilho de negligência de 10 min) edita `app.py` em `think()` e na chamada de `definir_ausencia`, porque o registro não tem gancho de interação nem de ausência. Ela vale só para esse PR. Outro toque em `app.py` depois do T1 pede decisão própria.

### Onda 2: frentes em paralelo (depois do portão A)

| ID | Rótulo | Conteúdo | Arquivos de que é dono | Depende de | Pronto quando |
|---|---|---|---|---|---|
| DOC-P2 | fácil | `PRIVACIDADE.md` para os dados desta onda: fotografia diária, gravação de sentidos, episódios gerais, conversa | `PRIVACIDADE.md` | T1 | Entra antes de AC-1, AC-3, ME-1 e LI-0 |
| NE-1 | pesado | Dinâmica Izhikevich: tipos RS, FS, IB, CH e LTS, corrente sináptica exponencial, passo de 0,5 ms. Nenhuma população existente muda | `core/bio/neuronios.py`, `core/bio/rede.py`, `core/bio/projecoes.py`, `tests/test_bio_izhikevich.py` | T2 | Padrões de disparo de cada tipo reproduzidos; custo medido |
| NE-2 | pesado | Interneurônios inibitórios (QUIET, INHIB) em FS | os de NE-1, seção de decisões de `ajustes.py`, testes existentes de limiar | NE-1 | Suíte e simulação de noites passam |
| NE-3 | pesado | Interneurônios excitatórios em RS; drives e humor em IB e CH | idem | NE-2 | idem |
| NE-4 | pesado | Motores em RS; limiares de decisão refeitos | idem, mais `ferramentas/gerar_doc_rede.py` | NE-3 | idem, e `REDE_NEURAL.md` gerado do cérebro novo |
| PL-1 | pesado | STDP de três fatores por pulso, δ = r − V (D3), ACh na taxa de aprendizado | `core/bio/plasticidade.py`, `core/bio/moduladores.py`, `core/conditioning.py`, `tests/test_plasticidade_*.py` | T2 | Habituação, aprendizado por δ, bloqueio, extinção e surpresa (spec, seção 10) |
| EU-1 | pesado | Modelo do eu: preditor do próprio estado, sinais de surpresa e tédio, como módulo do app | `core/modelo_eu.py` (novo), `tests/test_eu_*.py` | T1 | Erro abaixo do preditor ingênuo depois de rotina simulada; sobe com quebra de rotina |
| ME-1 | pesado | Hipocampo: episódios de qualquer momento marcante, replay equilibrado entre bons e ruins | `core/hipocampo.py` (novo), `core/episodic.py`, `tests/test_hipocampo_*.py` | T1, DOC-P2 | Episódio sem travessura entra no replay; simulação de noites sem colapso |
| AC-1 | fácil | Fotografia diária, no formato da seção 8 | `core/diario.py` (novo), `tests/test_diario.py` | T1, DOC-P2 | Um arquivo por dia; dado inválido é recusado; "apagar todos os dados" apaga |
| AC-2 | fácil | Painel de evolução e relatório em HTML | `ui/evolucao.py` (novo), `ferramentas/relatorio_evolucao.py` (novo), `tests/test_evolucao.py` | Só o formato da seção 8 | Curvas a partir de fotografias de exemplo; campos nulos não quebram |
| AC-3 | pesado | Gravador dos sentidos e gêmeos de ablação | `core/gravador.py` (novo), `ferramentas/gemeos.py` (novo), `tests/test_gemeos.py` | T1, T2, DOC-P2 (V6 decidida: grava com permissão própria, desligada por padrão) | A mesma gravação, com a mesma semente, dá o mesmo resultado; com um módulo desligado, a diferença é relatada |
| LAR-1 | fácil | O lar: canto fixo com cama; ele dorme na cama | `world/lar.py` (novo), `mind/lar_ctl.py` (novo), `body/behavior.py`, `tests/test_lar.py` | T1 | Não rouba foco; some em tela cheia; pausa e pânico funcionam |
| LAR-2 | fácil | Canais de hora do dia e de presença | `sense/senses.py`, `core/bio/spec_corpo.py`, `tests/test_sentidos_corpo.py` | T2 | Canais chegam à rede nova; a rede antiga não muda |
| LAR-4 | fácil | Presença em segundo plano: estado dele no ícone da bandeja | `ui/ui.py`, `tests/test_bandeja_estado.py` | T1 | Dormindo, acordado e pausado aparecem no ícone |
| LI-0 | fácil | Caixa de conversa e balão de fala, sem rede por trás | `ui/conversa.py` (novo), `world/balao.py` (novo), `tests/test_conversa_ui.py` | T1, DOC-P2 | Permissão própria, desligada por padrão; o texto só chega ao módulo de linguagem |
| TA-1 | fácil | Respiração: oscilador de fase que escala o corpo (spec, seção 9.3) | `core/respiracao.py` (novo), `core/motor.py`, `tests/test_respiracao.py` | T1 | Frequência perto de 0,25 Hz, amplitude estável |
| F2 | fácil | Fechamento: junta os changelogs, roda `gerar_readmes.py` e `gerar_doc_rede.py` | os arquivos da regra 4 | todos os desta onda | Geradores sem diferença depois de rodar |

A frente NE é uma fila: uma thread só, do NE-1 ao NE-4. Ela pode atravessar a onda 3.

### Onda 3 (depois do portão B)

| ID | Rótulo | Conteúdo | Arquivos de que é dono | Depende de | Pronto quando |
|---|---|---|---|---|---|
| DOC-P3 | fácil | `PRIVACIDADE.md`: sinapses que passam a registrar padrões de uso (exigência da spec antes de M6) e vocabulário | `PRIVACIDADE.md` | F2 | Entra antes de CR-1 |
| PL-2 | pesado | Moduladores A e S; S no lugar do acumulador de queixa | `core/bio/moduladores.py`, `core/protesto.py`, `mind/protest_ctl.py`, `tests/test_moduladores_*.py` | PL-1 | Teste de ausência de 3 dias: S não sobe (R1) |
| ME-2 | pesado | Marca e captura; consolidação sináptica ("dureza") | `core/bio/consolidacao.py`, `tests/test_consolidacao_*.py` | PL-1 | Retenção de 80% depois de 5 aprendizados novos |
| CR-1 | pesado | Sinaptogênese e poda, aplicadas no sono (spec, seção 7.5) | `core/bio/crescimento.py`, `tests/test_crescimento_*.py` | PL-1, DOC-P3 | Limite de grau respeitado; custo dentro do orçamento; R3 testada |
| WS-1 | pesado | Workspace com três módulos (percepção, drives, modelo do eu), winner-take-all com FS | `core/bio/workspace.py`, `core/bio/spec_workspace.py`, `tests/test_workspace_*.py` | NE-1, EU-1 | Um vencedor por vez; tempo mínimo de permanência; guardas vetam |
| TA-2 | pesado | Porta talâmica e via rápida de susto (spec, seções 8.2 e 9.1) | `core/bio/talamo.py`, `tests/test_talamo_*.py` | PL-2, NE-1 | Sono reduz a entrada em 50%; estímulo acima de 0,9 passa |
| LAR-3 | pesado | Fome saciável por ele mesmo, e a comida do lar | `core/homeostasis.py`, `world/lar.py`, `mind/lar_ctl.py`, `tests/test_fome_*.py` | LAR-1 (V3 decidida) | 3 dias sem usuário: ele come sozinho; CARTAZ, FUGIR e tristeza não sobem |
| F3 | fácil | Fechamento da onda | os da regra 4 | todos os desta onda | Geradores sem diferença |

### Onda 4: pesquisa (cada item atrás do seu portão)

| ID | Rótulo | Conteúdo | Arquivos de que é dono | Depende de | Pronto quando |
|---|---|---|---|---|---|
| EU-2 | pesado | Erro do modelo do eu ligado ao núcleo: surpresa sobe A e ACh; tédio vem do erro baixo | `core/modelo_eu.py`, `core/bio/spec_eu.py` | EU-1, PL-2 | Gêmeo sem modelo do eu tem distribuição de ações diferente |
| CR-2 | pesado | Neurogênese com maturação e teto de 1500 neurônios (decisão V2); número de neurônios variável no estado salvo e no monitor; fórmula da pressão de sono revista para o tamanho novo | `core/bio/crescimento.py`, `ui/monitor.py` | CR-1, EU-1 | Neurônio novo só sobrevive se recrutado; teto de 1500 respeitado; custo medido com 1500 na máquina de referência, dentro de 25% de um núcleo, ou o crescimento para antes; ele não passa a dormir mais por ter crescido |
| CR-3 | fácil | Plasticidade que diminui de forma contínua por população | `core/bio/crescimento.py` | CR-1 | Curva contínua, sem degrau; aparece na fotografia diária |
| LI-1 | pesado | Texto em pulsos e assembleias de palavras por STDP | `core/linguagem/` (pacote novo), `core/bio/spec_linguagem.py` | PL-1, NE-1 | Teste do tutor: reconhecimento acima do acaso |
| LI-2 | pesado | Aterramento: palavra ligada ao estado do corpo | `core/linguagem/` | LI-1, WS-1 | Compreensão acima do acaso |
| WS-2 | pesado | Memória e fala entram no workspace | `core/bio/workspace.py`, `core/bio/spec_workspace.py` | WS-1, ME-1, LI-2 | Um vencedor por vez com cinco módulos |
| ME-3 | pesado | Lembrar por pista parcial: assembleias recorrentes que se completam a partir de um pedaço (tipo CA3) | `core/bio/assembleias.py`, `tests/test_assembleias_*.py` | ME-1, ME-2, NE-1 | Com metade do padrão como pista, a assembleia reativa o resto acima do acaso; padrões diferentes não se misturam |
| LI-3 | pesado | Produção de sequência e auto-escuta | `core/linguagem/` | WS-2 | Produção acima do acaso; ausente, ele não fala |
| NE-5 | fácil | Trocar o padrão para `cerebro = "bio"` | `config.py` (uma linha), `tests/test_troca_padrao.py` (novo) | NE-4, portão D | Portão D passa. Voltar para `"lif"` na configuração funciona, e a troca não apaga nem corrompe o estado salvo de nenhum dos dois cérebros |

## 5. Arquivos quentes

| Arquivo | Quem pode editar | Regra |
|---|---|---|
| `core/nervous_system.py` | #5, B2 (só `taxas()`); depois só o T2, na função `criar_cerebro` | Congelado depois do B2 (decisão V1) |
| `app.py` | #5, depois só o T1; #18 por exceção aceita em 2026-11-13, só para esse PR | Frente nova entra pelo registro de módulos |
| `ajustes.py` | #5, B4 (comentários), T1; depois cada frente só na própria seção reservada, e a NE na seção de decisões | O T1 cria as seções, com marcas de início e fim, também dentro de `_LIMITES` |
| `config.py` | T1 (chaves e permissões de todas as frentes, escondidas enquanto a chave está desligada), T2 (`CEREBROS_PRONTOS`) | Ligar por padrão é PR à parte |
| `paths.py` | T1 | Estado novo usa a pasta por módulo |
| `core/bio/rede.py` | T2, depois só a frente NE | As outras frentes preenchem o próprio arquivo |
| `mind/sleep.py`, `core/episodic.py` | #5; B4 (`sleep.py`); depois T1 (`sleep.py`) e ME-1 (`episodic.py`) | O B2 não toca nenhum dos dois. O B4 entra antes do T1 |
| `core/homeostasis.py` | B4 (`pressao_quitada`); depois só a LAR-3 | Em série: B4 na onda 0, LAR-3 na onda 3 |
| `core/bio/crescimento.py` | CR-1, CR-3, CR-2, nessa ordem | Em série dentro da frente |
| `CHANGELOG.md`, `PRIVACIDADE.md`, READMEs gerados, `REDE_NEURAL.md`, spec | #5, #9 e B4 (uma entrada cada, antes dos trilhos), B3, DOC-P, F | Regras 4 e 5 |
| Testes existentes | T2 (via `conftest.py`) e a frente NE (limiares) | Regra 9 |

## 6. Portões

| Portão | Antes de | Condição |
|---|---|---|
| A | Onda 2 | #5, B2, T1 e T2 na `main`. A suíte passa nos dois cérebros. Na simulação de noites de `ferramentas/linha_de_base.py` (cenários duro, misto e carinhoso, sementes 1 a 20, dia 30), a média de cada população da tabela (PLAYFUL, CALM, FRUSTRATION, GLOOM, CHEER e SAD) do `BioBrain` fica a no máximo 2 erros-padrão da média do LIF registrada em `docs/LINHA_DE_BASE_LIF.md`, ou a no máximo 0,05 Hz dela quando 0,05 Hz for maior. **O piso de 0,05 Hz é um número escolhido, não medido** (decidido pelo Cantyll em 2026-11-13): ele existe porque FRUSTRATION, GLOOM e SAD ficam perto de 0 Hz no misto e no carinhoso, onde 2 erros-padrão dá 0,000 Hz. Nenhuma população com média acima do piso no LIF zera no `BioBrain`. A faixa de mínimo a máximo de 5 sementes, que estava aqui, saiu: uma rodada nova cai dentro dela com probabilidade (n−1)/(n+1), 67% com 5 sementes |
| B | Onda 3 | F2 na `main`. Custo do `BioBrain` medido na máquina de referência, dentro de 25% de um núcleo. PL-1 passa nos fenômenos da spec |
| C | LI-1 | WS-1 com um vencedor por vez. PL-1 e NE-1 na `main`. O teste do tutor está escrito antes do código da linguagem |
| D | NE-5 | NE-4 na `main`. A suíte passa com `cerebro = "bio"` como padrão. A simulação de noites, com 5 sementes, fica dentro da linha de base vigente (regra 8) e nenhuma população zera. Sem semana de uso real: o Cantyll decidiu a V7 em 2026-11-12 |

Se um portão não passa, a frente para e o resultado é registrado. Não se abre a frente seguinte para
"adiantar".

## 7. Conferência de sobreposição

Rodar antes de cada merge e ao fim de cada onda.

Arquivos tocados por mais de um PR aberto (a saída deve trazer só arquivos previstos na seção 5):

```bash
git fetch origin
for b in $(git branch -r | grep 'origin/claude/' | tr -d ' '); do
  git diff --name-only origin/main...$b | sed "s|^|$b |"
done | sort -k2 | awk '{c[$2]++; l[$2]=l[$2]" "$1} END {for (f in c) if (c[f]>1) print f":"l[f]}'
```

Conflito de texto entre dois ramos, sem mexer na cópia de trabalho (git 2.38 ou mais novo; saída diferente
de zero quer dizer conflito):

```bash
git merge-tree --write-tree origin/claude/<ramo-a> origin/claude/<ramo-b> > /dev/null; echo $?
```

Conflito de calibração: depois de cada merge da frente NE, o CI da `main` roda a suíte e a simulação de
noites. Os PRs abertos fazem rebase e rodam de novo antes do próprio merge (regra 6).

## 8. Formato da fotografia diária

Contrato entre AC-1 (quem grava) e AC-2 (quem lê). Campo de frente que ainda não existe vale `null`.

```json
{
  "versao": 1,
  "data": "2026-11-12",
  "pet": "bryan",
  "horas_acordado": 123.4,
  "rede": {
    "tipo": "bio",
    "neuronios": 630,
    "sinapses": 21000,
    "por_populacao": {"ALERT": {"neuronios": 16, "taxa_hz": 2.1, "plasticidade": 1.0}}
  },
  "crescimento": {"sinapses_criadas": 0, "sinapses_podadas": 0, "neuronios_criados": 0, "neuronios_removidos": 0},
  "pesos": {"media": 0.0, "p10": 0.0, "p90": 0.0},
  "eu": {"erro_medio": null, "erro_ingenuo": null},
  "linguagem": {"palavras": null},
  "memoria": {"episodios": 0, "mais_fortes": []},
  "custo": {"us_por_passo": null}
}
```

Só contagens, taxas e pesos. Nenhum nome de programa, título ou texto (R6).

## 9. Fora deste plano

- Gânglios da base liberando ação (spec, M4): o Cantyll adiou a D5 em 2026-11-12. Ela só é decidida depois
  que o PL-1 estiver na `main`. Até lá, nenhum PR deste plano depende dela.
- Microfone: a V4 ficou em só texto escrito, e o microfone ficou em aberto para depois.
- Nível de som do sistema: a V5 ficou em fora por enquanto. Voz sintetizada e sons seguem fora.
- A medida do "valor percebido" da spec (uma semana de uso real com cada cérebro): a V7 tirou ela do caminho
  da troca do padrão. Nenhum PR deste plano a faz.
- LLM como tradutor opcional.
- Conectoma de qualquer organismo.

## 10. Contagem

40 pull requests além do #5: 25 pesados e 15 fáceis. Onda 0: 4. Onda 1: 2. Onda 2: 17. Onda 3: 8. Onda 4: 9.
No pico da onda 2, até 9 threads ao mesmo tempo (NE, PL, EU, ME, AC, LAR, LI, TA e documentação).
