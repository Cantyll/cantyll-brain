# Custo do M1: Izhikevich contra LIF

Medida prévia, feita na nuvem: Intel Xeon 2,1 GHz, 4 vCPU compartilhadas, Python 3.13.18, numpy 2.5.3,
Linux. **Não é a máquina de referência** (ver `docs/CUSTO_DO_PASSO.md`). Antes de decidir D2 e M1, rode
`python ferramentas/medir_custo_izhikevich.py` na referência e registre a saída aqui.

## O que foi medido

- Os dois modelos passam pelo mesmo `_substep` sintético, com o mesmo tamanho, a mesma multiplicação densa
  de entrada (densidade de 7%, como na rede real), a mesma habituação, a mesma contagem de pools e o mesmo
  ruído. Só o núcleo do neurônio muda.
- Izhikevich: v e u, com um passo de Euler de 0,5 ms por chamada. 20% de neurônios FS e 80% RS. Disparo em
  30 mV, reset com `c` e `d`.
- Medição pareada: LIF e Izhikevich se alternam em cada rodada. 15 rodadas de 2000 passos; mediana.
  Assim o ruído da máquina pesa igual nos dois.

## Resultado (3 execuções)

| Execução | LIF 470 (µs, fração) | Izhikevich 470 | LIF 630 | Izhikevich 630 | Razão 630 |
|---|---:|---:|---:|---:|---:|
| 1 | 51,9 (10,4%) | 56,0 (11,1%) | 135,2 (26,8%) | 148,9 (29,7%) | 1,11 |
| 2 | 50,7 (10,0%) | 51,4 (10,3%) | 143,7 (28,7%) | 145,5 (29,1%) | 1,02 |
| 3 | 51,3 (9,9%) | 55,6 (11,1%) | 143,8 (28,5%) | 145,6 (28,7%) | 1,01 |

Razões em 470: 1,07, 1,03 e 1,12. Frações a 0,5 ms (2000 passos por segundo).

**Leitura:** nesta máquina, trocar o núcleo do LIF pelo do Izhikevich adiciona de 0% a 11% ao passo de
630 neurônios, com mediana perto de 2%. Como a troca mudou o passo em no máximo 11%, o grosso do custo
está no resto do `_substep`, que é igual nos dois modelos (inclui a matriz densa). Quanto é a matriz
não foi separado.

**Atenção à fração absoluta:** nesta execução, o LIF de 630 deu 27% a 29%. Na medida anterior, na mesma
nuvem, deu 23% a 27%. A VM ficou mais lenta, e o ruído entre execuções é de ±15%. Por isso só a razão,
medida na mesma rodada, deve ser lida. A fração absoluta só vale na máquina de referência.

## O que não está medido

- **Dois subpassos por 0,5 ms.** A receita de Izhikevich (2003) integra em meios passos. Se o M1 integrar
  em 0,25 ms, o núcleo do neurônio custa o dobro. A fração de 0,5 ms passa a ser o teto de uma conta que
  ainda não foi feita.
- **Sinapses com condutância e tipos de sinapse.** O sintético soma corrente, como o LIF atual.
- **`step()` real:** o custo aqui é só do `_substep`. Gravação, pools e o laço de `step()` ficam de fora.
- **Quanto da fração vem da multiplicação densa.** Não foi separado. Essa é a hipótese para testar com W
  esparso, antes de M6.
- **Máquina de referência.** Só nuvem.

## Consequência

- O risco de orçamento de 25% está menos no Izhikevich do que dizia a seção "O que este número não cobre"
  de `CUSTO_DO_PASSO.md`. Nesta máquina, o M1 adiciona pouco por cima do LIF. O que pesa é o resto do passo.
- A ordem recomendada da spec (seção 13) põe M1 depois de M3, M2, M5 e M6. Esta medida não muda essa ordem:
  mostra só que o custo do M1 não é o bloqueio.
