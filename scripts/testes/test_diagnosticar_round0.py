"""Diagnóstico sobre artefatos inteiramente sintéticos, sem detector ou base real."""

from copy import deepcopy
import csv
from io import BytesIO, StringIO
import json
from math import pi
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.blobs import diagnosticar_round0 as cli


def json_bytes(dados):
    return (json.dumps(dados, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def csv_bytes(linhas, campos=None):
    s = StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=campos or list(linhas[0])); w.writeheader(); w.writerows(linhas)
    return s.getvalue().encode("utf-8-sig")


class DiagnosticarRound0Test(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory(); self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.saida = self.raiz / "resultados/frame-to-frame/blobs/round0"
        self.timestamp = "20000101T000000000000Z"
        self.origem = self.saida / f"inspecao__{self.timestamp}"
        for nome, valor in (("RAIZ", self.raiz), ("SAIDA", self.saida)):
            p = patch.object(cli, nome, valor); p.start(); self.addCleanup(p.stop)
        for fonte in cli.FONTES_CODIGO:
            self.gravar(self.raiz / fonte, b"# fonte sintetica de fixture\n")

    def gravar(self, destino, conteudo):
        destino.parent.mkdir(parents=True, exist_ok=True); destino.write_bytes(conteudo)
        return destino

    def rel(self, p):
        return p.relative_to(self.raiz).as_posix()

    def construir(self, vazio=False):
        escolhidas = [(v, 0) for v in ("11", "12", "15", "19", "21", "22")]
        img, ann = b"imagem original sintetica", b"0 0.5 0.5 0.25 0.25\n"
        dev = []
        for v in ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60"):
            for q in range(0, 1401, 100):
                if (v, q) in (("23", 900), ("23", 1100)):
                    continue
                x = {"video_id": v, "quadro": q,
                     "imagem": f"bases_de_dados/visem_tracking/dataset/Train/{v}/images/{v}_frame_{q}.jpg",
                     "anotacao": f"bases_de_dados/visem_tracking/dataset/Train/{v}/labels/{v}_frame_{q}.txt",
                     "sha256_imagem": cli.hash_bytes(img), "sha256_anotacao": cli.hash_bytes(ann)}
                dev.append(x)
                if (v, q) in escolhidas:
                    self.gravar(self.raiz / x["imagem"], img); self.gravar(self.raiz / x["anotacao"], ann)
        origem_dev = "scripts/limiarizacao/rodadas/round1.json"
        dev_bytes = json_bytes({"versao": 1, "algoritmo": "limiarizacao", "particao": "desenvolvimento", "rodada": "round1", "quadros": dev})
        self.gravar(self.raiz / origem_dev, dev_bytes)
        quadros = []
        for x in dev:
            if (x["video_id"], x["quadro"]) in escolhidas:
                quadros.append({**{k: x[k] for k in ("video_id", "quadro", "imagem", "anotacao")},
                                "imagem_sha256": x["sha256_imagem"], "anotacao_sha256": x["sha256_anotacao"], "objetivo": "Inspeção sintética."})
        configs = [{"id": "b01", "parametros": {"polaridade": "claro"}}, {"id": "b02", "parametros": {"polaridade": "escuro"}}]
        self.plano = {"versao": 1, "algoritmo": "blobs", "particao": "desenvolvimento", "rodada": "round0", "etapa": "inspecao",
                      "quadros": quadros, "configuracoes": configs,
                      "origem_desenvolvimento": {"plano": origem_dev, "sha256": cli.hash_bytes(dev_bytes)}}
        pb = json_bytes(self.plano); self.gravar(self.origem / "plano.json", pb)
        fonte_plano = "scripts/blobs/inspecao/round0.json"; self.gravar(self.raiz / fonte_plano, pb)
        self.gravar(self.origem / "origem_desenvolvimento.json", dev_bytes)
        b = BytesIO()
        with ZipFile(b, "w") as z:
            z.writestr("origem.py", b"# fonte original sintetica\n")
        self.gravar(self.origem / "codigo.zip", b.getvalue())
        opencv = {"b01": {"blobColor": 255}, "b02": {"blobColor": 0}}
        self.m = {"versao": 1, "tipo": "inspecao_blobs", "situacao": "concluida", "algoritmo": "blobs", "etapa": "inspecao",
                  "rodada": "round0", "particao": "desenvolvimento", "configuracoes_previstas": 2,
                  "configuracoes_concluidas": 2, "quadros_por_configuracao": 6, "plano_sha256": cli.hash_bytes(pb),
                  "parametros_opencv": opencv, "execucoes": [], "criterios": {"versao": 1},
                  "origens_sha256": {fonte_plano: cli.hash_bytes(pb), origem_dev: cli.hash_bytes(dev_bytes)},
                  "codigo": {"sha256_zip": cli.hash_bytes(b.getvalue()), "sha256_arquivos": {"origem.py": cli.hash_bytes(b"# fonte original sintetica\n")}}}
        for q in quadros:
            for k in ("imagem", "anotacao"):
                self.m["origens_sha256"][q[k]] = q[f"{k}_sha256"]
        self.pastas = []; linhas = []; resumos = []
        for cfg in configs:
            ident = cfg["id"]; p = self.saida / f"{ident}__sintetica__{self.timestamp}"; self.pastas.append(p)
            self.m["execucoes"].append({"configuracao_id": ident, "pasta": self.rel(p)})
            canonico = json.dumps(cfg["parametros"], sort_keys=True, separators=(",", ":")).encode()
            cm = {"situacao": "concluida", "tipo": "inspecao_blobs", "configuracao_id": ident,
                  "quadros_concluidos": 6, "batch": self.rel(self.origem), "plano_sha256": self.m["plano_sha256"],
                  "configuracao_sha256": cli.hash_bytes(canonico), "parametros_opencv": opencv[ident]}
            for n, v in (("execucao.json", cm), ("configuracao.json", cfg["parametros"]), ("configuracao_opencv.json", opencv[ident]), ("avaliacao.json", {"quantidade_quadros": 6})):
                self.gravar(p / n, json_bytes(v))
            linhas_cfg = []
            for q in quadros:
                d = p / "quadros" / f"{q['video_id']}_frame_{q['quadro']}"
                orig = {k: q[k] for k in ("video_id", "quadro", "imagem", "anotacao")}
                a = {**orig, "indice_anotacao": 0, "classe": 0, "caixa_x_px": 30, "caixa_y_px": 30, "caixa_largura_px": 20, "caixa_altura_px": 20}
                det = {**orig, "indice_deteccao": 0, "classe": 0, "caixa_x_px": 35, "caixa_y_px": 35, "caixa_largura_px": 10, "caixa_altura_px": 10,
                       "centro_blob_x_px": 40, "centro_blob_y_px": 40, "diametro_blob_px": 10, "area_estimada_blob_px2": pi * 25,
                       "origem_medidas": "simpleblob_keypoint", "algoritmo": "blobs"}
                self.gravar(d / "anotacoes.csv", csv_bytes([a]))
                self.gravar(d / "deteccoes.csv", csv_bytes([] if vazio else [det], list(det)))
                self.gravar(d / "avaliacao.json", json_bytes({"origem": orig, "dimensoes": {"largura": 80, "altura": 80}, "criterios": self.m["criterios"]}))
                for n in ("pares.csv", "pendentes.csv", "predicoes.txt", "comparacao.png"):
                    self.gravar(d / n, b"artefato sintetico\n")
                linha = {"configuracao_id": ident, **orig, "quantidade_anotacoes": 1, "quantidade_deteccoes": 0 if vazio else 1,
                         "imagem_largura_px": 80, "imagem_altura_px": 80}
                linhas_cfg.append(linha); linhas.append(linha)
            self.gravar(p / "resumo_por_quadro.csv", csv_bytes(linhas_cfg))
            resumos.append({"configuracao_id": ident, "quantidade_quadros": 6})
        self.gravar(self.origem / "resumo_por_quadro.csv", csv_bytes(linhas))
        self.gravar(self.origem / "resumo_configuracoes.csv", csv_bytes(resumos))
        self.m["saidas_sha256"] = {self.rel(p): cli.hash_bytes(p.read_bytes()) for base in [self.origem, *self.pastas] for p in base.rglob("*") if p.is_file()}
        self.assertEqual(len(self.m["saidas_sha256"]), 99)
        self.salvar_manifesto()
        self.gravar(self.origem / "relatorio.json", json_bytes({"situacao": "falhou", "erro": "PDF não solicitado na fixture."}))

    def salvar_manifesto(self):
        self.gravar(self.origem / "execucao.json", json_bytes(self.m))

    def atualizar_hash(self, p):
        self.m["saidas_sha256"][self.rel(p)] = cli.hash_bytes(p.read_bytes()); self.salvar_manifesto()

    def assinaturas_origem(self):
        return {self.rel(p): cli.hash_bytes(p.read_bytes()) for d in [self.origem, *self.pastas] for p in d.rglob("*") if p.is_file()}

    def test_fluxo_sintetico_completo_e_campos_humanos_em_branco(self):
        self.construir(); antes = self.assinaturas_origem()
        destino = cli.executar(self.origem)
        manifesto = cli.carregar_json((destino / "execucao.json").read_bytes())
        self.assertEqual(manifesto["situacao"], "concluida"); self.assertEqual(manifesto["casos_concluidos"], 12)
        self.assertEqual(len(list((destino / "quadros").rglob("diagnostico.json"))), 12)
        campos, linhas = cli.ler_csv((destino / "anotacoes.csv").read_bytes())
        self.assertEqual(len(linhas), 12); self.assertTrue(all(x["quantidade_centros"] == "1" for x in linhas))
        self.assertTrue(all(float(x["melhor_iou_mesmo_grupo"]) == 0.25 for x in linhas))
        self.assertFalse(any("f1" in c.lower() for c in campos))
        _, humanas = cli.ler_csv((destino / "modelo_revisao_humana.csv").read_bytes())
        self.assertEqual(len(humanas), 24)
        self.assertEqual(sum(x["tipo_registro"] == "anotacao" for x in humanas), 12)
        self.assertEqual(sum(x["tipo_registro"] == "deteccao" for x in humanas), 12)
        self.assertTrue(all(x["quantidade_relacoes"] == "1" for x in humanas))
        self.assertTrue(all(not x["observacao_humana"] and not x["hipotese_em_revisao"] for x in humanas))
        self.assertFalse(list(destino.rglob("*.png"))); self.assertFalse(list(destino.rglob("*.pdf")))
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(cli.hash_bytes((self.raiz / nome).read_bytes()), digest)
        self.assertEqual(antes, self.assinaturas_origem())

    def test_repeticao_cria_novo_diagnostico_preservando_origem(self):
        self.construir(); antes = self.assinaturas_origem()
        primeiro = cli.executar(self.origem); segundo = cli.executar(self.origem)
        self.assertNotEqual(primeiro, segundo); self.assertEqual(antes, self.assinaturas_origem())

    def test_hash_de_saida_corrupto_nao_cria_resultados(self):
        self.construir(); p = self.origem / "resumo_configuracoes.csv"; p.write_bytes(p.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Hash de saída"):
            cli.executar(self.origem)
        self.assertFalse(list(self.saida.glob("diagnostico__*")))

    def test_resumo_deve_preservar_cartesiano_dos_12_casos(self):
        self.construir(); p = self.origem / "resumo_por_quadro.csv"
        campos, linhas = cli.ler_csv(p.read_bytes()); linhas[1] = deepcopy(linhas[0]); p.write_bytes(csv_bytes(linhas, campos)); self.atualizar_hash(p)
        with self.assertRaisesRegex(ValueError, "12 casos"):
            cli.executar(self.origem)
        self.assertFalse(list(self.saida.glob("diagnostico__*")))

    def test_rejeita_estado_parcial_versao_booleana_e_pasta_incorreta(self):
        self.construir()
        for campo, valor in (("situacao", "falhou"), ("versao", True), ("configuracoes_concluidas", 1)):
            copia = deepcopy(self.m); self.m[campo] = valor; self.salvar_manifesto()
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                cli.congelar(self.origem)
            self.m = copia; self.salvar_manifesto()
        with self.assertRaises(ValueError):
            cli.congelar(self.saida)

    def test_zero_deteccoes_mantem_anotacoes_e_csv_com_cabecalho(self):
        self.construir(vazio=True); destino = cli.executar(self.origem)
        campos, det = cli.ler_csv((destino / "deteccoes.csv").read_bytes())
        self.assertIn("indice_deteccao", campos); self.assertEqual(det, [])
        _, anot = cli.ler_csv((destino / "anotacoes.csv").read_bytes())
        self.assertEqual(len(anot), 12)
        self.assertTrue(all(x["quantidade_centros"] == "0" and x["melhor_iou_qualquer_classe"] == "" for x in anot))

    def test_falha_diagnostico_preserva_original_e_registra_incompleto(self):
        self.construir(); antes = self.assinaturas_origem()
        with patch("analise.diagnostico_blobs.diagnosticar_quadro", side_effect=RuntimeError("falha sintética")):
            with self.assertRaisesRegex(RuntimeError, "falha sintética"):
                cli.executar(self.origem)
        destino = next(self.saida.glob("diagnostico__*"))
        m = cli.carregar_json((destino / "execucao.json").read_bytes())
        self.assertEqual(m["situacao"], "falhou"); self.assertEqual(m["casos_concluidos"], 0)
        self.assertEqual(antes, self.assinaturas_origem())

    def test_valor_nao_finito_rejeitado_antes_de_criar_saida(self):
        self.construir(); p = next(self.pastas[0].rglob("deteccoes.csv"))
        campos, linhas = cli.ler_csv(p.read_bytes()); linhas[0]["centro_blob_x_px"] = "nan"
        p.write_bytes(csv_bytes(linhas, campos)); self.atualizar_hash(p)
        with self.assertRaisesRegex(ValueError, "finitas"):
            cli.executar(self.origem)
        self.assertFalse(list(self.saida.glob("diagnostico__*")))


if __name__ == "__main__":
    unittest.main()
