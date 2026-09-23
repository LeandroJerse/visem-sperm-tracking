"""Integração com mídia sintética e contratos do plano de vídeos de watershed."""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np

from scripts.watershed import executar_videos as s
from scripts.watershed import planejamento_videos as p
from scripts.watershed import executar_rodada as comum
from scripts.watershed.saidas_selecao import executar_quadro
from scripts.limiarizacao import executar_videos as base
from scripts.watershed.planejamento import bytes_json, sha

RAIZ = Path(__file__).resolve().parents[2]


def csv_ler(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def criar_dados(raiz):
    """Duas sequências de três frames fabricados; nenhum frame da base."""
    plano = json.loads(p.PLANO.read_bytes())
    hashes, anotacoes, imagens = {}, {}, {}
    videos = []
    for v in ("13", "29"):
        pasta = raiz / f"bases_de_dados/visem_tracking/dataset/Train/{v}"
        pasta.mkdir(parents=True)
        path = pasta / f"{v}.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (480, 80))
        if not writer.isOpened():
            raise RuntimeError("Codec MP4 indisponível no teste sintético.")
        try:
            for i in range(3):
                img = np.full((80, 480, 3), 30 + 60 * i, np.uint8)
                cv2.circle(img, (240, 40), 10, (255, 255, 255), -1)
                writer.write(img)
        finally:
            writer.release()
        refs, labels = [], []
        cap = cv2.VideoCapture(str(path))
        try:
            for q in range(3):
                ok, img = cap.read()
                assert ok
                imagens[v, q] = img
                jpeg = pasta / f"ref{q}.jpg"
                ok, buf = cv2.imencode(".jpg", img)
                assert ok
                jpeg.write_bytes(buf.tobytes())
                label = pasta / f"label{q}.txt"
                label.write_text(f"{q % 3} 0.5 0.5 0.05 0.3\n" if q < 2 else "", encoding="utf-8")
                anotacoes[v, q] = comum.ler_anotacoes(label.read_bytes())
                refs.append({"quadro": q, "imagem": jpeg.relative_to(raiz).as_posix(), "sha256": sha(jpeg.read_bytes())})
                labels.append({"quadro": q, "arquivo": label.relative_to(raiz).as_posix(), "sha256": sha(label.read_bytes())})
                for f in (jpeg, label):
                    hashes[f.relative_to(raiz).as_posix()] = sha(f.read_bytes())
        finally:
            cap.release()
        nome = path.relative_to(raiz).as_posix()
        hashes[nome] = base.hash_arquivo(path)
        videos.append({"video_id": v, "arquivo": nome, "sha256": hashes[nome], "fps": 10,
                       "largura": 480, "altura": 80, "quantidade_quadros": 3,
                       "indice_inicial": 0, "referencias_alinhamento": refs, "anotacoes": labels})
    plano["videos"] = videos
    plano["proveniencia"]["fontes"] = {"execucao_selecao": {"arquivo": "fonte.json"}}
    fonte = bytes_json({"dependencias": comum.dependencias()})
    (raiz / "fonte.json").write_bytes(fonte)
    hashes["fonte.json"] = sha(fonte)
    return {"plano": plano, "plano_bytes": bytes_json(plano), "hashes": hashes,
            "anotacoes": anotacoes, "codigo": {"sintetico.py": b"# fixture\n"},
            "origens": {"execucao_selecao": fonte}}, imagens


class PlanoVideosWatershedTest(unittest.TestCase):
    def test_reproducao_e_fontes_congeladas(self):
        plano = p.construir_plano()
        self.assertEqual(bytes_json(plano), p.PLANO.read_bytes())
        self.assertEqual(len(plano["proveniencia"]["fontes"]), 19)
        self.assertEqual([c["id"] for c in plano["configuracoes"]], list(p.IDS))
        self.assertEqual(sum(v["quantidade_quadros"] for v in plano["videos"]), 5850)

    def test_recusa_mudancas_em_parametros_ids_criterios_e_quadros(self):
        original = json.loads(p.PLANO.read_bytes())
        for campo in ("parametro", "ordem", "classe", "quadro", "final", "seed", "fontes"):
            with self.subTest(campo=campo):
                plano = deepcopy(original)
                if campo == "parametro":
                    plano["configuracoes"][0]["parametros"]["deslocamento_otsu"] += 1
                elif campo == "ordem":
                    plano["configuracoes"].reverse()
                elif campo == "classe":
                    plano["criterios"] = {}
                elif campo == "quadro":
                    plano["videos"][0]["anotacoes"].pop()
                elif campo == "final":
                    plano["particao"] = "final"
                elif campo == "seed":
                    plano["seed"] = 1
                else:
                    plano["proveniencia"]["fontes"]["origem_selecao"]["sha256"] = "0" * 64
                with self.assertRaises((ValueError, TypeError)):
                    p.validar_plano(plano)


class VideosWatershedTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.raiz = Path(temp.name)
        self.dados, self.imagens = criar_dados(self.raiz)
        self.saida = self.raiz / "resultados/videos/watershed/selecao"
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        for mod in (s, base, comum):
            contexts.enter_context(patch.object(mod, "RAIZ", self.raiz))
        contexts.enter_context(patch.object(s, "SAIDA", self.saida))

    def executar(self):
        with patch.object(s, "atualizar_relatorio", return_value=self.raiz / "pdf_sintetico.pdf"), redirect_stdout(StringIO()):
            return s.processar(self.dados, {"dependencias": comum.dependencias()})

    def test_integracao_mesmos_pixels_caixas_tempos_e_mp4(self):
        antes = {n: (self.raiz / n).read_bytes() for n in self.dados["hashes"]}
        pasta = self.executar()
        m = json.loads((pasta / "execucao.json").read_bytes())
        self.assertEqual(m["situacao"], "concluida")
        self.assertEqual((m["configuracoes_concluidas"], m["videos_concluidos"], m["avaliacoes_concluidas"]), (5, 10, 30))
        self.assertEqual(len(list(pasta.rglob("*.mp4"))), 10)
        for item, e in zip(self.dados["plano"]["configuracoes"], m["execucoes"]):
            local = self.raiz / e["pasta"]
            linhas = csv_ler(local / "por_quadro.csv")
            self.assertEqual([(x["video_id"], int(x["quadro"])) for x in linhas], [(v, q) for v in ("13", "29") for q in range(3)])
            det = csv_ler(local / "deteccoes.csv")
            for linha in linhas:
                v, q = linha["video_id"], int(linha["quadro"])
                registros, diag = s.processar_quadro(self.imagens[v, q], p.ler_configuracao(item["parametros"]))
                self.assertEqual(int(linha["quantidade_deteccoes"]), len(registros))
                self.assertEqual(float(linha["tempo_segundos"]), q / 10)
                for k, val in diag.items():
                    if k != "tempo_detector_ns":
                        self.assertEqual(linha[k], str(val))
                salvos = [x for x in det if x["video_id"] == v and int(x["quadro"]) == q]
                self.assertEqual(len(salvos), len(registros))
                for salvo, previsto in zip(salvos, registros):
                    for k, val in previsto.items():
                        self.assertEqual(salvo[k], "" if val is None else str(val))
            estado = json.loads((local / "execucao.json").read_bytes())
            self.assertTrue(all(x["decodificacao_conferida"] for x in estado["videos"]))
        for nome, digest in m["saidas_sha256"].items():
            self.assertEqual(base.hash_arquivo(self.raiz / nome), digest)
        for nome, blob in antes.items():
            self.assertEqual((self.raiz / nome).read_bytes(), blob)
        outra = self.executar()
        self.assertNotEqual(outra, pasta)

    def test_mesma_saida_da_selecao_em_imagens(self):
        for item in self.dados["plano"]["configuracoes"]:
            with self.subTest(id=item["id"]):
                config = p.ler_configuracao(item["parametros"])
                img = self.imagens["13", 0]
                anotacoes = base.caixas_anotadas(self.dados["anotacoes"]["13", 0], 480, 80)
                destino = self.raiz / item["id"]
                linha, _ = executar_quadro({"imagem": img, "anotacoes": anotacoes,
                    "quadro": {"video_id": "13", "quadro": 0, "imagem": "sintetica.png", "anotacao": "sintetica.txt"}},
                    item, config, destino)
                registros, diagnostico = s.processar_quadro(img, config)
                for a, b in zip(csv_ler(destino / "deteccoes.csv"), registros):
                    for k, valor in b.items():
                        self.assertEqual(a[k], "" if valor is None else str(valor))
                self.assertEqual(len(csv_ler(destino / "deteccoes.csv")), len(registros))
                for k, valor in diagnostico.items():
                    if k != "tempo_detector_ns":
                        self.assertEqual(linha[k], valor)

    def test_conferir_nao_decodifica_ou_detecta(self):
        class Captura:
            def get(self, prop):
                return {cv2.CAP_PROP_FRAME_WIDTH: 480, cv2.CAP_PROP_FRAME_HEIGHT: 80,
                        cv2.CAP_PROP_FRAME_COUNT: 3}[prop]
            def release(self):
                pass
            def read(self):
                raise AssertionError("Não deveria ler quadros.")
        with patch.object(base, "abrir_video", return_value=Captura()), patch.object(s, "inspecionar", side_effect=AssertionError):
            s.conferir_ambiente(self.dados)
        self.assertFalse(self.saida.exists())

    def test_falha_alignmento_interrompe_antes_da_deteccao(self):
        with patch.object(base, "conferir_alinhamento", side_effect=ValueError("alinhamento")), \
             patch.object(s, "processar_quadro") as detector, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with self.assertRaises(ValueError):
                self.executar()
        detector.assert_not_called()
        m = json.loads(next(self.saida.glob("batch__*/execucao.json")).read_bytes())
        self.assertEqual(m["situacao"], "falhou")
        self.assertEqual(m["avaliacoes_concluidas"], 0)

    def test_pixels_divergentes_e_interrupcao_preservam_falha(self):
        for erro in (ValueError("pixels divergentes"), KeyboardInterrupt()):
            with self.subTest(erro=type(erro).__name__), patch.object(s, "processar_quadro", side_effect=erro), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                with self.assertRaises(type(erro)):
                    self.executar()
        for f in self.saida.glob("batch__*/execucao.json"):
            self.assertEqual(json.loads(f.read_bytes())["situacao"], "falhou")

    def test_falha_pdf_nao_invalida_execucao(self):
        with patch.object(s, "atualizar_relatorio", side_effect=RuntimeError("pdf")), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            pasta = s.processar(self.dados, {"dependencias": comum.dependencias()})
        self.assertEqual(json.loads((pasta / "execucao.json").read_bytes())["situacao"], "concluida")

    def test_final_nao_preparado(self):
        with self.assertRaises(ValueError):
            s.especificacao_etapa("final")


if __name__ == "__main__":
    unittest.main()

