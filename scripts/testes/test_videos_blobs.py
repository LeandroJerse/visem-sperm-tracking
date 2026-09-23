"""Integração de vídeos de blobs com MP4s e anotações exclusivamente sintéticos."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

import cv2
import numpy as np

from analise.avaliacao_individuos import CRITERIOS
from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
from algoritmos.classicos.comum import Caixa, ClasseObjeto, Deteccao, MedidasBlob, ResultadoDeteccao
from scripts.blobs import executar_rodada as rodada
from scripts.blobs import executar_videos as script
from scripts.blobs.planejamento import hash_configuracao
from scripts.limiarizacao import executar_videos as video_base


PROJETO = Path(__file__).resolve().parents[2]
IDS = ("s052", "s082", "s084", "s103", "s051")


def ler_csv(caminho):
    with Path(caminho).open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def ler_json(caminho):
    return json.loads(Path(caminho).read_bytes())


def bytes_json(valor):
    return (json.dumps(valor, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


class VideosBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name)
        self.saida = self.raiz / "resultados/videos/blobs/selecao"
        self.saida_final = self.raiz / "resultados/videos/blobs/final"
        self.contextos = ExitStack()
        self.addCleanup(self.contextos.close)
        for modulo, campo, valor in (
            (script, "RAIZ", self.raiz), (script, "SAIDA", self.saida),
            (script, "SAIDA_FINAL", self.saida_final),
            (rodada, "RAIZ", self.raiz), (video_base, "RAIZ", self.raiz),
        ):
            self.contextos.enter_context(patch.object(modulo, campo, valor))
        catalogo = ler_json(PROJETO / "scripts/blobs/selecao/plano.json")
        itens = {c["id"]: c for c in catalogo["configuracoes"]}
        self.imagens = []
        for valor in (30, 100, 170):
            imagem = np.full((80, 480, 3), valor, dtype=np.uint8)
            cv2.circle(imagem, (240, 40), 4, (255, 255, 255), -1)
            self.imagens.append(imagem)
        self.hashes, self.anotacoes, self.decodificadas = {}, {}, {}
        videos = [self.criar_video(video_id) for video_id in ("13", "29")]
        plano = {
            "versao": 1, "tipo": "videos_selecao_blobs", "algoritmo": "blobs",
            "etapa": "selecao_videos", "particao": "selecao", "seed": 42,
            "criterios": deepcopy(CRITERIOS), "criterios_avaliacao": deepcopy(CRITERIOS),
            "politica_anotacoes_ausentes": "erro",
            "proveniencia": {"fontes": {"origem_selecao": {"arquivo": "fontes/origem_selecao.json"}}},
            "configuracoes": [deepcopy(itens[identificador]) for identificador in IDS],
            "videos": videos,
        }
        self.caminho = self.gravar("scripts/blobs/videos/plano_selecao.json", bytes_json(plano))
        fontes = {
            "scripts/blobs/executar_videos.py": b"# executor sintetico\n",
            "algoritmos/classicos/variantes_blobs.py": b"# variantes sinteticas\n",
        }
        for nome, conteudo in fontes.items():
            self.gravar(nome, conteudo)
        self.dados = {
            "plano": plano, "plano_bytes": self.caminho.read_bytes(),
            "hashes": self.hashes, "anotacoes": self.anotacoes, "codigo": fontes,
            "origens": {"origem_selecao": bytes_json({"origem": "sintetica"})},
        }

    def gravar(self, nome, conteudo):
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        self.hashes[nome] = hashlib.sha256(conteudo).hexdigest()
        return caminho

    def criar_video(self, video_id, imagens=None):
        imagens = self.imagens if imagens is None else imagens
        base = f"bases_de_dados/visem_tracking/dataset/Train/{video_id}"
        arquivo = f"{base}/{video_id}.mp4"
        caminho = self.raiz / arquivo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        escritor = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), 10, (480, 80))
        try:
            self.assertTrue(escritor.isOpened(), "Codec mp4v indisponível para a fixture sintética.")
            for imagem in imagens:
                escritor.write(imagem)
        finally:
            escritor.release()
        self.hashes[arquivo] = rodada.hash_arquivo(caminho)
        captura = cv2.VideoCapture(str(caminho))
        decodificadas = []
        try:
            self.assertTrue(captura.isOpened())
            while True:
                sucesso, imagem = captura.read()
                if not sucesso:
                    break
                decodificadas.append(imagem)
        finally:
            captura.release()
        self.assertEqual(len(decodificadas), len(imagens))
        referencias, anotacoes = [], []
        for quadro, imagem in enumerate(decodificadas):
            self.decodificadas[(video_id, quadro)] = imagem
            nome_jpeg = f"{base}/images/{video_id}_frame_{quadro}.jpg"
            sucesso, jpeg = cv2.imencode(".jpg", imagem)
            self.assertTrue(sucesso)
            self.gravar(nome_jpeg, jpeg.tobytes())
            referencias.append({"quadro": quadro, "imagem": nome_jpeg, "sha256": self.hashes[nome_jpeg]})
            texto = (b"0 0.5 0.5 0.041666666666666664 0.25\n1 0.1 0.1 0.02 0.1\n" if quadro == 0
                     else b"2 0.5 0.5 0.041666666666666664 0.25\n" if quadro == 1 else b"")
            nome_gt = f"{base}/labels/{video_id}_frame_{quadro}.txt"
            self.gravar(nome_gt, texto)
            self.anotacoes[(video_id, quadro)] = rodada.ler_anotacoes(texto)
            anotacoes.append({"quadro": quadro, "arquivo": nome_gt, "sha256": self.hashes[nome_gt]})
        return {
            "video_id": video_id, "arquivo": arquivo, "sha256": self.hashes[arquivo],
            "fps": 10, "largura": 480, "altura": 80, "quantidade_quadros": len(imagens),
            "indice_inicial": 0, "anotacoes": anotacoes, "referencias_alinhamento": referencias,
        }

    @staticmethod
    def resultado_sbd():
        caixa = Caixa(236, 36, 8, 8)
        medidas = MedidasBlob(240., 40., 8., 16 * math.pi, 64, False)
        return ResultadoDeteccao("blobs", 480, 80, (Deteccao(ClasseObjeto.NORMAL, caixa, medidas),), None)

    def pdf_sintetico(self, pasta):
        self.assertEqual(ler_json(pasta / "execucao.json")["situacao"], "concluida")
        caminho = pasta / "relatorios" / "sintetico" / "relatorio.pdf"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"%PDF-sintetico\n")
        return caminho

    def executar_sintetico(self, *, falha_pdf=False, etapa="selecao"):
        recebidas = []
        processar = script.processar_quadro

        def acompanhar(imagem, item, *args, **kwargs):
            recebidas.append((item["id"], hashlib.sha256(imagem.tobytes()).hexdigest()))
            return processar(imagem, item, *args, **kwargs)

        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(script, "processar_quadro", side_effect=acompanhar), \
                patch("algoritmos.classicos.blobs.detectar", return_value=self.resultado_sbd()) as sbd, \
                patch("skimage.feature.blob_dog", return_value=np.array([[40., 240., 2.]])) as dog, \
                patch.object(script, "atualizar_relatorio", side_effect=RuntimeError("PDF sintético indisponível")
                             if falha_pdf else self.pdf_sintetico) as relatorio, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            pasta = script.executar(self.caminho, etapa=etapa)
        self.assertEqual((sbd.call_count, dog.call_count), (24, 6))
        relatorio.assert_called_once_with(pasta)
        esperados = [hashlib.sha256(self.decodificadas[(v, q)].tobytes()).hexdigest()
                     for v in (v["video_id"] for v in self.dados["plano"]["videos"]) for q in range(3)]
        for identificador in IDS:
            self.assertEqual([digest for item, digest in recebidas if item == identificador], esperados)
        return pasta

    def test_execucao_cinco_configuracoes_com_mp4_reais_sinteticos_preserva_saidas(self):
        antes = deepcopy(self.dados)
        pasta = self.executar_sintetico()
        self.assertEqual(self.dados, antes)
        self.assertEqual(pasta.parent, self.saida)
        manifesto = ler_json(pasta / "execucao.json")
        self.assertEqual(manifesto["situacao"], "concluida")
        self.assertEqual(manifesto["particao"], "selecao")
        self.assertEqual(manifesto["pasta_origens"], "origens")
        self.assertTrue(manifesto["alinhamento_conferido"])
        self.assertEqual(manifesto["configuracoes_concluidas"], 5)
        self.assertEqual(manifesto["quadros_por_configuracao"], 6)
        self.assertEqual(manifesto["videos_por_configuracao"], 2)
        self.assertEqual((pasta / "plano.json").read_bytes(), antes["plano_bytes"])
        self.assertEqual(len(list(pasta.rglob("*.mp4"))), 10)
        self.assertFalse(list(pasta.rglob("predicoes.txt")))
        with ZipFile(pasta / "codigo.zip") as arquivo:
            self.assertEqual(set(arquivo.namelist()), set(antes["codigo"]))
            for nome, conteudo in antes["codigo"].items():
                self.assertEqual(arquivo.read(nome), conteudo)
        for nome, conteudo in antes["origens"].items():
            self.assertEqual((pasta / "origens" / f"{nome}.json").read_bytes(), conteudo)
            self.assertFalse((pasta / f"{nome}.json").exists())
        for item, execucao in zip(antes["plano"]["configuracoes"], manifesto["execucoes"]):
            pasta_config = self.raiz / execucao["pasta"]
            self.assertEqual(ler_json(pasta_config / "configuracao.json"), item)
            backend = ler_json(pasta_config / "configuracao_backend.json")
            self.assertEqual(backend, manifesto["parametros_backend"][item["id"]])
            self.assertEqual(backend["classificacao"], item["parametros"]["classificacao"])
            registro = ler_json(pasta_config / "execucao.json")
            self.assertEqual(registro["situacao"], "concluida")
            self.assertEqual(registro["quadros_concluidos"], 6)
            self.assertEqual(registro["configuracao_sha256"], hash_configuracao(item))
            self.assertEqual(len(registro["videos"]), 2)
            for video in registro["videos"]:
                self.assertEqual(video["quantidade_quadros"], 3)
                self.assertTrue(video["decodificacao_conferida"])
                self.assertEqual((video["largura"], video["altura"]), (960, 184))
            deteccoes = ler_csv(pasta_config / "deteccoes.csv")
            self.assertEqual(len(deteccoes), 6)
            for d in deteccoes:
                self.assertEqual(float(d["tempo_segundos"]), int(d["quadro"]) / 10)
                self.assertEqual(d["metodo_detector"], item["metodo"])
                self.assertEqual(d["preprocessamento"], "nenhum")
                self.assertEqual(d["area_pixels"], "")
                self.assertEqual(d["classe"], "2" if item["metodo"] == "dog" else "0")
                self.assertGreater(int(d["caixa_largura_px"]), int(d["original_caixa_largura_px"]))
                self.assertAlmostEqual(float(d["caixa_centro_x_norm"]), .5)
                self.assertEqual(d["sigma_blob_px"], "2.0" if item["metodo"] == "dog" else "")
            pares = ler_csv(pasta_config / "pares.csv")
            self.assertEqual(len(pares), 4)
            self.assertEqual(sum(p["classe_correta"] == "False" for p in pares), 2)
            self.assertEqual({p["grupo"] for p in pares}, {"individuos"})
            self.assertEqual({a["classe"] for a in ler_csv(pasta_config / "anotacoes.csv")}, {"0", "1", "2"})
            quadros = ler_csv(pasta_config / "por_quadro.csv")
            self.assertEqual(len(quadros), 6)
            for quadro in quadros:
                self.assertEqual(int(quadro["tempo_pipeline_ns"]), sum(int(quadro[f"tempo_{nome}_ns"])
                                 for nome in ("preprocessamento", "detector", "adaptacao")))
                self.assertEqual(quadro["tempo_preprocessamento_ns"], "0")
            self.assertEqual(len(ler_csv(pasta_config / "pendentes.csv")), 4)
        for resumo in ler_csv(pasta / "resumo_configuracoes.csv"):
            self.assertEqual((resumo["tp_individuos"], resumo["fp_individuos"], resumo["fn_individuos"]), ("4", "2", "0"))
            self.assertEqual((resumo["tp_aglomerados"], resumo["fn_aglomerados"]), ("0", "2"))
        self.assertEqual(len(ler_csv(pasta / "resumo_por_video.csv")), 10)
        self.assertEqual(len(ler_csv(pasta / "ranking.csv")), 5)
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(rodada.hash_arquivo(self.raiz / nome), digest)

    def test_conferir_le_metadados_sem_decodificar_detectar_ou_criar_resultados(self):
        capturas = []

        def captura_metadados(video, cv):
            valores = {cv.CAP_PROP_FRAME_WIDTH: 480, cv.CAP_PROP_FRAME_HEIGHT: 80,
                       cv.CAP_PROP_FRAME_COUNT: 3}
            captura = SimpleNamespace(get=valores.__getitem__, release=Mock(),
                                      read=Mock(side_effect=AssertionError("Decodificação indevida")))
            capturas.append(captura)
            return captura

        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(script, "executar", side_effect=AssertionError("Execução indevida")), \
                patch.object(video_base, "abrir_video", side_effect=captura_metadados), \
                patch.object(script, "processar_quadro", side_effect=AssertionError("Detecção indevida")), \
                redirect_stdout(StringIO()) as saida:
            self.assertEqual(script.main(["--conferir"]), 0)
        self.assertFalse(self.saida.exists())
        self.assertIn("5", saida.getvalue())
        self.assertEqual(len(capturas), 2)
        for captura in capturas:
            captura.read.assert_not_called()
            captura.release.assert_called_once()

    def simular_planejador(self):
        contexto = ExitStack()
        contexto.enter_context(patch.object(script, "carregar_plano", return_value=self.dados["plano"]))
        contexto.enter_context(patch.object(script, "conferir_origens", return_value=self.dados["origens"]))
        contexto.enter_context(patch.object(script, "caminhos_origens", return_value={
            "origem_selecao": "fontes/origem_selecao.json"}))
        contexto.enter_context(patch.object(script, "FONTES_CODIGO", tuple(self.dados["codigo"])))
        return contexto

    def preparar_final_sintetico(self):
        """Troca somente a partição dos clips; preserva integralmente os cinco itens."""
        self.dados["plano"].update(tipo="videos_final_blobs", etapa="final_videos", particao="final")
        self.dados["plano"]["videos"] = [self.criar_video(v) for v in ("14", "24")]
        self.caminho = self.gravar("scripts/blobs/videos/plano_final.json", bytes_json(self.dados["plano"]))
        self.dados["plano_bytes"] = self.caminho.read_bytes()

    def test_final_grava_mp4_metricas_e_proveniencia_sem_alterar_selecao(self):
        itens = deepcopy(self.dados["plano"]["configuracoes"])
        preservado = self.saida / "batch__anterior" / "ranking.csv"
        preservado.parent.mkdir(parents=True)
        preservado.write_bytes(b"resultado anterior preservado\n")
        self.preparar_final_sintetico()
        antes = {nome: (self.raiz / nome).read_bytes() for nome in self.hashes}
        pasta = self.executar_sintetico(etapa="final")
        self.assertEqual(pasta.parent, self.saida_final)
        self.assertEqual(preservado.read_bytes(), b"resultado anterior preservado\n")
        self.assertEqual(list(self.saida.iterdir()), [preservado.parent])
        for nome, conteudo in antes.items():
            self.assertEqual((self.raiz / nome).read_bytes(), conteudo)
        registro = ler_json(pasta / "execucao.json")
        self.assertEqual((registro["tipo"], registro["etapa"], registro["particao"]),
                         ("videos_final_blobs", "final_videos", "final"))
        self.assertEqual(registro["situacao"], "concluida")
        self.assertEqual(registro["videos_concluidos"], 10)
        self.assertEqual(registro["avaliacoes_concluidas"], 30)
        self.assertTrue(registro["alinhamento_conferido"])
        self.assertEqual(ler_json(pasta / "plano.json")["configuracoes"], itens)
        self.assertEqual({r["video_id"] for r in ler_csv(pasta / "resumo_por_video.csv")}, {"14", "24"})
        self.assertEqual({r["configuracao_id"] for r in ler_csv(pasta / "ranking.csv")}, set(IDS))
        self.assertEqual(len(list(pasta.rglob("*.mp4"))), 10)
        for execucao in registro["execucoes"]:
            pasta_config = self.raiz / execucao["pasta"]
            self.assertTrue(pasta_config.is_relative_to(pasta))
            interno = ler_json(pasta_config / "execucao.json")
            self.assertEqual(interno["tipo"], "videos_final_blobs")
            self.assertEqual(interno["particao"], "final")
            self.assertEqual({v["video_id"] for v in interno["videos"]}, {"14", "24"})
            self.assertTrue(all(v["decodificacao_conferida"] for v in interno["videos"]))
            for linha in ler_csv(pasta_config / "por_quadro.csv"):
                self.assertIn(linha["video_id"], {"14", "24"})
        self.assertFalse((pasta / "origem_selecao.json").exists())
        self.assertTrue((pasta / "origens/origem_selecao.json").is_file())
        for nome, digest in registro["saidas_sha256"].items():
            self.assertEqual(rodada.hash_arquivo(self.raiz / nome), digest)

    def test_cli_escolhe_plano_da_etapa_e_preserva_caminho_explicito(self):
        casos = (
            ([], "selecao", self.raiz / script.PLANO_PADRAO),
            (["--etapa", "selecao"], "selecao", self.raiz / script.PLANO_PADRAO),
            (["--etapa", "final"], "final", self.raiz / script.PLANO_FINAL),
            (["--etapa", "final", "--plano", str(self.caminho)], "final", self.caminho),
        )
        for argumentos, etapa, plano in casos:
            with self.subTest(argumentos=argumentos), \
                    patch.object(script, "executar", return_value=self.raiz / "batch__sintetico") as executar, \
                    redirect_stdout(StringIO()):
                self.assertEqual(script.main(argumentos), 0)
            executar.assert_called_once_with(plano, etapa)

    def test_final_conferir_nao_decodifica_detecta_ou_cria_resultados(self):
        self.preparar_final_sintetico()
        capturas = []

        def captura_metadados(video, cv):
            valores = {cv.CAP_PROP_FRAME_WIDTH: 480, cv.CAP_PROP_FRAME_HEIGHT: 80,
                       cv.CAP_PROP_FRAME_COUNT: 3}
            captura = SimpleNamespace(get=valores.__getitem__, release=Mock(),
                                      read=Mock(side_effect=AssertionError("Decodificação indevida")))
            capturas.append(captura)
            return captura

        with patch.object(script, "congelar_entradas", return_value=self.dados) as congelar, \
                patch.object(script, "executar", side_effect=AssertionError("Execução indevida")), \
                patch.object(video_base, "abrir_video", side_effect=captura_metadados), \
                patch.object(script, "processar_quadro", side_effect=AssertionError("Detecção indevida")), \
                redirect_stdout(StringIO()):
            self.assertEqual(script.main(["--etapa", "final", "--conferir"]), 0)
        congelar.assert_called_once_with(self.raiz / script.PLANO_FINAL, "final")
        self.assertEqual(len(capturas), 2)
        self.assertFalse(self.saida.exists())
        self.assertFalse(self.saida_final.exists())
        for captura in capturas:
            captura.read.assert_not_called()
            captura.release.assert_called_once()

    def test_execucao_recusa_plano_da_outra_particao_antes_de_criar_resultados(self):
        selecao = deepcopy(self.dados)
        self.preparar_final_sintetico()
        final = deepcopy(self.dados)
        for etapa, dados in (("final", selecao), ("selecao", final)):
            with self.subTest(etapa=etapa), \
                    patch.object(script, "congelar_entradas", return_value=dados), \
                    patch.object(script, "processar_quadro") as detectar, \
                    redirect_stdout(StringIO()), self.assertRaises(ValueError):
                script.executar(self.caminho, etapa)
            detectar.assert_not_called()
            self.assertFalse(self.saida.exists())
            self.assertFalse(self.saida_final.exists())

    def test_congelamento_final_usa_validador_proprio_sem_decodificar_video(self):
        from scripts.blobs import planejamento_videos_final as planejamento_final

        self.preparar_final_sintetico()
        with patch.object(planejamento_final, "carregar_plano", return_value=self.dados["plano"]) as carregar, \
                patch.object(planejamento_final, "conferir_origens", return_value=self.dados["origens"]) as origens, \
                patch.object(script, "carregar_plano", side_effect=AssertionError("Validador de seleção indevido")), \
                patch.object(script, "conferir_origens", side_effect=AssertionError("Origem de seleção indevida")), \
                patch.object(script, "FONTES_CODIGO", tuple(self.dados["codigo"])), \
                patch.object(cv2, "VideoCapture", side_effect=AssertionError("Decodificação indevida")), \
                redirect_stdout(StringIO()):
            dados = script.congelar_entradas(self.caminho, "final")
        carregar.assert_called_once_with(self.caminho.read_bytes())
        origens.assert_called_once_with(self.dados["plano"], self.raiz)
        self.assertEqual(set(dados["anotacoes"]), {(v, q) for v in ("14", "24") for q in range(3)})
        self.assertEqual(dados["anotacoes"][("14", 2)], [])
        self.assertEqual([a["classe"] for a in dados["anotacoes"][("24", 0)]], [0, 1])
        self.assertEqual(dados["plano_bytes"], self.caminho.read_bytes())
        self.assertEqual(dados["codigo"], self.dados["codigo"])
        self.assertFalse(self.saida.exists())
        self.assertFalse(self.saida_final.exists())

    def test_congelamento_recusa_particao_cruzada_antes_de_conferir_origens(self):
        from scripts.blobs import planejamento_videos_final as planejamento_final

        selecao = deepcopy(self.dados["plano"])
        self.preparar_final_sintetico()
        final = deepcopy(self.dados["plano"])
        for etapa, plano in (("final", selecao), ("selecao", final)):
            with self.subTest(etapa=etapa), \
                    patch.object(script, "carregar_plano", return_value=plano), \
                    patch.object(planejamento_final, "carregar_plano", return_value=plano), \
                    patch.object(script, "conferir_origens") as origem_selecao, \
                    patch.object(planejamento_final, "conferir_origens") as origem_final, \
                    patch.object(cv2, "VideoCapture", side_effect=AssertionError("Decodificação indevida")), \
                    self.assertRaisesRegex(ValueError, "Plano incompatível"):
                script.congelar_entradas(self.caminho, etapa)
            origem_selecao.assert_not_called()
            origem_final.assert_not_called()
        self.assertFalse(self.saida.exists())
        self.assertFalse(self.saida_final.exists())

    def test_recuperacao_pdf_aceita_pasta_final_sem_flag_de_etapa(self):
        pasta = self.saida_final / "batch__sintetico"
        pasta.mkdir(parents=True)
        registro = pasta / "execucao.json"
        registro.write_bytes(bytes_json({"tipo": "videos_final_blobs", "particao": "final", "situacao": "concluida"}))
        antes = registro.read_bytes()
        with patch("analise.relatorio_videos_blobs.gerar_relatorio", side_effect=self.pdf_sintetico) as pdf, \
                patch.object(script, "congelar_entradas", side_effect=AssertionError("Preflight indevido")), \
                patch.object(script, "executar", side_effect=AssertionError("Execução indevida")), \
                patch.object(cv2, "VideoCapture", side_effect=AssertionError("Decodificação indevida")), \
                redirect_stdout(StringIO()):
            self.assertEqual(script.main(["--somente-relatorio", str(pasta)]), 0)
        pdf.assert_called_once_with(pasta)
        self.assertEqual(registro.read_bytes(), antes)
        self.assertEqual(ler_json(pasta / "relatorio.json"), {
            "situacao": "concluido",
            "arquivo": (pasta / "relatorios/sintetico/relatorio.pdf").relative_to(self.raiz).as_posix(),
        })
        self.assertFalse(self.saida.exists())

    def test_congelamento_real_preserva_anotacao_vazia_e_classes_sem_abrir_video(self):
        with self.simular_planejador(), \
                patch.object(cv2, "VideoCapture", side_effect=AssertionError("Decodificação indevida")), \
                redirect_stdout(StringIO()):
            dados = script.congelar_entradas(self.caminho)
        self.assertEqual(dados["anotacoes"], self.anotacoes)
        self.assertEqual(dados["anotacoes"][("13", 2)], [])
        self.assertEqual([a["classe"] for a in dados["anotacoes"][("13", 0)]], [0, 1])
        self.assertEqual(dados["anotacoes"][("13", 1)][0]["classe"], 2)
        self.assertEqual(dados["codigo"], self.dados["codigo"])
        self.assertFalse(self.saida.exists())

    def test_congelamento_real_recusa_gt_ausente_e_hash_alterado(self):
        nome = self.dados["plano"]["videos"][0]["anotacoes"][1]["arquivo"]
        caminho = self.raiz / nome
        original = caminho.read_bytes()
        for alteracao in ("ausente", "modificado"):
            if alteracao == "ausente":
                caminho.unlink()
            else:
                caminho.write_bytes(original + b"\n")
            with self.subTest(alteracao=alteracao), self.simular_planejador(), \
                    patch.object(script, "processar_quadro") as detectar, \
                    redirect_stdout(StringIO()), self.assertRaises((OSError, ValueError)):
                script.executar(self.caminho)
            detectar.assert_not_called()
            self.assertFalse(self.saida.exists())
            caminho.write_bytes(original)

    def test_falha_preflight_nao_cria_resultados(self):
        for erro in (FileNotFoundError("GT ausente"), ValueError("Hash divergente")):
            with self.subTest(erro=erro), \
                    patch.object(script, "congelar_entradas", side_effect=erro), \
                    patch.object(script, "processar_quadro") as detectar, \
                    redirect_stdout(StringIO()), self.assertRaises(type(erro)):
                script.executar(self.caminho)
            detectar.assert_not_called()
            self.assertFalse(self.saida.exists())

    def verificar_bloqueio_alinhamento(self):
        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(script, "processar_quadro") as detectar, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(ValueError):
            script.executar(self.caminho)
        detectar.assert_not_called()
        batches = list(self.saida.glob("batch__*"))
        self.assertEqual(len(batches), 1)
        registro = ler_json(batches[0] / "execucao.json")
        self.assertEqual(registro["situacao"], "falhou")
        self.assertFalse(registro["alinhamento_conferido"])
        self.assertFalse(list(batches[0].rglob("deteccoes.csv")))

    def test_indice_da_referencia_errado_interrompe_antes_de_detectar(self):
        self.dados["plano"]["videos"][0]["referencias_alinhamento"][0]["quadro"] = 1
        self.verificar_bloqueio_alinhamento()

    def test_video_truncado_interrompe_antes_de_detectar(self):
        self.criar_video("13", self.imagens[:2])
        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(script, "processar_quadro") as detectar, \
                redirect_stdout(StringIO()), self.assertRaisesRegex(ValueError, "Metadados"):
            script.executar(self.caminho)
        detectar.assert_not_called()
        self.assertFalse(self.saida.exists())

    def test_quadros_duplicados_interrompem_por_alinhamento_ambiguo(self):
        self.criar_video("13", [self.imagens[0], self.imagens[0], self.imagens[2]])
        self.verificar_bloqueio_alinhamento()

    def test_pixels_diferentes_da_conferencia_interrompem_antes_de_detectar(self):
        conferir = video_base.conferir_alinhamento

        def divergente(*args, **kwargs):
            resultado = conferir(*args, **kwargs)
            resultado["pixels_sha256"][("13", 0)] = "0" * 64
            return resultado

        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(video_base, "conferir_alinhamento", side_effect=divergente), \
                patch.object(script, "processar_quadro") as detectar, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()), \
                self.assertRaisesRegex(ValueError, "Pixels|pixels"):
            script.executar(self.caminho)
        detectar.assert_not_called()
        pasta = next(self.saida.glob("batch__*"))
        self.assertEqual(ler_json(pasta / "execucao.json")["situacao"], "falhou")

    def test_falha_de_gravacao_preserva_manifestos_incompletos(self):
        escritor = SimpleNamespace(isOpened=lambda: False, release=Mock())
        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(cv2, "VideoWriter", return_value=escritor), \
                patch.object(script, "processar_quadro") as detectar, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(ValueError):
            script.executar(self.caminho)
        escritor.release.assert_called_once()
        detectar.assert_not_called()
        pasta = next(self.saida.glob("batch__*"))
        self.assertEqual(ler_json(pasta / "execucao.json")["situacao"], "falhou")
        internos = [p for p in pasta.rglob("execucao.json") if p.parent != pasta]
        self.assertEqual(len(internos), 1)
        self.assertEqual(ler_json(internos[0])["situacao"], "falhou")

    def test_escritor_que_abre_mas_nao_grava_mp4_valido_nao_conclui_batch(self):
        def escritor_invalido(caminho, *_):
            Path(caminho).write_bytes(b"arquivo truncado sintetico")
            return SimpleNamespace(isOpened=lambda: True, write=Mock(), release=Mock())

        with patch.object(script, "congelar_entradas", return_value=self.dados), \
                patch.object(cv2, "VideoWriter", side_effect=escritor_invalido), \
                patch("algoritmos.classicos.blobs.detectar", return_value=self.resultado_sbd()) as detector, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()), \
                self.assertRaisesRegex(ValueError, "inválido|incompleto"):
            script.executar(self.caminho)
        self.assertEqual(detector.call_count, 3)
        pasta = next(self.saida.glob("batch__*"))
        self.assertEqual(ler_json(pasta / "execucao.json")["situacao"], "falhou")
        self.assertFalse((pasta / "ranking.csv").exists())
        tabelas = list(pasta.rglob("deteccoes.csv"))
        self.assertEqual(len(tabelas), 1)
        self.assertEqual(len(ler_csv(tabelas[0])), 3)

    def test_falha_pdf_preserva_videos_metricas_e_manifesto_concluidos(self):
        pasta = self.executar_sintetico(falha_pdf=True)
        self.assertEqual(ler_json(pasta / "execucao.json")["situacao"], "concluida")
        self.assertEqual(len(list(pasta.rglob("*.mp4"))), 10)
        self.assertTrue((pasta / "ranking.csv").is_file())

    def test_somente_relatorio_nao_reabre_videos_nem_executa_detector(self):
        pasta = self.saida / "batch__sintetico"
        pasta.mkdir(parents=True)
        registro = pasta / "execucao.json"
        registro.write_bytes(bytes_json({"situacao": "concluida"}))
        antes = registro.read_bytes()
        with patch.object(script, "atualizar_relatorio", side_effect=self.pdf_sintetico) as pdf, \
                patch.object(script, "congelar_entradas", side_effect=AssertionError("Preflight indevido")), \
                patch.object(script, "executar", side_effect=AssertionError("Execução indevida")), \
                patch.object(cv2, "VideoCapture", side_effect=AssertionError("Decodificação indevida")), \
                redirect_stdout(StringIO()):
            self.assertEqual(script.main(["--somente-relatorio", str(pasta)]), 0)
        pdf.assert_called_once_with(pasta)
        self.assertEqual(registro.read_bytes(), antes)

    def test_cli_recusa_etapa_desconhecida_ou_conferencia_com_somente_relatorio(self):
        for argumentos in (["--etapa", "outra"], ["--conferir", "--somente-relatorio", "batch__invalido"]):
            with self.subTest(argumentos=argumentos), \
                    patch.object(script, "executar") as executar, \
                    patch.object(script, "atualizar_relatorio") as pdf, \
                    redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                script.main(argumentos)
            executar.assert_not_called()
            pdf.assert_not_called()

    def test_processamento_de_video_preserva_contrato_da_imagem_sem_deriva(self):
        imagem = self.decodificadas[("13", 0)]
        sucesso, png = cv2.imencode(".png", imagem)
        self.assertTrue(sucesso)
        quadro = {"video_id": "13", "quadro": 0, "imagem": "sintetica.png", "anotacao": "sintetica.txt"}
        entrada = {"quadro": quadro, "imagem_bytes": png.tobytes(), "anotacao_bytes": b"",
                   "anotacoes": []}
        for item in (self.dados["plano"]["configuracoes"][0], self.dados["plano"]["configuracoes"][3]):
            with self.subTest(metodo=item["metodo"]), \
                    patch("algoritmos.classicos.blobs.detectar", return_value=self.resultado_sbd()), \
                    patch("skimage.feature.blob_dog", return_value=np.array([[40., 240., 2.]])):
                config, detectar = rodada.preparar_detector(item)
                caixa_config = configuracao_caixa_de_dict(item["caixa"])
                registros, tempos = script.processar_quadro(imagem, item, config, caixa_config, detectar)
                pasta = self.raiz / f"imagem-{item['id']}"
                rodada.executar_quadro(entrada, config, caixa_config, item, pasta, cv2, np, detectar)
            salva = ler_csv(pasta / "deteccoes.csv")
            self.assertEqual(len(registros), len(salva))
            for novo, anterior in zip(registros, salva):
                for chave, valor in novo.items():
                    self.assertEqual(anterior[chave], "" if valor is None else str(valor), chave)
            self.assertEqual(tempos["tempo_pipeline_ns"], sum(tempos[f"tempo_{nome}_ns"]
                             for nome in ("preprocessamento", "detector", "adaptacao")))
            self.assertEqual(tempos["tempo_preprocessamento_ns"], 0)


if __name__ == "__main__":
    unittest.main()
