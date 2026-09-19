"""Validação do plano e das entradas, sem executar detectores ou ler a base."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.limiarizacao import executar_rodada as batch


PLANO = Path(__file__).resolve().parents[1] / "limiarizacao" / "rodadas" / "round1.json"


class TestePlanoEEntradas(unittest.TestCase):
    def setUp(self):
        # A lista congelada serve somente como fixture; nenhum caminho da base
        # original é aberto. As leituras de entrada usam diretórios temporários.
        self.plano = json.loads(PLANO.read_text(encoding="utf-8-sig"))

    def conteudo(self):
        return json.dumps(self.plano, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def test_aceita_exclusoes_acordadas_e_preserva_composicao_congelada(self):
        carregado = batch.carregar_plano(self.conteudo())
        self.assertEqual(carregado, self.plano)
        self.assertEqual(len(carregado["configuracoes"]), 48)
        self.assertEqual(len(carregado["quadros"]), 178)
        self.assertEqual(
            {(item["video_id"], item["quadro"]) for item in carregado["exclusoes"]},
            {("23", 900), ("23", 1100)},
        )

    def test_rejeita_novas_exclusoes_quadros_omitidos_ou_repetidos(self):
        original = deepcopy(self.plano)
        for caso in ("exclusao_nova", "omitido", "repetido"):
            self.plano = deepcopy(original)
            if caso == "exclusao_nova":
                item = self.plano["exclusoes"][0]
                item["quadro"] = 950
                item["imagem"] = (
                    "bases_de_dados/visem_tracking/dataset/Train/23/images/23_frame_950.jpg"
                )
                item["anotacao"] = (
                    "bases_de_dados/visem_tracking/dataset/Train/23/labels/23_frame_950.txt"
                )
            elif caso == "omitido":
                self.plano["quadros"].pop()
            else:
                self.plano["quadros"].append(deepcopy(self.plano["quadros"][0]))
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                batch.carregar_plano(self.conteudo())

    def test_rejeita_configuracoes_equivalentes_com_morfologia_desativada(self):
        original = next(item for item in self.plano["configuracoes"]
                        if item["parametros"]["abertura"]["iteracoes"] == 0)
        duplicada = deepcopy(original)
        duplicada["id"] = "duplicada_inativa"
        duplicada["parametros"]["abertura"] = {
            "forma": "cruz", "tamanho": 7, "iteracoes": 0,
        }
        self.plano["configuracoes"].append(duplicada)
        with self.assertRaisesRegex(ValueError, "configurações equivalentes"):
            batch.carregar_plano(self.conteudo())

    def test_rejeita_videos_reservados_e_caminhos_incoerentes(self):
        original = deepcopy(self.plano["quadros"][0])
        for video in ("13", "14"):
            item = deepcopy(original)
            item["video_id"] = video
            for campo, pasta, sufixo in (("imagem", "images", "jpg"),
                                          ("anotacao", "labels", "txt")):
                item[campo] = (
                    f"bases_de_dados/visem_tracking/dataset/Train/{video}/{pasta}/"
                    f"{video}_frame_{item['quadro']}.{sufixo}"
                )
            self.plano["quadros"][0] = item
            with self.subTest(video=video), self.assertRaisesRegex(ValueError, "desenvolvimento"):
                batch.carregar_plano(self.conteudo())
        self.plano["quadros"][0] = original
        self.plano["quadros"][0]["imagem"] = "../../fora_da_base.jpg"
        with self.assertRaisesRegex(ValueError, "Caminho incoerente"):
            batch.carregar_plano(self.conteudo())

    def test_hash_confere_conteudo_e_rejeita_arquivo_alterado(self):
        item = deepcopy(self.plano["quadros"][0])
        conteudo = b"0 0.5 0.5 0.1 0.1\n"
        item["sha256_anotacao"] = hashlib.sha256(conteudo).hexdigest()
        with TemporaryDirectory() as temporaria, patch.object(batch, "RAIZ", Path(temporaria)):
            arquivo = Path(temporaria) / item["anotacao"]
            arquivo.parent.mkdir(parents=True)
            arquivo.write_bytes(conteudo)
            self.assertEqual(batch.ler_entrada(item, "anotacao"), conteudo)
            arquivo.write_bytes(b"0 0.6 0.5 0.1 0.1\n")
            with self.assertRaisesRegex(ValueError, "mudou desde"):
                batch.ler_entrada(item, "anotacao")

    def test_anotacao_ausente_nao_e_tratada_como_arquivo_vazio(self):
        item = deepcopy(self.plano["quadros"][0])
        item["sha256_anotacao"] = hashlib.sha256(b"").hexdigest()
        with TemporaryDirectory() as temporaria, patch.object(batch, "RAIZ", Path(temporaria)):
            arquivo = Path(temporaria) / item["anotacao"]
            arquivo.parent.mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):
                batch.ler_entrada(item, "anotacao")
            arquivo.write_bytes(b"")
            self.assertEqual(batch.ler_entrada(item, "anotacao"), b"")


if __name__ == "__main__":
    unittest.main()
