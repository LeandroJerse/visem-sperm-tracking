"""Fontes sintéticas completas: integridade, agregação e PDF de 48 configurações."""

from __future__ import annotations

from copy import deepcopy
import csv
from io import StringIO
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from analise import relatorio_rodada_blobs as relatorio


def _json(dados):
    return (json.dumps(dados, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _csv(linhas):
    buffer = StringIO(newline="")
    escritor = csv.DictWriter(buffer, fieldnames=list(linhas[0]))
    escritor.writeheader()
    escritor.writerows(linhas)
    return buffer.getvalue().encode("utf-8-sig")


def _metricas(indice, fator=1, vazio=False):
    normal = 0 if vazio else indice % 4
    pequeno = 0 if vazio else indice % 2
    anotacoes = (0, 0) if vazio else (3, 1)
    fp = 0 if vazio else indice % 3
    fp_aglom = 0 if vazio else indice % 2
    linhas = {}
    for grupo, tp, fp_, fn in (("individuos", normal + pequeno, fp, sum(anotacoes) - normal - pequeno),
                               ("aglomerados", 0, fp_aglom, 0)):
        tp, fp_, fn = tp * fator, fp_ * fator, fn * fator
        razao = lambda a, b: a / b if b else ""
        linhas.update({f"tp_{grupo}": tp, f"fp_{grupo}": fp_, f"fn_{grupo}": fn,
                       f"precisao_{grupo}": razao(tp, tp + fp_),
                       f"recall_{grupo}": razao(tp, tp + fn),
                       f"f1_{grupo}": razao(2 * tp, 2 * tp + fp_ + fn),
                       f"situacao_f1_{grupo}": "definido" if 2 * tp + fp_ + fn else "sem_casos"})
    for classe, total, localizada in ((0, anotacoes[0], normal), (2, anotacoes[1], pequeno), (1, 0, 0)):
        linhas.update({f"anotacoes_classe_{classe}": total * fator,
                       f"localizadas_classe_{classe}": localizada * fator,
                       f"perdidas_classe_{classe}": (total - localizada) * fator,
                       f"recall_classe_{classe}": localizada / total if total else ""})
    trocas = int(normal > 0)
    linhas.update(pares_corretos=(normal + pequeno - trocas) * fator,
                  pares_incorretos=trocas * fator, pares_total=(normal + pequeno) * fator,
                  acuracia_condicional=(normal + pequeno - trocas) / (normal + pequeno) if normal + pequeno else "",
                  matriz_0_0=(normal - trocas) * fator, matriz_0_2=trocas * fator,
                  matriz_2_0=0, matriz_2_2=pequeno * fator)
    return linhas


def criar_fixture(raiz: Path, rodada="round1", vazio=False):
    """Cria apenas plano e resumos fictícios; nenhum arquivo da base é necessário."""
    pasta = raiz / f"resultados/frame-to-frame/blobs/{rodada}/batch__sintetico"
    pasta.mkdir(parents=True, exist_ok=False)
    quadros = [{"video_id": video, "quadro": quadro,
                "imagem": f"base_ficticia/{video}_{quadro}.jpg",
                "anotacao": f"base_ficticia/{video}_{quadro}.txt",
                "imagem_sha256": "0" * 64, "anotacao_sha256": "1" * 64}
               for video in relatorio.VIDEOS for quadro in range(0, 1401, 100)
               if (video, quadro) not in (("23", 900), ("23", 1100))]
    caixas = [{"modo": "original"}, *[{"modo": "escala", "fator": i} for i in (2, 3, 4)],
              *[{"modo": "margem", "pixels": i} for i in (4, 8)]]
    configs = [{"id": f"b{i + 1:02d}", "bloco": "controle" if i < 12 else "exploracao",
                "referencia": ("b01" if i < 6 else "b02") if i < 12 else None,
                "perfil_forma": "sem_filtro" if i < 12 else "circularidade_04",
                "parametros": {"polaridade": "claro" if i % 12 < 6 else "escuro"},
                "caixa": deepcopy(caixas[i % 6])} for i in range(relatorio.ORCAMENTO[rodada])]
    plano = {"versao": 1, "algoritmo": "blobs", "etapa": "desenvolvimento",
             "rodada": rodada, "particao": "desenvolvimento", "quadros": quadros,
             "configuracoes": configs}
    linhas, resumos, videos = [], [], []
    for i, item in enumerate(configs):
        pasta_origem = f"resultados/frame-to-frame/blobs/{rodada}/{item['id']}__sintetico"
        for q in quadros:
            metricas = _metricas(i, vazio=vazio)
            linhas.append({"configuracao_id": item["id"], "pasta_origem": pasta_origem,
                           **{k: q[k] for k in ("video_id", "quadro", "imagem", "anotacao")},
                           "pasta_quadro": f"{pasta_origem}/quadros/{q['video_id']}_frame_{q['quadro']}",
                           "quantidade_anotacoes": 0 if vazio else 4,
                           "quantidade_deteccoes": sum(metricas[f"{k}_{g}"] for k in ("tp", "fp") for g in ("individuos", "aglomerados")),
                           "imagem_largura_px": 640, "imagem_altura_px": 480,
                           "tempo_detector_ns": 100, "tempo_adaptacao_ns": 20, "tempo_pipeline_ns": 140,
                           **metricas})
        resumos.append({"configuracao_id": item["id"], "pasta_origem": pasta_origem,
                        "quantidade_quadros": 178, "bloco": item["bloco"],
                        "modo_caixa": item["caixa"]["modo"], "perfil_forma": item["perfil_forma"],
                        "tempo_detector_total_ns": 17800, "tempo_adaptacao_total_ns": 3560,
                        "tempo_pipeline_total_ns": 24920, **_metricas(i, 178, vazio)})
        for video in relatorio.VIDEOS:
            n = 13 if video == "23" else 15
            videos.append({"configuracao_id": item["id"], "video_id": video,
                           "quantidade_quadros": n, "tempo_detector_total_ns": 100 * n,
                           "tempo_adaptacao_total_ns": 20 * n, "tempo_pipeline_total_ns": 140 * n,
                           **_metricas(i, n, vazio)})
    fontes = {"plano.json": _json(plano), "resumo_configuracoes.csv": _csv(resumos),
              "resumo_por_quadro.csv": _csv(linhas), "resumo_por_video.csv": _csv(videos)}
    for nome, conteudo in fontes.items():
        (pasta / nome).write_bytes(conteudo)
    n = len(configs)
    manifesto = {"versao": 1, "tipo": "rodada_blobs", "situacao": "concluida",
                 "algoritmo": "blobs", "etapa": "desenvolvimento", "rodada": rodada,
                 "particao": "desenvolvimento", "criterios": relatorio.CRITERIOS,
                 "configuracoes_previstas": n, "configuracoes_concluidas": n,
                 "quadros_por_configuracao": 178, "plano_sha256": relatorio.sha256(fontes["plano.json"]),
                 "saidas_sha256": {(pasta / nome).relative_to(raiz).as_posix(): relatorio.sha256(b) for nome, b in fontes.items()}}
    (pasta / "execucao.json").write_bytes(_json(manifesto))
    return pasta


class RelatorioRodadaBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name)
        for campo, valor in (("RAIZ", self.raiz), ("SAIDA", self.raiz / "resultados/frame-to-frame/blobs")):
            p = patch.object(relatorio, campo, valor)
            p.start(); self.addCleanup(p.stop)
        self.pasta = criar_fixture(self.raiz)

    def regravar(self, nome, conteudo):
        caminho = self.pasta / nome
        caminho.write_bytes(conteudo)
        manifesto = json.loads((self.pasta / "execucao.json").read_bytes())
        manifesto["saidas_sha256"][caminho.relative_to(self.raiz).as_posix()] = relatorio.sha256(conteudo)
        if nome == "plano.json":
            manifesto["plano_sha256"] = relatorio.sha256(conteudo)
        (self.pasta / "execucao.json").write_bytes(_json(manifesto))

    def linhas(self, nome):
        return relatorio._csv((self.pasta / nome).read_bytes())

    def test_carrega_48_sem_base_preserva_empates_e_ordem(self):
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["linhas"]), 8544)
        self.assertEqual(len(dados["por_video"]), 576)
        self.assertEqual(dados["ids"], [f"b{i:02d}" for i in range(1, 49)])
        self.assertEqual(dados["resumos"]["b01"]["f1_individuos"], dados["resumos"]["b13"]["f1_individuos"])
        self.assertFalse((self.raiz / "base_ficticia").exists())

    def test_rodadas_futuras_respeitam_orcamento(self):
        for rodada in ("round2", "round3", "round4", "round5"):
            with self.subTest(rodada=rodada):
                dados = relatorio.carregar(criar_fixture(self.raiz, rodada))
                self.assertEqual(len(dados["ids"]), relatorio.ORCAMENTO[rodada])

    def test_sem_casos_e_falso_positivo_sem_anotacao(self):
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(dados["resumos"]["b01"]["f1_aglomerados"], "")
        self.assertEqual(float(dados["resumos"]["b02"]["f1_aglomerados"]), 0)
        self.assertEqual(dados["resumos"]["b01"]["acuracia_condicional"], "")

    def test_hash_alterado_rejeitado(self):
        p = self.pasta / "resumo_por_video.csv"
        p.write_bytes(p.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            relatorio.carregar(self.pasta)

    def test_metricas_internamente_coerentes_mas_agregacao_errada(self):
        for nome, fator in (("resumo_configuracoes.csv", 178), ("resumo_por_video.csv", 15)):
            with self.subTest(nome=nome):
                original = (self.pasta / nome).read_bytes()
                linhas = self.linhas(nome)
                linhas[0].update(_metricas(1, fator))
                self.regravar(nome, _csv(linhas))
                with self.assertRaisesRegex(ValueError, "Agregação inconsistente"):
                    relatorio.carregar(self.pasta)
                self.regravar(nome, original)

    def test_agregacao_tempo_inconsistente(self):
        linhas = self.linhas("resumo_por_video.csv")
        linhas[0]["tempo_adaptacao_total_ns"] = "999"
        self.regravar("resumo_por_video.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "Agregação de tempo"):
            relatorio.carregar(self.pasta)

    def test_quadro_repetido_rejeitado(self):
        linhas = self.linhas("resumo_por_quadro.csv")
        linhas[1] = deepcopy(linhas[0])
        self.regravar("resumo_por_quadro.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "incompleto, repetido"):
            relatorio.carregar(self.pasta)

    def test_videos_selecao_rejeitados(self):
        plano = json.loads((self.pasta / "plano.json").read_bytes())
        plano["quadros"][0]["video_id"] = "13"
        self.regravar("plano.json", _json(plano))
        with self.assertRaisesRegex(ValueError, "178 quadros"):
            relatorio.carregar(self.pasta)

    def test_manifesto_booleano_e_incompleto_rejeitados(self):
        caminho = self.pasta / "execucao.json"
        original = json.loads(caminho.read_bytes())
        for campo, valor in (("versao", True), ("situacao", "em_andamento"), ("configuracoes_concluidas", 47)):
            m = deepcopy(original); m[campo] = valor
            caminho.write_bytes(_json(m))
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "Manifesto"):
                relatorio.carregar(self.pasta)

    def test_preserva_manifesto_e_gera_novas_pastas(self):
        antes = {x.name: x.read_bytes() for x in self.pasta.iterdir() if x.is_file()}
        def pdf_sintetico(caminho, dados):
            caminho.write_bytes(b"%PDF-SINTETICO\n")
            return 8
        with patch.object(relatorio, "escrever_pdf", side_effect=pdf_sintetico):
            primeiro = relatorio.gerar_relatorio(self.pasta)
            segundo = relatorio.gerar_relatorio(self.pasta)
        self.assertNotEqual(primeiro, segundo)
        for nome, conteudo in antes.items():
            self.assertEqual((self.pasta / nome).read_bytes(), conteudo)
        registro = json.loads((segundo.parent / "relatorio.json").read_bytes())
        self.assertEqual(registro["pdf_sha256"], relatorio.sha256(segundo.read_bytes()))
        self.assertEqual(len(registro["origens_sha256"]), 5)

    def test_pdf_48_paginado_e_sem_casos(self):
        pdf = relatorio.gerar_relatorio(self.pasta)
        conteudo = pdf.read_bytes()
        self.assertTrue(conteudo.startswith(b"%PDF-"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", conteudo)), 4)
        dados = relatorio.carregar(self.pasta)
        paginas = relatorio._paginas(dados)
        for tipo in ("metricas", "videos"):
            self.assertEqual([i for t, ids in paginas if t == tipo for i in ids], relatorio._ordem_visual(dados))
        vazios = relatorio.carregar(criar_fixture(self.raiz, "round5", vazio=True))
        destino = self.raiz / "vazio.pdf"
        self.assertEqual(relatorio.escrever_pdf(destino, vazios), 4)
        self.assertTrue(destino.read_bytes().startswith(b"%PDF-"))

    def converter_v2(self):
        self.pasta = criar_fixture(self.raiz, "round2")
        caminho = self.pasta / "execucao.json"
        m = json.loads(caminho.read_bytes()); m["versao"] = 2
        caminho.write_bytes(_json(m))
        plano = json.loads((self.pasta / "plano.json").read_bytes())
        plano["versao"] = 2
        plano["origem_round1"] = {"plano": "scripts/blobs/rodadas/round1.json", "sha256": "1" * 64}
        for i, item in enumerate(plano["configuracoes"]):
            item["metodo"] = ("simpleblob", "log", "dog")[i % 3]
            item["preprocessamento"] = ({"metodo": "nenhum"} if i % 2 == 0 else
                                       {"metodo": "clahe", "limite_contraste": 2.0, "grade": [8, 8]})
        self.regravar("plano.json", _json(plano))
        for nome in ("resumo_por_quadro.csv", "resumo_configuracoes.csv", "resumo_por_video.csv"):
            linhas = self.linhas(nome)
            for linha in linhas:
                agregado = nome != "resumo_por_quadro.csv"
                fator = int(linha["quantidade_quadros"]) if agregado else 1
                campo = "tempo_preprocessamento_total_ns" if agregado else "tempo_preprocessamento_ns"
                linha[campo] = 20 * fator
            self.regravar(nome, _csv(linhas))
        return plano

    def test_v2_metodos_clahe_tempos_e_pdf_compacto(self):
        self.converter_v2()
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["ids"]), 32)
        self.assertIn("LoG+H", relatorio._rotulo_configuracao(dados["plano"]["configuracoes"][1]))
        pdf = relatorio.gerar_relatorio(self.pasta)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 4)

    def test_v2_rejeita_pipeline_e_agregacao_preprocessamento(self):
        self.converter_v2()
        linhas = self.linhas("resumo_por_quadro.csv")
        original = (self.pasta / "resumo_por_quadro.csv").read_bytes()
        linhas[0]["tempo_preprocessamento_ns"] = "21"
        self.regravar("resumo_por_quadro.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "pipeline"):
            relatorio.carregar(self.pasta)
        self.regravar("resumo_por_quadro.csv", original)
        linhas = self.linhas("resumo_por_video.csv")
        linhas[0]["tempo_preprocessamento_total_ns"] = "999"
        self.regravar("resumo_por_video.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "Agregação de tempo"):
            relatorio.carregar(self.pasta)

    def test_empates_nao_usam_classe_normal_nem_id(self):
        dados = relatorio.carregar(self.pasta)
        for i in dados["ids"]:
            dados["resumos"][i]["f1_individuos"] = "0.5"
        dados["ids"].reverse()
        self.assertEqual(relatorio._ordem_visual(dados), dados["ids"])

    def test_delta_controlado_nao_mistura_metodo_ou_parametro(self):
        dados = relatorio.carregar(self.pasta)
        pares = relatorio._comparacoes_controle(dados)
        self.assertEqual(len(pares), 12)
        self.assertEqual(pares[1][1]["id"], "b01")
        dados["plano"]["configuracoes"][1]["parametros"]["outro"] = 1
        self.assertIsNone(relatorio._comparacoes_controle(dados)[1][1])

    def test_delta_clahe_v2_usa_controle_da_mesma_rodada(self):
        self.converter_v2()
        dados = relatorio.carregar(self.pasta)
        base = dados["plano"]["configuracoes"][0]
        for item in dados["plano"]["configuracoes"]:
            item["bloco"] = "exploracao"
            item["referencia"] = None
        base.update(bloco="controle", referencia="r1c29")
        variante = dados["plano"]["configuracoes"][1]
        ident = variante["id"]
        variante.update(deepcopy(base), id=ident, bloco="exploracao",
                        preprocessamento={"metodo": "clahe", "limite_contraste": 2, "grade": [8, 8]})
        comparacoes = relatorio._comparacoes_controle(dados)
        self.assertEqual(len(comparacoes), 2)
        self.assertEqual(comparacoes[1][1]["id"], base["id"])
        self.assertAlmostEqual(comparacoes[1][2], float(dados["resumos"][ident]["f1_individuos"]))

    def converter_v3(self):
        return self.converter_fatorial(3)

    def converter_v4(self):
        return self.converter_fatorial(4)

    def converter_v5(self):
        return self.converter_fatorial(5)

    def converter_fatorial(self, versao):
        """Desenho completo sintético; não lê imagens, anotações ou resultados reais."""
        self.pasta = criar_fixture(self.raiz, f"round{versao}")
        caminho = self.pasta / "execucao.json"
        m = json.loads(caminho.read_bytes()); m["versao"] = versao
        caminho.write_bytes(_json(m))
        plano = json.loads((self.pasta / "plano.json").read_bytes())
        plano["versao"] = versao
        for origem in range(1, versao):
            plano[f"origem_round{origem}"] = {"plano": f"scripts/blobs/rodadas/round{origem}.json", "sha256": str(origem) * 64}
        configs = []
        areas = {3: (32, 48, 64), 4: (48, 64, 80), 5: (56, 64, 72)}[versao]
        distancias = (6, 12) if versao == 3 else (6,)
        margens_sb = (3, 4) if versao == 3 else (2, 3)
        for area in areas:
            for distancia in distancias:
                for margem in margens_sb:
                    configs.append({"metodo": "simpleblob", "caixa": {"modo": "margem", "pixels": margem},
                                    "parametros": {"polaridade": "claro", "area_minima": area,
                                                   "distancia_minima": distancia, "area_maxima": 500}})
        escalas = {
            3: {"log": ((0.05, 0.08, 0.12), (4, 6)), "dog": ((0.05, 0.08, 0.12), (4, 6))},
            4: {"dog": ((0.12, 0.16, 0.20, 0.24), (6, 8)), "log": ((0.08, 0.12), (5, 6))},
            5: {"dog": ((0.10, 0.12, 0.14), (5, 6))},
        }[versao]
        for metodo, (respostas, margens) in escalas.items():
            for resposta in respostas:
                for margem in margens:
                    configs.append({"metodo": metodo, "caixa": {"modo": "margem", "pixels": margem},
                                    "parametros": {"polaridade": "claro", "limiar_resposta": resposta,
                                                   "sigma_minimo": 2, "sigma_maximo": 12}})
        if versao == 5:
            for raio in (12, 14):
                configs.append({"metodo": "log", "caixa": {"modo": "margem", "pixels": 6},
                                "parametros": {"polaridade": "claro", "limiar_resposta": 0.12,
                                               "sigma_minimo": 2, "sigma_maximo": 12,
                                               "classificacao": {"area_maxima_pequeno": math.pi * 4 ** 2,
                                                                 "area_minima_aglomerado": math.pi * raio ** 2}}})
        referencias = {
            3: {2: "r2c14", 3: "r2c06", 4: "r2c01", 8: "r2c11"},
            4: {2: "r3c05", 4: "r3c09", 7: "r3c24", 16: "r3c16", 18: "r3c18"},
            5: {3: "r4c03", 4: "r4c04", 10: "r4c07", 13: "r4c18"},
        }[versao]
        for i, config in enumerate(configs, 1):
            config.update(id=f"r{versao}c{i:02d}", bloco="controle" if i in referencias else "exploracao",
                          referencia=referencias.get(i), preprocessamento={"metodo": "nenhum"},
                          perfil_forma="inercia_04" if config["metodo"] == "simpleblob" else "escala")
        plano["configuracoes"] = configs
        self.regravar("plano.json", _json(plano))
        for nome in ("resumo_por_quadro.csv", "resumo_configuracoes.csv", "resumo_por_video.csv"):
            linhas = self.linhas(nome)
            for linha in linhas:
                i = int(linha["configuracao_id"][1:]) - 1
                config = configs[i]
                linha["configuracao_id"] = config["id"]
                if "bloco" in linha:
                    linha.update(bloco=config["bloco"], modo_caixa="margem", perfil_forma=config["perfil_forma"])
                agregado = nome != "resumo_por_quadro.csv"
                fator = int(linha["quantidade_quadros"]) if agregado else 1
                sufixo = "_total_ns" if agregado else "_ns"
                linha[f"tempo_preprocessamento{sufixo}"] = 0
                linha[f"tempo_pipeline{sufixo}"] = 120 * fator
            self.regravar(nome, _csv(linhas))
        return plano

    def test_v3_carrega_24_e_pareia_margens_sem_posicao_dos_controles(self):
        self.converter_v3()
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["linhas"]), 4272)
        pares = relatorio._comparacoes_fatoriais(dados)
        self.assertEqual(len(pares), 12)
        self.assertEqual([x["id"] for x in dados["plano"]["configuracoes"] if x["bloco"] == "controle"],
                         ["r3c02", "r3c03", "r3c04", "r3c08"])
        for par in pares:
            self.assertEqual(par["base"]["parametros"], par["maior"]["parametros"])
            self.assertGreater(par["maior"]["caixa"]["pixels"], par["base"]["caixa"]["pixels"])
            self.assertAlmostEqual(par["delta"], par["f1_maior"] - par["f1_base"])
        self.assertEqual((pares[0]["base"]["id"], pares[0]["maior"]["id"]), ("r3c01", "r3c02"))
        dados["plano"]["configuracoes"].reverse()
        invertidos = relatorio._comparacoes_fatoriais(dados)
        assinatura = lambda ps: {(p["base"]["id"], p["maior"]["id"], p["delta"]) for p in ps}
        self.assertEqual(assinatura(pares), assinatura(invertidos))

    def test_v3_rejeita_par_com_parametro_diferente_ou_margem_repetida(self):
        plano = self.converter_v3()
        for campo in ("parametros", "caixa", "preprocessamento"):
            alterado = deepcopy(plano)
            if campo == "parametros":
                alterado["configuracoes"][1][campo]["area_maxima"] = 501
            elif campo == "caixa":
                alterado["configuracoes"][1][campo]["pixels"] = 3
            else:
                alterado["configuracoes"][1][campo] = {"metodo": "clahe", "limite_contraste": 2, "grade": [8, 8]}
            self.regravar("plano.json", _json(alterado))
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "fatorial"):
                relatorio.carregar(self.pasta)

    def test_v3_confere_tempo_e_exige_metodo_explicito(self):
        plano = self.converter_v3()
        original = (self.pasta / "resumo_por_quadro.csv").read_bytes()
        linhas = self.linhas("resumo_por_quadro.csv"); linhas[0]["tempo_preprocessamento_ns"] = 1
        self.regravar("resumo_por_quadro.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "pipeline"):
            relatorio.carregar(self.pasta)
        self.regravar("resumo_por_quadro.csv", original)
        del plano["configuracoes"][0]["metodo"]
        self.regravar("plano.json", _json(plano))
        with self.assertRaisesRegex(ValueError, "explícitos"):
            relatorio.carregar(self.pasta)

    def test_v3_pdf_quatro_paginas_sem_modificar_resumos(self):
        self.converter_v3()
        antes = {p.name: p.read_bytes() for p in self.pasta.iterdir() if p.is_file()}
        pdf = relatorio.gerar_relatorio(self.pasta)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 4)
        registro = json.loads((pdf.parent / "relatorio.json").read_bytes())
        self.assertIn("pares de margem na quarta página", registro["ordenacao"])
        for nome, conteudo in antes.items():
            self.assertEqual((self.pasta / nome).read_bytes(), conteudo)
        dados = relatorio.carregar(self.pasta)
        for i in dados["ids"]:
            dados["resumos"][i]["f1_individuos"] = ""
        self.assertTrue(all(p["delta"] is None for p in relatorio._comparacoes_fatoriais(dados)))

    def test_v4_carrega_18_e_nove_pares_com_controles_intercalados(self):
        self.converter_v4()
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["linhas"]), 3204)
        pares = relatorio._comparacoes_fatoriais(dados)
        self.assertEqual(len(pares), 9)
        self.assertEqual([p["base"]["metodo"] for p in pares], ["simpleblob"] * 3 + ["dog"] * 4 + ["log"] * 2)
        self.assertEqual([x["id"] for x in dados["plano"]["configuracoes"] if x["bloco"] == "controle"],
                         ["r4c02", "r4c04", "r4c07", "r4c16", "r4c18"])
        for par in pares:
            self.assertEqual(par["base"]["parametros"], par["maior"]["parametros"])
            self.assertAlmostEqual(par["delta"], par["f1_maior"] - par["f1_base"])
        self.assertEqual((pares[3]["base"]["id"], pares[3]["maior"]["id"]), ("r4c07", "r4c08"))

    def test_v4_rejeita_fatores_ou_margens_de_outra_rodada(self):
        plano = self.converter_v4()
        for fator in ("resposta", "margem"):
            alterado = deepcopy(plano)
            if fator == "resposta":
                for i in (6, 7): alterado["configuracoes"][i]["parametros"]["limiar_resposta"] = 0.05
            else:
                alterado["configuracoes"][7]["caixa"]["pixels"] = 4
            self.regravar("plano.json", _json(alterado))
            with self.subTest(fator=fator), self.assertRaises(ValueError):
                relatorio.carregar(self.pasta)

    def test_v4_confere_pipeline_e_agregacao_preprocessamento(self):
        self.converter_v4()
        original = (self.pasta / "resumo_por_quadro.csv").read_bytes()
        linhas = self.linhas("resumo_por_quadro.csv"); linhas[0]["tempo_preprocessamento_ns"] = 1
        self.regravar("resumo_por_quadro.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "pipeline"):
            relatorio.carregar(self.pasta)
        self.regravar("resumo_por_quadro.csv", original)
        linhas = self.linhas("resumo_por_video.csv"); linhas[0]["tempo_preprocessamento_total_ns"] = 1
        self.regravar("resumo_por_video.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "Agregação de tempo"):
            relatorio.carregar(self.pasta)

    def test_v4_pdf_quatro_paginas_faixas_certas_sem_clahe(self):
        from reportlab.pdfgen.canvas import Canvas
        textos = []

        class CanvasTexto(Canvas):
            def drawString(self, x, y, text, *args, **kwargs):
                textos.append(str(text))
                return super().drawString(x, y, text, *args, **kwargs)

        self.converter_v4()
        antes = {p.name: p.read_bytes() for p in self.pasta.iterdir() if p.is_file()}
        with patch("reportlab.pdfgen.canvas.Canvas", CanvasTexto):
            pdf = relatorio.gerar_relatorio(self.pasta)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 4)
        texto = " ".join(textos)
        self.assertNotIn("CLAHE", texto)
        self.assertIn("área mínima 48/64/80, distância 6 e margem 2/3", texto)
        self.assertIn("DoG: resposta 0,12/0,16/0,20/0,24 e margem 6/8", texto)
        self.assertIn("LoG: resposta 0,08/0,12 e margem 5/6", texto)
        self.assertIn("r4c07 = r3c24", texto)
        self.assertIn("sigma 8,192", texto)
        self.assertIn("Trocas/n = erros de classificação 0/2", texto)
        registro = json.loads((pdf.parent / "relatorio.json").read_bytes())
        self.assertIn("pares de margem na quarta página", registro["ordenacao"])
        for nome, conteudo in antes.items():
            self.assertEqual((self.pasta / nome).read_bytes(), conteudo)

    def test_v5_carrega_14_com_seis_pares_de_margem_e_um_de_classificacao(self):
        self.converter_v5()
        dados = relatorio.carregar(self.pasta)
        self.assertEqual(len(dados["linhas"]), 2492)
        pares = relatorio._comparacoes_round5(dados)
        self.assertEqual([p["tipo"] for p in pares], ["margem"] * 6 + ["classificacao"])
        cls = pares[-1]
        self.assertEqual((cls["base"]["id"], cls["variante"]["id"]), ("r5c13", "r5c14"))
        self.assertEqual(cls["base"]["caixa"], cls["variante"]["caixa"])
        self.assertAlmostEqual(cls["delta"], cls["f1_maior"] - cls["f1_base"])
        self.assertEqual([x["id"] for x in dados["plano"]["configuracoes"] if x["bloco"] == "controle"],
                         ["r5c03", "r5c04", "r5c10", "r5c13"])
        dados["plano"]["configuracoes"].reverse()
        invertidos = relatorio._comparacoes_round5(dados)
        self.assertEqual((invertidos[-1]["base"]["id"], invertidos[-1]["variante"]["id"]), ("r5c13", "r5c14"))
        for ident in dados["ids"]:
            dados["resumos"][ident]["f1_individuos"] = ""
        self.assertTrue(all(p["delta"] is None for p in relatorio._comparacoes_round5(dados)))

    def test_v5_par_classificacao_rejeita_qualquer_segunda_alteracao(self):
        plano = self.converter_v5()
        for mudanca in ("pequeno", "caixa", "sigma", "limite_aglomerado"):
            alterado = deepcopy(plano)
            variante = alterado["configuracoes"][-1]
            if mudanca == "pequeno":
                variante["parametros"]["classificacao"]["area_maxima_pequeno"] = 60
            elif mudanca == "caixa":
                variante["caixa"]["pixels"] = 7
            elif mudanca == "sigma":
                variante["parametros"]["sigma_maximo"] = 13
            else:
                variante["parametros"]["classificacao"]["area_minima_aglomerado"] = math.pi * 13 ** 2
            self.regravar("plano.json", _json(alterado))
            with self.subTest(mudanca=mudanca), self.assertRaisesRegex(ValueError, "classificação"):
                relatorio.carregar(self.pasta)

    def test_v5_margens_e_tempos_validados(self):
        plano = self.converter_v5()
        alterado = deepcopy(plano); alterado["configuracoes"][7]["caixa"]["pixels"] = 8
        self.regravar("plano.json", _json(alterado))
        with self.assertRaisesRegex(ValueError, "Par fatorial"):
            relatorio.carregar(self.pasta)
        self.regravar("plano.json", _json(plano))
        linhas = self.linhas("resumo_por_quadro.csv"); linhas[0]["tempo_preprocessamento_ns"] = 1
        self.regravar("resumo_por_quadro.csv", _csv(linhas))
        with self.assertRaisesRegex(ValueError, "pipeline"):
            relatorio.carregar(self.pasta)

    def test_v5_pdf_quatro_paginas_distingue_caixa_de_classificacao(self):
        from reportlab.pdfgen.canvas import Canvas
        textos = []

        class CanvasTexto(Canvas):
            def drawString(self, x, y, text, *args, **kwargs):
                textos.append(str(text))
                return super().drawString(x, y, text, *args, **kwargs)

        self.converter_v5()
        antes = {p.name: p.read_bytes() for p in self.pasta.iterdir() if p.is_file()}
        with patch("reportlab.pdfgen.canvas.Canvas", CanvasTexto):
            pdf = relatorio.gerar_relatorio(self.pasta)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())), 4)
        texto = " ".join(textos)
        self.assertNotIn("CLAHE", texto)
        self.assertIn("Comparações de margem e de classificação", texto)
        self.assertIn("área mínima 56/64/72, distância 6 e margem 2/3", texto)
        self.assertIn("DoG com resposta 0,10/0,12/0,14 e margem 5/6", texto)
        self.assertIn("452,389 para 615,752", texto)
        self.assertIn("pode alterar TP, FP, FN e F1 mesmo com caixas idênticas", texto)
        self.assertIn("r5c13 = r4c18", texto)
        self.assertIn("diâmetro agl. 24 para 28 px", texto)
        registro = json.loads((pdf.parent / "relatorio.json").read_bytes())
        self.assertIn("pares de margem e classificação na quarta página", registro["ordenacao"])
        for nome, conteudo in antes.items():
            self.assertEqual((self.pasta / nome).read_bytes(), conteudo)


if __name__ == "__main__":
    unittest.main()
