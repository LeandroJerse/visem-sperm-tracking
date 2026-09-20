"""Testes sintéticos da leitura, ordenação e saída da reavaliação da seleção."""

from contextlib import ExitStack
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.limiarizacao import reavaliar_selecao as script


def linha_ranking(identificador, tp, fp, fn, **extras):
    return {"configuracao_id": identificador, "tp_individuos": tp,
            "fp_individuos": fp, "fn_individuos": fn, **extras}


class RankingTest(unittest.TestCase):
    def test_empate_exato_nao_usa_classificacao_ou_aglomerados(self):
        linhas = [
            linha_ranking("s002", 2, 2, 2, acuracia_condicional=1, f1_aglomerados=1),
            linha_ranking("s001", 1, 1, 1, acuracia_condicional=0, f1_aglomerados=0),
            linha_ranking("s003", 0, 1, 0),
        ]
        resultado = script.construir_ranking(linhas)
        self.assertEqual([r["configuracao_id"] for r in resultado], ["s001", "s002", "s003"])
        self.assertEqual([r["rank_f1_individuos"] for r in resultado], [1, 1, 2])
        self.assertEqual([r["quantidade_empatadas"] for r in resultado], [2, 2, 1])
        self.assertEqual((resultado[0]["f1_numerador"], resultado[0]["f1_denominador"]), (1, 2))

    def test_fracoes_proximas_nao_viram_empate_por_arredondamento(self):
        resultado = script.construir_ranking([
            linha_ranking("s001", 10**18, 1, 0),
            linha_ranking("s002", 10**18 + 1, 1, 0),
        ])
        self.assertEqual([r["configuracao_id"] for r in resultado], ["s002", "s001"])
        self.assertEqual([r["rank_f1_individuos"] for r in resultado], [1, 2])

    def test_marca_todo_empate_que_atravessa_corte(self):
        linhas = [linha_ranking(f"s{i:03d}", 1, i - 1, 0) for i in range(1, 5)]
        linhas.extend(linha_ranking(f"s{i:03d}", 1, 4, 0) for i in range(5, 8))
        resultado = script.construir_ranking(linhas)
        self.assertEqual([r["configuracao_id"] for r in resultado if r["empate_no_corte_5"]],
                         ["s005", "s006", "s007"])
        self.assertTrue(all(r["rank_f1_individuos"] == 5 for r in resultado[4:]))

    def test_empate_que_termina_em_cinco_nao_atravessa_corte(self):
        linhas = [linha_ranking(f"s{i:03d}", 1, 0, 0) for i in range(1, 6)]
        linhas.append(linha_ranking("s006", 0, 1, 0))
        self.assertFalse(any(r["empate_no_corte_5"] for r in script.construir_ranking(linhas)))

    def test_sem_casos_vem_depois_de_f1_zero_e_nao_recebe_rank(self):
        resultado = script.construir_ranking([
            linha_ranking("s001", 0, 0, 0), linha_ranking("s002", 0, 0, 3),
        ])
        self.assertEqual(resultado[0]["configuracao_id"], "s002")
        self.assertEqual(resultado[0]["f1_numerador"], 0)
        self.assertTrue(resultado[1]["sem_casos"])
        self.assertIsNone(resultado[1]["rank_f1_individuos"])
        self.assertIsNone(resultado[1]["f1_denominador"])


class LeituraTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.contextos = ExitStack()
        self.addCleanup(self.contextos.close)
        self.contextos.enter_context(patch.object(script, "RAIZ", self.raiz))
        self.contextos.enter_context(patch.object(script, "CHAVES_QUADROS", {("13", 0)}))
        self.contextos.enter_context(patch.object(script, "VIDEOS", ("13",)))
        self.pasta = self.raiz / script.PASTA_SELECAO / "configuracao_teste"
        self.pasta.mkdir(parents=True)
        self.origem = {"imagem": "original.jpg", "anotacao": "original.txt", "video_id": "13",
                       "quadro": "0", "tempo_segundos": ""}
        self.parametros = {"metodo": "otsu", "polaridade": "claro"}
        conteudo_parametros = json.dumps(self.parametros, sort_keys=True, separators=(",", ":")).encode()
        self.escrever_json("configuracao.json", self.parametros)
        self.escrever_json("execucao.json", {"configuracao_sha256": script.sha256(conteudo_parametros)})
        self.linha_quadro = {
            **self.origem, "imagem_largura_px": "100", "imagem_altura_px": "100",
            "quantidade_anotacoes": "1", "quantidade_deteccoes": "1",
            "anotacoes_classe_0": "1", "anotacoes_classe_1": "0", "anotacoes_classe_2": "0",
            "deteccoes_classe_0": "0", "deteccoes_classe_1": "0", "deteccoes_classe_2": "1",
        }
        caixa = {"caixa_x_px": "0", "caixa_y_px": "0", "caixa_largura_px": "10", "caixa_altura_px": "10",
                 "caixa_centro_x_norm": "0.05", "caixa_centro_y_norm": "0.05",
                 "caixa_largura_norm": "0.1", "caixa_altura_norm": "0.1"}
        self.anotacao = {**self.origem, "indice_anotacao": "0", "classe": "0", **caixa}
        self.deteccao = {**self.origem, "indice_deteccao": "0", "classe": "2", "algoritmo": "limiarizacao",
                         "imagem_largura_px": "100", "imagem_altura_px": "100", **caixa}
        self.escrever_csv("por_quadro.csv", [self.linha_quadro])
        self.escrever_csv("anotacoes.csv", [self.anotacao])
        self.escrever_csv("deteccoes.csv", [self.deteccao])
        antigo = {"tp_classe_0": 0, "fp_classe_0": 0, "fn_classe_0": 1,
                  "tp_classe_1": 0, "fp_classe_1": 0, "fn_classe_1": 0,
                  "tp_classe_2": 0, "fp_classe_2": 1, "fn_classe_2": 0}
        self.dados = {
            "totais_por_id": {"s001": {"pasta": self.pasta.relative_to(self.raiz).as_posix()}},
            "configuracoes": {"s001": {"parametros": self.parametros}},
            "origens_sha256": {}, "anotacoes_referencia": {},
            "plano": {"quadros": [{"video_id": "13", "quadro": 0, "imagem": "original.jpg", "anotacao": "original.txt"}]},
            "por_video": {("s001", "13"): antigo},
        }

    def escrever_json(self, nome, dados):
        (self.pasta / nome).write_text(json.dumps(dados), encoding="utf-8")

    def escrever_csv(self, nome, linhas):
        buffer = StringIO(newline="")
        escritor = csv.DictWriter(buffer, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
        (self.pasta / nome).write_text(buffer.getvalue(), encoding="utf-8")

    def test_le_caixas_sem_abrir_imagem_ou_anotacao_original(self):
        resultado = script._carregar_configuracao(self.dados, "s001")
        self.assertEqual(resultado[0]["anotacoes"][0].classe, 0)
        self.assertEqual(resultado[0]["deteccoes"][0].classe, 2)
        self.assertFalse((self.raiz / "original.jpg").exists())
        self.assertEqual(len(self.dados["origens_sha256"]), 5)

    def test_alteracao_apos_prevalidacao_interrompe(self):
        script._carregar_configuracao(self.dados, "s001")
        self.deteccao["classe"] = "0"
        self.escrever_csv("deteccoes.csv", [self.deteccao])
        with self.assertRaisesRegex(ValueError, "entrada mudou"):
            script._carregar_configuracao(self.dados, "s001", congelados=True)

    def test_mesma_contagem_com_caixa_gt_diferente_e_rejeitada(self):
        script._carregar_configuracao(self.dados, "s001")
        self.anotacao.update({"caixa_x_px": "10", "caixa_centro_x_norm": "0.15"})
        self.escrever_csv("anotacoes.csv", [self.anotacao])
        self.dados["origens_sha256"] = {}
        with self.assertRaisesRegex(ValueError, "Anotações ou dimensões diferem"):
            script._carregar_configuracao(self.dados, "s001")

    def test_contagem_por_classe_incompativel_e_rejeitada(self):
        self.linha_quadro["anotacoes_classe_0"] = "0"
        self.escrever_csv("por_quadro.csv", [self.linha_quadro])
        with self.assertRaisesRegex(ValueError, "Contagem por classe divergente"):
            script._carregar_configuracao(self.dados, "s001")

    def test_caixas_incompativeis_com_resumo_antigo_sao_rejeitadas(self):
        self.dados["por_video"][("s001", "13")]["fp_classe_2"] = 2
        with self.assertRaisesRegex(ValueError, "Caixas e resumos salvos divergem"):
            script._carregar_configuracao(self.dados, "s001")

    def test_quadro_duplicado_e_rejeitado(self):
        self.escrever_csv("por_quadro.csv", [self.linha_quadro, self.linha_quadro])
        with self.assertRaisesRegex(ValueError, "sem repetição"):
            script._carregar_configuracao(self.dados, "s001")

    def test_leitor_bloqueia_arquivos_fora_da_selecao(self):
        fora = self.raiz / "fora.csv"
        fora.write_text("a\n1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "somente CSV/JSON"):
            script._ler(fora, {})

    def test_plano_diferente_do_aprovado_e_rejeitado_antes_do_carregador(self):
        self.escrever_json("execucao.json", {"execucoes": []})
        self.escrever_json("rodada.json", {"versao": 1})
        self.escrever_csv("resumo_configuracoes.csv", [{"configuracao_id": "s001"}])
        self.escrever_csv("resumo_por_video.csv", [{"configuracao_id": "s001"}])
        with patch.object(script, "_carregar") as carregar:
            with self.assertRaisesRegex(ValueError, "não é o plano aprovado"):
                script.prevalidar(self.pasta)
            carregar.assert_not_called()


class FluxoTest(unittest.TestCase):
    def test_falha_de_prevalidacao_impede_pareamento_e_criacao_de_saida(self):
        with patch.object(script, "prevalidar", side_effect=ValueError("entrada inválida")), \
                patch.object(script.avaliador, "avaliar") as avaliar, \
                patch.object(script, "_arquivar_codigo") as arquivar:
            with self.assertRaisesRegex(ValueError, "entrada inválida"):
                script.reavaliar(Path("batch"))
            avaliar.assert_not_called()
            arquivar.assert_not_called()

    def test_todas_as_configuracoes_sao_prevalidadas(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            pasta = raiz / script.PASTA_SELECAO / "batch_copia"
            pasta.mkdir(parents=True)
            plano = {"particao": "selecao", "algoritmo": "limiarizacao", "rodada": "selecao",
                     "seed": 42, "exclusoes": [],
                     "quadros": [{"video_id": v, "quadro": q} for v, q in sorted(script.CHAVES_QUADROS)]}
            dados = {"plano": plano, "execucao": {"etapa": "selecao_imagens", "exclusoes": []}, "origens_sha256": {},
                     "configuracoes": dict.fromkeys(script.IDS), "totais": []}
            with patch.object(script, "RAIZ", raiz), patch.object(script, "_carregar", return_value=dados), \
                    patch.object(script, "_prevalidar_caminhos", return_value={}), \
                    patch.object(script, "_carregar_configuracao") as carregar, \
                    patch.object(script.avaliador, "avaliar") as avaliar:
                script.prevalidar(pasta)
                self.assertEqual([c.args[1] for c in carregar.call_args_list], list(script.IDS))
                avaliar.assert_not_called()

    def test_somente_relatorio_nao_reavalia(self):
        with patch.object(script, "gerar_relatorio", return_value=Path("relatorio.pdf")) as gerar, \
                patch.object(script, "reavaliar") as reavaliar:
            script.main(["--somente-relatorio", "avaliacao_salva"])
            gerar.assert_called_once_with(Path("avaliacao_salva"))
            reavaliar.assert_not_called()

    def test_batch_padrao_e_fixo(self):
        with patch.object(script, "reavaliar", return_value=Path("nova_avaliacao")) as reavaliar:
            script.main([])
            reavaliar.assert_called_once_with(script.BATCH_PADRAO)
            self.assertEqual(script.BATCH_PADRAO.name, "batch__20260920T012713968145Z")

    def test_batch_e_somente_relatorio_sao_exclusivos(self):
        with patch.object(script, "reavaliar") as reavaliar, patch.object(script, "gerar_relatorio") as gerar:
            with self.assertRaises(SystemExit):
                script.main(["--batch", "batch", "--somente-relatorio", "avaliacao"])
            reavaliar.assert_not_called()
            gerar.assert_not_called()

    def test_recuperar_pdf_atualiza_estado_sem_modificar_manifesto_das_metricas(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            pasta = raiz / script.PASTA_SELECAO / "batch" / "reavaliacoes_individuos" / "execucao"
            pasta.mkdir(parents=True)
            manifesto = pasta / "execucao.json"
            manifesto.write_text('{"situacao": "concluida"}\n', encoding="utf-8")
            conteudo_original = manifesto.read_bytes()
            with patch.object(script, "RAIZ", raiz), \
                    patch("analise.relatorio_individuos.gerar_relatorio", side_effect=ValueError("dependência ausente")):
                with self.assertRaisesRegex(ValueError, "dependência ausente"):
                    script.gerar_relatorio(pasta)
                estado = json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))
                self.assertEqual(estado["situacao"], "falhou")
            pdf = pasta / "relatorios" / "segunda_tentativa" / "relatorio.pdf"
            with patch.object(script, "RAIZ", raiz), \
                    patch("analise.relatorio_individuos.gerar_relatorio", return_value=pdf):
                script.gerar_relatorio(pasta)
                estado = json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))
                self.assertEqual(estado["situacao"], "concluido")
                self.assertEqual(manifesto.read_bytes(), conteudo_original)


if __name__ == "__main__":
    unittest.main()
