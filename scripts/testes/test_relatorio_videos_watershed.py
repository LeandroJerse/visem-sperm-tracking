"""Relatório de vídeos com métricas artificiais; não executa a base de pesquisa."""

from contextlib import ExitStack
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from analise import relatorio_videos_watershed as r
from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import avaliar, agregar
from scripts.watershed import planejamento_videos as p
from scripts.watershed.planejamento import bytes_json, sha
from scripts.blobs.executar_inspecao import colunas_metricas
from scripts.testes.test_relatorio_selecao_blobs import bytes_csv

PROJETO = Path(__file__).resolve().parents[2]


def criar_fixture(raiz, vazio=False):
    """Copia a proveniência aprovada, mas fabrica métricas/mídias para testar o PDF."""
    plano_bytes = p.PLANO.read_bytes()
    plano = json.loads(plano_bytes)
    pasta = raiz / "resultados/videos/watershed/selecao/batch__sintetico"
    pasta.mkdir(parents=True)
    saidas, execucoes, resumos, por_video = {}, [], [], []
    hashes = {"scripts/watershed/videos/plano_selecao.json": sha(plano_bytes)}

    def gravar(path, blob):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        saidas[path.relative_to(raiz).as_posix()] = sha(blob)

    gravar(pasta / "plano.json", plano_bytes)
    for n, f in plano["proveniencia"]["fontes"].items():
        blob = (PROJETO / f["arquivo"]).read_bytes()
        gravar(pasta / "origens" / (n + Path(f["arquivo"]).suffix), blob)
        hashes[f["arquivo"]] = f["sha256"]
    for v in plano["videos"]:
        for item in (v, *v["anotacoes"], *v["referencias_alinhamento"]):
            hashes[item.get("arquivo", item.get("imagem"))] = item["sha256"]
    pixels = [{"video_id": v["video_id"], "quadro": q, "sha256_bgr": "0" * 64}
              for v in plano["videos"] for q in range(v["quantidade_quadros"])]
    pixel_bytes = bytes_csv(pixels)
    gravar(pasta / "conferencia/quadros_decodificados.csv", pixel_bytes)
    gravar(pasta / "conferencia/conferencia.json", bytes_json({
        "situacao": "concluida",
        "metodo": "MAE em cinza contra todos os quadros; índice previsto deve ser mínimo único.",
        "quadros_decodificados_sha256": sha(pixel_bytes), "referencias": [{}] * 20}))
    buffer = BytesIO()
    with ZipFile(buffer, "w") as z:
        z.writestr("sintetico.py", b"# fixture de teste\n")
    codigo = buffer.getvalue()
    gravar(pasta / "codigo.zip", codigo)
    for i, item in enumerate(plano["configuracoes"]):
        ident = item["id"]
        local = pasta / f"{ident}__sintetico"
        local_rel = local.relative_to(raiz).as_posix()
        gravar(local / "configuracao.json", bytes_json(item))
        execucoes.append({"configuracao_id": ident, "pasta": local_rel})
        linhas, todas, medias, aval_por_video = [], [], [], {}
        diag = dict.fromkeys(r.DIAGNOSTICO, 0)
        for j, video in enumerate(plano["videos"]):
            v, n = video["video_id"], video["quantidade_quadros"]
            reais = [] if vazio else [Objeto(0, 0, 10, 10, 12, 12), Objeto(1, 2, 50, 50, 6, 6), Objeto(2, 1, 100, 100, 40, 40)]
            previstas = [] if vazio else ([Objeto(0, 2 if i % 2 else 0, 10, 10, 12, 12)] +
                ([Objeto(1, 0, 50, 50, 6, 6)] if (i + j) % 2 else []) +
                [Objeto(k + 2, 0, 200 + 20*k, 20, 10, 10) for k in range((i + j) % 3)])
            a = avaliar(reais, previstas)
            d = {"componentes": len(previstas), "sementes": len(previstas),
                 "componentes_preservados": 0, "regioes_candidatas": len(previstas),
                 "deteccoes": len(previstas), "rejeitadas_area": 0, "tempo_detector_ns": (i + 1) * 123456}
            for q in range(n):
                linhas.append({"video": video["arquivo"], "anotacao": video["anotacoes"][q]["arquivo"],
                    "video_id": v, "quadro": q, "tempo_segundos": q / video["fps"],
                    "imagem_largura_px": 640, "imagem_altura_px": 480,
                    "quantidade_anotacoes": len(reais), "quantidade_deteccoes": len(previstas),
                    "tempo_decodificador_segundos": q / video["fps"], **d,
                    "limiar_otsu_original": 100, "deslocamento_otsu": item["parametros"]["deslocamento_otsu"],
                    "limiar_efetivo": 100 + item["parametros"]["deslocamento_otsu"],
                    "pixels_mascara": 100, "pixels_imagem": 640 * 480,
                    "fracao_pixels_mascara": 100 / (640 * 480), **colunas_metricas(a)})
            agregado = agregar([a] * n)
            aval_por_video[v] = agregado
            todas.extend([a] * n)
            por_video.append({"configuracao_id": ident, "pasta_origem": local_rel, "video_id": v,
                "quantidade_quadros": n, **{k: d[k] * n for k in r.DIAGNOSTICO}, **colunas_metricas(agregado)})
            for k in diag:
                diag[k] += d[k] * n
            media = local / "midia" / f"{ident}__video-{v}.mp4"
            blob = f"Mídia artificial para teste de hash: {ident}/{v}".encode()
            gravar(media, blob)
            medias.append({"video_id": v, "arquivo": media.relative_to(raiz).as_posix(),
                "quantidade_quadros": n, "fps": video["fps"], "largura": 1280, "altura": 584,
                "codec_solicitado": "mp4v", "decodificacao_conferida": True, "sha256": sha(blob)})
        total = agregar(todas)
        gravar(local / "por_quadro.csv", bytes_csv(linhas))
        gravar(local / "avaliacao.json", bytes_json({"criterios": r.CRITERIOS, "total": total, "por_video": aval_por_video}))
        gravar(local / "execucao.json", bytes_json({"situacao": "concluida", "configuracao_id": ident,
            "configuracao_sha256": item["parametros_sha256"], "plano_sha256": sha(plano_bytes),
            "batch": pasta.relative_to(raiz).as_posix(), "quadros_concluidos": 5850, "videos": medias}))
        resumos.append({"configuracao_id": ident, "pasta_origem": local_rel, "bloco": item["bloco"],
            "quantidade_quadros": 5850, **diag, **colunas_metricas(total)})
    gravar(pasta / "resumo_configuracoes.csv", bytes_csv(resumos))
    gravar(pasta / "resumo_por_video.csv", bytes_csv(por_video))
    gravar(pasta / "ranking.csv", bytes_csv(r.ordenar_por_f1(resumos)))
    manifesto = {"versao": 1, "tipo": "videos_selecao_watershed", "etapa": "selecao_videos",
        "particao": "selecao", "algoritmo": "watershed", "situacao": "concluida", "criterios": r.CRITERIOS,
        "configuracoes_previstas": 5, "configuracoes_concluidas": 5, "quadros_por_configuracao": 5850,
        "avaliacoes_concluidas": 29250, "videos_concluidos": 20, "alinhamento_conferido": True,
        "plano_sha256": sha(plano_bytes), "origens_sha256": hashes, "saidas_sha256": saidas,
        "pasta_origens": "origens", "execucoes": execucoes,
        "codigo": {"sha256_zip": sha(codigo), "sha256_arquivos": {"sintetico.py": sha(b"# fixture de teste\n")}}}
    (pasta / "execucao.json").write_bytes(bytes_json(manifesto))
    return pasta


class RelatorioVideosWatershedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.raiz = Path(cls.temp.name)
        cls.pasta = criar_fixture(cls.raiz)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(r, "RAIZ", self.raiz))
        stack.enter_context(patch.object(r, "SAIDA", self.pasta.parent))

    def adulterar(self, path, blob):
        original = path.read_bytes()
        manifesto_path = self.pasta / "execucao.json"
        manifesto_original = manifesto_path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        self.addCleanup(manifesto_path.write_bytes, manifesto_original)
        path.write_bytes(blob)
        m = json.loads(manifesto_original)
        m["saidas_sha256"][path.relative_to(self.raiz).as_posix()] = sha(blob)
        manifesto_path.write_bytes(bytes_json(m))

    def test_confere_29250_metricas_20_midias_e_pdf(self):
        dados = r.carregar(self.pasta)
        self.assertEqual(len(dados["midias"]), 20)
        self.assertEqual(len(dados["por_video"]), 20)
        antes = (self.pasta / "execucao.json").read_bytes()
        pdf1 = r.gerar_relatorio(self.pasta)
        pdf2 = r.gerar_relatorio(self.pasta)
        self.assertNotEqual(pdf1, pdf2)
        self.assertTrue(pdf1.read_bytes().startswith(b"%PDF-"))
        self.assertEqual((self.pasta / "execucao.json").read_bytes(), antes)
        registro = json.loads((pdf1.parent / "relatorio.json").read_bytes())
        self.assertEqual(registro["paginas"], 4)

    def test_recusa_sequencia_incompleta_mesmo_com_hash_atualizado(self):
        path = next(self.pasta.glob("s063*/por_quadro.csv"))
        linhas = r._csv(path.read_bytes())
        self.adulterar(path, bytes_csv(linhas[:-1]))
        with self.assertRaisesRegex(ValueError, "Sequência"):
            r.carregar(self.pasta)

    def test_recusa_metrica_e_tempo_inconsistentes(self):
        path = next(self.pasta.glob("s063*/por_quadro.csv"))
        linhas = r._csv(path.read_bytes())
        linhas[0]["tempo_segundos"] = "1"
        self.adulterar(path, bytes_csv(linhas))
        with self.assertRaisesRegex(ValueError, "Tempo"):
            r.carregar(self.pasta)

    def test_recusa_segmentacao_inconsistente(self):
        path = next(self.pasta.glob("s063*/por_quadro.csv"))
        linhas = r._csv(path.read_bytes())
        linhas[0]["limiar_efetivo"] = "100"
        self.adulterar(path, bytes_csv(linhas))
        with self.assertRaisesRegex(ValueError, "segmentação"):
            r.carregar(self.pasta)

    def test_recusa_ranking_falso(self):
        path = self.pasta / "ranking.csv"
        self.adulterar(path, bytes_csv(list(reversed(r._csv(path.read_bytes())))))
        with self.assertRaisesRegex(ValueError, "Ranking"):
            r.carregar(self.pasta)

    def test_recusa_video_trocado(self):
        path = next(self.pasta.glob("s063*/midia/*.mp4"))
        self.adulterar(path, b"alterado")
        with self.assertRaisesRegex(ValueError, "mídia"):
            r.carregar(self.pasta)

    def test_recusa_configuracao_trocada(self):
        path = next(self.pasta.glob("s063*/configuracao.json"))
        item = json.loads(path.read_bytes())
        item["parametros"]["deslocamento_otsu"] = 0
        self.adulterar(path, bytes_json(item))
        with self.assertRaisesRegex(ValueError, "Configuração"):
            r.carregar(self.pasta)

    def test_recusa_codigo_trocado(self):
        path = self.pasta / "codigo.zip"
        self.adulterar(path, b"codigo diferente")
        with self.assertRaisesRegex(ValueError, "código"):
            r.carregar(self.pasta)

    def test_sem_casos_e_empates(self):
        linhas = [{"configuracao_id": i, "tp_individuos": 0, "fp_individuos": 0, "fn_individuos": 0} for i in p.IDS]
        self.assertTrue(all(x["posicao"] is None for x in r.ordenar_por_f1(linhas)))
        for x in linhas:
            x.update(tp_individuos=1, fn_individuos=1)
        self.assertEqual({x["posicao"] for x in r.ordenar_por_f1(linhas)}, {1})
        self.assertEqual(r._valor(""), "sem casos")


if __name__ == "__main__":
    unittest.main()

