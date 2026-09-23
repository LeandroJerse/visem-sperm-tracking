"""Contrato e integridade dos PDFs de seleção e final com métricas sintéticas."""

from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from analise import relatorio_videos_blobs as relatorio
from scripts.testes.test_relatorio_rodada_blobs import _metricas
from scripts.testes.test_relatorio_selecao_blobs import bytes_json, bytes_csv, somar_metricas


def criar_fixture(raiz, vazio=False, particao="selecao"):
    etapa = relatorio._etapa(particao)
    quadros, fps = etapa["quadros"], etapa["fps"]
    quantidade = sum(quadros.values())
    pasta = raiz / f"resultados/videos/blobs/{particao}/batch__sintetico"
    pasta.mkdir(parents=True)
    ids = relatorio.IDS
    configs = [{"id": ident, "bloco": "exploracao", "perfil_forma": "inercia_04" if ident != "s103" else "escala",
                "referencia": None, "metodo": "dog" if ident == "s103" else "simpleblob",
                "preprocessamento": {"metodo": "nenhum"}, "parametros": {"polaridade": "claro", "area_minima": 48 + i},
                "caixa": {"modo": "margem", "pixels": margem}}
               for i, (ident, margem) in enumerate(zip(ids, (6, 4, 4, 8, 5)))]
    hashes_originais, fontes, documentos = {}, {}, {}
    def construir_videos(quadros, fps):
        videos = []
        for v, n in quadros.items():
            arquivo = f"ficticio/{v}.mp4"; hash_video = relatorio.sha256(arquivo.encode())
            hashes_originais[arquivo] = hash_video
            anotacoes = []
            for q in range(n):
                nome = f"ficticio/{v}/labels/{q}.txt"; digest = relatorio.sha256(nome.encode())
                anotacoes.append({"quadro": q, "arquivo": nome, "sha256": digest}); hashes_originais[nome] = digest
            refs = [{"quadro": q, "imagem": f"ficticio/{v}/images/{q}.jpg", "sha256": relatorio.sha256(f"ref{v}/{q}".encode())}
                    for q in (0, 100, 700, 1400, n - 1)]
            for ref in refs:
                hashes_originais[ref["imagem"]] = ref["sha256"]
            videos.append({"video_id": v, "arquivo": arquivo, "sha256": hash_video, "quantidade_quadros": n,
                           "fps": fps[v], "largura": 640, "altura": 480, "indice_inicial": 0,
                           "anotacoes": anotacoes, "referencias_alinhamento": refs})
        return videos
    videos = construir_videos(quadros, fps)
    videos_selecao = videos if particao == "selecao" else construir_videos(relatorio.QUADROS, relatorio.FPS)
    alinhamento = {"metodo": "referencias_sinteticas"}

    def origem(nome, dado, extensao=".json"):
        blob = bytes_json(dado) if extensao == ".json" else bytes_csv(dado)
        caminho = f"fontes/{nome}{extensao}"
        fontes[nome] = {"arquivo": caminho, "sha256": relatorio.sha256(blob)}
        hashes_originais[caminho] = relatorio.sha256(blob)
        documentos[nome + extensao] = blob

    origem("origem_videos_limiarizacao", {"videos": videos_selecao, "alinhamento": alinhamento})
    origem("origem_selecao", {"etapa": "selecao_imagens", "criterios": relatorio.CRITERIOS, "configuracoes": configs})
    hash_selecao = fontes["origem_selecao"]["sha256"]
    origem("execucao_selecao", {"situacao": "concluida", "criterios": relatorio.CRITERIOS, "configuracoes_concluidas": 119,
                                "quadros_por_configuracao": 60, "plano_sha256": hash_selecao})
    for nome in ("ranking_selecao", "resumo_configuracoes_selecao", "resumo_por_video_selecao", "resumo_por_quadro_selecao"):
        origem(nome, [{"dado": "fonte_sintetica"}], ".csv")
    prov_config = {}
    for item in configs:
        ident = item["id"]; digest = relatorio.sha256(bytes_json(item))
        origem(f"configuracao_{ident}", item)
        origem(f"avaliacao_{ident}", {"tipo": "sintetico"})
        origem(f"execucao_{ident}", {"configuracao_id": ident, "situacao": "concluida", "quadros_concluidos": 60,
                                     "configuracao_sha256": digest, "plano_sha256": hash_selecao})
        prov_config[ident] = {"configuracao_sha256": digest, "pasta_selecao": f"fontes/{ident}", "desenvolvimento": {}}
    if particao == "final":
        plano_selecao = {"versao": 1, "tipo": "videos_selecao_blobs", "etapa": "selecao_videos", "particao": "selecao",
                         "algoritmo": "blobs", "criterios": relatorio.CRITERIOS, "configuracoes": configs,
                         "videos": videos_selecao, "alinhamento": alinhamento,
                         "proveniencia": {"fontes": deepcopy(fontes), "configuracoes": deepcopy(prov_config)}}
        origem("origem_videos_selecao_blobs", plano_selecao)
        hash_video_selecao = fontes["origem_videos_selecao_blobs"]["sha256"]
        origem("origem_videos_final_limiarizacao", {"videos": videos, "alinhamento": alinhamento})
        origem("execucao_videos_selecao_blobs", {"versao": 1, "tipo": "videos_selecao_blobs", "etapa": "selecao_videos",
                "particao": "selecao", "algoritmo": "blobs", "criterios": relatorio.CRITERIOS, "situacao": "concluida",
                "configuracoes_previstas": 5, "configuracoes_concluidas": 5, "quadros_por_configuracao": 5850,
                "avaliacoes_concluidas": 29250, "videos_concluidos": 20, "alinhamento_conferido": True,
                "plano_sha256": hash_video_selecao})
        for nome in ("ranking_videos_selecao_blobs", "resumo_configuracoes_videos_selecao_blobs", "resumo_por_video_videos_selecao_blobs"):
            origem(nome, [{"dado": "fonte_sintetica"}], ".csv")
        for item in configs:
            ident = item["id"]
            origem(f"configuracao_video_{ident}", item)
            origem(f"avaliacao_video_{ident}", {"tipo": "sintetico"})
            origem(f"execucao_video_{ident}", {"configuracao_id": ident, "situacao": "concluida", "quadros_concluidos": 5850,
                   "configuracao_sha256": prov_config[ident]["configuracao_sha256"], "plano_sha256": hash_video_selecao})
    plano = {"versao": 1, "tipo": etapa["tipo"], "etapa": etapa["etapa"], "particao": particao,
             "algoritmo": "blobs", "seed": 42, "criterios": relatorio.CRITERIOS,
             "configuracoes": configs, "videos": videos, "alinhamento": alinhamento,
             "proveniencia": {"decisao": "aprovacao_sintetica", "ids_aprovados": list(ids),
                              "configuracoes_congeladas": True, "aleatoriedade_utilizada": False,
                              "fontes": fontes, "configuracoes": prov_config}}
    documentos["plano.json"] = bytes_json(plano)
    hash_plano = relatorio.sha256(documentos["plano.json"])
    hashes_originais[f"scripts/blobs/videos/plano_{particao}.json"] = hash_plano
    saidas, execucoes, resumos, parciais = {}, [], [], []

    def gravar(caminho, blob):
        caminho.write_bytes(blob)
        saidas[caminho.relative_to(raiz).as_posix()] = relatorio.sha256(blob)

    origem_pasta = pasta / "origens" if particao == "final" else pasta
    origem_pasta.mkdir(exist_ok=True)
    for nome, blob in documentos.items():
        gravar((pasta if nome == "plano.json" else origem_pasta) / nome, blob)
    for i, item in enumerate(configs):
        ident = item["id"]
        local = pasta / f"{ident}__configuracao__sintetico"; local.mkdir()
        local_rel = local.relative_to(raiz).as_posix()
        execucoes.append({"configuracao_id": ident, "pasta": local_rel})
        gravar(local / "configuracao.json", bytes_json(item))
        linhas, registros = [], []
        for j, video in enumerate(videos):
            v = video["video_id"]; n = video["quantidade_quadros"]
            metricas = _metricas(i + j, vazio=vazio)
            for q in range(n):
                linhas.append({"video": video["arquivo"], "anotacao": video["anotacoes"][q]["arquivo"],
                               "video_id": v, "quadro": q, "tempo_segundos": q / video["fps"],
                               "imagem_largura_px": 640, "imagem_altura_px": 480,
                               "quantidade_anotacoes": 0 if vazio else 4,
                               "quantidade_deteccoes": sum(metricas[f"{c}_{g}"] for c in ("tp", "fp") for g in ("individuos", "aglomerados")),
                               "tempo_decodificador_segundos": q / video["fps"],
                               "tempo_preprocessamento_ns": 0, "tempo_detector_ns": (i + 1) * 1000000,
                               "tempo_adaptacao_ns": 20000, "tempo_pipeline_ns": (i + 1) * 1000000 + 20000,
                               **metricas})
            midia = local / f"video_{v}.mp4"
            blob = f"midia sintética para teste de hash {ident}/{v}".encode()
            gravar(midia, blob)
            registros.append({"video_id": v, "arquivo": midia.relative_to(raiz).as_posix(), "quantidade_quadros": n,
                              "fps": video["fps"], "largura": 1280, "altura": 584, "sha256": relatorio.sha256(blob),
                              "codec_solicitado": "mp4v", "decodificacao_conferida": True})
            grupo = linhas[-n:]
            parciais.append({"configuracao_id": ident, "pasta_origem": local_rel, "video_id": v,
                             "quantidade_quadros": n,
                             **{f"tempo_{t}_total_ns": sum(x[f"tempo_{t}_ns"] for x in grupo) for t in relatorio.TEMPOS},
                             **somar_metricas(grupo)})
        gravar(local / "por_quadro.csv", bytes_csv(linhas))
        gravar(local / "execucao.json", bytes_json({"configuracao_id": ident, "configuracao_sha256": prov_config[ident]["configuracao_sha256"],
               "plano_sha256": hash_plano, "batch": pasta.relative_to(raiz).as_posix(), "situacao": "concluida",
               "quadros_concluidos": quantidade, "videos": registros}))
        resumos.append({"configuracao_id": ident, "pasta_origem": local_rel, "bloco": item["bloco"],
                        "perfil_forma": item["perfil_forma"], "modo_caixa": item["caixa"]["modo"], "quantidade_quadros": quantidade,
                        **{f"tempo_{t}_total_ns": sum(x[f"tempo_{t}_ns"] for x in linhas) for t in relatorio.TEMPOS},
                        **somar_metricas(linhas)})
    gravar(pasta / "resumo_configuracoes.csv", bytes_csv(resumos))
    gravar(pasta / "resumo_por_video.csv", bytes_csv(parciais))
    rows = relatorio._csv(bytes_csv(resumos))
    gravar(pasta / "ranking.csv", bytes_csv(relatorio._ranking({x["configuracao_id"]: x for x in rows}, list(ids))))
    manifesto = {"versao": 1, "tipo": etapa["tipo"], "etapa": etapa["etapa"], "particao": particao, "algoritmo": "blobs",
                 "situacao": "concluida", "criterios": relatorio.CRITERIOS, "configuracoes_previstas": 5,
                 "configuracoes_concluidas": 5, "quadros_por_configuracao": quantidade, "avaliacoes_concluidas": quantidade * 5,
                 "videos_concluidos": 20, "alinhamento_conferido": True, "plano_sha256": hash_plano,
                 "origens_sha256": hashes_originais, "saidas_sha256": saidas, "execucoes": execucoes}
    if particao == "final":
        manifesto["pasta_origens"] = "origens"
    (pasta / "execucao.json").write_bytes(bytes_json(manifesto))
    return pasta


class RelatorioVideosBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory(); self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name); self.pasta = criar_fixture(self.raiz)
        for campo, valor in (("RAIZ", self.raiz), ("SAIDA", self.pasta.parent)):
            contexto = patch.object(relatorio, campo, valor); contexto.start(); self.addCleanup(contexto.stop)

    def regravar(self, caminho, blob):
        caminho.write_bytes(blob)
        m = json.loads((self.pasta / "execucao.json").read_bytes())
        m["saidas_sha256"][caminho.relative_to(self.raiz).as_posix()] = relatorio.sha256(blob)
        if caminho.name == "plano.json":
            m["plano_sha256"] = relatorio.sha256(blob)
            m["origens_sha256"]["scripts/blobs/videos/plano_selecao.json"] = relatorio.sha256(blob)
        (self.pasta / "execucao.json").write_bytes(bytes_json(m))

    def test_le_origens_organizadas_preservando_compatibilidade_historica(self):
        anterior = relatorio.carregar(self.pasta)
        manifesto = json.loads((self.pasta / "execucao.json").read_bytes())
        (self.pasta / "origens").mkdir()
        for nome, fonte in anterior["plano"]["proveniencia"]["fontes"].items():
            origem = self.pasta / (nome + Path(fonte["arquivo"]).suffix)
            destino = self.pasta / "origens" / origem.name
            digest = manifesto["saidas_sha256"].pop(origem.relative_to(self.raiz).as_posix())
            origem.rename(destino)
            manifesto["saidas_sha256"][destino.relative_to(self.raiz).as_posix()] = digest
        manifesto["pasta_origens"] = "origens"
        (self.pasta / "execucao.json").write_bytes(bytes_json(manifesto))
        atual = relatorio.carregar(self.pasta)
        self.assertEqual(anterior["ranking"], atual["ranking"])
        self.assertEqual(anterior["por_video"], atual["por_video"])
        # Declarar a pasta nova não permite recorrer silenciosamente à raiz.
        fonte = self.pasta / "origens" / "origem_selecao.json"
        fonte.rename(self.pasta / fonte.name)
        with self.assertRaises(FileNotFoundError):
            relatorio.carregar(self.pasta)

    def test_rejeita_pasta_de_origens_fora_do_contrato(self):
        caminho = self.pasta / "execucao.json"
        manifesto = json.loads(caminho.read_bytes())
        for destino in ("../fora", "/tmp", "origens/alternativa", None):
            manifesto["pasta_origens"] = destino
            caminho.write_bytes(bytes_json(manifesto))
            with self.subTest(destino=destino), self.assertRaisesRegex(ValueError, "Pasta de origens"):
                relatorio.carregar(self.pasta)

    def test_completo_sem_abrir_videos_ou_base(self):
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["ranking"]), 5); self.assertEqual(len(dados["por_video"]), 20)
        self.assertEqual(len(dados["midias"]), 20); self.assertEqual(len(dados["hashes"]), 62)
        self.assertFalse((self.raiz / "ficticio").exists())

    def test_rejeita_manifesto_incompleto_e_alinhamento(self):
        caminho = self.pasta / "execucao.json"; original = json.loads(caminho.read_bytes())
        for campo, valor in (("versao", True), ("avaliacoes_concluidas", 29249), ("videos_concluidos", 19), ("alinhamento_conferido", False), ("situacao", "em_andamento")):
            m = deepcopy(original); m[campo] = valor; caminho.write_bytes(bytes_json(m))
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "Manifesto"):
                relatorio.carregar(self.pasta)

    def test_hashes_resumo_origem_midia_quadro(self):
        caminhos = [self.pasta / "resumo_configuracoes.csv", self.pasta / "ranking.csv",
                    self.pasta / "origem_selecao.json", next(self.pasta.glob("s052*/por_quadro.csv")),
                    next(self.pasta.glob("s052*/*.mp4"))]
        for caminho in caminhos:
            original = caminho.read_bytes(); caminho.write_bytes(original + b"\n")
            with self.subTest(nome=caminho.name), self.assertRaisesRegex(ValueError, "Hash"):
                relatorio.carregar(self.pasta)
            caminho.write_bytes(original)

    def test_sequencia_repetida_ou_faltante(self):
        caminho = next(self.pasta.glob("s052*/por_quadro.csv")); original = caminho.read_bytes()
        for alterar in (lambda r: r.pop(), lambda r: r.__setitem__(1, deepcopy(r[0]))):
            rows = relatorio._csv(original); alterar(rows); self.regravar(caminho, bytes_csv(rows))
            with self.assertRaisesRegex(ValueError, "Sequência"):
                relatorio.carregar(self.pasta)
        self.regravar(caminho, original)

    def test_metricas_internas_validas_mas_agregado_errado(self):
        caminho = self.pasta / "resumo_por_video.csv"
        rows = relatorio._csv(caminho.read_bytes()); rows[0].update(_metricas(9, 1470))
        self.regravar(caminho, bytes_csv(rows))
        with self.assertRaisesRegex(ValueError, "Agregação inconsistente"):
            relatorio.carregar(self.pasta)

    def test_timestamps_pipeline_e_origem_quadro(self):
        caminho = next(self.pasta.glob("s052*/por_quadro.csv")); original = caminho.read_bytes()
        rows = relatorio._csv(original); rows[0]["tempo_decodificador_segundos"] = ""
        self.regravar(caminho, bytes_csv(rows))
        self.assertEqual(len(relatorio.carregar(self.pasta)["ranking"]), 5)
        for campo, valor in (("tempo_segundos", "999"), ("tempo_decodificador_segundos", "nan"),
                             ("tempo_pipeline_ns", "1"), ("anotacao", "errada.txt")):
            rows = relatorio._csv(original); rows[0][campo] = valor; self.regravar(caminho, bytes_csv(rows))
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                relatorio.carregar(self.pasta)
        self.regravar(caminho, original)

    def test_registro_midia_precisa_corresponder_video(self):
        caminho = next(self.pasta.glob("s052*/execucao.json")); original = caminho.read_bytes()
        for campo, valor in (("video_id", "29"), ("quantidade_quadros", 2), ("decodificacao_conferida", False), ("largura", 640)):
            e = json.loads(original); e["videos"][0][campo] = valor; self.regravar(caminho, bytes_json(e))
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                relatorio.carregar(self.pasta)
        self.regravar(caminho, original)

    def test_ranking_nao_permite_posto_falso(self):
        caminho = self.pasta / "ranking.csv"; rows = relatorio._csv(caminho.read_bytes())
        rows[0]["posicao"] = "2"; self.regravar(caminho, bytes_csv(rows))
        with self.assertRaisesRegex(ValueError, "Ranking"):
            relatorio.carregar(self.pasta)

    def test_configuracao_congelada_e_pasta_interna(self):
        caminho = next(self.pasta.glob("s052*/configuracao.json")); item = json.loads(caminho.read_bytes())
        item["caixa"]["pixels"] += 1; self.regravar(caminho, bytes_json(item))
        with self.assertRaisesRegex(ValueError, "Configuração salva"):
            relatorio.carregar(self.pasta)

    def test_sem_casos_preserva_ausencia_e_posicao(self):
        raiz = self.raiz / "vazio"; pasta = criar_fixture(raiz, vazio=True)
        with patch.object(relatorio, "RAIZ", raiz), patch.object(relatorio, "SAIDA", pasta.parent):
            dados = relatorio.carregar(pasta)
        self.assertTrue(all(x["posicao"] == "" and x["f1_individuos"] == "" for x in dados["ranking"]))

    def test_gerar_preserva_fontes_e_versoes_pdf(self):
        antes = {x.name: x.read_bytes() for x in self.pasta.iterdir() if x.is_file()}
        def simular(caminho, dados):
            caminho.write_bytes(b"%PDF-sintetico\n"); return 4
        with patch.object(relatorio, "escrever_pdf", side_effect=simular):
            pdf1 = relatorio.gerar_relatorio(self.pasta); pdf2 = relatorio.gerar_relatorio(self.pasta)
        self.assertNotEqual(pdf1, pdf2)
        self.assertTrue(pdf1.exists())
        for nome, blob in antes.items():
            self.assertEqual((self.pasta / nome).read_bytes(), blob)
        m = json.loads((pdf2.parent / "relatorio.json").read_bytes())
        self.assertFalse(m["selecao_automatica"])
        self.assertEqual(m["pdf_sha256"], relatorio.sha256(pdf2.read_bytes()))

    def test_pdf_quatro_paginas_ids_e_limites(self):
        from reportlab.pdfgen.canvas import Canvas
        textos = []; original = Canvas.drawString
        def registrar(canvas, x, y, texto, *args, **kwargs):
            textos.append(str(texto)); return original(canvas, x, y, texto, *args, **kwargs)
        dados = relatorio.carregar(self.pasta); pdf = self.pasta / "teste.pdf"
        with patch.object(Canvas, "drawString", new=registrar):
            self.assertEqual(relatorio.escrever_pdf(pdf, dados), 4)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 4)
        texto = "\n".join(textos)
        for ident in relatorio.IDS:
            self.assertIn(ident, texto)
        self.assertIn("sem rastreamento", texto.lower())
        self.assertIn("Acurácia condicional", texto)
        self.assertNotIn("macro-F1", texto)

    def test_contrato_campos_com_executor_e_mp4_sintetico(self):
        from scripts.testes.test_videos_blobs import VideosBlobsTest
        fixture = VideosBlobsTest()
        try:
            fixture.setUp()
            executada = fixture.executar_sintetico()
            for nome in ("resumo_configuracoes.csv", "resumo_por_video.csv", "ranking.csv"):
                real = relatorio._csv((executada / nome).read_bytes())
                simulado = relatorio._csv((self.pasta / nome).read_bytes())
                self.assertEqual(set(real[0]), set(simulado[0]), nome)
            m = json.loads((executada / "execucao.json").read_bytes())
            origem = fixture.raiz / m["execucoes"][0]["pasta"]
            real = relatorio._csv((origem / "por_quadro.csv").read_bytes())
            simulado = relatorio._csv(next(self.pasta.glob("s052*/por_quadro.csv")).read_bytes())
            self.assertEqual(set(real[0]), set(simulado[0]))
            e = json.loads((origem / "execucao.json").read_bytes())
            sint = json.loads(next(self.pasta.glob("s052*/execucao.json")).read_bytes())
            self.assertTrue(set(sint).issubset(e))
            self.assertEqual(set(e["videos"][0]), set(sint["videos"][0]))
        finally:
            fixture.doCleanups()


class RelatorioVideosFinalBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory(); self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name); self.pasta = criar_fixture(self.raiz, particao="final")
        for campo, valor in (("RAIZ", self.raiz), ("SAIDA", self.raiz / "resultados/videos/blobs/selecao"),
                             ("SAIDA_FINAL", self.pasta.parent)):
            contexto = patch.object(relatorio, campo, valor); contexto.start(); self.addCleanup(contexto.stop)

    def regravar(self, caminho, blob):
        caminho.write_bytes(blob)
        m = json.loads((self.pasta / "execucao.json").read_bytes())
        m["saidas_sha256"][caminho.relative_to(self.raiz).as_posix()] = relatorio.sha256(blob)
        if caminho.name == "plano.json":
            m["plano_sha256"] = relatorio.sha256(blob)
            m["origens_sha256"]["scripts/blobs/videos/plano_final.json"] = relatorio.sha256(blob)
        (self.pasta / "execucao.json").write_bytes(bytes_json(m))

    def adulterar_origem(self, nome, documento):
        caminho = self.pasta / "origens" / f"{nome}.json"
        blob = bytes_json(documento); self.regravar(caminho, blob)
        plano = json.loads((self.pasta / "plano.json").read_bytes())
        fonte = plano["proveniencia"]["fontes"][nome]
        fonte["sha256"] = relatorio.sha256(blob)
        m = json.loads((self.pasta / "execucao.json").read_bytes())
        m["origens_sha256"][fonte["arquivo"]] = fonte["sha256"]
        (self.pasta / "execucao.json").write_bytes(bytes_json(m))
        self.regravar(self.pasta / "plano.json", bytes_json(plano))

    def test_final_completa_29550_linhas_43_origens_e_20_midias(self):
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(dados["manifesto"]["avaliacoes_concluidas"], 29550)
        self.assertEqual(len(dados["plano"]["proveniencia"]["fontes"]), 43)
        self.assertEqual(len(dados["hashes"]), 83)
        self.assertEqual(len(dados["midias"]), 20)
        self.assertEqual(set(v for _, v in dados["por_video"]), {"14", "24", "38", "82"})
        self.assertTrue(all(x["quantidade_quadros"] == "5910" for x in dados["resumos"].values()))
        self.assertFalse((self.raiz / "ficticio").exists())

    def test_etapa_e_contagens_precisam_corresponder_pasta_final(self):
        caminho = self.pasta / "execucao.json"; original = caminho.read_bytes()
        for campo, valor in (("tipo", "videos_selecao_blobs"), ("etapa", "selecao_videos"),
                             ("particao", "selecao"), ("quadros_por_configuracao", 5850),
                             ("avaliacoes_concluidas", 29250), ("alinhamento_conferido", False)):
            m = json.loads(original); m[campo] = valor; caminho.write_bytes(bytes_json(m))
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "Manifesto"):
                relatorio.carregar(self.pasta)
        caminho.write_bytes(original)
        with patch.object(relatorio, "SAIDA", self.pasta.parent), patch.object(relatorio, "SAIDA_FINAL", self.raiz / "outro"):
            with self.assertRaisesRegex(ValueError, "Manifesto"):
                relatorio.carregar(self.pasta)
        with self.assertRaisesRegex(ValueError, "batch diretamente"):
            relatorio.carregar(next(self.pasta.glob("s052*")))

    def test_plano_final_nao_aceita_videos_ou_fps_da_selecao(self):
        caminho = self.pasta / "plano.json"; original = caminho.read_bytes()
        for campo, valor in (("video_id", "13"), ("quantidade_quadros", 1470), ("fps", 49)):
            plano = json.loads(original); plano["videos"][-1][campo] = valor
            self.regravar(caminho, bytes_json(plano))
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "vídeos da etapa|Metadados"):
                relatorio.carregar(self.pasta)
        self.regravar(caminho, original)

    def test_selecao_de_videos_anterior_precisa_estar_concluida(self):
        nome = "execucao_videos_selecao_blobs"
        documento = json.loads((self.pasta / "origens" / f"{nome}.json").read_bytes())
        documento["situacao"] = "em_andamento"
        self.adulterar_origem(nome, documento)
        with self.assertRaisesRegex(ValueError, "Seleção de vídeos anterior incompleta"):
            relatorio.carregar(self.pasta)

    def test_candidato_final_precisa_ser_o_mesmo_da_selecao_em_videos(self):
        nome = "configuracao_video_s103"
        documento = json.loads((self.pasta / "origens" / f"{nome}.json").read_bytes())
        documento["caixa"]["pixels"] += 1
        self.adulterar_origem(nome, documento)
        with self.assertRaisesRegex(ValueError, "Configuração final difere"):
            relatorio.carregar(self.pasta)

    def test_final_detecta_corrupcao_e_metadados_incorretos_da_ultima_midia(self):
        midia = next(self.pasta.glob("s051*/video_82.mp4"))
        original_midia = midia.read_bytes(); midia.write_bytes(original_midia + b"alterado")
        with self.assertRaisesRegex(ValueError, "Hash da mídia"):
            relatorio.carregar(self.pasta)
        midia.write_bytes(original_midia)
        caminho = next(self.pasta.glob("s051*/execucao.json")); original = caminho.read_bytes()
        for campo, valor in (("quantidade_quadros", 1470), ("fps", 49), ("video_id", "54"),
                             ("altura", 480), ("decodificacao_conferida", False)):
            e = json.loads(original); e["videos"][-1][campo] = valor
            self.regravar(caminho, bytes_json(e))
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "Mídia|mídias"):
                relatorio.carregar(self.pasta)
        self.regravar(caminho, original)

    def test_pdf_final_quatro_paginas_textos_tempos_e_registro(self):
        from reportlab.pdfgen.canvas import Canvas
        textos = []; original = Canvas.drawString
        def registrar(canvas, x, y, texto, *args, **kwargs):
            textos.append(str(texto)); return original(canvas, x, y, texto, *args, **kwargs)
        antes = {x.relative_to(self.pasta): relatorio.sha256(x.read_bytes()) for x in self.pasta.rglob("*") if x.is_file()}
        with patch.object(Canvas, "drawString", new=registrar):
            pdf = relatorio.gerar_relatorio(self.pasta)
        texto = " ".join(textos)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 4)
        for trecho in ("VÍDEOS DE AVALIAÇÃO FINAL", "5.910 quadros", "29.550 avaliações", "Vídeo 82: 1.500 quadros, 50 FPS",
                       "não comprova que os vídeos sejam inéditos", "avaliação final com configurações congeladas"):
            self.assertIn(trecho, texto)
        self.assertNotIn("etapa anterior à avaliação final", texto)
        self.assertIn("1,020", texto)  # 1.000.000 + 20.000 ns por quadro, divisor final 5910.
        registro = json.loads((pdf.parent / "relatorio.json").read_bytes())
        self.assertEqual(registro["tipo"], "videos_final_blobs")
        self.assertIn("29550 linhas", registro["escopo_integridade"])
        for caminho, digest in antes.items():
            self.assertEqual(relatorio.sha256((self.pasta / caminho).read_bytes()), digest)


if __name__ == "__main__":
    unittest.main()
