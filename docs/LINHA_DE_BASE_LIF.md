# Linha de base do LIF (T2)

Arquivo gerado. Não editar à mão: rodar o comando abaixo e fazer commit do resultado.

    python ferramentas/linha_de_base.py

Simulação de noites (`ferramentas/simular_noites.py`), 30 noites, sementes 1 a 20 (20 rodadas por linha). Taxa de uso de cada população no dia 30, em Hz por neurônio. É simulação com uso suposto, não medida de uso real: as suposições estão no cabeçalho de `simular_noites.py`.

Colunas: média, desvio padrão (dp), mínimo e máximo das sementes, e dois erros-padrão da média (2·dp/√n), em Hz e em % da média. Os valores brutos de cada semente estão em `docs/linha_de_base_lif.json`. Com média abaixo de 0.05 Hz, a % não tem sentido e aparece como --: ali a comparação tem de ser em Hz.

## duro, 1 sono(s) por noite

| População | média | dp | mín | máx | ±2 EP | ±2 EP (%) |
|---|---|---|---|---|---|---|
| PLAYFUL | 1.972 | 0.315 | 1.433 | 2.606 | 0.141 | 7.1% |
| CALM | 0.476 | 0.104 | 0.304 | 0.696 | 0.047 | 9.8% |
| FRUSTRATION | 1.745 | 0.216 | 1.352 | 2.117 | 0.097 | 5.5% |
| GLOOM | 1.756 | 0.199 | 1.260 | 2.033 | 0.089 | 5.1% |
| CHEER | 3.170 | 0.483 | 2.482 | 4.357 | 0.216 | 6.8% |
| SAD | 0.973 | 0.260 | 0.502 | 1.445 | 0.116 | 12.0% |

## misto, 1 sono(s) por noite

| População | média | dp | mín | máx | ±2 EP | ±2 EP (%) |
|---|---|---|---|---|---|---|
| PLAYFUL | 3.773 | 0.475 | 2.948 | 4.894 | 0.212 | 5.6% |
| CALM | 3.210 | 0.268 | 2.627 | 3.704 | 0.120 | 3.7% |
| FRUSTRATION | 0.000 | 0.001 | 0.000 | 0.006 | 0.001 | -- |
| GLOOM | 0.001 | 0.006 | 0.000 | 0.025 | 0.002 | -- |
| CHEER | 5.730 | 0.655 | 4.845 | 7.272 | 0.293 | 5.1% |
| SAD | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -- |

## carinhoso, 1 sono(s) por noite

| População | média | dp | mín | máx | ±2 EP | ±2 EP (%) |
|---|---|---|---|---|---|---|
| PLAYFUL | 9.298 | 0.347 | 8.652 | 10.106 | 0.155 | 1.7% |
| CALM | 11.639 | 0.581 | 10.656 | 12.823 | 0.260 | 2.2% |
| FRUSTRATION | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -- |
| GLOOM | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -- |
| CHEER | 12.865 | 1.027 | 11.055 | 14.697 | 0.459 | 3.6% |
| SAD | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -- |
