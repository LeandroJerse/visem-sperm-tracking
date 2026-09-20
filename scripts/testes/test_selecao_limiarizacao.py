"""Confere o contrato de seleção sem ler imagens ou executar detectores."""

from copy import deepcopy
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.limiarizacao import executar_rodada as batch
from scripts.limiarizacao import executar_selecao as selecao


PASTA = Path(__file__).resolve().parents[1] / "limiarizacao"


class TestePlanoSelecao(unittest.TestCase):
    def setUp(self):
        # Apenas planos versionados servem de fixture. As fontes de resultados
        # são representadas em memória; nenhuma pasta de imagem é consultada.
        self.plano = json.loads((PASTA / "selecao" / "plano.json").read_text(encoding="utf-8-sig"))
        origens = {
            (origem["rodada"], origem["configuracao_id"]): origem["pasta_execucao"]
            for item in self.plano["configuracoes"] for origem in item["origens"]
        }
        self.fontes = []
        for fonte in deepcopy(self.plano["geracao"]["fontes_desenvolvimento"]):
            rodada = fonte["rodada"]
            anterior = json.loads((PASTA / "rodadas" / f"{rodada}.json").read_text(encoding="utf-8-sig"))
            execucao = {"execucoes": [
                {"configuracao_id": item["id"], "pasta": origens[(rodada, item["id"])]}
                for item in anterior["configuracoes"]
            ]}
            self.fontes.append((fonte, anterior, execucao))

    def conteudo(self):
        return json.dumps(self.plano, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def carregar(self):
        with patch.object(selecao, "_conferir_fontes", return_value=self.fontes):
            return selecao.carregar_plano_selecao(self.conteudo())

    def test_preserva_as_122_candidatas_as_136_origens_e_os_60_quadros(self):
        carregado = self.carregar()
        self.assertEqual(carregado, self.plano)
        self.assertEqual(len(carregado["configuracoes"]), 122)
        self.assertEqual(sum(len(item["origens"]) for item in carregado["configuracoes"]), 136)
        self.assertEqual(len(carregado["quadros"]), 60)
        self.assertEqual(carregado["exclusoes"], [])

    def test_rejeita_candidata_omitida_ou_reordenada(self):
        original = deepcopy(self.plano)
        for caso in ("omitida", "reordenada"):
            self.plano = deepcopy(original)
            if caso == "omitida":
                self.plano["configuracoes"].pop()
            else:
                self.plano["configuracoes"][0], self.plano["configuracoes"][1] = (
                    self.plano["configuracoes"][1], self.plano["configuracoes"][0]
                )
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                self.carregar()

    def test_rejeita_duplicata_equivalente_com_morfologia_desativada(self):
        duplicada = deepcopy(self.plano["configuracoes"][0])
        self.assertEqual(duplicada["parametros"]["abertura"]["iteracoes"], 0)
        duplicada["id"] = "s002"
        duplicada["parametros"]["abertura"] = {"forma": "cruz", "tamanho": 7, "iteracoes": 0}
        self.plano["configuracoes"][1] = duplicada
        with self.assertRaisesRegex(ValueError, "equivalentes duplicadas"):
            self.carregar()

    def test_rejeita_parametro_ou_proveniencia_alterados(self):
        original = deepcopy(self.plano)
        for caso in ("parametro", "origem", "hash"):
            self.plano = deepcopy(original)
            item = self.plano["configuracoes"][0]
            if caso == "parametro":
                item["parametros"]["area_minima"] += 1
            elif caso == "origem":
                item["origens"][0]["configuracao_id"] = "outra"
            else:
                item["sha256_parametros_canonicos"] = "0" * 64
            with self.subTest(caso=caso), self.assertRaisesRegex(ValueError, "diverge"):
                self.carregar()

    def test_rejeita_quadro_omitido_repetido_excluido_ou_fora_da_particao(self):
        original = deepcopy(self.plano)
        for caso in ("omitido", "repetido", "excluido", "desenvolvimento", "final"):
            self.plano = deepcopy(original)
            if caso == "omitido":
                self.plano["quadros"].pop()
            elif caso == "repetido":
                self.plano["quadros"][1] = deepcopy(self.plano["quadros"][0])
            elif caso == "excluido":
                self.plano["exclusoes"].append(deepcopy(self.plano["quadros"][0]))
            else:
                self.plano["quadros"][0]["video_id"] = "11" if caso == "desenvolvimento" else "14"
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                self.carregar()

    def test_rejeita_caminho_anotacao_ftid_hash_invalido_e_json_duplicado(self):
        original = deepcopy(self.plano)
        for caso in ("ftid", "fora", "hash"):
            self.plano = deepcopy(original)
            item = self.plano["quadros"][0]
            if caso == "ftid":
                item["anotacao"] = item["anotacao"].replace("/labels/", "/labels_ftid/")
            elif caso == "fora":
                item["imagem"] = "../../imagem.jpg"
            else:
                item["sha256_imagem"] = "invalido"
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                self.carregar()
        with self.assertRaisesRegex(ValueError, "Campo repetido"):
            selecao.carregar_plano_selecao(b'{"versao": 1, "versao": 1}')

    def test_desenvolvimento_continua_rejeitando_plano_de_selecao(self):
        with self.assertRaises(ValueError):
            batch.carregar_plano(self.conteudo())

    def test_rejeita_criterios_divergentes_do_motor_de_avaliacao(self):
        original = deepcopy(self.plano)
        for campo, valor in (("iou_minimo", 0.7), ("ordenacao", "Priorizar classe 0"),
                             ("sem_casos", "Converter em zero"), ("tempo", "Desempate automático")):
            self.plano = deepcopy(original)
            self.plano["criterios_avaliacao"][campo] = valor
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "contrato acordado"):
                self.carregar()
        self.plano = deepcopy(original)
        del self.plano["criterios_avaliacao"]
        with self.assertRaisesRegex(ValueError, "contrato acordado"):
            self.carregar()

    def test_fontes_incompletas_nao_sao_aceitas(self):
        self.plano["geracao"]["fontes_desenvolvimento"].pop()
        with self.assertRaisesRegex(ValueError, "cinco fontes"):
            selecao._conferir_fontes(self.plano)

    def test_hash_da_fonte_confere_arquivo_e_rejeita_alteracao(self):
        with TemporaryDirectory() as temporaria:
            raiz = Path(temporaria)
            arquivo = raiz / "analise" / "resumo.json"
            arquivo.parent.mkdir()
            arquivo.write_bytes(b"{}")
            esperado = batch.sha256(b"{}")
            with patch.object(selecao, "RAIZ", raiz):
                self.assertEqual(selecao._ler_fonte("analise/resumo.json", esperado, arquivo.parent), b"{}")
                arquivo.write_bytes(b'{"alterado":true}')
                with self.assertRaisesRegex(ValueError, "mudou desde o congelamento"):
                    selecao._ler_fonte("analise/resumo.json", esperado, arquivo.parent)
                with self.assertRaises(ValueError):
                    selecao._ler_fonte("../fora.json", esperado, arquivo.parent)

    def test_entrada_selecao_reutiliza_pipeline_com_validador_e_fonte_proprios(self):
        with patch.object(batch, "executar_plano", return_value=Path("resultado")) as executar:
            retorno = selecao.executar(argparse.Namespace(plano=PASTA / "selecao" / "plano.json"))
        self.assertEqual(retorno, Path("resultado"))
        executar.assert_called_once_with(
            (PASTA / "selecao" / "plano.json").resolve(), selecao.carregar_plano_selecao,
            rodada_solicitada="selecao", fontes_adicionais=(Path(selecao.__file__).resolve(),),
        )


if __name__ == "__main__":
    unittest.main()
