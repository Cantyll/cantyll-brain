"""
Replay noturno (M3, spec seção 9.4): os episódios mais marcantes voltam à rede durante o sono.

Rodar: python -m pytest tests/test_replay.py -q
"""
import json

from pestinha import ajustes
from pestinha.core.episodic import EpisodicMemory
from pestinha.core.nervous_system import LIFBrain
from pestinha.mind.sleep import SleepController


def _memoria(tmp_path):
    return EpisodicMemory(tmp_path / "episodes.jsonl", tmp_path / "preferences.json")


def _grava(mem, n, valencia, sentidos, contexto="WORK|curioso", acao="bilhete"):
    """Escreve n episódios resolvidos no arquivo, do mais antigo ao mais novo."""
    with open(mem.episodes_path, "a", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"id": f"{contexto}-{acao}-{valencia}-{i}", "quando": "2026-11-11T00:00:00",
                                "contexto": contexto, "acao": acao, "resultado": "teste",
                                "valencia": valencia, "sentidos": sentidos}) + "\n")


def _peso(brain, canal, post):
    """Peso aprendido de um canal sensorial para um neurônio pós plástico (0 no começo)."""
    return float(brain.learned[brain.sensory_names.index(canal), brain.plastic_posts.index(post)])


def test_episodio_guarda_os_sentidos_do_momento(tmp_path):
    mem = _memoria(tmp_path)
    mem.sentidos_atuais = {"WORK": 0.7}
    ep = mem.start("WORK|curioso", "bilhete")
    mem.sentidos_atuais = {"WORK": 0.1}
    assert ep["sentidos"] == {"WORK": 0.7}          # cópia: mudar depois não altera o episódio


def test_replay_pega_no_maximo_50_e_deixa_de_fora_o_neutro(tmp_path):
    mem = _memoria(tmp_path)
    _grava(mem, 30, 0.0, {"WORK": 0.8})              # δ = 0: não ensina nada
    _grava(mem, 80, 0.6, {"WORK": 0.8})
    escolhidos = mem.escolher_replay()
    assert len(escolhidos) == ajustes.REPLAY_EPISODIOS == 50
    assert all(abs(delta - ajustes.REPLAY_FATOR * 0.6) < 1e-9 for _, delta in escolhidos)   # δ_replay = 0,5 · δ


def test_replay_prioriza_o_mais_marcante_mesmo_que_antigo(tmp_path):
    mem = _memoria(tmp_path)
    _grava(mem, 1, -0.9, {"WORK": 0.5})              # antigo, mas forte
    _grava(mem, 60, 0.2, {"TYPING": 0.5})            # muitos, fracos e recentes
    primeiro_delta = mem.escolher_replay()[0][1]
    assert abs(primeiro_delta - ajustes.REPLAY_FATOR * -0.9) < 1e-9   # |δ| pesa mais que a idade aqui


def test_replay_ignora_episodio_sem_padrao_sensorial_valido(tmp_path):
    mem = _memoria(tmp_path)
    _grava(mem, 5, 0.7, {})                          # sem sentidos: fica só para o bandit
    _grava(mem, 5, 0.7, {"WORK": 2.0})               # fora de [0, 1]: descartado
    assert mem.escolher_replay() == []


def test_replay_positivo_reforca_o_padrao_e_negativo_enfraquece(tmp_path):
    pos = LIFBrain(seed=7, seed_ruido=42)
    neg = LIFBrain(seed=7, seed_ruido=42)
    pos.replay({"WORK": 1.0}, 500, +0.4)
    neg.replay({"WORK": 1.0}, 500, -0.4)
    # PLAYFUL tem sinal +1 e GLOOM tem sinal -1 na regra de aprendizado
    assert _peso(pos, "WORK", "PLAYFUL") > 0 > _peso(pos, "WORK", "GLOOM")
    assert _peso(neg, "WORK", "PLAYFUL") < 0 < _peso(neg, "WORK", "GLOOM")


class _Sem:
    """Stand-in para as dependências do sono que o teste não usa (emoção, necessidades)."""
    pressao = 0.9


def _dorme(tmp_path, n_episodios):
    mem = _memoria(tmp_path)
    _grava(mem, n_episodios, 0.6, {"WORK": 0.8})
    sono = SleepController(None, _Sem(), mem, lambda: False)
    sono.fall_asleep()
    return sono


def test_sono_monta_fila_com_no_maximo_50_episodios(tmp_path):
    sono = _dorme(tmp_path, 60)
    assert len(sono.replay_fila) == ajustes.REPLAY_EPISODIOS
    assert all(item["restante"] == ajustes.REPLAY_MS for item in sono.replay_fila)


def test_sem_episodios_a_fila_fica_vazia(tmp_path):
    sono = _dorme(tmp_path, 0)
    assert sono.asleep and sono.replay_fila == []


def test_replay_passo_gasta_o_orcamento_e_acordar_limpa_a_fila(tmp_path):
    sono = _dorme(tmp_path, 2)                       # 2 episódios de 500 ms
    brain = LIFBrain(seed=7, seed_ruido=42)
    assert sono.replay_passo(brain, 300, 0.004) == 300
    assert sono.replay_fila[0]["restante"] == ajustes.REPLAY_MS - 300
    while sono.replay_fila:                          # o resto da noite, por quadros
        sono.replay_passo(brain, ajustes.REPLAY_MS_POR_FRAME, 0.004)
    assert sono.replay_passo(brain, 100, 0.004) == 0  # fila vazia: nada a gastar
    sono.replay_fila = [{"sentidos": {"WORK": 0.8}, "delta": 0.3, "restante": 200}]
    sono.wake(startled=False)                        # acordou no meio: o que sobrou não roda
    assert sono.replay_fila == []
