"""
Núcleo novo do pet (plano, T2; spec, seção 12). `BioBrain` em rede.py implementa a interface Brain.

Cada frente do plano preenche o próprio arquivo deste pacote (plano, seção 2, regra 2). Os arquivos das
frentes já existem, vazios, com o dono e o que vão conter escritos no topo.
"""
from .rede import BIO_VERSION, BioBrain, Pool

__all__ = ["BIO_VERSION", "BioBrain", "Pool"]
