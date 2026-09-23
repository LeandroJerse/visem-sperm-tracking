"""Gravação segura diante de bloqueios transitórios, sem executar experimentos."""

from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import call, patch

from scripts.blobs import arquivos


def erro_windows(codigo):
    erro = PermissionError("Arquivo temporariamente bloqueado")
    erro.winerror = codigo
    return erro


class ArquivosBlobsTest(unittest.TestCase):
    def setUp(self):
        self.pasta_temporaria = TemporaryDirectory()
        self.addCleanup(self.pasta_temporaria.cleanup)
        self.pasta = Path(self.pasta_temporaria.name)
        self.destino = self.pasta / "execucao.json"
        self.temporario = self.destino.with_suffix(".json.tmp")
        self.destino.write_bytes(b"conteudo anterior")
        self.temporario.write_bytes(b"conteudo novo")

    def test_substituicao_sem_bloqueio_nao_espera(self):
        with patch.object(arquivos, "sleep") as esperar:
            arquivos.substituir_arquivo(self.temporario, self.destino)
        esperar.assert_not_called()
        self.assertEqual(self.destino.read_bytes(), b"conteudo novo")
        self.assertFalse(self.temporario.exists())

    def test_bloqueio_transitorio_preserva_destino_ate_troca_bem_sucedida(self):
        substituir_original = Path.replace
        for codigo in (5, 32, 33):
            with self.subTest(winerror=codigo):
                self.destino.write_bytes(b"conteudo anterior")
                self.temporario.write_bytes(b"conteudo novo")
                tentativas = []

                def substituir(caminho, destino):
                    self.assertEqual(caminho, self.temporario)
                    self.assertEqual(destino, self.destino)
                    tentativas.append(caminho)
                    if len(tentativas) <= 2:
                        raise erro_windows(codigo)
                    return substituir_original(caminho, destino)

                def esperar(_segundos):
                    self.assertEqual(self.destino.read_bytes(), b"conteudo anterior")
                    self.assertEqual(self.temporario.read_bytes(), b"conteudo novo")

                aviso = StringIO()
                with patch.object(Path, "replace", autospec=True, side_effect=substituir), \
                        patch.object(arquivos, "sleep", side_effect=esperar) as pausa, \
                        redirect_stderr(aviso):
                    arquivos.substituir_arquivo(self.temporario, self.destino)

                self.assertEqual(len(tentativas), 3)
                self.assertEqual(pausa.call_args_list, [
                    call(arquivos.INTERVALOS_REPETICAO[0]),
                    call(arquivos.INTERVALOS_REPETICAO[1]),
                ])
                self.assertEqual(len(aviso.getvalue().strip().splitlines()), 1)
                self.assertEqual(self.destino.read_bytes(), b"conteudo novo")
                self.assertFalse(self.temporario.exists())

    def test_bloqueio_persistente_esgota_limite_e_preserva_ambos_arquivos(self):
        for codigo in (5, 32, 33):
            with self.subTest(winerror=codigo):
                erro = erro_windows(codigo)
                with patch.object(Path, "replace", autospec=True, side_effect=erro) as trocar, \
                        patch.object(arquivos, "sleep") as pausa, \
                        redirect_stderr(StringIO()), \
                        self.assertRaises(PermissionError) as capturado:
                    arquivos.substituir_arquivo(self.temporario, self.destino)
                self.assertIs(capturado.exception, erro)
                self.assertEqual(trocar.call_count, len(arquivos.INTERVALOS_REPETICAO) + 1)
                self.assertEqual(pausa.call_args_list, [
                    call(intervalo) for intervalo in arquivos.INTERVALOS_REPETICAO
                ])
                self.assertEqual(self.destino.read_bytes(), b"conteudo anterior")
                self.assertEqual(self.temporario.read_bytes(), b"conteudo novo")

    def test_outros_erros_nao_sao_repetidos(self):
        erros = [FileNotFoundError("Origem inexistente"),
                 OSError("Sem espaço"), PermissionError("Sem código do Windows"),
                 erro_windows(87)]
        for erro in erros:
            with self.subTest(erro=repr(erro), winerror=getattr(erro, "winerror", None)):
                with patch.object(Path, "replace", autospec=True, side_effect=erro) as trocar, \
                        patch.object(arquivos, "sleep") as pausa, \
                        redirect_stderr(StringIO()) as aviso, \
                        self.assertRaises(type(erro)) as capturado:
                    arquivos.substituir_arquivo(self.temporario, self.destino)
                self.assertIs(capturado.exception, erro)
                trocar.assert_called_once_with(self.temporario, self.destino)
                pausa.assert_not_called()
                self.assertEqual(aviso.getvalue(), "")
                self.assertEqual(self.destino.read_bytes(), b"conteudo anterior")
                self.assertEqual(self.temporario.read_bytes(), b"conteudo novo")

    def test_json_preserva_unicode_estrutura_e_quebra_final(self):
        dados = {"situação": "concluída", "quadros": [0, 100], "f1": None}
        with patch.object(arquivos, "substituir_arquivo", wraps=arquivos.substituir_arquivo) as trocar:
            arquivos.gravar_json(self.destino, dados)
        trocar.assert_called_once_with(self.temporario, self.destino)
        texto = self.destino.read_text(encoding="utf-8")
        self.assertEqual(json.loads(texto), dados)
        self.assertEqual(texto, json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        self.assertFalse(self.temporario.exists())

    def test_json_invalido_nao_substitui_destino(self):
        for valor, tipo_erro in ((float("nan"), ValueError),
                                 (float("inf"), ValueError),
                                 (float("-inf"), ValueError),
                                 (object(), TypeError)):
            with self.subTest(valor=valor), \
                    patch.object(arquivos, "substituir_arquivo") as trocar, \
                    self.assertRaises(tipo_erro):
                arquivos.gravar_json(self.destino, {"valor": valor})
            trocar.assert_not_called()
            self.assertEqual(self.destino.read_bytes(), b"conteudo anterior")

    def test_json_com_bloqueio_transitorio_chega_integro_ao_destino(self):
        substituir_original = Path.replace
        dados = {"estado": "em andamento", "quadros_concluidos": 88}
        tentativas = []

        def substituir(caminho, destino):
            tentativas.append(caminho)
            self.assertEqual(json.loads(caminho.read_text(encoding="utf-8")), dados)
            if len(tentativas) == 1:
                raise erro_windows(32)
            return substituir_original(caminho, destino)

        with patch.object(Path, "replace", autospec=True, side_effect=substituir), \
                patch.object(arquivos, "sleep") as pausa, \
                redirect_stderr(StringIO()):
            arquivos.gravar_json(self.destino, dados)
        self.assertEqual(len(tentativas), 2)
        pausa.assert_called_once_with(arquivos.INTERVALOS_REPETICAO[0])
        self.assertEqual(json.loads(self.destino.read_text(encoding="utf-8")), dados)
        self.assertFalse(self.temporario.exists())


if __name__ == "__main__":
    unittest.main()
