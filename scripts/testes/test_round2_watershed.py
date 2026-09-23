"""Verificações sintéticas do Otsu ajustado, protocolo e saídas do round2."""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
from dataclasses import asdict, replace
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from algoritmos.classicos import variantes_watershed as variante
from algoritmos.classicos.watershed import inspecionar as original
from analise import relatorio_round2_watershed as pdf
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.limiarizacao.inspecionar_imagem import ler_anotacoes
from scripts.watershed import execucao_round2 as runner
from scripts.watershed import planejamento_round2 as desenho
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, bytes_json, sha

PLANO_REAL = runner.PLANO


def plano():
    return carregar_json(PLANO_REAL.read_bytes())


def imagem():
    im = np.full((80, 100), 45, np.uint8)
    im[10:30, 10:30] = 140
    im[16:25, 20:42] = 240
    im[50:56, 60:66] = 200
    return im


class VarianteTest(unittest.TestCase):
    def setUp(self):
        self.config = variante.configuracao_de_dict(plano()["configuracoes"][0]["parametros"])

    def comparar(self, a, b):
        for campo in ("mascara", "distancia", "componentes", "marcadores", "regioes"):
            np.testing.assert_array_equal(getattr(a, campo), getattr(b, campo))
        self.assertEqual(list(a.resultado.registros()), list(b.resultado.registros()))
        self.assertEqual(a.candidatos, b.candidatos)
        self.assertEqual(a.componentes_info, b.componentes_info)

    def test_zero_identico_gray_bgr_ambas_politicas_e_imagem_preservada(self):
        for politica in ("separar", "preservar_por_area"):
            c = replace(self.config, watershed=replace(self.config.watershed, politica_aglomerados=politica))
            for im in (imagem(), cv2.cvtColor(imagem(), cv2.COLOR_GRAY2BGR)):
                antes = im.copy()
                with patch.object(variante, "original", wraps=original) as chamado:
                    d, m = variante.inspecionar(im, c)
                chamado.assert_called_once()
                self.assertIs(chamado.call_args.args[1], c.watershed)
                self.comparar(d, original(im, c.watershed))
                np.testing.assert_array_equal(antes, im)
                self.assertEqual(m["limiar_efetivo"], m["limiar_otsu_original"])

    def test_ajuste_antes_da_morfologia_clamp_e_medidas_na_imagem_original(self):
        im = imagem()
        t = int(cv2.threshold(im, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY)[0])
        for delta in (-255, -20, -10, 10, 20, 255):
            efetivo = min(255, max(0, t + delta))
            c = replace(self.config, deslocamento_otsu=delta)
            d, m = variante.inspecionar(im, c)
            manual = replace(c.watershed, segmentacao=replace(c.watershed.segmentacao,
                              metodo="manual", limiar_manual=efetivo))
            self.comparar(d, original(im, manual))
            self.assertEqual(m["limiar_efetivo"], efetivo)
            self.assertEqual(m["pixels_mascara"], int(np.count_nonzero(d.mascara)))
            self.assertEqual(m["fracao_pixels_mascara"], m["pixels_mascara"]/im.size)

    def test_uniforme_e_sem_deteccoes_ainda_tem_metadados(self):
        for intensidade in (0, 255):
            d, m = variante.inspecionar(np.full((30, 30), intensidade, np.uint8),
                                       replace(self.config, deslocamento_otsu=255))
            self.assertEqual(list(d.resultado.registros()), [])
            self.assertEqual(m["limiar_efetivo"], 255)
            self.assertEqual(m["fracao_pixels_mascara"], 0)

    def test_rejeita_config_incompleta_manual_bool_float_e_imagem_invalida(self):
        p = asdict(self.config)
        for delta in (True, 1.0, -256, 256, None, "10"):
            with self.assertRaises(ValueError):
                variante.configuracao_de_dict({**p, "deslocamento_otsu": delta})
        with self.assertRaises(ValueError):
            variante.configuracao_de_dict({**p, "desconhecido": 1})
        with self.assertRaises(ValueError):
            variante.configuracao_de_dict({"watershed": p["watershed"]})
        manual = deepcopy(p); manual["watershed"]["segmentacao"].update(metodo="manual", limiar_manual=120)
        with self.assertRaises(ValueError):
            variante.configuracao_de_dict(manual)
        for im in (np.empty((0, 10), np.uint8), np.zeros((10, 10), float), np.zeros((10, 10, 4), np.uint8)):
            for delta in (0, 10):
                with self.assertRaises(ValueError):
                    variante.inspecionar(im, replace(self.config, deslocamento_otsu=delta))


class PlanejamentoTest(unittest.TestCase):
    def test_plano_reproduzido_pares_e_quatro_controles_exatos(self):
        p = plano()
        self.assertEqual(p, desenho.construir_plano())
        anterior = carregar_json((desenho.RAIZ / desenho.ROUND1 / "plano.json").read_bytes())
        conhecidos = {hash_configuracao({"watershed": c["parametros"], "deslocamento_otsu": 0})
                      for c in anterior["configuracoes"]}
        self.assertEqual(sum(c["parametros_sha256"] in conhecidos for c in p["configuracoes"]), 4)
        self.assertEqual(len({c["parametros_sha256"] for c in p["configuracoes"]}), 32)
        self.assertEqual(len(p["fontes_controles"]), 2848)
        for i in range(0, 32, 2):
            a, b = [deepcopy(x["parametros"]) for x in p["configuracoes"][i:i+2]]
            self.assertEqual(a["watershed"].pop("politica_aglomerados"), "separar")
            self.assertEqual(b["watershed"].pop("politica_aglomerados"), "preservar_por_area")
            self.assertEqual(a, b)

    def test_recusa_plano_alterado_dados_reservados_e_controle_incompleto(self):
        for mudar in (lambda p: p.update(seed=True), lambda p: p["quadros"][0].update(video_id="14"),
                      lambda p: p["configuracoes"][16]["parametros"].update(deslocamento_otsu=-30),
                      lambda p: p["fontes_controles"].pop(), lambda p: p.update(exclusoes=[])):
            p = plano(); mudar(p)
            with self.assertRaises(ValueError): desenho.validar_plano(p)

    def test_rejeicao_antes_de_qualquer_detector(self):
        with patch.object(runner, "construir_plano", return_value={}), patch.object(runner, "executar_quadro") as detectar:
            with self.assertRaisesRegex(ValueError, "congelada"): runner.congelar_entradas()
            detectar.assert_not_called()

    def test_dispatch_preserva_round1_e_round2(self):
        with patch.object(runner, "executar_argumentos", return_value=0) as executar:
            self.assertEqual(runner.comum.main(["--rodada", "round2", "--conferir"]), 0)
            self.assertTrue(executar.call_args.args[0].conferir)


class SaidasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="watershed_round2_sintetico_")
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        self.saida = self.raiz / "resultados/frame-to-frame/watershed/round2"
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner.comum, "RAIZ", self.raiz))
        self.stack.enter_context(patch.object(runner.comum.inspecao, "RAIZ", self.raiz))
        self.stack.enter_context(patch.object(runner, "SAIDA", self.saida))
        p = plano(); p["configuracoes"] = p["configuracoes"][:2] + p["configuracoes"][16:17]
        p["quadros"] = p["quadros"][:2]; p["fontes_controles"] = []
        ok, png = cv2.imencode(".png", imagem()); self.assertTrue(ok)
        anotacao = b"0 0.2 0.25 0.2 0.25\n"
        entradas = [{"quadro": q, "imagem_bytes": png.tobytes(), "anotacao_bytes": anotacao,
                     "anotacoes": ler_anotacoes(anotacao)} for q in p["quadros"]]
        for item in p["configuracoes"][:2]:
            config = variante.configuracao_de_dict(item["parametros"]).watershed
            for entrada in entradas:
                q = entrada["quadro"]; destino = self.raiz / "referencia" / item["id"] / str(q["quadro"])
                runner.comum.inspecao.executar_quadro(runner.comum.decodificar(entrada), item, config, destino)
                for n in ARQUIVOS_CONTROLE:
                    p["fontes_controles"].append({"configuracao_id": item["id"], "video_id": q["video_id"],
                        "quadro": q["quadro"], "nome": n, "sha256": sha((destino/n).read_bytes())})
        self.dados = {"plano": p, "plano_bytes": bytes_json(p), "entradas": entradas, "origens": {},
                      "hashes": {}, "codigo": {"teste.txt": b"Sintetico"}, "dependencias": runner.comum.dependencias()}

    def rodar(self):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()): return runner.processar(self.dados)

    def test_controles_iguais_metadados_tabelas_e_repeticao_preservada(self):
        with patch.object(pdf, "gerar_relatorio", return_value="sintetico.pdf"):
            pasta = self.rodar(); repeticao = self.rodar()
        self.assertNotEqual(pasta, repeticao)
        m = carregar_json((pasta/"execucao.json").read_bytes())
        self.assertEqual(m["situacao"], "concluida"); self.assertEqual(m["avaliacoes_concluidas"], 6)
        for nome, digest in m["saidas_sha256"].items(): self.assertEqual(sha((self.raiz/nome).read_bytes()), digest)
        self.assertEqual(carregar_json((pasta/"controles.json").read_bytes())["casos_conferidos"], 4)
        tabelas = [pdf.base._csv((pasta/n).read_bytes()) for n in
                   ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv", "ranking.csv")]
        pdf.base.conferir_tabelas(self.dados["plano"], *tabelas)
        self.assertEqual(len(list(pasta.rglob("segmentacao.json"))), 6)
        self.assertEqual(len(list(pasta.rglob("mapas.npz"))), 6)
        self.assertIn("otsu-dm20", m["execucoes"][2]["pasta"])
        for r in tabelas[1]:
            meta = carregar_json((self.raiz / r["pasta_quadro"] / "segmentacao.json").read_bytes())
            self.assertEqual(r["limiar_efetivo"], str(meta["limiar_efetivo"]))

    def test_falha_controle_preserva_parcial_e_nao_gera_pdf(self):
        self.dados["plano"]["fontes_controles"][0]["sha256"] = "0"*64
        with patch.object(pdf, "gerar_relatorio") as gerar:
            with self.assertRaisesRegex(ValueError, "diverge do round1"): self.rodar()
            gerar.assert_not_called()
        m = carregar_json((next(self.saida.glob("batch__*"))/"execucao.json").read_bytes())
        self.assertEqual(m["situacao"], "falhou")

    def test_interrupcao_preserva_parcial(self):
        with patch.object(runner, "executar_quadro", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.rodar()
        m = carregar_json((next(self.saida.glob("batch__*"))/"execucao.json").read_bytes())
        self.assertEqual(m["situacao"], "interrompida")

    def test_falha_pdf_preserva_metricas(self):
        with patch.object(pdf, "gerar_relatorio", side_effect=RuntimeError("teste")): pasta = self.rodar()
        self.assertEqual(carregar_json((pasta/"execucao.json").read_bytes())["situacao"], "concluida")
        self.assertEqual(carregar_json((pasta/"relatorio.json").read_bytes())["situacao"], "falhou")


if __name__ == "__main__": unittest.main()
