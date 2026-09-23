"""Fontes inteiramente sintéticas para integridade e PDF das 119 candidatas."""

from copy import deepcopy
import csv
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from analise import relatorio_selecao_blobs as relatorio
from scripts.testes.test_relatorio_rodada_blobs import _metricas


def bytes_json(valor):
    return (json.dumps(valor, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def bytes_csv(linhas):
    texto = StringIO(newline="")
    escritor = csv.DictWriter(texto, fieldnames=list(linhas[0]))
    escritor.writeheader(); escritor.writerows(linhas)
    return texto.getvalue().encode("utf-8-sig")


def somar_metricas(metricas):
    contagens = {c: sum(int(x[c]) for x in metricas) for c in relatorio.CONTAGENS}
    def razao(a, b):
        return a / b if b else ""
    saida = {}
    for grupo in ("individuos", "aglomerados"):
        tp, fp, fn = (contagens[f"{c}_{grupo}"] for c in ("tp", "fp", "fn"))
        saida.update({f"tp_{grupo}": tp, f"fp_{grupo}": fp, f"fn_{grupo}": fn,
                      f"precisao_{grupo}": razao(tp, tp + fp), f"recall_{grupo}": razao(tp, tp + fn),
                      f"f1_{grupo}": razao(2 * tp, 2 * tp + fp + fn),
                      f"situacao_f1_{grupo}": "definido" if 2 * tp + fp + fn else "sem_casos"})
    for classe in (0, 2, 1):
        for nome in ("anotacoes", "localizadas", "perdidas"):
            saida[f"{nome}_classe_{classe}"] = contagens[f"{nome}_classe_{classe}"]
        saida[f"recall_classe_{classe}"] = razao(contagens[f"localizadas_classe_{classe}"], contagens[f"anotacoes_classe_{classe}"])
    for nome in ("pares_corretos", "pares_incorretos", "pares_total"):
        saida[nome] = contagens[nome]
    saida["acuracia_condicional"] = razao(contagens["pares_corretos"], contagens["pares_total"])
    for nome in ("matriz_0_0", "matriz_0_2", "matriz_2_0", "matriz_2_2"):
        saida[nome] = contagens[nome]
    return saida


def criar_fixture(raiz, vazio=False):
    pasta = raiz / "resultados/frame-to-frame/blobs/selecao/batch__sintetico"
    pasta.mkdir(parents=True)
    quadros = [{"video_id": v, "quadro": q, "imagem": f"ficticio/{v}_{q}.jpg",
                "anotacao": f"ficticio/{v}_{q}.txt", "imagem_sha256": "0" * 64,
                "anotacao_sha256": "1" * 64} for v in relatorio.VIDEOS for q in range(0, 1401, 100)]
    configs = [{"id": f"s{i:03d}", "bloco": "exploracao", "perfil_forma": "sem_filtro", "referencia": None,
                "metodo": "simpleblob" if i <= 84 else "dog" if i <= 106 else "log",
                "preprocessamento": {"metodo": "nenhum"},
                "parametros": {"polaridade": "claro", "area_minima": i}, "caixa": {"modo": "margem", "pixels": 3}}
               for i in range(1, 120)]
    fontes = {"origem_desenvolvimento.json": bytes_json({"tipo": "fonte_sintetica"}),
              "origem_inspecao.json": bytes_json({"tipo": "inspecao_sintetica"}),
              "origem_quadros.json": bytes_json({"quadros": quadros})}
    mapa_origens = {"scripts/limiarizacao/rodadas/round1.json": relatorio.sha256(fontes["origem_desenvolvimento.json"]),
                   "scripts/blobs/inspecao/round0.json": relatorio.sha256(fontes["origem_inspecao.json"]),
                   "scripts/limiarizacao/selecao/plano.json": relatorio.sha256(fontes["origem_quadros.json"])}
    proveniencia = {c["id"]: {"configuracao_sha256": f"{i:064x}", "primeira_origem": None, "origens": []}
                   for i, c in enumerate(configs, 1)}
    origens_rodadas, numero = [], 0
    for r, n in enumerate((48, 32, 24, 18, 14), 1):
        rodada = f"round{r}"
        anteriores, execucoes, hashes = [], [], {}
        for j in range(1, n + 1):
            ident = f"s{numero % 119 + 1:03d}"
            base = deepcopy(configs[numero % 119]); numero += 1
            base["id"] = f"r{r}c{j:02d}"
            anteriores.append(base)
            local = f"resultados/frame-to-frame/blobs/{rodada}/{base['id']}__sintetico"
            alias = {"rodada": rodada, "configuracao_id": base["id"], "pasta_execucao": local,
                     "sha256_arquivo_configuracao": relatorio.sha256(bytes_json(base)),
                     "sha256_manifesto_execucao": relatorio.sha256(bytes_json({"id": base["id"]}))}
            prov = proveniencia[ident]
            prov["origens"].append(alias)
            if prov["primeira_origem"] is None:
                prov["primeira_origem"] = {k: alias[k] for k in ("rodada", "configuracao_id")}
            execucoes.append({"configuracao_id": base["id"], "pasta": local})
            hashes[local + "/configuracao.json"] = alias["sha256_arquivo_configuracao"]
            hashes[local + "/execucao.json"] = alias["sha256_manifesto_execucao"]
        anterior = {"rodada": rodada, "particao": "desenvolvimento", "configuracoes": anteriores,
                    "origem_desenvolvimento": {"plano": "scripts/limiarizacao/rodadas/round1.json", "sha256": mapa_origens["scripts/limiarizacao/rodadas/round1.json"]},
                    "origem_inspecao": {"plano": "scripts/blobs/inspecao/round0.json", "sha256": mapa_origens["scripts/blobs/inspecao/round0.json"]}}
        blob = bytes_json(anterior); digest = relatorio.sha256(blob)
        fontes[f"origem_{rodada}.json"] = blob
        execucao = {"rodada": rodada, "situacao": "concluida", "criterios": relatorio.CRITERIOS,
                    "plano_sha256": digest, "configuracoes_concluidas": n,
                    "quadros_por_configuracao": 178, "avaliacoes_concluidas": n * 178,
                    "execucoes": execucoes, "saidas_sha256": hashes}
        blob_exec = bytes_json(execucao)
        fontes[f"execucao_{rodada}.json"] = blob_exec
        origem = {"rodada": rodada, "plano": f"scripts/blobs/rodadas/{rodada}.json", "plano_sha256": digest,
                  "batch": f"resultados/frame-to-frame/blobs/{rodada}/batch__sintetico", "manifesto_sha256": relatorio.sha256(blob_exec)}
        origens_rodadas.append(origem)
        mapa_origens[origem["plano"]] = digest
        mapa_origens[origem["batch"] + "/execucao.json"] = origem["manifesto_sha256"]
    plano = {"versao": 1, "algoritmo": "blobs", "etapa": "selecao_imagens", "rodada": "selecao",
             "particao": "selecao", "criterios": relatorio.CRITERIOS, "seed": 42,
             "quadros": quadros, "configuracoes": configs, "proveniencia": proveniencia,
             "origem_quadros": {"plano": "scripts/limiarizacao/selecao/plano.json", "sha256": mapa_origens["scripts/limiarizacao/selecao/plano.json"]},
             "origens_rodadas": origens_rodadas}
    fontes["plano.json"] = bytes_json(plano)
    mapa_origens["scripts/blobs/selecao/plano.json"] = relatorio.sha256(fontes["plano.json"])
    for q in quadros:
        for tipo in ("imagem", "anotacao"):
            mapa_origens[q[tipo]] = q[f"{tipo}_sha256"]
    linhas, resumos, videos = [], [], []
    for i, item in enumerate(configs):
        origem = f"resultados/frame-to-frame/blobs/selecao/{item['id']}__sintetico"
        por_config = []
        for q in quadros:
            metricas = _metricas(i + relatorio.VIDEOS.index(q["video_id"]), vazio=vazio)
            linha = {"configuracao_id": item["id"], **{k: q[k] for k in ("imagem", "anotacao", "video_id", "quadro")},
                     "tempo_segundos": "", "pasta_quadro": f"{origem}/quadros/{q['video_id']}_frame_{q['quadro']}",
                     "quantidade_anotacoes": 0 if vazio else 4,
                     "quantidade_deteccoes": sum(metricas[f"{c}_{g}"] for c in ("tp", "fp") for g in ("individuos", "aglomerados")),
                     "imagem_largura_px": 80, "imagem_altura_px": 80,
                     "tempo_preprocessamento_ns": 0, "tempo_detector_ns": 100,
                     "tempo_adaptacao_ns": 20, "tempo_pipeline_ns": 120, **metricas}
            por_config.append(linha); linhas.append(linha)
        total = {"configuracao_id": item["id"], "pasta_origem": origem, "bloco": item["bloco"],
                 "modo_caixa": item["caixa"]["modo"], "perfil_forma": item["perfil_forma"],
                 "quantidade_quadros": 60,
                 **{f"tempo_{t}_total_ns": sum(x[f"tempo_{t}_ns"] for x in por_config) for t in relatorio.TEMPOS},
                 **somar_metricas(por_config)}
        resumos.append(total)
        for v in relatorio.VIDEOS:
            grupo = [x for x in por_config if x["video_id"] == v]
            videos.append({"configuracao_id": item["id"], "video_id": v, "quantidade_quadros": 15,
                           **{f"tempo_{t}_total_ns": sum(x[f"tempo_{t}_ns"] for x in grupo) for t in relatorio.TEMPOS},
                           **somar_metricas(grupo)})
    for nome, dados in (("resumo_configuracoes.csv", resumos), ("resumo_por_quadro.csv", linhas), ("resumo_por_video.csv", videos)):
        fontes[nome] = bytes_csv(dados)
    rows = relatorio._csv(fontes["resumo_configuracoes.csv"])
    fontes["ranking.csv"] = bytes_csv(relatorio._ranking({x["configuracao_id"]: x for x in rows}, [x["id"] for x in configs]))
    for nome, blob in fontes.items():
        (pasta / nome).write_bytes(blob)
    manifesto = {"versao": 1, "tipo": "selecao_blobs", "situacao": "concluida", "algoritmo": "blobs",
                 "etapa": "selecao_imagens", "rodada": "selecao", "particao": "selecao", "criterios": relatorio.CRITERIOS,
                 "configuracoes_previstas": 119, "configuracoes_concluidas": 119, "quadros_por_configuracao": 60,
                 "avaliacoes_concluidas": 7140, "plano_sha256": relatorio.sha256(fontes["plano.json"]),
                 "origens_sha256": mapa_origens,
                 "saidas_sha256": {(pasta / n).relative_to(raiz).as_posix(): relatorio.sha256(b) for n, b in fontes.items()}}
    (pasta / "execucao.json").write_bytes(bytes_json(manifesto))
    return pasta


class RelatorioSelecaoBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name)
        self.pasta = criar_fixture(self.raiz)
        for campo, valor in (("RAIZ", self.raiz), ("SAIDA", self.pasta.parent)):
            contexto = patch.object(relatorio, campo, valor)
            contexto.start(); self.addCleanup(contexto.stop)

    def regravar(self, nome, blob):
        (self.pasta / nome).write_bytes(blob)
        m = json.loads((self.pasta / "execucao.json").read_bytes())
        m["saidas_sha256"][(self.pasta / nome).relative_to(self.raiz).as_posix()] = relatorio.sha256(blob)
        if nome == "plano.json":
            m["plano_sha256"] = relatorio.sha256(blob)
            m["origens_sha256"]["scripts/blobs/selecao/plano.json"] = relatorio.sha256(blob)
        (self.pasta / "execucao.json").write_bytes(bytes_json(m))

    def test_carrega_completo_sem_base_nem_detectores(self):
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["linhas"]), 7140)
        self.assertEqual(len(dados["por_video"]), 476)
        self.assertEqual(len(dados["ranking"]), 119)
        self.assertEqual(len(dados["hashes"]), 19)
        self.assertFalse((self.raiz / "ficticio").exists())

    def test_todos_os_hashes_de_csv_conferidos(self):
        for nome in ("ranking.csv", "resumo_configuracoes.csv", "resumo_por_video.csv", "resumo_por_quadro.csv"):
            caminho = self.pasta / nome; antes = caminho.read_bytes()
            caminho.write_bytes(antes + b"\n")
            with self.subTest(nome=nome), self.assertRaisesRegex(ValueError, "Hash divergente"):
                relatorio.carregar(self.pasta)
            caminho.write_bytes(antes)

    def test_treze_hashes_de_origem_conferidos(self):
        for caminho in list(self.pasta.glob("origem_*.json")) + list(self.pasta.glob("execucao_round*.json")):
            antes = caminho.read_bytes(); caminho.write_bytes(antes + b"\n")
            with self.subTest(nome=caminho.name), self.assertRaisesRegex(ValueError, "Hash divergente"):
                relatorio.carregar(self.pasta)
            caminho.write_bytes(antes)

    def test_hash_plano_manifesto_incompleto_rejeitados(self):
        caminho = self.pasta / "execucao.json"; original = json.loads(caminho.read_bytes())
        for campo, valor in (("versao", True), ("configuracoes_concluidas", 118), ("avaliacoes_concluidas", 7139), ("situacao", "em_andamento"), ("plano_sha256", "a" * 64)):
            alterado = deepcopy(original); alterado[campo] = valor
            caminho.write_bytes(bytes_json(alterado))
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                relatorio.carregar(self.pasta)
        caminho.write_bytes(bytes_json(original))

    def test_frame_repetido_ou_video_ausente_rejeitado(self):
        for nome in ("resumo_por_quadro.csv", "resumo_por_video.csv"):
            antes = (self.pasta / nome).read_bytes(); rows = relatorio._csv(antes)
            rows[1] = deepcopy(rows[0]); self.regravar(nome, bytes_csv(rows))
            with self.subTest(nome=nome), self.assertRaisesRegex(ValueError, "incompleto, repetido"):
                relatorio.carregar(self.pasta)
            self.regravar(nome, antes)

    def test_agregados_metricas_tempos_e_caminho_rejeitados(self):
        casos = [("resumo_por_video.csv", "tp_individuos", "999"),
                 ("resumo_por_video.csv", "tempo_pipeline_total_ns", "999"),
                 ("resumo_por_quadro.csv", "tempo_pipeline_ns", "999"),
                 ("resumo_por_quadro.csv", "pasta_quadro", "outro/quadro"),
                 ("resumo_por_quadro.csv", "imagem", "outro.jpg")]
        for nome, campo, valor in casos:
            antes = (self.pasta / nome).read_bytes(); rows = relatorio._csv(antes)
            rows[0][campo] = valor; self.regravar(nome, bytes_csv(rows))
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                relatorio.carregar(self.pasta)
            self.regravar(nome, antes)

    def test_ranking_reordenado_e_posto_falso_rejeitados(self):
        antes = (self.pasta / "ranking.csv").read_bytes()
        for alterar in (lambda r: r.reverse(), lambda r: r[0].update(posicao="2")):
            rows = relatorio._csv(antes); alterar(rows); self.regravar("ranking.csv", bytes_csv(rows))
            with self.assertRaisesRegex(ValueError, "Ranking"):
                relatorio.carregar(self.pasta)
        self.regravar("ranking.csv", antes)

    def test_fracoes_exatas_distinguem_valores_mesmo_float(self):
        n = 10 ** 20
        def linha(i, tp, fp, fn):
            return {"configuracao_id": i, "tp_individuos": str(tp), "fp_individuos": str(fp), "fn_individuos": str(fn)}
        rows = {x["configuracao_id"]: x for x in (linha("s001", n, 1, 0), linha("s002", n, 0, 0), linha("s003", 2 * n, 2, 0))}
        rank = relatorio._ranking(rows, list(rows))
        self.assertEqual([r["configuracao_id"] for r in rank], ["s002", "s001", "s003"])
        self.assertEqual([r["posicao"] for r in rank], ["1", "2", "2"])
        self.assertEqual(float(relatorio._pontuacao(rows["s001"])), float(relatorio._pontuacao(rows["s002"])))

    def test_empate_limite_nao_promove_cinco(self):
        dados = relatorio.carregar(self.pasta)
        self.assertTrue(dados["limite_cinco"]["empate"])
        self.assertGreater(len(dados["limite_cinco"]["ids_empatados"]), 5)
        self.assertIn("Revisão conjunta necessária", relatorio._aviso_limite(dados))

    def test_sem_casos_nao_zero_nem_posto(self):
        rows = {"s001": {"configuracao_id": "s001", "tp_individuos": "0", "fp_individuos": "0", "fn_individuos": "0"},
                "s002": {"configuracao_id": "s002", "tp_individuos": "0", "fp_individuos": "1", "fn_individuos": "0"}}
        rank = relatorio._ranking(rows, list(rows))
        self.assertEqual([r["posicao"] for r in rank], ["1", ""])
        self.assertIsNone(relatorio._pontuacao(rows["s001"]))
        self.assertEqual(relatorio._pontuacao(rows["s002"]), Fraction(0))
        self.assertEqual(relatorio._limite_cinco(rank)["situacao"], "menos_de_cinco_definidos")

    def test_metodos_e_proveniencia_incompativeis_rejeitados(self):
        antes = (self.pasta / "plano.json").read_bytes()
        for alterar in (lambda p: p["configuracoes"][0].update(metodo="log"),
                        lambda p: p["proveniencia"]["s001"].update(configuracao_sha256=p["proveniencia"]["s002"]["configuracao_sha256"]),
                        lambda p: p["configuracoes"][0]["parametros"].update(area_minima=999)):
            p = json.loads(antes); alterar(p); self.regravar("plano.json", bytes_json(p))
            with self.assertRaises(ValueError):
                relatorio.carregar(self.pasta)
        self.regravar("plano.json", antes)

    def test_geracao_preserva_fontes_e_pdf_anterior(self):
        antes = {x.name: x.read_bytes() for x in self.pasta.iterdir() if x.is_file()}
        def simular(caminho, dados):
            caminho.write_bytes(b"%PDF-sintetico\n"); return 7
        with patch.object(relatorio, "escrever_pdf", side_effect=simular):
            primeiro = relatorio.gerar_relatorio(self.pasta)
            segundo = relatorio.gerar_relatorio(self.pasta)
        self.assertNotEqual(primeiro, segundo)
        self.assertTrue(primeiro.exists())
        for nome, blob in antes.items():
            self.assertEqual((self.pasta / nome).read_bytes(), blob)
        m = json.loads((segundo.parent / "relatorio.json").read_bytes())
        self.assertFalse(m["selecao_automatica"])
        self.assertEqual(m["pdf_sha256"], relatorio.sha256(segundo.read_bytes()))
        self.assertEqual(len(m["origens_sha256"]), 19)

    def test_pdf_sete_paginas_contem_todos_ids(self):
        from reportlab.pdfgen.canvas import Canvas
        textos = []
        original = Canvas.drawString
        def registrar(canvas, x, y, texto, *args, **kwargs):
            textos.append(str(texto))
            return original(canvas, x, y, texto, *args, **kwargs)
        dados = relatorio.carregar(self.pasta)
        pdf = self.pasta / "teste.pdf"
        with patch.object(Canvas, "drawString", new=registrar):
            self.assertEqual(relatorio.escrever_pdf(pdf, dados), 7)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 7)
        tudo = "\n".join(textos)
        for ident in dados["ids"]:
            self.assertIn(ident, tudo)
        self.assertIn("EMPATE NO LIMITE DE CINCO", tudo)
        self.assertIn("Ac. cond.", tudo)
        self.assertNotIn("macro-F1", tudo)

    def test_contrato_mesmos_campos_executor_em_jpeg_sintetico(self):
        import cv2
        import numpy as np
        from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
        from algoritmos.classicos.comum import ResultadoDeteccao
        from scripts.blobs import executar_rodada as executor
        q = json.loads((self.pasta / "plano.json").read_bytes())["quadros"][0]
        item = json.loads((self.pasta / "plano.json").read_bytes())["configuracoes"][0]
        sucesso, jpeg = cv2.imencode(".jpg", np.zeros((80, 80, 3), dtype=np.uint8))
        self.assertTrue(sucesso)
        entrada = {"quadro": q, "imagem_bytes": jpeg.tobytes(), "anotacao_bytes": b"", "anotacoes": []}
        destino = self.raiz / "contrato/quadros/13_frame_0"
        def candidatos_controlados(imagem, config):
            return ResultadoDeteccao("blobs", 80, 80, (), None)
        with patch.object(executor, "RAIZ", self.raiz):
            linha, avaliacao = executor.executar_quadro(entrada, None, configuracao_caixa_de_dict(item["caixa"]), item, destino, cv2, np, candidatos_controlados)
        self.assertEqual(set(linha), set(relatorio._csv((self.pasta / "resumo_por_quadro.csv").read_bytes())[0]))
        self.assertNotIn("pasta_origem", linha)
        resumo = executor.resumo(item, [linha], [avaliacao], pasta_origem="contrato", bloco=item["bloco"], modo_caixa=item["caixa"]["modo"], perfil_forma=item["perfil_forma"])
        por_video = executor.resumo(item, [linha], [avaliacao], video_id="13")
        self.assertEqual(set(resumo), set(relatorio._csv((self.pasta / "resumo_configuracoes.csv").read_bytes())[0]))
        self.assertEqual(set(por_video), set(relatorio._csv((self.pasta / "resumo_por_video.csv").read_bytes())[0]))
        ranking = executor.ordenar_por_f1([resumo])
        self.assertEqual(set(ranking[0]), set(relatorio._csv((self.pasta / "ranking.csv").read_bytes())[0]))


if __name__ == "__main__":
    unittest.main()
