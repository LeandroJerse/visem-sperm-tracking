"""Migração de proveniência com preservação, falhas e compatibilidade histórica."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.blobs import organizacao


def bytes_json(dados):
    return (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


class OrganizacaoBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name)
        self.pasta = self.raiz / "resultados/videos/blobs/selecao/batch__sintetico"
        self.pasta.mkdir(parents=True)
        fontes, saidas, hashes_originais = {}, {}, {}
        for i in range(22):
            nome = f"origem_{i:02d}"
            extensao = ".csv" if i % 3 == 0 else ".json"
            conteudo = f"campo\n{i}\n".encode() if extensao == ".csv" else bytes_json({"valor": i})
            arquivo = self.pasta / (nome + extensao)
            arquivo.write_bytes(conteudo)
            original = f"fontes/{nome}{extensao}"
            fontes[nome] = {"arquivo": original, "sha256": sha(conteudo)}
            hashes_originais[original] = sha(conteudo)
            saidas[arquivo.relative_to(self.raiz).as_posix()] = sha(conteudo)
        plano = bytes_json({"proveniencia": {"fontes": fontes}})
        (self.pasta / "plano.json").write_bytes(plano)
        saidas[(self.pasta / "plano.json").relative_to(self.raiz).as_posix()] = sha(plano)
        for nome, conteudo in (("codigo.zip", b"codigo original"), ("ranking.csv", b"ranking original\n"),
                               ("s052__config/midia/video.mp4", b"video original")):
            arquivo = self.pasta / nome
            arquivo.parent.mkdir(exist_ok=True, parents=True)
            arquivo.write_bytes(conteudo)
            saidas[arquivo.relative_to(self.raiz).as_posix()] = sha(conteudo)
        manifesto = {"versao": 1, "tipo": "videos_selecao_blobs", "situacao": "concluida",
                     "plano_sha256": sha(plano), "origens_sha256": hashes_originais, "saidas_sha256": saidas,
                     "codigo": {"arquivo": "codigo.zip"}, "avaliacoes_concluidas": 29250}
        self.manifesto_path = self.pasta / "execucao.json"
        self.manifesto_path.write_bytes(bytes_json(manifesto))
        relatorio = self.pasta / "relatorios/historico"
        relatorio.mkdir(parents=True)
        (relatorio / "execucao_origem.json").write_bytes(self.manifesto_path.read_bytes())
        (relatorio / "relatorio.pdf").write_bytes(b"%PDF sintetico inalterado")
        (relatorio / "relatorio.json").write_bytes(bytes_json({
            "origens_sha256": {self.manifesto_path.relative_to(self.raiz).as_posix(): sha(self.manifesto_path.read_bytes())}}))
        self.antes = self.snapshot()

    def snapshot(self):
        return {p.relative_to(self.pasta).as_posix(): p.read_bytes() for p in self.pasta.rglob("*") if p.is_file()}

    def executar(self):
        return organizacao.organizar_origens(self.pasta, self.raiz)

    def modificar_manifesto(self, **campos):
        m = json.loads(self.manifesto_path.read_bytes())
        m.update(campos)
        self.manifesto_path.write_bytes(bytes_json(m))

    def test_migracao_preserva_fontes_pdf_e_resultados(self):
        resultado = self.executar()
        self.assertTrue(resultado["alterado"])
        self.assertEqual(resultado["arquivos_movidos"], 22)
        m = json.loads(self.manifesto_path.read_bytes())
        antigo = json.loads(self.antes["execucao.json"])
        self.assertEqual(m["pasta_origens"], "origens")
        self.assertEqual(m["origens_sha256"], antigo["origens_sha256"])
        for nome, blob in self.antes.items():
            if nome.startswith("origem_"):
                self.assertFalse((self.pasta / nome).exists())
                self.assertEqual((self.pasta / "origens" / nome).read_bytes(), blob)
            elif nome != "execucao.json":
                self.assertEqual((self.pasta / nome).read_bytes(), blob)
        for nome, digest in m["saidas_sha256"].items():
            self.assertEqual(sha((self.raiz / nome).read_bytes()), digest)
        historico = self.pasta / "origens/historico_organizacao"
        self.assertEqual((historico / "manifesto_anterior.json").read_bytes(), self.antes["execucao.json"])
        registro = json.loads((historico / "registro.json").read_bytes())
        self.assertEqual(len(registro["mapeamento"]), 22)
        self.assertEqual(sha(self.manifesto_path.read_bytes()), resultado["manifesto_sha256"])
        # O hash antigo do PDF continua verificável no manifesto arquivado.
        registro_pdf = json.loads(self.antes["relatorios/historico/relatorio.json"])
        self.assertEqual(registro["manifesto_anterior"]["sha256"], next(iter(registro_pdf["origens_sha256"].values())))

    def test_repeticao_e_noop_sem_troca_de_manifesto(self):
        self.executar()
        antes = self.snapshot()
        with patch.object(organizacao, "_mover", side_effect=AssertionError("Movimento repetido")), \
                patch.object(organizacao, "gravar_json", side_effect=AssertionError("Gravação repetida")):
            resultado = self.executar()
        self.assertFalse(resultado["alterado"])
        self.assertEqual(resultado["arquivos_conferidos"], 22)
        self.assertEqual(antes, self.snapshot())

    def test_batch_novo_organizado_sem_historico(self):
        self.executar()
        m = json.loads(self.manifesto_path.read_bytes())
        historico = self.pasta / "origens/historico_organizacao"
        for p in historico.iterdir():
            m["saidas_sha256"].pop(p.relative_to(self.raiz).as_posix())
            p.unlink()
        historico.rmdir()
        self.manifesto_path.write_bytes(bytes_json(m))
        antes = self.snapshot()
        self.assertFalse(self.executar()["alterado"])
        self.assertEqual(antes, self.snapshot())

    def test_fonte_ausente_ou_hash_alterado_nao_move_nada(self):
        caminho = self.pasta / "origem_21.csv"
        original = caminho.read_bytes()
        for ausencia in (True, False):
            if ausencia:
                caminho.unlink()
            else:
                caminho.write_bytes(original + b"alterado")
            antes = self.snapshot()
            with self.subTest(ausencia=ausencia), self.assertRaises((ValueError, FileNotFoundError)):
                self.executar()
            self.assertEqual(antes, self.snapshot())
            self.assertFalse((self.pasta / "origens").exists())
            caminho.write_bytes(original)

    def test_destino_conflitante_preservado(self):
        destino = self.pasta / "origens"
        destino.mkdir()
        (destino / "origem_21.csv").write_bytes(b"arquivo do pesquisador")
        antes = self.snapshot()
        with self.assertRaisesRegex(ValueError, "já existe"):
            self.executar()
        self.assertEqual(antes, self.snapshot())

    def test_temporario_preexistente_nao_e_substituido(self):
        (self.pasta / "execucao.json.tmp").write_bytes(b"arquivo anterior")
        antes = self.snapshot()
        with self.assertRaisesRegex(ValueError, "temporário"):
            self.executar()
        self.assertEqual(antes, self.snapshot())

    def test_falha_apos_alguns_movimentos_reverte_tudo(self):
        mover = organizacao._mover
        contador = 0
        def falhar(origem, destino):
            nonlocal contador
            contador += 1
            if contador == 4:
                raise PermissionError("acesso negado sintético")
            mover(origem, destino)
        with patch.object(organizacao, "_mover", side_effect=falhar), self.assertRaises(PermissionError):
            self.executar()
        self.assertEqual(self.antes, self.snapshot())
        self.assertFalse((self.pasta / "origens").exists())

    def test_falha_gravacao_manifesto_reverte_todos_movimentos(self):
        def falhar(caminho, dados):
            caminho.with_suffix(".json.tmp").write_bytes(b"arquivo incompleto")
            raise PermissionError("bloqueado")
        with patch.object(organizacao, "gravar_json", side_effect=falhar), self.assertRaises(PermissionError):
            self.executar()
        self.assertEqual(self.antes, self.snapshot())
        self.assertFalse((self.pasta / "origens").exists())

    def test_reversao_bloqueada_preserva_historico_para_recuperacao(self):
        mover = organizacao._mover
        contador = 0
        def falhar(origem, destino):
            nonlocal contador
            contador += 1
            if contador > 1:
                raise PermissionError("movimento e reversão bloqueados")
            mover(origem, destino)
        with patch.object(organizacao, "_mover", side_effect=falhar), self.assertRaisesRegex(RuntimeError, "reversão incompleta"):
            self.executar()
        self.assertEqual(self.manifesto_path.read_bytes(), self.antes["execucao.json"])
        self.assertEqual((self.pasta / "origens/historico_organizacao/manifesto_anterior.json").read_bytes(), self.antes["execucao.json"])
        self.assertTrue((self.pasta / "origens/origem_00.csv").exists())

    def test_rollback_preserva_pasta_origens_que_ja_existia(self):
        (self.pasta / "origens").mkdir()
        with patch.object(organizacao, "gravar_json", side_effect=PermissionError("bloqueado")), self.assertRaises(PermissionError):
            self.executar()
        self.assertTrue((self.pasta / "origens").is_dir())
        self.assertEqual(self.antes, self.snapshot())

    def test_layout_e_execucao_incompleta_rejeitados(self):
        for campos in ({"pasta_origens": "../../fora"}, {"situacao": "em_andamento"}, {"tipo": "outro"}):
            self.manifesto_path.write_bytes(self.antes["execucao.json"])
            self.modificar_manifesto(**campos)
            antes = self.snapshot()
            with self.subTest(campos=campos), self.assertRaises(ValueError):
                self.executar()
            self.assertEqual(antes, self.snapshot())

    def test_legacy_ponto_explicito(self):
        self.modificar_manifesto(pasta_origens=".")
        self.assertTrue(self.executar()["alterado"])
        self.assertFalse(self.executar()["alterado"])

    def test_nome_origem_com_traversal_rejeitado_antes_de_mover(self):
        plano_path = self.pasta / "plano.json"
        plano = json.loads(plano_path.read_bytes())
        fontes = plano["proveniencia"]["fontes"]
        fontes["../escape"] = fontes.pop("origem_21")
        blob = bytes_json(plano)
        plano_path.write_bytes(blob)
        m = json.loads(self.manifesto_path.read_bytes())
        m["plano_sha256"] = sha(blob)
        m["saidas_sha256"][plano_path.relative_to(self.raiz).as_posix()] = sha(blob)
        self.manifesto_path.write_bytes(bytes_json(m))
        antes = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Nome"):
            self.executar()
        self.assertEqual(antes, self.snapshot())

    def test_batch_fora_do_destino_rejeitado(self):
        for pasta, raiz in ((self.pasta, self.raiz / "resultados"), (self.pasta.parent, self.raiz)):
            with self.subTest(pasta=pasta), self.assertRaises(ValueError):
                organizacao.organizar_origens(pasta, raiz)
        self.assertEqual(self.antes, self.snapshot())

    def test_noop_confere_historico_e_fontes(self):
        self.executar()
        for nome in ("origens/origem_21.csv", "origens/historico_organizacao/manifesto_anterior.json",
                     "origens/historico_organizacao/registro.json"):
            caminho = self.pasta / nome
            original = caminho.read_bytes()
            caminho.write_bytes(original + b" ")
            antes = self.snapshot()
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                self.executar()
            self.assertEqual(antes, self.snapshot())
            caminho.write_bytes(original)

    def test_noop_rejeita_copia_duplicada_e_manifesto_modificado(self):
        self.executar()
        duplicada = self.pasta / "origem_00.csv"
        duplicada.write_bytes((self.pasta / "origens/origem_00.csv").read_bytes())
        with self.assertRaisesRegex(ValueError, "duplicada"):
            self.executar()
        duplicada.unlink()
        self.modificar_manifesto(avaliacoes_concluidas=1)
        with self.assertRaisesRegex(ValueError, "Manifesto atual"):
            self.executar()


if __name__ == "__main__":
    unittest.main()
