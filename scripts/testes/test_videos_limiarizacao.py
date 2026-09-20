"""Contratos sintéticos dos vídeos, sem acesso aos dados ou codecs reais."""

from contextlib import ExitStack
from copy import deepcopy
import csv
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from scripts.limiarizacao import executar_videos as script


class CapturaSintetica:
    def __init__(self, imagens, fps=49, aberta=True):
        self.imagens = iter(imagens)
        self.fps = fps
        self.aberta = aberta
        self.liberada = False

    def isOpened(self):
        return self.aberta

    def get(self, propriedade):
        return self.fps

    def getBackendName(self):
        return "sintetico"

    def read(self):
        try:
            return True, next(self.imagens)
        except StopIteration:
            return False, None

    def release(self):
        self.liberada = True


class CvSintetico:
    CAP_PROP_FPS = 5
    IMREAD_UNCHANGED = -1
    COLOR_BGR2GRAY = 6
    NORM_L1 = 2

    def __init__(self, capturas, dimensoes=(4, 6, 3)):
        self.capturas = list(capturas)
        self.pendentes = iter(self.capturas)
        self.dimensoes = dimensoes

    def VideoCapture(self, caminho):
        return next(self.pendentes)

    def imdecode(self, dados, modo):
        return np.full(self.dimensoes, int(dados.tobytes()), dtype=np.uint8)

    def cvtColor(self, imagem, modo):
        return imagem[:, :, 0].copy()

    def norm(self, esquerda, direita, modo):
        return float(np.abs(esquerda.astype(np.int16) - direita.astype(np.int16)).sum())

    def imencode(self, formato, imagem):
        return True, np.frombuffer(b"imagem-sintetica", dtype=np.uint8)


def imagens_constantes(valores, dimensoes=(4, 6, 3)):
    return [np.full(dimensoes, valor, dtype=np.uint8) for valor in valores]


class MinimosTest(unittest.TestCase):
    def estado(self, quadro=2):
        return {"quadro": quadro, "menores": [], "erro_previsto": None}

    def test_minimo_unico_no_indice_previsto_e_valido(self):
        estado = self.estado()
        for indice, erro in enumerate((3, 2, .25, 4)):
            script.atualizar_minimos(estado, indice, erro)
        self.assertEqual(estado["menores"], [(.25, 2), (2, 1)])
        self.assertEqual(estado["erro_previsto"], .25)
        self.assertTrue(script.alinhamento_valido(estado))

    def test_menor_erro_em_outro_indice_nao_corrige_offset(self):
        estado = self.estado()
        for indice, erro in enumerate((3, .25, 2, 4)):
            script.atualizar_minimos(estado, indice, erro)
        self.assertFalse(script.alinhamento_valido(estado))
        self.assertEqual(estado["quadro"], 2)
        self.assertEqual(estado["erro_previsto"], 2)

    def test_empate_nao_e_resolvido_pela_ordem_dos_indices(self):
        for quadro in (1, 2):
            estado = self.estado(quadro)
            for indice, erro in enumerate((3, .25, .25, 4)):
                script.atualizar_minimos(estado, indice, erro)
            self.assertFalse(script.alinhamento_valido(estado))

    def test_diferenca_dentro_da_tolerancia_e_ambigua(self):
        estado = self.estado(0)
        script.atualizar_minimos(estado, 0, 1)
        script.atualizar_minimos(estado, 1, 1 + 5e-10)
        self.assertFalse(script.alinhamento_valido(estado))

    def test_menos_de_dois_quadros_nao_confirma_alinhamento(self):
        estado = self.estado(0)
        self.assertFalse(script.alinhamento_valido(estado))
        script.atualizar_minimos(estado, 0, 0)
        self.assertFalse(script.alinhamento_valido(estado))


class AlinhamentoTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.contextos = ExitStack()
        self.addCleanup(self.contextos.close)
        self.contextos.enter_context(patch.object(script, "caminho_fonte", side_effect=lambda nome: self.raiz / nome))
        self.contextos.enter_context(patch.object(script, "desenhar_painel", side_effect=lambda cv, n, imagem, *_: imagem.copy()))

    def video(self, identificador="13", referencias=((0, 10), (2, 100), (3, 160))):
        itens = []
        for quadro, valor in referencias:
            nome = f"{identificador}_frame_{quadro}.jpg"
            (self.raiz / nome).write_text(str(valor), encoding="ascii")
            itens.append({"quadro": quadro, "imagem": nome})
        return {"video_id": identificador, "arquivo": f"{identificador}.mp4", "fps": 49,
                "largura": 6, "altura": 4, "quantidade_quadros": 4,
                "referencias_alinhamento": itens}

    def test_confere_todos_videos_e_preserva_indices_e_referencias(self):
        plano = {"videos": [self.video("13"), self.video("29")]}
        antes = deepcopy(plano)
        capturas = [CapturaSintetica(imagens_constantes((10, 40, 100, 160))) for _ in range(2)]
        resultado = script.conferir_alinhamento(plano, self.raiz / "conferencia", CvSintetico(capturas), np)
        self.assertEqual(plano, antes)
        self.assertEqual(len(resultado["referencias"]), 6)
        self.assertTrue(all(r["alinhamento_confirmado"] for r in resultado["referencias"]))
        self.assertTrue(all(r["quadro_previsto"] == r["melhor_quadro"] for r in resultado["referencias"]))
        self.assertEqual(len(resultado["pixels_sha256"]), 8)
        esperado = hashlib.sha256(imagens_constantes((10,))[0].tobytes()).hexdigest()
        self.assertEqual(resultado["pixels_sha256"][("13", 0)], esperado)
        self.assertEqual([v["backend"] for v in resultado["videos"]], ["sintetico", "sintetico"])
        self.assertTrue(all(c.liberada for c in capturas))
        self.assertEqual(len(list((self.raiz / "conferencia").glob("*.png"))), 6)
        registro = json.loads((self.raiz / "conferencia/conferencia.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["situacao"], "concluida")
        self.assertEqual(registro["quadros_decodificados_sha256"],
                         script.hash_arquivo(self.raiz / "conferencia/quadros_decodificados.csv"))

    def test_indice_diferente_interrompe_com_diagnostico(self):
        video = self.video(referencias=((0, 10), (2, 160), (3, 160)))
        antes = deepcopy(video)
        captura = CapturaSintetica(imagens_constantes((10, 40, 100, 160)))
        with self.assertRaisesRegex(ValueError, "divergente ou ambíguo"):
            script.conferir_alinhamento({"videos": [video]}, self.raiz / "conferencia", CvSintetico([captura]), np)
        self.assertTrue(captura.liberada)
        self.assertEqual(video, antes)
        with (self.raiz / "conferencia/alinhamento.csv").open(encoding="utf-8-sig", newline="") as arquivo:
            linhas = list(csv.DictReader(arquivo))
        divergente = next(r for r in linhas if r["quadro_previsto"] == "2")
        self.assertEqual(divergente["melhor_quadro"], "3")
        self.assertEqual(divergente["alinhamento_confirmado"], "False")
        self.assertFalse((self.raiz / "conferencia/conferencia.json").exists())

    def test_quadros_iguais_interrompem_por_ambiguidade(self):
        captura = CapturaSintetica(imagens_constantes((10, 10, 100, 160)))
        with self.assertRaisesRegex(ValueError, "divergente ou ambíguo"):
            script.conferir_alinhamento({"videos": [self.video()]}, self.raiz / "conferencia", CvSintetico([captura]), np)
        self.assertTrue(captura.liberada)

    def test_video_curto_ou_com_quadros_extras_e_rejeitado(self):
        video = self.video()
        for numero, valores in enumerate(((10, 40), (10, 40, 100, 160, 200))):
            captura = CapturaSintetica(imagens_constantes(valores))
            with self.subTest(valores=valores), self.assertRaises(ValueError):
                script.conferir_alinhamento({"videos": [video]}, self.raiz / f"conferencia-{numero}", CvSintetico([captura]), np)
            self.assertTrue(captura.liberada)

    def test_fps_incompativel_libera_captura(self):
        captura = CapturaSintetica([], fps=48)
        with self.assertRaisesRegex(ValueError, "FPS"):
            script.abrir_video(self.video(), CvSintetico([captura]))
        self.assertTrue(captura.liberada)

    def test_captura_nao_aberta_e_liberada(self):
        captura = CapturaSintetica([], aberta=False)
        with self.assertRaisesRegex(ValueError, "abrir"):
            script.abrir_video(self.video(), CvSintetico([captura]))
        self.assertTrue(captura.liberada)

    def test_formato_do_quadro_precisa_corresponder_ao_plano(self):
        video = self.video()
        for imagem in (None, np.zeros((4, 6), dtype=np.uint8), np.zeros((4, 6, 3), dtype=np.float32)):
            with self.subTest(imagem=type(imagem)), self.assertRaises(ValueError):
                script.conferir_quadro(imagem, video)


class VideoGravadoTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.caminho = self.raiz / "comparacao.mp4"
        self.caminho.write_bytes(b"video-sintetico")
        self.video = {"fps": 49, "largura": 6, "altura": 4, "quantidade_quadros": 2}
        self.patcher = patch.object(script, "RAIZ", self.raiz)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_exige_todos_quadros_com_dimensoes_do_painel(self):
        captura = CapturaSintetica(imagens_constantes((10, 40), (108, 12, 3)))
        resultado = script.conferir_video_gravado(self.caminho, self.video, CvSintetico([captura]))
        self.assertEqual(resultado["quantidade_quadros"], 2)
        self.assertEqual((resultado["largura"], resultado["altura"]), (12, 108))
        self.assertTrue(resultado["decodificacao_conferida"])
        self.assertEqual(resultado["sha256"], script.hash_arquivo(self.caminho))
        self.assertTrue(captura.liberada)

    def test_rejeita_video_truncado_extra_ou_com_dimensoes_erradas(self):
        casos = [imagens_constantes((10,), (108, 12, 3)),
                 imagens_constantes((10, 20, 30), (108, 12, 3)),
                 imagens_constantes((10, 20), (4, 6, 3))]
        for imagens in casos:
            captura = CapturaSintetica(imagens)
            with self.subTest(quadros=len(imagens)), self.assertRaises(ValueError):
                script.conferir_video_gravado(self.caminho, self.video, CvSintetico([captura]))
            self.assertTrue(captura.liberada)

    def test_rejeita_fps_errado_e_libera_captura(self):
        captura = CapturaSintetica([], fps=48)
        with self.assertRaises(ValueError):
            script.conferir_video_gravado(self.caminho, self.video, CvSintetico([captura]))
        self.assertTrue(captura.liberada)


def videos_sinteticos(quadros, fps):
    videos = []
    for identificador, quantidade in quadros.items():
        base = f"bases_de_dados/visem_tracking/dataset/Train/{identificador}"
        videos.append({
            "video_id": identificador, "arquivo": f"{base}/{identificador}.mp4",
            "quantidade_quadros": quantidade, "fps": fps[identificador],
            "largura": 640, "altura": 480, "indice_inicial": 0, "sha256": "a" * 64,
            "anotacoes": [{"quadro": q, "arquivo": f"{base}/labels/{identificador}_frame_{q}.txt",
                           "sha256": "b" * 64} for q in range(quantidade)],
            "referencias_alinhamento": [
                {"quadro": q, "imagem": f"{base}/images/{identificador}_frame_{q}.jpg", "sha256": "c" * 64}
                for q in (0, 100, 700, 1400, quantidade - 1)
            ],
        })
    return videos


class PlanoTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.contextos = ExitStack()
        self.addCleanup(self.contextos.close)
        self.contextos.enter_context(patch.object(script, "RAIZ", self.raiz))
        parametros = {
            "metodo": "manual", "limiar_manual": 90, "polaridade": "claro",
            "abertura": {"forma": "elipse", "tamanho": 3, "iteracoes": 0},
            "fechamento": {"forma": "elipse", "tamanho": 5, "iteracoes": 1},
            "area_minima": 24, "area_maxima": None, "conectividade": 8,
            "classificacao": {"area_maxima_pequeno": 80, "area_minima_aglomerado": 1000},
        }
        configuracoes = [{"id": identificador, "parametros": deepcopy(parametros)} for identificador in script.IDS]
        fonte = self.raiz / script.PLANO_IMAGENS
        fonte.parent.mkdir(parents=True)
        fonte.write_text(json.dumps({"configuracoes": configuracoes}), encoding="utf-8")
        self.contextos.enter_context(patch.object(script, "HASH_PLANO_IMAGENS", script.hash_arquivo(fonte)))
        self.plano = {
            "versao": 1, "tipo": "videos_selecao", "algoritmo": "limiarizacao",
            "particao": "selecao", "seed": 42, "politica_anotacoes_ausentes": "erro",
            "criterios_avaliacao": deepcopy(script.CRITERIOS), "configuracoes": configuracoes,
            "videos": videos_sinteticos(script.QUADROS, script.FPS),
        }

    def carregar(self, plano, etapa="selecao"):
        conteudo = json.dumps(plano, allow_nan=False).encode("utf-8")
        constante = "HASH_PLANO_FINAL" if etapa == "final" else "HASH_PLANO_VIDEOS"
        with patch.object(script, constante, hashlib.sha256(conteudo).hexdigest()):
            return script.carregar_plano(conteudo, etapa)

    def plano_final(self):
        plano = deepcopy(self.plano)
        plano.update(tipo="videos_final", particao="final",
                     videos=videos_sinteticos(script.QUADROS_FINAL, script.FPS_FINAL))
        return plano

    def test_cinco_configuracoes_e_quatro_videos_inteiros(self):
        resultado = self.carregar(self.plano)
        self.assertEqual([c["id"] for c in resultado["configuracoes"]], ["s068", "s067", "s090", "s099", "s101"])
        self.assertEqual(sum(v["quantidade_quadros"] for v in resultado["videos"]), 5850)
        self.assertEqual([v["video_id"] for v in resultado["videos"]], ["13", "29", "52", "54"])

    def test_rejeita_bytes_que_nao_correspondem_ao_plano_congelado(self):
        conteudo = json.dumps(self.plano).encode()
        with patch.object(script, "HASH_PLANO_VIDEOS", hashlib.sha256(conteudo).hexdigest()):
            with self.assertRaisesRegex(ValueError, "congelado"):
                script.carregar_plano(conteudo + b" ")

    def test_rejeita_alteracao_de_parametros_e_criterios(self):
        alteracoes = (
            lambda p: p["configuracoes"][0]["parametros"].update(limiar_manual=91),
            lambda p: p["criterios_avaliacao"].update(limiar_iou=.4),
            lambda p: p["configuracoes"].reverse(),
            lambda p: p.update(politica_anotacoes_ausentes="ignorar"),
        )
        for alterar in alteracoes:
            plano = deepcopy(self.plano)
            alterar(plano)
            with self.subTest(alterar=alterar), self.assertRaises(ValueError):
                self.carregar(plano)

    def test_rejeita_video_final_lacuna_fps_ou_referencia_diferentes(self):
        alteracoes = (
            lambda p: p["videos"][0].update(video_id="14"),
            lambda p: p["videos"][0]["anotacoes"].pop(),
            lambda p: p["videos"][0].update(fps=50),
            lambda p: p["videos"][0]["referencias_alinhamento"][2].update(quadro=701),
            lambda p: p["videos"][0]["anotacoes"][0].update(sha256=""),
            lambda p: p["videos"][0]["anotacoes"][0].update(arquivo="fora.txt"),
        )
        for alterar in alteracoes:
            plano = deepcopy(self.plano)
            alterar(plano)
            with self.subTest(alterar=alterar), self.assertRaises(ValueError):
                self.carregar(plano)

    def test_rejeita_modificacao_no_plano_original_das_candidatas(self):
        fonte = self.raiz / script.PLANO_IMAGENS
        fonte.write_bytes(fonte.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "original"):
            self.carregar(self.plano)

    def test_final_preserva_candidatas_e_usa_5910_quadros_reservados(self):
        plano = self.plano_final()
        resultado = self.carregar(plano, "final")
        self.assertEqual(resultado["configuracoes"], self.plano["configuracoes"])
        self.assertEqual([v["video_id"] for v in resultado["videos"]], ["14", "24", "38", "82"])
        self.assertEqual([v["quantidade_quadros"] for v in resultado["videos"]], [1470, 1470, 1470, 1500])
        self.assertEqual([v["fps"] for v in resultado["videos"]], [49, 49, 49, 50])
        self.assertEqual(sum(v["quantidade_quadros"] for v in resultado["videos"]), 5910)
        self.assertEqual(resultado["criterios_avaliacao"], self.plano["criterios_avaliacao"])

    def test_plano_de_uma_etapa_nao_passa_na_outra(self):
        for plano, etapa in ((self.plano, "final"), (self.plano_final(), "selecao")):
            with self.subTest(etapa=etapa), self.assertRaisesRegex(ValueError, "incompatível"):
                self.carregar(plano, etapa)

    def test_final_rejeita_video_de_selecao_e_fps_49_no_video_82(self):
        alteracoes = (
            lambda p: p["videos"][0].update(video_id="13"),
            lambda p: p["videos"][3].update(fps=49),
            lambda p: p["videos"][3]["anotacoes"].pop(),
            lambda p: p["configuracoes"][0]["parametros"].update(area_minima=48),
            lambda p: p["criterios_avaliacao"].update(limiar_iou=.7),
        )
        for alterar in alteracoes:
            plano = self.plano_final()
            alterar(plano)
            with self.subTest(alterar=alterar), self.assertRaises(ValueError):
                self.carregar(plano, "final")

    def test_hashes_das_etapas_nao_sao_intercambiaveis(self):
        selecao = json.dumps(self.plano).encode()
        final = json.dumps(self.plano_final()).encode()
        with patch.object(script, "HASH_PLANO_VIDEOS", hashlib.sha256(selecao).hexdigest()), \
                patch.object(script, "HASH_PLANO_FINAL", hashlib.sha256(final).hexdigest()):
            for conteudo, etapa in ((final, "selecao"), (selecao, "final"), (final + b" ", "final")):
                with self.subTest(etapa=etapa), self.assertRaisesRegex(ValueError, "congelado"):
                    script.carregar_plano(conteudo, etapa)

    def test_etapa_desconhecida_e_rejeitada(self):
        with self.assertRaisesRegex(ValueError, "Etapa"):
            script.especificacao_etapa("desenvolvimento")


class FontesTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.patcher = patch.object(script, "RAIZ", self.raiz)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.base = "bases_de_dados/visem_tracking/dataset/Train/13"
        self.video = {"video_id": "13", **self.fonte("13.mp4", b"video-sintetico"),
                      "anotacoes": [
                          {"quadro": 0, **self.fonte("labels/13_frame_0.txt", b"2 .5 .5 .2 .2\n")},
                          {"quadro": 1, **self.fonte("labels/13_frame_1.txt", b"")},
                      ], "referencias_alinhamento": []}
        self.plano = {"proveniencia": {"reavaliacao": {"arquivos_sha256": {}}}, "videos": [self.video]}

    def fonte(self, sufixo, conteudo):
        nome = f"{self.base}/{sufixo}"
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        return {"arquivo": nome, "sha256": hashlib.sha256(conteudo).hexdigest()}

    def test_anotacao_vazia_existe_e_classes_originais_sao_preservadas(self):
        antes = {(self.raiz / a["arquivo"]): (self.raiz / a["arquivo"]).read_bytes() for a in self.video["anotacoes"]}
        hashes, anotacoes = script.conferir_fontes(self.plano)
        self.assertEqual(anotacoes[("13", 0)][0]["classe"], 2)
        self.assertEqual(anotacoes[("13", 1)], [])
        self.assertIn(self.video["arquivo"], hashes)
        self.assertTrue(all(caminho.read_bytes() == conteudo for caminho, conteudo in antes.items()))

    def test_anotacao_ausente_nao_e_convertida_em_quadro_vazio(self):
        (self.raiz / self.video["anotacoes"][1]["arquivo"]).unlink()
        with self.assertRaises(FileNotFoundError):
            script.conferir_fontes(self.plano)

    def test_hash_divergente_e_rejeitado(self):
        (self.raiz / self.video["anotacoes"][0]["arquivo"]).write_bytes(b"0 .5 .5 .2 .2\n")
        with self.assertRaisesRegex(ValueError, "alterado"):
            script.conferir_fontes(self.plano)

    def test_caminho_fora_da_base_e_rejeitado(self):
        (self.raiz / "fora.txt").write_bytes(b"fora")
        with self.assertRaisesRegex(ValueError, "fora"):
            script.caminho_fonte("fora.txt")

    def proveniencia_final(self):
        origens = {}
        for chave, pasta in (("reavaliacao", "resultados/frame-to-frame/limiarizacao/selecao"),
                             ("selecao_videos", "resultados/videos/limiarizacao/selecao")):
            nome = f"{pasta}/batch__sintetico/execucao.json"
            caminho = self.raiz / nome
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_bytes(b'{"situacao":"concluida"}')
            origens[chave] = {"arquivos_sha256": {nome: script.hash_arquivo(caminho)}}
        return {"particao": "final", "proveniencia": origens, "videos": []}

    def test_final_confere_proveniencia_das_imagens_e_dos_videos_de_selecao(self):
        plano = self.proveniencia_final()
        hashes, anotacoes = script.conferir_fontes(plano)
        for origem in plano["proveniencia"].values():
            for nome, esperado in origem["arquivos_sha256"].items():
                self.assertEqual(hashes[nome], esperado)
        self.assertEqual(anotacoes, {})

    def test_final_rejeita_proveniencia_dos_videos_alterada(self):
        plano = self.proveniencia_final()
        nome = next(iter(plano["proveniencia"]["selecao_videos"]["arquivos_sha256"]))
        (self.raiz / nome).write_bytes(b'{"situacao":"falhou"}')
        with self.assertRaisesRegex(ValueError, "alterado"):
            script.conferir_fontes(plano)

    def test_final_nao_aceita_resultado_final_como_origem_da_selecao(self):
        plano = self.proveniencia_final()
        nome = "resultados/videos/limiarizacao/final/batch__outro/execucao.json"
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True)
        caminho.write_bytes(b"{}")
        plano["proveniencia"]["selecao_videos"]["arquivos_sha256"] = {nome: script.hash_arquivo(caminho)}
        with self.assertRaisesRegex(ValueError, "fora"):
            script.conferir_fontes(plano)

    def test_final_exige_proveniencia_dos_videos_de_selecao(self):
        plano = self.proveniencia_final()
        del plano["proveniencia"]["selecao_videos"]
        with self.assertRaises(KeyError):
            script.conferir_fontes(plano)


class RelatorioEtapasTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.contextos = ExitStack()
        self.addCleanup(self.contextos.close)
        self.contextos.enter_context(patch.object(script, "RAIZ", self.raiz))
        self.saidas = {etapa: self.raiz / "resultados/videos/limiarizacao" / etapa for etapa in ("selecao", "final")}
        self.contextos.enter_context(patch.object(script, "SAIDA", self.saidas["selecao"]))
        self.contextos.enter_context(patch.object(script, "SAIDA_FINAL", self.saidas["final"]))
        self.batch = {}
        for etapa, pasta in self.saidas.items():
            self.batch[etapa] = pasta / "batch__sintetico"
            self.batch[etapa].mkdir(parents=True)
            (self.batch[etapa] / "execucao.json").write_bytes(b'{"preservar":true}')
        self.gerador = self.contextos.enter_context(patch("analise.relatorio_videos.gerar_relatorio"))

    def test_inferencia_pela_pasta_funciona_nas_duas_etapas(self):
        for etapa, pasta in self.batch.items():
            pdf = pasta / "relatorio_sintetico.pdf"
            self.gerador.return_value = pdf
            self.assertEqual(script.gerar_relatorio(pasta), pdf)
            self.gerador.assert_called_with(pasta)
            registro = json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))
            self.assertEqual(registro["situacao"], "concluido")
            self.assertEqual((pasta / "execucao.json").read_bytes(), b'{"preservar":true}')

    def test_etapa_explicita_incompativel_nao_gera_nem_atualiza_status(self):
        for etapa, pasta in self.batch.items():
            outra = "selecao" if etapa == "final" else "final"
            with self.subTest(etapa=etapa), self.assertRaisesRegex(ValueError, "correspondente"):
                script.gerar_relatorio(pasta, outra)
            self.assertFalse((pasta / "relatorio.json").exists())
        self.gerador.assert_not_called()

    def test_etapa_explicita_correta_e_recuperacao_preservam_manifesto(self):
        pasta = self.batch["final"]
        self.gerador.side_effect = ValueError("falha sintética")
        with self.assertRaisesRegex(ValueError, "sintética"):
            script.gerar_relatorio(pasta, "final")
        self.assertEqual(json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))["situacao"], "falhou")
        self.gerador.side_effect = None
        self.gerador.return_value = pasta / "outro_relatorio.pdf"
        script.gerar_relatorio(pasta, "final")
        self.assertEqual(json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))["situacao"], "concluido")
        self.assertEqual((pasta / "execucao.json").read_bytes(), b'{"preservar":true}')

    def test_pasta_fora_dos_batches_das_etapas_e_rejeitada(self):
        fora = self.raiz / "batch__fora"
        fora.mkdir()
        with self.assertRaises(ValueError):
            script.gerar_relatorio(fora)
        self.gerador.assert_not_called()


class InterfaceEtapasTest(unittest.TestCase):
    def setUp(self):
        self.contextos = ExitStack()
        self.addCleanup(self.contextos.close)
        self.executar = self.contextos.enter_context(patch.object(script, "executar", return_value=Path("resultado")))
        self.relatorio = self.contextos.enter_context(patch.object(script, "gerar_relatorio", return_value=Path("relatorio.pdf")))
        self.contextos.enter_context(patch("sys.stdout", StringIO()))
        self.contextos.enter_context(patch("sys.stderr", StringIO()))

    def test_sem_argumentos_preserva_etapa_selecao(self):
        script.main([])
        self.executar.assert_called_once_with(script.PLANO_PADRAO, "selecao")
        self.relatorio.assert_not_called()

    def test_etapa_final_usa_plano_final(self):
        script.main(["--etapa", "final"])
        self.executar.assert_called_once_with(script.PLANO_FINAL, "final")
        self.relatorio.assert_not_called()

    def test_plano_explicito_mantem_etapa_escolhida(self):
        script.main(["--etapa", "final", "--plano", "copia_final.json"])
        self.executar.assert_called_once_with(Path("copia_final.json"), "final")

    def test_plano_explicito_sem_etapa_continua_selecao(self):
        script.main(["--plano", "copia_selecao.json"])
        self.executar.assert_called_once_with(Path("copia_selecao.json"), "selecao")

    def test_somente_relatorio_sem_etapa_delega_inferencia(self):
        script.main(["--somente-relatorio", "batch__final"])
        self.relatorio.assert_called_once_with(Path("batch__final"), None)
        self.executar.assert_not_called()

    def test_somente_relatorio_com_etapa_explicita_preserva_restricao(self):
        script.main(["--etapa", "final", "--somente-relatorio", "batch__final"])
        self.relatorio.assert_called_once_with(Path("batch__final"), "final")
        self.executar.assert_not_called()

    def test_argumentos_incompativeis_ou_etapa_desconhecida_nao_executam(self):
        for argumentos in (["--etapa", "desenvolvimento"],
                           ["--plano", "plano.json", "--somente-relatorio", "batch__teste"]):
            with self.subTest(argumentos=argumentos), self.assertRaises(SystemExit) as contexto:
                script.main(argumentos)
            self.assertEqual(contexto.exception.code, 2)
        self.executar.assert_not_called()
        self.relatorio.assert_not_called()


@dataclass
class ConfiguracaoSintetica:
    metodo: str = "manual"


class IntegridadeDecodificacaoTest(unittest.TestCase):
    def test_pixels_diferentes_da_conferencia_interrompem_antes_do_detector(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            captura = CapturaSintetica(imagens_constantes((10,)))
            escritor = SimpleNamespace(isOpened=lambda: True, release=Mock())
            cv = SimpleNamespace(VideoWriter=lambda *_: escritor, VideoWriter_fourcc=lambda *_: 0)
            detectar = Mock(side_effect=AssertionError("O detector não pode ser chamado."))
            video = {"video_id": "13", "fps": 49, "largura": 6, "altura": 4, "quantidade_quadros": 1}
            pixels = {("13", 0): hashlib.sha256(imagens_constantes((20,))[0].tobytes()).hexdigest()}
            pasta = raiz / "configuracao"
            with patch.object(script, "RAIZ", raiz), \
                    patch.object(script, "abrir_video", return_value=captura), \
                    patch.object(script, "nome_configuracao", return_value="configuracao"), \
                    self.assertRaisesRegex(ValueError, "decodifica"):
                script.executar_configuracao({"id": "s068"}, ConfiguracaoSintetica(),
                    {"videos": [video]}, pasta, {}, {}, pixels, cv, np, detectar)
            detectar.assert_not_called()
            self.assertTrue(captura.liberada)
            escritor.release.assert_called_once()
            registro = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
            self.assertEqual(registro["situacao"], "falhou")
            self.assertEqual(registro["quadros_concluidos"], 0)


class CaixasETabelasTest(unittest.TestCase):
    def test_conversao_para_pixels_preserva_classes_indices_e_entradas(self):
        itens = [{"indice_anotacao": 7, "classe": 2, "linha_original": 3,
                  "caixa_centro_x_norm": .5, "caixa_centro_y_norm": .5,
                  "caixa_largura_norm": .25, "caixa_altura_norm": .25}]
        antes = deepcopy(itens)
        resultado = script.caixas_anotadas(itens, 640, 480)
        self.assertEqual(itens, antes)
        self.assertEqual([resultado[0][c] for c in script.CAMPOS_CAIXA], [240, 180, 160, 120])
        self.assertEqual((resultado[0]["classe"], resultado[0]["indice_anotacao"]), (2, 7))
        objeto = script.objetos(resultado, "indice_anotacao")[0]
        self.assertEqual((objeto.indice, objeto.classe), (7, 2))

    def test_tabelas_tem_origem_temporal_caixas_medidas_e_indices_locais(self):
        with tempfile.TemporaryDirectory() as temporario:
            pasta = Path(temporario)
            with ExitStack() as pilha:
                script.abrir_tabelas(pasta, pilha)
            for nome in ("deteccoes", "anotacoes", "por_quadro", "pares", "pendentes"):
                with (pasta / f"{nome}.csv").open(encoding="utf-8-sig", newline="") as arquivo:
                    campos = next(csv.reader(arquivo))
                self.assertEqual(len(campos), len(set(campos)))
                self.assertTrue(set(script.CAMPOS_ORIGEM).issubset(campos))
                self.assertNotIn("track_id", campos)
                if nome == "deteccoes":
                    self.assertTrue(set(script.CAMPOS_CAIXA).issubset(campos))
                    self.assertTrue({"classe", "indice_deteccao", "centroide_x_px", "centroide_y_px",
                                     "area_pixels", "caixa_centro_x_norm", "caixa_altura_norm"}.issubset(campos))
                elif nome == "por_quadro":
                    self.assertTrue({"tempo_decodificador_segundos", "tempo_detector_ns", "f1_individuos",
                                     "f1_aglomerados", "recall_classe_2", "acuracia_condicional"}.issubset(campos))

    def test_abertura_de_tabelas_nao_sobrescreve_resultados(self):
        with tempfile.TemporaryDirectory() as temporario:
            pasta = Path(temporario)
            arquivo = pasta / "deteccoes.csv"
            arquivo.write_bytes(b"preservar")
            with ExitStack() as pilha, self.assertRaises(FileExistsError):
                script.abrir_tabelas(pasta, pilha)
            self.assertEqual(arquivo.read_bytes(), b"preservar")

    def test_json_rejeita_duplicatas_nao_finitos_e_lista(self):
        for conteudo in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'):
            with self.subTest(conteudo=conteudo), self.assertRaises(ValueError):
                script.carregar_json(conteudo)


if __name__ == "__main__":
    unittest.main()
