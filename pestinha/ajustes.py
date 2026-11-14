"""
AJUSTES - todos os números que dão o jeito do pet, em um lugar só.

Mudar um valor aqui muda o comportamento. Ao importar, `validar()` confere os
tipos e os limites de cada valor e, se algo estiver fora, levanta ValueError
com a lista completa dos problemas (o programa não sobe com ajuste errado).

Os perfis de tempo (teste e normal) ficam em `pestinha/config.py`.
"""

# ---------------------------------------------------------------------------
# Interação com o mouse
# ---------------------------------------------------------------------------
COOLDOWN_CUTUCADA = 0.25        # s entre cutucadas que contam
TEMPO_MAX_CUTUCADA_MS = 350     # ms: clique mais longo que isso não é cutucada
DISTANCIA_INICIO_ARRASTE = 5    # px que o mouse precisa andar para virar arraste
VELOCIDADE_ARREMESSO = 700      # px/s: soltar mais rápido que isso é arremesso
JANELA_CARINHO = 1.2            # s analisados para reconhecer o carinho
TROCAS_CARINHO = 3              # trocas de direção em JANELA_CARINHO para ser carinho
DESLOCAMENTO_CARINHO = 60       # px percorridos em JANELA_CARINHO para ser carinho
DURACAO_CARINHO = 0.4           # s que o carinho dura depois do último esfregão

# ---------------------------------------------------------------------------
# Batidas e reflexos
# ---------------------------------------------------------------------------
BATIDA_FORTE = 1500             # px/s: batida que ele sente
BATIDA_TONTA = 2000             # px/s: batida que deixa ele tonto
DURACAO_TONTURA = 1.6           # s olhando em volta depois de uma batida tonta
INTERVALO_BATIDA = 0.6          # s: quiques da mesma batida não contam de novo
ATIVIDADE_MINIMA_VOO = 4.0      # Hz: abaixo disso o reflexo de voo é só alegria
SILENCIO_MOUSE = 0.4            # s sem o cursor andar para o teclado contar

# ---------------------------------------------------------------------------
# Cutucada e a resposta medida na rede
# ---------------------------------------------------------------------------
ESPERA_MEDIDA_CUTUCADA = 0.5    # s depois da cutucada em que se mede a resposta
HZ_RESPOSTA_CHEIA = 6.0         # aumento de CHEER que vale resposta 1,0
RESPOSTA_MINIMA = 0.12          # abaixo disso ele só pisca e olha
RECOMPENSA_CARINHO = 1.0        # recompensa por segundo de carinho (aprendizado)
PUNICAO_DISPENSA = -0.6         # recompensa negativa depois de dispensar
DISPENSA_RAPIDA = 3.0           # s: fechou tão rápido assim = dispensa "na cara"
PENALIDADE_DISPENSA = 1.0       # s em que a dispensa pesa no aprendizado
HABITUACAO_DISPENSA = 10.0      # dispensas seguidas para o peso no aprendizado cair à metade (0 desliga; core/habituacao.py)
RECUPERACAO_DISPENSA_H = 8.0    # h: constante de tempo em que a habituação à dispensa passa
DESABITUACAO_CARINHO = 1.0      # fração da habituação à dispensa que um carinho desfaz (0 = nenhuma, 1 = toda)

# ---------------------------------------------------------------------------
# Física do corpo (núcleo)
# ---------------------------------------------------------------------------
GRAVIDADE = 2200.0              # px/s² do pet e da bolinha
QUICA = 0.35                    # quanto da velocidade sobra depois de quicar
ATRITO_CHAO = 6.0               # 1/s
ARRASTO_AR = 0.15               # 1/s
ARRASTO_GIRO_AR = 0.8           # 1/s
MOLA_ENDIREITAR = 60.0          # força que ajeita o corpo tombado
AMORTECIMENTO_ENDIREITAR = 9.0
GIRO_MAXIMO = 1000.0            # graus/s
BOTOES_JANELA = 150             # px à direita da janela onde ele não pousa

# ---------------------------------------------------------------------------
# Bolinha
# ---------------------------------------------------------------------------
RAIO_BOLINHA = 18               # px
PERTO_BOLINHA = 170             # px: perto dele
LONGE_BOLINHA = 420             # px: longe o bastante para ter sido "levada"
MEMORIA_SOLTURA = 4.0           # s: depois de soltar, ainda conta como "você mexeu"
REPOUSO_BATIDA = 0.45           # quanto da velocidade sobra depois de bater
INTERVALO_CURSOR = 0.25         # s: o cursor não chuta a bolinha de novo logo depois

# ---------------------------------------------------------------------------
# Brincadeira
# ---------------------------------------------------------------------------
ALCANCE_BRINCADEIRA = 240       # px: a bolinha precisa estar perto dele
TEMPO_VOO_ARREMESSO = 0.7       # s de voo do arremesso até o cursor
INTERVALO_BRINCADEIRA = (2.5, 5.0)   # s entre tentativas de brincar
INTERVALO_PAPEL = 0.45          # s entre bolinhas de papel na revolução

# ---------------------------------------------------------------------------
# Protesto (raiva) e tristeza
# ---------------------------------------------------------------------------
LIMITES_ESTAGIO = [0.25, 0.5, 0.75, 1.0]   # insatisfação para entrar em 1, 2, 3, 4
HISTERESE = 0.12                # para sair de um estágio, cair isso abaixo
INSATISFACAO_MAXIMA = 1.3
ALIVIO_CARINHO = 0.3            # por segundo de carinho
REPRESSAO = 0.15                # cartaz arrancado à força
CRESCIMENTO_BANDEIRA = 0.25     # cada revolução: bandeira 25% maior
ESCALA_MAXIMA = 2.0
TEMPO_CARTAZ_FIM = 3.5          # s que o cartaz de fim (acordo ou volto) fica

# ---------------------------------------------------------------------------
# Travessuras
# ---------------------------------------------------------------------------
TAMANHO_MEME = 230              # px, lado maior de um meme entregue
TAMANHO_MEME_CANTO = 120        # px, meme pequeno de revolta no cantinho

# ---------------------------------------------------------------------------
# Fogos de artifício
# ---------------------------------------------------------------------------
TAMANHO_JANELA_FOGOS = 420      # px
TEMPO_FOGUETE = 0.55            # s que o foguete leva para subir
GRAVIDADE_FOGOS = 260.0         # px/s² das partículas
VIDA_PARTICULA = 1.8            # s
ESPERA_FOGOS = 40.0             # s entre um fogo e outro
EUFORIA_MAXIMA = 1.5

# ---------------------------------------------------------------------------
# Mesa (notebook)
# ---------------------------------------------------------------------------
FOCO_MAXIMO_HZ = 6.0           # taxa da população FOCUS que vale foco 1,0
FRACAO_ESCONDIDA_NOTEBOOK = 0.45  # fração da altura do pet escondida atrás da tampa do notebook
ALCANCE_NOTEBOOK = 300          # px: arrastar o notebook além disso faz o pet levantar e reagir
INSATISFACAO_NOTEBOOK = 0.35    # quanto a insatisfação sobe quando ele é arrancado da mesa (máximo 1,3)
PEDIDO_VALIDADE_S = 60.0        # s em que um pedido para trabalhar ainda vale
JANELA_PEDIDOS_S = 900.0        # s em que os pedidos contam para a frustração

FELIZ_APOS_CARINHO = 1.5        # s com os olhinhos fechados de felicidade depois do último carinho

# ---------------------------------------------------------------------------
# DECISÕES PELA REDE: cada uma é um neurônio motor. O limiar é a taxa de disparo
# (Hz) dele; a frequência de uma travessura ou de uma bolinha é a taxa vezes o ganho.
# ---------------------------------------------------------------------------
# >>> decisões (dono: frente NE; outras frentes não editam entre estas marcas)
LIMIAR_SENTAR_HZ = 6.0          # SENTAR acima disso: senta
LIMIAR_LEVANTAR_HZ = 3.0        # SENTAR abaixo disso: levanta (histerese)
LIMIAR_FUGA_HZ = 2.0            # FUGIR acima disso enche a vontade de fugir; abaixo, ela vaza
CARGA_FUGA_HZ_S = 300.0         # Hz·s acima do limiar para a vontade encher (bravo: ~30 s; entediado: ~50 s)
LIMIAR_CANTO_HZ = 3.0           # CANTO acima disso: vai para o cantinho
GANHO_TRAVESSURA = 0.002        # travessuras por segundo, por Hz do motor TRAVESSURA
GANHO_CARTAZ = 0.5              # cartazes por segundo, por Hz do motor CARTAZ
GANHO_PAPEL = 0.05              # bolinhas de papel por segundo, por Hz do motor PAPEL
# Neurônios do BioBrain (frente NE; core/bio/neuronios.py). Só valem para o cérebro "bio". Toda população que
# migra usa τ sináptico = τ_m que tinha no LIF (decisão do Cantyll, 2026-11-13, opção A); o ganho multiplica a
# escala de partida (escala_de_corrente: a mesma entrada mínima de disparo do LIF).
# NE-5 (decisão do Cantyll, 2026-11-13, opção B): as três chaves ficam ligadas por padrão. PESTINHA_NE=0 no ambiente
# desliga as três sem mexer no código: o BioBrain volta aos neurônios LIF, para separar o efeito do cérebro do efeito
# do neurônio.
from os import environ as _ambiente  # noqa: E402 (só a seção da frente NE usa)
_NE_LIGADA = _ambiente.get("PESTINHA_NE", "1").strip() != "0"
NE_INIBIDORES_FS = _NE_LIGADA   # NE-2: QUIET e INHIB em Izhikevich FS
NE_GANHO_QUIET = 1.0            # medido (comparar_izhikevich.py --calibrar): com 1,0 a QUIET dá 2,3 Hz contra 2,4 do LIF
NE_GANHO_INHIB = 1.2            # medido (idem): com 1,0 a INHIB dá 24 Hz contra 37 do LIF; com 1,2, 35
NE_EXCITATORIOS = _NE_LIGADA    # NE-3: os 8 excitatórios em Izhikevich (7 RS, ALERT CH).
#                                 Neles o pulso gasta um limiar do LIF da corrente sináptica (gasta_corrente), como o
#                                 reset do LIF: sem isso a corrente lenta (τ de 60 a 400 ms) sustenta trens de disparo.
# Ganhos da NE-3, ajustados por bisseção para a taxa somada em 9 contextos (sementes 3, 7 e 11) ficar igual à do LIF
# (±2% na 10ª rodada): python ferramentas/comparar_izhikevich.py --ajustar ne3. Valem com a NE-2 ligada. A ALERT fica
# fora da bisseção: em CH e com a adaptação lenta do LIF, o ganho dela iguala o susto do LIF (tests/test_ne_susto.py).
NE_GANHO_ALERT = 1.0              # ALERT em CH, com a adaptação lenta: ajustado pelo susto (--comportamento)
NE_GANHO_FOCUS = 1.028
NE_GANHO_CURIOUS = 1.028
NE_GANHO_PLAYFUL = 1.015
NE_GANHO_CALM = 0.92
NE_GANHO_TIRED = 0.96
NE_GANHO_FRUSTRATION = 1.015
NE_GANHO_GLOOM = 0.885
NE_MOTORES = _NE_LIGADA         # NE-4: os 15 motores em Izhikevich (14 RS, STARTLE CH), o pulso gasta a corrente
# Ganhos da NE-4, ajustados como os da NE-3 (python ferramentas/comparar_izhikevich.py --ajustar ne4), com a NE-2 e a
# NE-3 ligadas. Os limiares de decisão em Hz (LIMIAR_*_HZ, castigo_ctl, mesa, MotorDecoder, Emotion) não mudam: a
# NE-4 só passa se as taxas e o comportamento decodificado ficarem os do LIF (tests/test_ne4_motores.py). O STARTLE
# fica fora da bisseção: o ganho dele iguala o reflexo de susto (--comportamento ne4), não a taxa somada.
NE_GANHO_STARTLE = 0.55
NE_GANHO_WATCH = 0.893
NE_GANHO_WANDER = 0.885
NE_GANHO_CHEER = 0.96
NE_GANHO_SETTLE = 1.059
NE_GANHO_DROWSE = 0.964
NE_GANHO_ANGRY = 1.087
NE_GANHO_SAD = 0.998
NE_GANHO_SENTAR = 0.866
NE_GANHO_FUGIR = 1.087
NE_GANHO_CARTAZ = 1.015
NE_GANHO_CANTO = 1.011
NE_GANHO_TRAVESSURA = 1.006
NE_GANHO_PAPEL = 1.032
NE_GANHO_ACEITAR = 1.002
# Numba (decisão do Cantyll, 2026-11-13, opção C): com o Numba instalado (requirements-numba.txt), o passo do BioBrain
# roda compilado, com os mesmos pulsos do numpy (core/bio/acelerado.py). Sem o Numba, ou com False, fica o numpy.
NE_NUMBA = True
# <<< decisões

# ---------------------------------------------------------------------------
# Rosto e janela
# ---------------------------------------------------------------------------
LADO_JANELA_PET = 200         # px da janela transparente do corpo
ZZZ_QUANTIDADE = 3
ZZZ_PERIODO = 2.4               # s que cada Z leva para subir e sumir

# ---------------------------------------------------------------------------
# Ritmo e sono (docs/ESPECIFICACAO_NUCLEO_BIOLOGICO.md, seções 8 e 8.1; ritmo.py)
# ---------------------------------------------------------------------------
PICO_VIGILIA_H = 16.0           # h: pico de vigília, no fim da tarde (cada pet troca em pets/*.json: pico_vigilia_h)
K_PRESSAO_ACORDADO = 0.1        # 1/h: P sobe de 0 a ~0,8 em 16 h acordado (spec: 0,1)
K_PRESSAO_DORMINDO = 0.12       # 1/h: P cai de ~0,8 a 0,25 em ~10 h dormindo (spec: 0,35, que dava só 3,7 h de sono)
PRESSAO_INICIAL = 0.3           # P de um pet novo
LIMIAR_DORME_PRESSAO = 0.75     # dorme se P passa disso e o relógio está na noite (C < LIMIAR_DORME_C)
LIMIAR_DORME_C = 0.2
LIMIAR_DORME_FORCADO = 0.95     # dorme de qualquer jeito se P passar disso (não passa 16 h acordado)
LIMIAR_ACORDA_PRESSAO = 0.25    # acorda se P cair abaixo disso
LIMIAR_ACORDA_C = 0.6           # ou se estiver no pico de vigília (C > isso) com P abaixo de LIMIAR_ACORDA_PRESSAO_DIA
LIMIAR_ACORDA_PRESSAO_DIA = 0.5

# ---------------------------------------------------------------------------
# Ausência (R1): modulador da rede, não sensor (core/nervous_system.py, definir_ausencia)
# ---------------------------------------------------------------------------
AUSENCIA_CORRENTE = 0.2         # corrente inibitória por ms em FUGIR e TRAVESSURA quando você está ausente (limiar de disparo: 1,0)
NEGLIGENCIA_S = 600.0           # s: você presente e sem interagir com o pet por esse tempo liga a mesma guarda (decisão do Cantyll, 2026-11-13: 10 minutos; core/negligencia.py)

# ---------------------------------------------------------------------------
# Replay noturno (M3): reaplica os episódios durante o sono (spec, seção 9.4)
# ---------------------------------------------------------------------------
REPLAY_EPISODIOS = 50           # episódios reaplicados num sono de uma noite de dívida, por |δ| e recência (dívida menor: a parte dela)
REPLAY_FATOR = 0.5              # δ_replay = REPLAY_FATOR · δ registrado (spec, seção 9.4)
REPLAY_MS = 500                 # cada episódio reativa o padrão sensorial por 0,5 s
REPLAY_MS_POR_FRAME = 100       # simulação de replay por quadro, para a tela não travar

# ---------------------------------------------------------------------------
# Homeostase sináptica no sono (decisão D4, hipótese SHY; spec, seção 9.4)
# Sem isso, o replay de episódios negativos levava a tristeza (GLOOM) ao teto e ela ficava lá.
# ---------------------------------------------------------------------------
HOMEOSTASE_SHY = 0.2            # um sono de uma noite de dívida desfaz essa fração das sinapses aprendidas (dívida menor: 1 − 0,8^fração)
HOMEOSTASE_TETO = 0.5           # o replay para de empurrar uma sinapse em 50% do seu limite (LEARN_MAX / LEARN_MIN)

# ---------------------------------------------------------------------------
# FRENTES (seções reservadas pelo T1; plano, seção 5). Cada frente põe os próprios números só entre as
# suas marcas, aqui e em _LIMITES. A chave que liga a frente fica em config.FRENTES.
# ---------------------------------------------------------------------------
# >>> frente lar (dono: LAR-1, LAR-3)
# O lar (LAR-1): um canto fixo com cama. Com sono chegando, ele vai para a cama e dorme lá.
LAR_MARGEM_PRESSAO = 0.05       # sonolento: a pressão de sono a esta distância do limiar de dormir
LAR_MARGEM_C = 0.1              # e o relógio a esta distância do limiar da noite (~25 min antes)
LAR_VELOCIDADE_CAMA = 90.0      # px/s: com sono, ele vai devagar até a cama
LAR_CHEGOU_CAMA = 14            # px do centro da cama: já está deitado nela
LAR_VALIDADE_CAMA = 1.0         # s: o pedido de ir para a cama vale isso; sem o módulo renovar, ele esquece
LAR_DURACAO_BAGUNCA = 8.0       # s: uma travessura de casa (pular na cama e bagunçar o canto)
LAR_PULOS_BAGUNCA = 1.5         # pulinhos por segundo enquanto bagunça a cama
LAR_MEIA_VIDA_CARINHO_S = 30.0  # teto do carinho: depois de 30 s de carinho recente, ele ensina a metade (0 desliga)
LAR_RECUPERACAO_CARINHO_H = 8.0 # τ da volta: a carga de carinho vaza com esta constante de tempo
LAR_RECOMPENSA_TEDIO = 3.0      # reforço do lar (PL-1): recompensa total por tirar o tédio inteiro (1 → 0) bagunçando
# <<< frente lar
# >>> frente modelo_eu (dono: EU-1, EU-2)
# <<< frente modelo_eu
# >>> frente hipocampo (dono: ME-1)
# <<< frente hipocampo
# >>> frente diario (dono: AC-1)
# <<< frente diario
# >>> frente gravador (dono: AC-3)
# <<< frente gravador
# >>> frente respiracao (dono: TA-1)
# <<< frente respiracao
# >>> frente conversa (dono: LI-0)
# <<< frente conversa
# >>> frente bandeja_estado (dono: LAR-4)
# <<< frente bandeja_estado
# >>> frente plasticidade (dono: PL-1)
# Plasticidade do BioBrain com erro de predição (PL-1, parte 1; spec, seções 7.2, 7.4 e 8). Desligada, o
# BioBrain aprende como o LIF (recompensa bruta). Ligada: δ = r − V, com V de um crítico (core/conditioning.py,
# decisão D3), e a taxa multiplicada por (0,5 + ACh). Só vale para o cérebro "bio". Números escolhidos, não medidos,
# a não ser onde o comentário diz.
PL_DELTA = True                 # δ = r − V no BioBrain. Ligada por padrão desde 2026-11-13 (decisão do Cantyll); o app
                                # segue no LIF (config.CEREBRO), então só vale quando o cérebro for o bio
PL_CRITICO_TAXA = 0.5           # por passo de 0,1 s: quão rápido o crítico aprende a prever (calibrado: 20 pares pista e
                                # recompensa levam δ a ~0%; com 0,3 o PEDIDO ainda subia 10% em mais 20 pares)
PL_CRITICO_TAU_S = 30.0         # τ_V: até quantos segundos depois de uma pista a recompensa ainda conta como dela
PL_CRITICO_LIMITE = 5.0         # |peso| máximo de cada canal no crítico (só para não divergir)
PL_ACH = False                  # ACh na taxa. Desligada: fator 1. Com ela, a regra 8 falha no misto e no carinhoso
                                # (medido em 2026-11-13, ferramentas/comparar_pl1.py); volta com a STDP (PL-1, parte 2)
PL_ACH_TAU_S = 30.0             # τ da acetilcolina (spec, seção 8)
PL_ACH_REF_HZ = 15.0            # taxa do FOCUS que vale ACh 1 (medido: semente 7, programando, ~15 Hz)
PL_ACH_MEDIA_H = 24.0           # τ da média lenta da ACh (h): a taxa é dividida por (0,5 + média)
PL_ACH_MEDIA_INICIAL = 0.3      # média de quem ainda não tem histórico (escolhido: ~30% do dia programando)
# Canais que o crítico lê: as pistas, que vêm antes de uma interação. Contexto (atividade, tédio, carência) e a
# própria sensação da recompensa (CARESS, DISMISS) ficam de fora: senão V vira a recompensa média de cada contexto,
# que é quase zero, e quase nada mais ensina (ver core/bio/plasticidade.py). None: todos os canais.
PL_CANAIS_CRITICO = ("PEDIDO", "ANTICIPATE", "ANTECIPA_PLACA", "PLACA", "VISITA", "TOY_NEAR", "TOY_TAKEN", "RECUSA")
# <<< frente plasticidade

# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

# nome: (tipo, mínimo, máximo) para números; listas e tuplas têm regra própria
_LIMITES = {
    "PICO_VIGILIA_H": (float, 0.0, 23.99),
    "K_PRESSAO_ACORDADO": (float, 0.001, 2.0),
    "K_PRESSAO_DORMINDO": (float, 0.001, 2.0),
    "PRESSAO_INICIAL": (float, 0.0, 1.0),
    "LIMIAR_DORME_PRESSAO": (float, 0.0, 1.0),
    "LIMIAR_DORME_C": (float, -1.0, 1.0),
    "LIMIAR_DORME_FORCADO": (float, 0.0, 1.0),
    "LIMIAR_ACORDA_PRESSAO": (float, 0.0, 1.0),
    "LIMIAR_ACORDA_C": (float, -1.0, 1.0),
    "LIMIAR_ACORDA_PRESSAO_DIA": (float, 0.0, 1.0),
    "COOLDOWN_CUTUCADA": (float, 0.0, 5.0),
    "TEMPO_MAX_CUTUCADA_MS": (int, 50, 2000),
    "DISTANCIA_INICIO_ARRASTE": (int, 0, 100),
    "VELOCIDADE_ARREMESSO": (float, 100.0, 5000.0),
    "JANELA_CARINHO": (float, 0.1, 10.0),
    "TROCAS_CARINHO": (int, 1, 20),
    "DESLOCAMENTO_CARINHO": (float, 0.0, 1000.0),
    "DURACAO_CARINHO": (float, 0.0, 10.0),
    "BATIDA_FORTE": (float, 100.0, 10000.0),
    "BATIDA_TONTA": (float, 100.0, 10000.0),
    "DURACAO_TONTURA": (float, 0.0, 10.0),
    "INTERVALO_BATIDA": (float, 0.0, 10.0),
    "ATIVIDADE_MINIMA_VOO": (float, 0.0, 100.0),
    "SILENCIO_MOUSE": (float, 0.0, 10.0),
    "ESPERA_MEDIDA_CUTUCADA": (float, 0.0, 5.0),
    "HZ_RESPOSTA_CHEIA": (float, 0.1, 100.0),
    "RESPOSTA_MINIMA": (float, 0.0, 1.0),
    "RECOMPENSA_CARINHO": (float, 0.0, 10.0),
    "PUNICAO_DISPENSA": (float, -10.0, 0.0),
    "DISPENSA_RAPIDA": (float, 0.0, 60.0),
    "PENALIDADE_DISPENSA": (float, 0.0, 60.0),
    "HABITUACAO_DISPENSA": (float, 0.0, 1000.0),
    "RECUPERACAO_DISPENSA_H": (float, 0.01, 168.0),
    "DESABITUACAO_CARINHO": (float, 0.0, 1.0),
    "GRAVIDADE": (float, 0.0, 100000.0),
    "QUICA": (float, 0.0, 1.0),
    "ATRITO_CHAO": (float, 0.0, 100.0),
    "ARRASTO_AR": (float, 0.0, 100.0),
    "ARRASTO_GIRO_AR": (float, 0.0, 100.0),
    "MOLA_ENDIREITAR": (float, 0.0, 10000.0),
    "AMORTECIMENTO_ENDIREITAR": (float, 0.0, 1000.0),
    "GIRO_MAXIMO": (float, 0.0, 100000.0),
    "BOTOES_JANELA": (int, 0, 1000),
    "RAIO_BOLINHA": (int, 4, 200),
    "PERTO_BOLINHA": (int, 1, 2000),
    "LONGE_BOLINHA": (int, 1, 5000),
    "MEMORIA_SOLTURA": (float, 0.0, 60.0),
    "REPOUSO_BATIDA": (float, 0.0, 1.0),
    "INTERVALO_CURSOR": (float, 0.0, 10.0),
    "ALCANCE_BRINCADEIRA": (int, 1, 5000),
    "TEMPO_VOO_ARREMESSO": (float, 0.05, 10.0),
    "INTERVALO_PAPEL": (float, 0.05, 60.0),
    "HISTERESE": (float, 0.0, 1.0),
    "INSATISFACAO_MAXIMA": (float, 0.1, 10.0),
    "ALIVIO_CARINHO": (float, 0.0, 10.0),
    "REPRESSAO": (float, 0.0, 10.0),
    "CRESCIMENTO_BANDEIRA": (float, 0.0, 10.0),
    "ESCALA_MAXIMA": (float, 1.0, 10.0),
    "TEMPO_CARTAZ_FIM": (float, 0.0, 60.0),
    "TAMANHO_MEME": (int, 16, 2000),
    "TAMANHO_MEME_CANTO": (int, 16, 2000),
    "TAMANHO_JANELA_FOGOS": (int, 100, 2000),
    "TEMPO_FOGUETE": (float, 0.05, 10.0),
    "GRAVIDADE_FOGOS": (float, 0.0, 100000.0),
    "VIDA_PARTICULA": (float, 0.05, 60.0),
    "ESPERA_FOGOS": (float, 0.0, 3600.0),
    "EUFORIA_MAXIMA": (float, 0.1, 10.0),
    "FOCO_MAXIMO_HZ": (float, 0.1, 500.0),
    "FRACAO_ESCONDIDA_NOTEBOOK": (float, 0.0, 0.9),
    "ALCANCE_NOTEBOOK": (int, 50, 2000),
    "INSATISFACAO_NOTEBOOK": (float, 0.0, 1.3),
    "PEDIDO_VALIDADE_S": (float, 1.0, 600.0),
    "JANELA_PEDIDOS_S": (float, 60.0, 86400.0),
    "FELIZ_APOS_CARINHO": (float, 0.0, 30.0),
    "NEGLIGENCIA_S": (float, 1.0, 86400.0),
    # >>> decisões
    "LIMIAR_SENTAR_HZ": (float, 0.0, 200.0),
    "LIMIAR_LEVANTAR_HZ": (float, 0.0, 200.0),
    "LIMIAR_FUGA_HZ": (float, 0.0, 200.0),
    "CARGA_FUGA_HZ_S": (float, 0.1, 10000.0),
    "LIMIAR_CANTO_HZ": (float, 0.0, 200.0),
    "GANHO_TRAVESSURA": (float, 0.0, 1.0),
    "GANHO_CARTAZ": (float, 0.0, 1.0),
    "GANHO_PAPEL": (float, 0.0, 1.0),
    "NE_GANHO_QUIET": (float, 0.1, 10.0),
    "NE_GANHO_INHIB": (float, 0.1, 10.0),
    "NE_GANHO_ALERT": (float, 0.05, 10.0),
    "NE_GANHO_FOCUS": (float, 0.05, 10.0),
    "NE_GANHO_CURIOUS": (float, 0.05, 10.0),
    "NE_GANHO_PLAYFUL": (float, 0.05, 10.0),
    "NE_GANHO_CALM": (float, 0.05, 10.0),
    "NE_GANHO_TIRED": (float, 0.05, 10.0),
    "NE_GANHO_FRUSTRATION": (float, 0.05, 10.0),
    "NE_GANHO_GLOOM": (float, 0.05, 10.0),
    "NE_GANHO_STARTLE": (float, 0.05, 10.0),
    "NE_GANHO_WATCH": (float, 0.05, 10.0),
    "NE_GANHO_WANDER": (float, 0.05, 10.0),
    "NE_GANHO_CHEER": (float, 0.05, 10.0),
    "NE_GANHO_SETTLE": (float, 0.05, 10.0),
    "NE_GANHO_DROWSE": (float, 0.05, 10.0),
    "NE_GANHO_ANGRY": (float, 0.05, 10.0),
    "NE_GANHO_SAD": (float, 0.05, 10.0),
    "NE_GANHO_SENTAR": (float, 0.05, 10.0),
    "NE_GANHO_FUGIR": (float, 0.05, 10.0),
    "NE_GANHO_CARTAZ": (float, 0.05, 10.0),
    "NE_GANHO_CANTO": (float, 0.05, 10.0),
    "NE_GANHO_TRAVESSURA": (float, 0.05, 10.0),
    "NE_GANHO_PAPEL": (float, 0.05, 10.0),
    "NE_GANHO_ACEITAR": (float, 0.05, 10.0),
    # <<< decisões
    "LADO_JANELA_PET": (int, 100, 1000),
    "ZZZ_QUANTIDADE": (int, 0, 20),
    "ZZZ_PERIODO": (float, 0.1, 60.0),
    # >>> frente lar
    "LAR_MARGEM_PRESSAO": (float, 0.0, 0.5),
    "LAR_MARGEM_C": (float, 0.0, 1.0),
    "LAR_VELOCIDADE_CAMA": (float, 10.0, 1000.0),
    "LAR_CHEGOU_CAMA": (int, 1, 200),
    "LAR_VALIDADE_CAMA": (float, 0.1, 10.0),
    "LAR_DURACAO_BAGUNCA": (float, 0.5, 120.0),
    "LAR_PULOS_BAGUNCA": (float, 0.0, 10.0),
    "LAR_MEIA_VIDA_CARINHO_S": (float, 0.0, 86400.0),
    "LAR_RECUPERACAO_CARINHO_H": (float, 0.01, 168.0),
    "LAR_RECOMPENSA_TEDIO": (float, 0.0, 100.0),
    # <<< frente lar
    # >>> frente modelo_eu
    # <<< frente modelo_eu
    # >>> frente hipocampo
    # <<< frente hipocampo
    # >>> frente diario
    # <<< frente diario
    # >>> frente gravador
    # <<< frente gravador
    # >>> frente respiracao
    # <<< frente respiracao
    # >>> frente conversa
    # <<< frente conversa
    # >>> frente bandeja_estado
    # <<< frente bandeja_estado
    # >>> frente plasticidade
    "PL_CRITICO_TAXA": (float, 0.0, 1.0),
    "PL_CRITICO_TAU_S": (float, 0.1, 3600.0),
    "PL_CRITICO_LIMITE": (float, 0.0, 1000.0),
    "PL_ACH_TAU_S": (float, 0.1, 3600.0),
    "PL_ACH_REF_HZ": (float, 0.1, 500.0),
    "PL_ACH_MEDIA_H": (float, 0.01, 720.0),
    "PL_ACH_MEDIA_INICIAL": (float, 0.0, 1.0),
    # <<< frente plasticidade
}


def validar():
    """Confere tipo e limite de cada ajuste. Levanta ValueError com todos os problemas."""
    erros = []
    atuais = globals()
    for nome, (tipo, minimo, maximo) in _LIMITES.items():
        valor = atuais.get(nome)
        if valor is None:
            erros.append(f"{nome}: falta o ajuste")
            continue
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            erros.append(f"{nome}: deveria ser número, veio {type(valor).__name__}")
            continue
        if tipo is int and not float(valor).is_integer():
            erros.append(f"{nome}: deveria ser inteiro, veio {valor}")
        if not (minimo <= valor <= maximo):
            erros.append(f"{nome}: {valor} está fora de [{minimo}, {maximo}]")
    for nome in ("INTERVALO_BRINCADEIRA",):
        par = atuais[nome]
        if not (isinstance(par, tuple) and len(par) == 2 and 0 < par[0] <= par[1] <= 600):
            erros.append(f"{nome}: deveria ser (mínimo, máximo) com 0 < mínimo <= máximo <= 600")
    limites = atuais["LIMITES_ESTAGIO"]
    if not (len(limites) == 4 and all(0 < a < b for a, b in zip(limites, limites[1:]))):
        erros.append("LIMITES_ESTAGIO: deveria ter 4 valores crescentes e positivos")
    if erros:
        raise ValueError("ajustes inválidos:\n  " + "\n  ".join(erros))


validar()
