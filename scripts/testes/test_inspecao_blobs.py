"""Contratos de round0 com arquivos e detecções sintéticos em pasta temporária."""

from __future__ import annotations

from copy import deepcopy
import csv
import json
from math import pi
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from algoritmos.classicos.comum import Caixa, ClasseObjeto, Deteccao, MedidasBlob, ResultadoDeteccao
from scripts.blobs import executar_inspecao as executor
from analise import relatorio_inspecao_blobs as relatorio


def bytes_json(dados):
    return (json.dumps(dados, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def linhas_csv(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


class InspecaoBlobsTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.saida = self.raiz / "resultados/frame-to-frame/blobs/round0"
        for modulo in (executor, relatorio):
            p = patch.object(modulo, "RAIZ", self.raiz); p.start(); self.addCleanup(p.stop)
            p = patch.object(modulo, "SAIDA", self.saida); p.start(); self.addCleanup(p.stop)
        fonte = "scripts/blobs/executar_inspecao.py"
        self.gravar(fonte, b"# fonte sintetica\n")
        p = patch.object(executor, "FONTES_CODIGO", (fonte,)); p.start(); self.addCleanup(p.stop)
        chaves = [("11", 0), ("12", 200), ("19", 0), ("21", 0), ("23", 0), ("36", 1300)]
        imagem = np.zeros((80, 80, 3), dtype=np.uint8)
        cv2.circle(imagem, (40, 40), 8, (255, 255, 255), -1)
        ok, encoded = cv2.imencode(".jpg", imagem)
        self.assertTrue(ok)
        self.imagem = encoded.tobytes()
        self.anotacao = b"0 0.5 0.5 0.25 0.25\n"
        origem_quadros = []
        for v in executor.VIDEOS_DESENVOLVIMENTO:
            for q in range(0, 1401, 100):
                if (v, q) in (("23", 900), ("23", 1100)):
                    continue
                item = {"video_id": v, "quadro": q,
                        "imagem": f"bases_de_dados/visem_tracking/dataset/Train/{v}/images/{v}_frame_{q}.jpg",
                        "anotacao": f"bases_de_dados/visem_tracking/dataset/Train/{v}/labels/{v}_frame_{q}.txt",
                        "sha256_imagem": executor.sha256(self.imagem),
                        "sha256_anotacao": executor.sha256(self.anotacao)}
                origem_quadros.append(item)
                if (v, q) in chaves:
                    self.gravar(item["imagem"], self.imagem)
                    self.gravar(item["anotacao"], self.anotacao)
        origem = {"algoritmo": "limiarizacao", "particao": "desenvolvimento", "rodada": "round1", "quadros": origem_quadros}
        origem_bytes = bytes_json(origem)
        self.gravar(executor.ORIGEM_DESENVOLVIMENTO, origem_bytes)
        parametros = {"polaridade": "claro", "limiar_minimo": 10, "limiar_maximo": 250,
                      "passo_limiar": 10, "repetibilidade_minima": 2, "distancia_minima": 3,
                      "area_minima": 3, "area_maxima": 5000, "circularidade_minima": None,
                      "inercia_minima": None, "convexidade_minima": None,
                      "classificacao": {"area_maxima_pequeno": pi * 16, "area_minima_aglomerado": pi * 144}}
        quadros = []
        por_chave = {(x["video_id"], x["quadro"]): x for x in origem_quadros}
        for chave in chaves:
            x = por_chave[chave]
            quadros.append({k: x[k] for k in ("video_id", "quadro", "imagem", "anotacao")})
            quadros[-1].update(imagem_sha256=x["sha256_imagem"], anotacao_sha256=x["sha256_anotacao"], objetivo="Inspeção sintética.")
        self.plano = {"versao": 1, "algoritmo": "blobs", "etapa": "inspecao", "rodada": "round0",
                      "particao": "desenvolvimento", "seed": 42,
                      "origem_desenvolvimento": {"plano": executor.ORIGEM_DESENVOLVIMENTO, "sha256": executor.sha256(origem_bytes)},
                      "quadros": quadros, "configuracoes": [{"id": "b01", "parametros": parametros},
                                                              {"id": "b02", "parametros": {**parametros, "polaridade": "escuro"}}],
                      "observacoes": ["Somente dados sintéticos."]}
        self.caminho_plano = self.raiz / "scripts/blobs/inspecao/round0.json"
        self.salvar_plano()

    def gravar(self, nome, conteudo):
        destino = self.raiz / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        return destino

    def salvar_plano(self):
        self.gravar(self.caminho_plano.relative_to(self.raiz), bytes_json(self.plano))

    def resultado(self):
        caixa = Caixa(30, 30, 20, 20)
        medidas = MedidasBlob(40.0, 40.0, 20.0, pi * 100, 400, False)
        return ResultadoDeteccao("blobs", 80, 80, (Deteccao(ClasseObjeto.NORMAL, caixa, medidas),), None)

    def executar_sintetico(self):
        with patch("algoritmos.classicos.blobs.detectar", return_value=self.resultado()) as detector:
            with patch.object(relatorio, "gerar_relatorio", side_effect=RuntimeError("PDF indisponível no teste")):
                pasta = executor.executar(self.caminho_plano)
        self.assertEqual(detector.call_count, 12)
        return pasta

    def test_plano_valido_congela_fontes_sem_criar_resultados(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        self.assertEqual(len(dados["entradas"]), 6)
        self.assertEqual(len(dados["hashes"]), 14)
        self.assertFalse(self.saida.exists())

    def test_bytes_congelados_independem_de_mudanca_posterior(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        self.gravar(self.plano["quadros"][0]["imagem"], b"alterada")
        self.assertEqual(dados["entradas"][0]["imagem_bytes"], self.imagem)

    def test_hash_divergente_rejeita_antes_de_saida(self):
        self.gravar(self.plano["quadros"][0]["anotacao"], b"0 0.5 0.5 0.2 0.2\n")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_hash_origem_divergente(self):
        self.plano["origem_desenvolvimento"]["sha256"] = "0" * 64
        self.salvar_plano()
        with self.assertRaisesRegex(ValueError, "plano de desenvolvimento"):
            executor.congelar_entradas(self.caminho_plano)

    def test_hash_do_quadro_deve_ser_o_mesmo_do_desenvolvimento(self):
        q = self.plano["quadros"][0]
        self.gravar(q["imagem"], b"novo conteudo")
        q["imagem_sha256"] = executor.sha256(b"novo conteudo")
        self.salvar_plano()
        with self.assertRaisesRegex(ValueError, "manifesto de desenvolvimento"):
            executor.congelar_entradas(self.caminho_plano)

    def test_rejeita_quadros_excluidos(self):
        q = self.plano["quadros"][4]
        for campo in ("imagem", "anotacao"):
            q[campo] = q[campo].replace("_frame_0.", "_frame_900.")
        q["quadro"] = 900
        self.salvar_plano()
        with self.assertRaisesRegex(ValueError, "178"):
            executor.congelar_entradas(self.caminho_plano)

    def test_rejeita_selecao_final_e_rodadas(self):
        for campo, valor in (("particao", "selecao"), ("particao", "final"), ("rodada", "round1")):
            with self.subTest(campo=campo, valor=valor):
                plano = deepcopy(self.plano); plano[campo] = valor
                with self.assertRaises(ValueError):
                    executor.carregar_plano(bytes_json(plano))

    def test_rejeita_tipo_booleano_e_chaves_desconhecidas(self):
        for campo, valor in (("seed", True), ("versao", True), ("desconhecido", 1)):
            plano = deepcopy(self.plano); plano[campo] = valor
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                executor.carregar_plano(bytes_json(plano))

    def test_rejeita_quadro_repetido(self):
        self.plano["quadros"][1] = deepcopy(self.plano["quadros"][0])
        with self.assertRaisesRegex(ValueError, "repetido"):
            executor.carregar_plano(bytes_json(self.plano))

    def test_rejeita_configuracoes_equivalentes(self):
        self.plano["configuracoes"][1]["parametros"] = deepcopy(self.plano["configuracoes"][0]["parametros"])
        self.plano["configuracoes"][1]["parametros"]["area_minima"] = 3.0
        with self.assertRaisesRegex(ValueError, "repetida"):
            executor.carregar_plano(bytes_json(self.plano))

    def test_rejeita_labels_ftid_e_caminho_incompativel(self):
        for nome in ("bases_de_dados/outro.txt", "../fora.txt", self.plano["quadros"][0]["anotacao"].replace("/labels/", "/labels_ftid/")):
            plano = deepcopy(self.plano); plano["quadros"][0]["anotacao"] = nome
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                executor.carregar_plano(bytes_json(plano))

    def test_rejeita_chave_json_repetida(self):
        with self.assertRaises(ValueError):
            executor.carregar_plano(b'{"versao":1,"versao":1}')

    def test_execucao_preserva_metricas_se_pdf_falha_e_exporta_estimativas(self):
        pasta = self.executar_sintetico()
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual(manifesto["situacao"], "concluida")
        self.assertEqual(manifesto["configuracoes_concluidas"], 2)
        self.assertEqual(executor.carregar_json((pasta / "relatorio.json").read_bytes())["situacao"], "falhou")
        self.assertEqual(len(linhas_csv(pasta / "resumo_por_quadro.csv")), 12)
        for item in manifesto["execucoes"]:
            config = self.raiz / item["pasta"]
            self.assertEqual(config.parent, pasta.parent)
            self.assertNotEqual(config, pasta)
            self.assertEqual(len(list(config.rglob("comparacao.png"))), 6)
            r = linhas_csv(next(config.rglob("deteccoes.csv")))[0]
            self.assertEqual(r["centroide_x_px"], "")
            self.assertEqual(r["area_pixels"], "")
            self.assertEqual(r["intensidade_media"], "")
            self.assertAlmostEqual(float(r["area_estimada_blob_px2"]), pi * 100)
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(executor.sha256((self.raiz / nome).read_bytes()), digest)
        dados = relatorio.carregar(pasta)
        self.assertEqual(dados["ids"], ["b01", "b02"])
        self.assertEqual(float(dados["resumos"]["b01"]["f1_individuos"]), 1.0)

    def test_falha_detector_registrada_sem_sobrescrever_origens(self):
        antes = self.caminho_plano.read_bytes()
        with patch("algoritmos.classicos.blobs.detectar", side_effect=RuntimeError("falha sintética")):
            with self.assertRaisesRegex(RuntimeError, "falha sintética"):
                executor.executar(self.caminho_plano)
        pasta = next(self.saida.glob("inspecao__*"))
        self.assertEqual(executor.carregar_json((pasta / "execucao.json").read_bytes())["situacao"], "falhou")
        self.assertEqual(self.caminho_plano.read_bytes(), antes)
        self.assertFalse((pasta / "resumo_configuracoes.csv").exists())

    def test_relatorio_rejeita_tabela_alterada(self):
        pasta = self.executar_sintetico()
        p = pasta / "resumo_configuracoes.csv"
        p.write_bytes(p.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            relatorio.carregar(pasta)

    def test_relatorio_rejeita_versao_booleana_ou_incompativel_no_manifesto(self):
        pasta = self.executar_sintetico()
        caminho = pasta / "execucao.json"
        original = executor.carregar_json(caminho.read_bytes())
        for versao in (True, 2):
            with self.subTest(versao=versao):
                manifesto = deepcopy(original)
                manifesto["versao"] = versao
                executor.gravar_json(caminho, manifesto)
                with self.assertRaisesRegex(ValueError, "Manifesto"):
                    relatorio.carregar(pasta)

    def test_relatorio_rejeita_versao_do_plano_mesmo_com_hash_atualizado(self):
        pasta = self.executar_sintetico()
        caminho_plano, caminho_manifesto = pasta / "plano.json", pasta / "execucao.json"
        plano_original = executor.carregar_json(caminho_plano.read_bytes())
        manifesto_original = executor.carregar_json(caminho_manifesto.read_bytes())
        for versao in (True, 2):
            with self.subTest(versao=versao):
                plano, manifesto = deepcopy(plano_original), deepcopy(manifesto_original)
                plano["versao"] = versao
                conteudo = bytes_json(plano)
                caminho_plano.write_bytes(conteudo)
                digest = executor.sha256(conteudo)
                manifesto["plano_sha256"] = digest
                manifesto["saidas_sha256"][caminho_plano.relative_to(self.raiz).as_posix()] = digest
                executor.gravar_json(caminho_manifesto, manifesto)
                with self.assertRaisesRegex(ValueError, "Versão do plano"):
                    relatorio.carregar(pasta)

    def test_relatorio_rejeita_agregado_inconsistente_mesmo_com_hash_atualizado(self):
        pasta = self.executar_sintetico()
        p = pasta / "resumo_configuracoes.csv"
        linhas = linhas_csv(p)
        linhas[0]["tp_individuos"] = "100"
        executor.gravar_csv(p, list(linhas[0]), linhas)
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        manifesto["saidas_sha256"][p.relative_to(self.raiz).as_posix()] = executor.sha256(p.read_bytes())
        executor.gravar_json(pasta / "execucao.json", manifesto)
        with self.assertRaises(ValueError):
            relatorio.carregar(pasta)

    def test_regeneracao_relatorio_nao_altera_manifestos_anteriores(self):
        pasta = self.executar_sintetico()
        antes = {nome: (pasta / nome).read_bytes() for nome in ("execucao.json", "relatorio.json", "plano.json")}
        def gravar_pdf(destino, dados):
            destino.write_bytes(b"%PDF-TESTE\n")
            return 2
        with patch.object(relatorio, "escrever_pdf", side_effect=gravar_pdf):
            pdf = relatorio.gerar_relatorio(pasta)
        self.assertTrue(pdf.is_file())
        for nome, conteudo in antes.items():
            self.assertEqual((pasta / nome).read_bytes(), conteudo)
        novo = executor.carregar_json((pdf.parent / "relatorio.json").read_bytes())
        self.assertEqual(novo["situacao"], "concluida")
        self.assertEqual(novo["pdf_sha256"], executor.sha256(pdf.read_bytes()))

    def test_pdf_sintetico_completo(self):
        pasta = self.executar_sintetico()
        antes = (pasta / "execucao.json").read_bytes()
        pdf = relatorio.gerar_relatorio(pasta)
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
        self.assertGreater(pdf.stat().st_size, 1000)
        registro = executor.carregar_json((pdf.parent / "relatorio.json").read_bytes())
        self.assertEqual(registro["paginas"], 2)
        self.assertEqual(registro["situacao"], "concluida")
        self.assertEqual((pasta / "execucao.json").read_bytes(), antes)


if __name__ == "__main__":
    unittest.main()
