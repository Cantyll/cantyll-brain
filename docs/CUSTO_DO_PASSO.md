# Custo do passo da rede

Quanto de um núcleo de CPU a rede gasta por segundo simulado. Os números vêm de
`ferramentas/medir_custo_passo.py`, rodado em cada máquina. A máquina de referência é a de uso diário
do Cantyll (seção abaixo). A primeira medida foi feita nela, num Windows 11.

Reproduzir:

    python ferramentas/medir_custo_passo.py

## Máquina de referência

A referência é o computador em que o Pestinha roda no dia a dia de quem o usa. O pet vive no PC de
quem o usa, então o critério é que ele caiba nesse PC, e não num servidor.

Procedimento:

1. Ligar o computador na tomada, com o modo de energia de desempenho ou equilibrado. Em bateria, o
   processador costuma reduzir o clock, e a medida fica pior sem motivo.
2. Rodar `python ferramentas/medir_custo_passo.py` três vezes, sem outros programas pesados abertos.
3. Registrar a linha "Ambiente" e a tabela das três execuções, e comparar a mediana do passo de 630 neurônios.

Critério: com 630 neurônios e passo de 0,5 ms, a fração de um núcleo fica em até 25% (spec, seção 10).
Se passar, a saída é reduzir populações ou voltar para passo de 1 ms (D2).

### Regra de escolha

- A referência é a máquina de uso diário de quem usa o Pestinha, ligada na tomada, no modo de energia
  de desempenho ou equilibrado.
- A referência deste projeto é a máquina de uso diário do Cantyll. Ele a escolheu em 2026-11-11 por esse
  motivo, e não pelo número que ela daria.
- A medida na nuvem (Xeon compartilhado, 23% a 27% para 630 neurônios sintéticos) já existia quando a
  referência foi escolhida. Ela não é a referência; fica registrada como medida.
- A referência só muda com decisão registrada neste arquivo, com data e motivo. Se mudar, o LIF atual
  (470 neurônios) é medido de novo na máquina nova antes de qualquer comparação.
- Medidas em outras máquinas entram como medidas, não como referência.

### Primeira medida: Windows 11, 8 núcleos lógicos

Ambiente: Intel família 6 modelo 140, 8 núcleos lógicos, Python 3.15.2, numpy 2.5.4, Windows 11.

| Execução | Real 470, 1 ms (µs/passo) | Controle 470 (µs/passo) | 630, 1 ms (µs/passo) | 630, 0,5 ms: fração de 1 núcleo |
|---|---:|---:|---:|---:|
| 1 | 51,4 (4,7%) | 50,9 | 78,0 | 15,6% |
| 2 | 48,1 (4,7%) | 48,4 | 76,2 | 15,6% |
| 3 | 47,4 (4,7%) | 48,5 | 76,6 | 15,6% |

Leitura: o passo de 630 neurônios com 0,5 ms gasta cerca de 15,6% de um núcleo nesta máquina, contra
o teto de 25%. O controle sintético bate com a rede real (até 3% de diferença), então a medida é
confiável também no Windows. Esta máquina é cerca de 1,6 vez mais rápida no passo de 630 do que o
sandbox da primeira seção.

Uma observação para o M1: a razão entre o passo de 630 e o de 470 aqui é 76,6 / 48,4, cerca de 1,6.
No sandbox foi cerca de 2,2. A razão depende da máquina e da biblioteca de álgebra linear, então o
custo tem de ser medido, não extrapolado.

Confirmado pelo Cantyll: essa é a máquina de uso diário, e ela estava na tomada durante as execuções.
A referência está fechada com essa máquina.

## Ambiente desta medida

- CPU: Intel Xeon 2,1 GHz, 4 vCPU, container na nuvem (VM compartilhada: a variação entre rodadas é de até ±15%).
- Python 3.13, numpy 2.5, uma thread de BLAS (`OPENBLAS_NUM_THREADS=1`), para o número ser de um núcleo.
- Mediana de 15 rodadas de 1 s simulado (rede real) ou de 2000 passos (sintética). Três execuções
  seguidas foram feitas para ver a variação.

## O que foi medido

1. **Rede real (LIF atual):** 470 neurônios, 180 sensoriais, 15808 sinapses (semente 7), passo de 1 ms.
   Mede `step()` com estímulo, como o app faz.
2. **Controle sintético (470):** o mesmo `_substep` com arrays sintéticos do mesmo tamanho. Serve para
   provar que a sintética reproduz a real: se os números batem, a sintética de 630 é confiável.
3. **Sintética de 630:** o mesmo `_substep`, com 630 neurônios. Os 180 sensoriais ficam como estão e os
   160 novos entram nos neurônios não sensoriais. Isso bate com a tabela de regiões da spec (seção 4,
   linha 65): 180 sensoriais e 450 não sensoriais (via rápida 20, córtex 140, gânglios 210, expressão 80).
   A multiplicação densa `W_lif` passa de 470 × 290 para 630 × 450.

Um passo de 0,5 ms custa o mesmo que um de 1 ms com as mesmas formas de array; por isso o passo de
0,5 ms é uma conta de 2000 passos por segundo, não uma medida nova.

## Resultado

| Execução | Real 470, 1 ms (µs/passo) | Controle 470 (µs/passo) | 630, 1 ms (µs/passo) | 630, 0,5 ms: fração de 1 núcleo |
|---|---:|---:|---:|---:|
| 1 | 54,0 (5,4%) | 53,1 | 117,4 | 23,2% |
| 2 | 52,7 (5,3%) | 56,0 | 121,7 | 23,8% |
| 3 | 56,2 (5,6%) | 56,1 | 135,7 | 26,9% |

Depois do modulador de ausência (um `if` por passo, que só age quando você está ausente), três
novas execuções deram: rede real 51 a 57 µs (5,1% a 5,7%); 630 com passo de 0,5 ms entre 23,1% e 23,9%.
Ou seja, o custo ficou dentro do ruído das medidas anteriores.

Resumo: **a rede atual gasta cerca de 5,5% de um núcleo**. Uma rede de 630 neurônios com passo de
0,5 ms gastaria **entre 23% e 27% de um núcleo** nesta máquina (mediana perto de 24%).

Os 23% a 27% são de uma rede sintética de 630 neurônios, que ainda não existe. A rede real de 470,
que existe, gasta 5,5% na mesma máquina. Não compare o 630 sintético com a rede real como se fossem a
mesma coisa.

## Contra os critérios da spec (seção 10)

- "Menos de 0,5 ms por passo para acompanhar o tempo real": **passa com folga**. O passo de 630 custa
  0,12 a 0,14 ms.
- "Fração de CPU medida, estimativa inicial até 25% de um núcleo": **no limite**. O intervalo medido
  (23% a 27%) cruza o 25%. Não dá para dizer que passa com segurança, e a conta só tem o LIF atual.
- Na referência (Windows, seção acima), o mesmo passo mede 15,6%: passa com folga, mas só para o LIF atual.

## Onde a spec errou na conta

A seção 6 (linha 88) diz que a rede de 630 com passo de 0,5 ms custaria "cerca de 3,6 vezes mais por
segundo simulado (2 × (630/470)²)". A medida dá **4,3 a 4,8 vezes** (divisão da fração de 630 a 0,5 ms
pela fração real atual). A conta da spec supõe custo quadrático em N, mas a matriz que domina é
`N × (N − Ns)`, e `Ns` não cresce: 630 × 450 contra 470 × 290 dá 2,1 vezes o trabalho, e não 1,8.
Quem quiser a conta correta precisa dessa forma, não de N².

## O que este número não cobre

- **Izhikevich (M1):** cada neurônio terá mais operações por passo. Isso não está medido, e é o maior
  risco para o orçamento de 25%.
- **Plasticidade e replay:** o aprendizado por carinho roda fora do passo, mas o replay do M3 não está
  medido.
- **Densidade:** a multiplicação densa custa o mesmo com 7% ou 100% de sinapses preenchidas. Um W esparso
  pode ser mais barato, mas isso não foi testado. A spec (linha 270) pede essa decisão antes do M6.
- **Máquina de referência:** a medida da nuvem (Xeon compartilhado) não é a referência. A referência
  tem a medida do Windows, e só ela.

## Próximos passos (não feitos aqui)

1. Medir de novo na referência sempre que a rede mudar de forma (por exemplo, no M1).
2. No M1, medir o passo com Izhikevich e o passo com W esparso, nas mesmas condições, antes de fixar D2.
3. Se o passo de 630 passar de 25% de um núcleo na máquina de referência, a saída é reduzir populações
   ou usar passo de 1 ms (revisar D2), não otimizar no escuro.
