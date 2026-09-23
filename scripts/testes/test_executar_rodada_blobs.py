"""Integração de rodadas em arquivos temporários e imagens sintéticas."""

from contextlib import redirect_stdout
from copy import deepcopy
import csv
from io import StringIO
import json
from math import pi
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from algoritmos.classicos.blobs import configuracao_de_dict, detectar
from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
from algoritmos.classicos.comum import Caixa, ClasseObjeto, Deteccao, MedidasBlob, ResultadoDeteccao
from scripts.blobs import executar_rodada as executor
from scripts.blobs.planejamento import gerar_round1

PROJETO = Path(__file__).resolve().parents[2]


def bytes_json(dados):
    return (json.dumps(dados, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def linhas_csv(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


class RodadaBlobsTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.saida = self.raiz / "resultados/frame-to-frame/blobs"
        for campo, valor in (("RAIZ", self.raiz), ("SAIDA", self.saida)):
            p = patch.object(executor, campo, valor); p.start(); self.addCleanup(p.stop)
        fonte = "scripts/blobs/executar_rodada.py"
        self.gravar(fonte, b"# fonte sintetica\n")
        p = patch.object(executor, "FONTES_CODIGO", (fonte,)); p.start(); self.addCleanup(p.stop)
        desenvolvimento = json.loads((PROJETO / "scripts/limiarizacao/rodadas/round1.json").read_text(encoding="utf-8-sig"))
        inspecao = json.loads((PROJETO / "scripts/blobs/inspecao/round0.json").read_text(encoding="utf-8-sig"))
        imagem = np.zeros((80, 80, 3), dtype=np.uint8)
        cv2.circle(imagem, (40, 40), 10, (255, 255, 255), -1)
        ok, encoded = cv2.imencode(".jpg", imagem)
        self.assertTrue(ok)
        self.imagem = encoded.tobytes()
        self.anotacao = b"0 0.5 0.5 0.25 0.25\n"
        for q in desenvolvimento["quadros"]:
            q["sha256_imagem"] = executor.sha256(self.imagem)
            q["sha256_anotacao"] = executor.sha256(self.anotacao)
            self.gravar(q["imagem"], self.imagem)
            self.gravar(q["anotacao"], self.anotacao)
        desenvolvimento_bytes = bytes_json(desenvolvimento)
        inspecao["origem_desenvolvimento"]["sha256"] = executor.sha256(desenvolvimento_bytes)
        for q in inspecao["quadros"]:
            q["imagem_sha256"] = executor.sha256(self.imagem)
            q["anotacao_sha256"] = executor.sha256(self.anotacao)
        inspecao_bytes = bytes_json(inspecao)
        self.gravar("scripts/limiarizacao/rodadas/round1.json", desenvolvimento_bytes)
        self.gravar("scripts/blobs/inspecao/round0.json", inspecao_bytes)
        self.plano = gerar_round1(desenvolvimento_bytes, inspecao_bytes)
        self.caminho_plano = self.gravar("scripts/blobs/rodadas/round1.json", bytes_json(self.plano))

    def gravar(self, nome, conteudo):
        p = self.raiz / nome
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(conteudo)
        return p

    def resultado(self):
        caixa = Caixa(30, 30, 20, 20)
        medidas = MedidasBlob(40., 40., 20., pi * 100, 400, False)
        return ResultadoDeteccao("blobs", 80, 80, (Deteccao(ClasseObjeto.NORMAL, caixa, medidas),), None)

    def dados_reduzidos(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        dados["plano"] = deepcopy(dados["plano"])
        dados["plano"]["configuracoes"] = dados["plano"]["configuracoes"][:2]
        dados["plano"]["quadros"] = dados["plano"]["quadros"][:3]
        dados["entradas"] = dados["entradas"][:3]
        dados["plano_bytes"] = bytes_json(dados["plano"])
        return dados

    def executar_sintetico(self, efeito=None):
        dados = self.dados_reduzidos()
        with patch.object(executor, "congelar_entradas", return_value=dados), \
             patch("algoritmos.classicos.blobs.detectar", **(
                 {"side_effect": efeito} if efeito else {"return_value": self.resultado()})) as detector, \
             patch("analise.relatorio_rodada_blobs.gerar_relatorio", side_effect=RuntimeError("PDF sintético indisponível")), \
             redirect_stdout(StringIO()):
            pasta = executor.executar(self.caminho_plano)
        self.assertEqual(detector.call_count, 6)
        return pasta

    def test_preflight_confere_178_imagens_sem_detector_ou_resultados(self):
        with patch("algoritmos.classicos.blobs.detectar", side_effect=AssertionError("Não deveria detectar")):
            dados = executor.congelar_entradas(self.caminho_plano)
            executor.conferir_ambiente_e_imagens(dados)
        self.assertEqual(len(dados["entradas"]), 178)
        self.assertEqual(len(dados["plano"]["configuracoes"]), 48)
        self.assertEqual(len(dados["hashes"]), 359)
        self.assertFalse(self.saida.exists())

    def test_fonte_congelada_e_anotacoes_nao_sao_mutadas_ao_decodificar(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        entrada = dados["entradas"][0]
        antes = deepcopy(entrada)
        self.gravar(entrada["quadro"]["imagem"], b"alterada posteriormente")
        preparada = executor.decodificar_entrada(entrada, cv2, np)
        self.assertEqual(entrada, antes)
        self.assertEqual(preparada["imagem"].shape, (80, 80, 3))
        self.assertNotIn("caixa_x_px", entrada["anotacoes"][0])

    def test_hash_divergente_falha_antes_de_criar_resultados(self):
        self.gravar(self.plano["quadros"][0]["imagem"], b"divergente")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_entrada_prevista_ausente_nao_e_excluida(self):
        (self.raiz / self.plano["quadros"][0]["anotacao"]).unlink()
        with self.assertRaises(FileNotFoundError):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_jpeg_invalido_mesmo_com_hash_consistente_falha_no_preflight(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        dados["entradas"][0]["imagem_bytes"] = b"nao e jpeg"
        with self.assertRaisesRegex(ValueError, "Imagem inválida"):
            executor.conferir_ambiente_e_imagens(dados)
        self.assertFalse(self.saida.exists())

    def test_integracao_salva_caixas_originais_e_metricas_mesmo_sem_pdf(self):
        pasta = self.executar_sintetico()
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual(manifesto["situacao"], "concluida")
        self.assertEqual(manifesto["avaliacoes_concluidas"], 6)
        self.assertEqual(manifesto["configuracoes_concluidas"], 2)
        self.assertEqual(executor.carregar_json((pasta / "relatorio.json").read_bytes())["situacao"], "falhou")
        linhas = linhas_csv(pasta / "resumo_por_quadro.csv")
        self.assertEqual(len(linhas), 6)
        self.assertEqual((pasta / "resumo_por_quadro.csv").read_bytes().count(b"\xef\xbb\xbf"), 1)
        resumo = linhas_csv(pasta / "resumo_configuracoes.csv")
        self.assertEqual(resumo[0]["tp_individuos"], "3")
        self.assertEqual(resumo[1]["tp_individuos"], "0")
        self.assertEqual(resumo[1]["fp_individuos"], "3")
        for item in manifesto["execucoes"]:
            config = self.raiz / item["pasta"]
            self.assertEqual(len(list(config.rglob("comparacao.png"))), 3)
            r = linhas_csv(next(config.rglob("deteccoes.csv")))[0]
            self.assertEqual(r["original_caixa_largura_px"], "20")
            self.assertEqual(r["centro_blob_x_px"], "40.0")
            self.assertEqual(r["classe"], "0")
            self.assertEqual(r["area_pixels"], "")
            self.assertAlmostEqual(float(r["area_estimada_blob_px2"]), pi * 100)
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(executor.hash_arquivo(self.raiz / nome), digest)

    def test_repetir_cria_nova_pasta_e_preserva_a_anterior(self):
        primeira = self.executar_sintetico()
        antes = {p.relative_to(primeira): p.read_bytes() for p in primeira.rglob("*") if p.is_file()}
        segunda = self.executar_sintetico()
        self.assertNotEqual(primeira, segunda)
        for nome, conteudo in antes.items():
            self.assertEqual((primeira / nome).read_bytes(), conteudo)

    def test_bloqueio_temporario_no_manifesto_nao_repete_deteccoes_ou_linhas(self):
        substituir = Path.replace
        bloqueios = 0

        def troca(origem, destino):
            nonlocal bloqueios
            if (Path(destino).name == "execucao.json" and bloqueios < 2
                    and executor.carregar_json(origem.read_bytes()).get("quadros_concluidos") == 1):
                bloqueios += 1
                erro = PermissionError("Bloqueio simulado do Windows")
                erro.winerror = 5
                raise erro
            return substituir(origem, destino)

        with patch.object(Path, "replace", troca), patch("scripts.blobs.arquivos.sleep") as espera:
            pasta = self.executar_sintetico()
        self.assertEqual(bloqueios, 2)
        self.assertEqual(espera.call_count, 2)
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual(manifesto["situacao"], "concluida")
        linhas = linhas_csv(pasta / "resumo_por_quadro.csv")
        self.assertEqual(len(linhas), 6)
        self.assertEqual(len({(r["configuracao_id"], r["video_id"], r["quadro"]) for r in linhas}), 6)

    def test_regeneracao_pdf_atualiza_apontador_sem_alterar_metricas(self):
        pasta = self.executar_sintetico()
        antes = {nome: (pasta / nome).read_bytes() for nome in (
            "execucao.json", "plano.json", "resumo_configuracoes.csv")}
        pdf = pasta / "relatorios/sintetico/relatorio.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-sintetico\n")
        with patch("analise.relatorio_rodada_blobs.gerar_relatorio", return_value=pdf), redirect_stdout(StringIO()):
            self.assertEqual(executor.main(["--somente-relatorio", str(pasta)]), 0)
        registro = executor.carregar_json((pasta / "relatorio.json").read_bytes())
        self.assertEqual(registro["situacao"], "concluido")
        self.assertEqual(registro["arquivo"], executor.relativo(pdf))
        for nome, conteudo in antes.items():
            self.assertEqual((pasta / nome).read_bytes(), conteudo)

    def test_falha_preserva_quadros_concluidos_e_identifica_quadro_pendente(self):
        dados = self.dados_reduzidos()
        with patch.object(executor, "congelar_entradas", return_value=dados), \
             patch("algoritmos.classicos.blobs.detectar", side_effect=[self.resultado(), RuntimeError("interrompido")]), \
             redirect_stdout(StringIO()):
            with self.assertRaisesRegex(RuntimeError, "interrompido"):
                executor.executar(self.caminho_plano)
        pasta = next((self.saida / "round1").glob("batch__*"))
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual(manifesto["situacao"], "falhou")
        self.assertEqual(manifesto["avaliacoes_concluidas"], 1)
        self.assertEqual(len(linhas_csv(pasta / "resumo_por_quadro.csv")), 1)
        config = next(p for p in pasta.parent.iterdir() if p != pasta)
        atual = executor.carregar_json((config / "execucao.json").read_bytes())
        self.assertEqual(atual["quadros_concluidos"], 1)
        self.assertEqual(atual["quadro_em_andamento"]["quadro"], 100)
        self.assertEqual(len(list(config.rglob("comparacao.png"))), 1)

    def test_detector_real_em_imagem_sintetica_passa_por_exportacao_e_avaliacao(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        item = self.plano["configuracoes"][0]
        linha, avaliacao = executor.executar_quadro(
            dados["entradas"][0], configuracao_de_dict(item["parametros"]),
            configuracao_caixa_de_dict(item["caixa"]), item, self.raiz / "teste_integracao", cv2, np, detectar)
        self.assertEqual(linha["quantidade_deteccoes"], 1)
        self.assertEqual(avaliacao["por_grupo"]["individuos"]["tp"], 1)
        self.assertEqual(linha["tempo_pipeline_ns"], linha["tempo_detector_ns"] + linha["tempo_adaptacao_ns"])

    def test_quadro_sintetico_vazio_produz_cabecalhos_e_sem_casos(self):
        dados = executor.congelar_entradas(self.caminho_plano)
        entrada = deepcopy(dados["entradas"][0])
        entrada["anotacoes"] = []
        item = self.plano["configuracoes"][0]
        vazio = ResultadoDeteccao("blobs", 80, 80, (), None)
        destino = self.raiz / "teste_vazio"
        linha, _ = executor.executar_quadro(entrada, configuracao_de_dict(item["parametros"]),
            configuracao_caixa_de_dict(item["caixa"]), item, destino, cv2, np, lambda *_: vazio)
        self.assertIsNone(linha["f1_individuos"])
        self.assertEqual(linhas_csv(destino / "deteccoes.csv"), [])
        self.assertEqual((destino / "predicoes.txt").read_bytes(), b"")

    def test_ranking_preserva_empates_e_sem_casos(self):
        dados = [{"configuracao_id": i, "f1_individuos": f,
                  "tp_individuos": tp, "fp_individuos": fp, "fn_individuos": fn}
                 for i, f, tp, fp, fn in (("z", 0.5, 1, 2, 0), ("x", None, 0, 0, 0),
                                          ("y", 0.5, 2, 4, 0), ("w", 0.0, 0, 1, 0))]
        resultado = executor.ordenar_por_f1(dados)
        self.assertEqual([r["posicao"] for r in resultado], [1, 1, 3, None])
        self.assertEqual([r["configuracao_id"] for r in resultado], ["y", "z", "w", "x"])

    def test_cli_conferir_nao_chama_executar(self):
        with patch.object(executor, "executar", side_effect=AssertionError("Não executar")), redirect_stdout(StringIO()):
            self.assertEqual(executor.main(["--rodada", "round1", "--conferir"]), 0)
        self.assertFalse(self.saida.exists())

    def test_cli_round2_nao_preparado_falha_sem_saida(self):
        self.assertEqual(executor.main(["--rodada", "round2"]), 1)
        self.assertFalse(self.saida.exists())


if __name__ == "__main__":
    unittest.main()
