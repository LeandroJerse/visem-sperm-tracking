"""Plano, execução sintética e relatório completo do round5."""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2

from analise import relatorio_round5_watershed as pdf
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.limiarizacao.inspecionar_imagem import ler_anotacoes
from scripts.testes.test_round2_watershed import imagem
from scripts.testes.test_relatorio_round2_watershed import montar_relatorio_sintetico
from scripts.watershed import execucao_round5 as runner
from scripts.watershed import planejamento_round5 as desenho
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, bytes_json, sha

PLANO_REAL = runner.PLANO


def plano():
    return carregar_json(PLANO_REAL.read_bytes())


def origens_sinteticas(p, codigo):
    """Manifesto e artefatos fictícios; parâmetros e composição vêm do plano."""
    p2bytes = (desenho.RAIZ / desenho.ROUND4 / "plano.json").read_bytes()
    p1bytes = (desenho.RAIZ / desenho.ROUND4 / "origens/round1_plano.json").read_bytes()
    m2 = {"situacao": "concluida", "avaliacoes_concluidas": 3204, "configuracoes_concluidas": 18,
          "criterios": runner.comum.CRITERIOS, "plano_sha256": sha(p2bytes), "codigo": {"sha256_zip": sha(codigo)},
          "execucoes": [{"configuracao_id": c["referencia_round4"], "pasta": "sintetico/"+c["referencia_round4"]}
                       for c in p["configuracoes"][:6]],
          "saidas_sha256": {f["arquivo"]: f["sha256"] for f in p["fontes_controles"]}}
    mbytes = bytes_json(m2)
    return {"round4_plano.json": p2bytes, "round4_execucao.json": mbytes, "round4_codigo.zip": codigo,
            "round1_plano.json": p1bytes,
            "round3_plano.json": (desenho.RAIZ / desenho.ROUND4 / "origens/round3_plano.json").read_bytes(),
            "round2_plano.json": (desenho.RAIZ / desenho.ROUND4 / "origens/round2_plano.json").read_bytes(),
            "estatisticas_round4.json": bytes_json({"manifesto_sha256": sha(mbytes), "situacao": "conferida"})}


class PlanoTest(unittest.TestCase):
    def test_reproducao_referencias_e_oito_configuracoes_novas(self):
        p = plano()
        self.assertEqual(p, desenho.construir_plano())
        self.assertEqual(len(p["configuracoes"]), 14)
        self.assertEqual(len(p["fontes_controles"]), 4272)
        self.assertEqual(len({c["parametros_sha256"] for c in p["configuracoes"]}), 14)
        self.assertEqual([c["referencia_round4"] for c in p["configuracoes"][:6]], list(desenho.CONTROLES))
        p2 = carregar_json((desenho.RAIZ / desenho.ROUND4 / "plano.json").read_bytes())
        conhecidos = {c["parametros_sha256"] for c in p2["configuracoes"]}
        self.assertEqual(sum(c["parametros_sha256"] in conhecidos for c in p["configuracoes"]), 6)
        for i in range(0, 14, 2):
            a, b = [deepcopy(c["parametros"]) for c in p["configuracoes"][i:i+2]]
            self.assertEqual(a["watershed"].pop("politica_aglomerados"), "separar")
            self.assertEqual(b["watershed"].pop("politica_aglomerados"), "preservar_por_area")
            self.assertEqual(a, b)

    def test_contrastes_mudam_somente_o_eixo_declarado(self):
        itens = {c["id"]: c for c in plano()["configuracoes"]}
        contrastes = plano()["contrastes"]
        self.assertEqual(len(contrastes), 14)
        self.assertEqual(len({(c["referencia"], c["nova"]) for c in contrastes}), 14)
        for c in contrastes:
            a = deepcopy(itens[c["referencia"]]["parametros"]); b = deepcopy(itens[c["nova"]]["parametros"])
            if c["eixo"] == "area":
                self.assertNotEqual(a["watershed"]["segmentacao"].pop("area_minima"), b["watershed"]["segmentacao"].pop("area_minima"))
            elif c["eixo"] == "semente":
                self.assertNotEqual(a["watershed"].pop("fracao_semente"), b["watershed"].pop("fracao_semente"))
            elif c["eixo"] == "fechamento":
                self.assertNotEqual(a["watershed"]["segmentacao"]["fechamento"].pop("tamanho"), b["watershed"]["segmentacao"]["fechamento"].pop("tamanho"))
            else:
                self.assertNotEqual(a.pop("deslocamento_otsu"), b.pop("deslocamento_otsu"))
            self.assertEqual(a, b)
        for c in itens.values():
            if c["contraste_com"]:
                self.assertIn({"referencia":c["contraste_com"], "nova":c["id"], "eixo":c["bloco"]}, contrastes)

    def test_combinacao_tripla_tem_duas_referencias_sem_confundir_efeitos(self):
        p = plano()
        for i in (0, 1):
            nova = f"r5c{11+i:02}"
            refs = {c["referencia"] for c in p["contrastes"] if c["nova"] == nova}
            self.assertEqual(refs, {f"r5c{7+i:02}", f"r5c{9+i:02}"})
        p["contrastes"][8]["referencia"] = "r5c01"
        with self.assertRaisesRegex(ValueError, "Contrastes"):
            desenho.validar_plano(p)

    def test_recusa_alteracoes_reservados_e_controles_ausentes(self):
        for mudar in (lambda p:p.update(seed=True), lambda p:p["quadros"][0].update(video_id="14"),
                      lambda p:p["fontes_controles"].pop(), lambda p:p["configuracoes"][6]["parametros"]["watershed"]["segmentacao"].update(area_minima=107),
                      lambda p:p["configuracoes"][6].update(contraste_com="r5c05")):
            p = plano(); mudar(p)
            with self.assertRaises(ValueError): desenho.validar_plano(p)

    def test_plano_inconsistente_para_antes_de_detector(self):
        with patch.object(runner, "construir_plano", return_value={}), patch.object(runner.base, "executar_quadro") as detectar:
            with self.assertRaisesRegex(ValueError, "congelada"): runner.congelar_entradas()
            detectar.assert_not_called()

    def test_dispatch_conferencia_e_recuperacao_pdf(self):
        with patch.object(runner, "executar_argumentos", return_value=0) as executar:
            self.assertEqual(runner.comum.main(["--rodada", "round5", "--conferir"]), 0)
            self.assertTrue(executar.call_args.args[0].conferir)
            self.assertEqual(runner.comum.main(["--rodada", "round5", "--somente-relatorio", "batch"]), 0)
            self.assertEqual(executar.call_args.args[0].somente_relatorio, Path("batch"))


class ExecucaoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="watershed_round5_sintetico_")
        self.addCleanup(self.tmp.cleanup); self.raiz = Path(self.tmp.name).resolve()
        self.saida = self.raiz / "resultados/frame-to-frame/watershed/round5"
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner.comum, "RAIZ", self.raiz))
        self.stack.enter_context(patch.object(runner, "SAIDA", self.saida))
        p = plano(); p["quadros"] = p["quadros"][:2]; p["fontes_controles"] = []
        ok, png = cv2.imencode(".png", imagem()); self.assertTrue(ok)
        an = b"0 0.2 0.25 0.2 0.25\n"
        entradas = [{"quadro":q, "imagem_bytes":png.tobytes(), "anotacao_bytes":an, "anotacoes":ler_anotacoes(an)} for q in p["quadros"]]
        for item in p["configuracoes"][:6]:
            for e in entradas:
                q = e["quadro"]; destino = self.raiz/"referencia"/item["id"]/str(q["quadro"])
                runner.base.executar_quadro(runner.comum.decodificar(e), item, runner.configuracao_de_dict(item["parametros"]), destino)
                for n in ARQUIVOS_CONTROLE:
                    p["fontes_controles"].append({"configuracao_id":item["id"], "video_id":q["video_id"], "quadro":q["quadro"],
                                                "nome":n, "sha256":sha((destino/n).read_bytes())})
        self.dados = {"plano":p, "plano_bytes":bytes_json(p), "entradas":entradas, "origens":{}, "hashes":{},
                      "codigo":{"sintetico.txt":b"Teste"}, "dependencias":runner.comum.dependencias()}

    def rodar(self):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()): return runner.processar(self.dados)

    def test_14_configuracoes_controles_e_reexecucao_sinteticas(self):
        with patch.object(pdf, "gerar_relatorio", return_value="sintetico.pdf"):
            pasta = self.rodar(); segunda = self.rodar()
        self.assertNotEqual(pasta, segunda)
        m = carregar_json((pasta/"execucao.json").read_bytes())
        self.assertEqual(m["situacao"], "concluida"); self.assertEqual(m["avaliacoes_concluidas"], 28)
        self.assertEqual(carregar_json((pasta/"controles.json").read_bytes())["casos_conferidos"], 12)
        for nome, digest in m["saidas_sha256"].items(): self.assertEqual(sha((self.raiz/nome).read_bytes()), digest)
        tabelas = [pdf.base._csv((pasta/n).read_bytes()) for n in
                   ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv", "ranking.csv")]
        pdf.base.conferir_tabelas(self.dados["plano"], *tabelas)
        self.assertEqual(len(list(pasta.rglob("segmentacao.json"))), 28)
        self.assertIn("otsu-dm5", m["execucoes"][12]["pasta"])

    def test_falha_controle_e_interrupcao_preservam_parciais(self):
        self.dados["plano"]["fontes_controles"][0]["sha256"] = "0"*64
        with patch.object(pdf, "gerar_relatorio") as gerar:
            with self.assertRaisesRegex(ValueError, "diverge do round4"): self.rodar()
            gerar.assert_not_called()
        with patch.object(runner.base, "executar_quadro", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.rodar()
        estados = {carregar_json((b/"execucao.json").read_bytes())["situacao"] for b in self.saida.glob("batch__*")}
        self.assertEqual(estados, {"falhou", "interrompida"})

    def test_pdf_falha_sem_invalidar_metricas(self):
        with patch.object(pdf, "gerar_relatorio", side_effect=RuntimeError("Teste")): pasta = self.rodar()
        self.assertEqual(carregar_json((pasta/"execucao.json").read_bytes())["situacao"], "concluida")
        self.assertEqual(carregar_json((pasta/"relatorio.json").read_bytes())["situacao"], "falhou")


class RelatorioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="pdf_round5_sintetico_"); cls.raiz = Path(cls.tmp.name).resolve()
        cls.batch = montar_relatorio_sintetico(cls.raiz, plano(), origens_sinteticas)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(pdf.base, "RAIZ", self.raiz))
        self.stack.enter_context(patch.object(pdf, "SAIDA", self.batch.parent))
        self.stack.enter_context(patch.object(desenho, "MANIFESTO_SHA256", sha((self.batch/"origens/round4_execucao.json").read_bytes())))

    def test_pdf_completo_e_recuperacao(self):
        d = pdf.carregar(self.batch)
        self.assertEqual(len(d["quadros"]), 2492); self.assertEqual(len(d["videos"]), 168)
        self.assertEqual(d["controles"]["casos_conferidos"], 1068)
        primeiro, segundo = pdf.gerar_relatorio(self.batch), pdf.gerar_relatorio(self.batch)
        self.assertNotEqual(primeiro, segundo)
        r = carregar_json((segundo.parent/"relatorio.json").read_bytes())
        self.assertEqual(r["paginas"], 5); self.assertEqual(r["pdf_sha256"], sha(segundo.read_bytes()))

    def test_recusa_batch_incompleto_controle_e_metadados_alterados(self):
        for nome, mudar, erro in (
            ("execucao.json", lambda b:bytes_json({**carregar_json(b),"avaliacoes_concluidas":2491}), "incompleta"),
            ("r5c06/quadros/11_frame_0/predicoes.txt", lambda b:b+b"alterado", "Saída alterada"),
            ("r5c14/quadros/11_frame_0/segmentacao.json", lambda b:b+b"alterado", "Saída alterada")):
            f = self.batch/nome; b = f.read_bytes()
            try:
                f.write_bytes(mudar(b))
                with self.assertRaisesRegex(ValueError, erro): pdf.carregar(self.batch)
            finally: f.write_bytes(b)

    def test_origem_controle_fora_manifesto_e_ranking_inconsistente(self):
        p = carregar_json((self.batch/"plano.json").read_bytes())
        fontes = {n:(self.batch/"origens"/n).read_bytes() for n in p["origens"]}
        p["fontes_controles"][0]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "manifesto histórico"): desenho.conferir_origens(p, fontes)
        d = pdf.carregar(self.batch); d["ranking"][0]["posicao"] = "2"
        with self.assertRaisesRegex(ValueError, "Ranking diverge"):
            pdf.base.conferir_tabelas(d["plano"], d["resumos"], d["quadros"], d["videos"], d["ranking"])


if __name__ == "__main__": unittest.main()
