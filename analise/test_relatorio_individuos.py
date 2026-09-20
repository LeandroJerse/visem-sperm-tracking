"""Validações sintéticas do leitor do relatório, sem gerar PDFs ou usar a base."""

from copy import deepcopy
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analise.avaliacao_individuos import CRITERIOS
from analise import relatorio_individuos as relatorio


def _recalcular_taxas(linha):
    """Preenche taxas de uma fixture a partir das contagens sintéticas."""
    def taxa(numerador, denominador):
        return numerador / denominador if denominador else None

    for grupo in ("individuos", "aglomerados"):
        tp, fp, fn = (linha[f"{campo}_{grupo}"] for campo in ("tp", "fp", "fn"))
        linha[f"precisao_{grupo}"] = taxa(tp, tp + fp)
        linha[f"recall_{grupo}"] = taxa(tp, tp + fn)
        linha[f"f1_{grupo}"] = taxa(2 * tp, 2 * tp + fp + fn)
        linha[f"situacao_f1_{grupo}"] = "definido" if tp + fp + fn else "sem_casos"
    for classe in (0, 2, 1):
        linha[f"recall_classe_{classe}"] = taxa(
            linha[f"localizadas_classe_{classe}"], linha[f"anotacoes_classe_{classe}"],
        )
    linha["acuracia_condicional"] = taxa(linha["pares_corretos"], linha["pares_total"])
    return linha


def _linha_sintetica(identificador="s001", video="13", tp=1, fp=1, fn=1):
    linha = {campo: 0 for campo in relatorio.CONTAGENS}
    linha.update({
        "configuracao_id": identificador,
        "pasta_origem": f"resultados/frame-to-frame/limiarizacao/selecao/{identificador}",
        "video_id": video,
        "quantidade_quadros": 1,
        "tp_individuos": tp, "fp_individuos": fp, "fn_individuos": fn,
        "pares_corretos": tp, "pares_total": tp, "matriz_0_0": tp,
        "anotacoes_classe_0": tp + fn, "localizadas_classe_0": tp,
        "perdidas_classe_0": fn,
    })
    return _recalcular_taxas(linha)


class TesteValidacaoLinhaIndividuos(unittest.TestCase):
    def test_denominador_zero_exige_nulo_e_zero_com_denominador_e_definido(self):
        relatorio._taxa_confere({"taxa": None}, "taxa", 0, 0)
        relatorio._taxa_confere({"taxa": 0.0}, "taxa", 0, 7)
        with self.assertRaisesRegex(ValueError, "Taxa incompatível"):
            relatorio._taxa_confere({"taxa": 0.0}, "taxa", 0, 0)
        with self.assertRaisesRegex(ValueError, "Taxa incompatível"):
            relatorio._taxa_confere({"taxa": None}, "taxa", 0, 7)

    def test_linha_sem_casos_preserva_nulos_e_previsao_isolada_da_zero(self):
        vazio = relatorio._linha(_linha_sintetica(tp=0, fp=0, fn=0))
        falso_positivo = relatorio._linha(_linha_sintetica(tp=0, fp=1, fn=0))
        self.assertIsNone(vazio["f1_individuos"])
        self.assertEqual(vazio["situacao_f1_individuos"], "sem_casos")
        self.assertIsNone(vazio["acuracia_condicional"])
        self.assertEqual(falso_positivo["f1_individuos"], 0.0)
        self.assertIsNone(falso_positivo["recall_individuos"])
        self.assertEqual(falso_positivo["situacao_f1_individuos"], "definido")

    def test_acuracia_condicional_nao_inclui_objetos_perdidos(self):
        linha = _linha_sintetica(tp=1, fp=5, fn=99)
        resultado = relatorio._linha(linha)
        self.assertEqual(resultado["acuracia_condicional"], 1.0)
        self.assertEqual(resultado["recall_classe_0"], 0.01)
        linha["acuracia_condicional"] = 0.01
        with self.assertRaisesRegex(ValueError, "acuracia_condicional"):
            relatorio._linha(linha)

    def test_rejeita_matriz_e_cobertura_incoerentes(self):
        base = _linha_sintetica(tp=2, fp=1, fn=3)
        casos = (
            {"pares_total": 3},
            {"matriz_0_0": 1, "matriz_2_2": 1},
            {"anotacoes_classe_0": 6},
            {"localizadas_classe_0": 1, "perdidas_classe_0": 4, "recall_classe_0": 0.2},
        )
        for alteracao in casos:
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                relatorio._linha({**base, **alteracao})

    def test_troca_de_classe_preserva_cobertura_mas_reduz_acuracia_condicional(self):
        linha = _linha_sintetica(tp=2, fp=0, fn=0)
        linha.update(matriz_0_0=1, matriz_0_2=1, pares_corretos=1,
                     pares_incorretos=1, acuracia_condicional=0.5)
        resultado = relatorio._linha(linha)
        self.assertEqual(resultado["f1_individuos"], 1.0)
        self.assertEqual(resultado["recall_classe_0"], 1.0)
        self.assertEqual(resultado["acuracia_condicional"], 0.5)

    def test_pontuacao_usa_fracao_exata_em_vez_do_float_salvo(self):
        grande = 10 ** 18
        melhor = _linha_sintetica(tp=grande, fp=0, fn=0)
        pior = _linha_sintetica(tp=grande, fp=1, fn=0)
        self.assertEqual(melhor["f1_individuos"], pior["f1_individuos"])
        self.assertEqual(relatorio._pontuacao(melhor), Fraction(1))
        self.assertGreater(relatorio._pontuacao(melhor), relatorio._pontuacao(pior))
        self.assertIsNone(relatorio._pontuacao(_linha_sintetica(tp=0, fp=0, fn=0)))


class TesteLeituraRelatorioIndividuos(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name).resolve()
        self.batch = self.raiz / "resultados/frame-to-frame/limiarizacao/selecao/batch__sintetico"
        self.pasta = self.batch / "reavaliacoes_individuos/sintetica"
        self.pasta.mkdir(parents=True)
        substituicao = patch.object(relatorio, "RAIZ", self.raiz)
        substituicao.start()
        self.addCleanup(substituicao.stop)

    def _json(self, caminho, valor):
        caminho.write_text(json.dumps(valor, ensure_ascii=False, allow_nan=False), encoding="utf-8")

    def _csv(self, nome, linhas):
        campos = ["configuracao_id", "pasta_origem"]
        if nome == "resumo_por_video.csv":
            campos.append("video_id")
        campos.extend(relatorio.CONTAGENS)
        campos.extend(relatorio.TAXAS)
        campos.extend(["situacao_f1_individuos", "situacao_f1_aglomerados"])
        with (self.pasta / nome).open("w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(linhas)

    def _hash(self, caminho):
        return hashlib.sha256(caminho.read_bytes()).hexdigest()

    def _atualizar_hashes_saidas(self):
        self.manifesto["saidas_sha256"] = {
            caminho.relative_to(self.raiz).as_posix(): self._hash(caminho)
            for caminho in (self.pasta / "resumo_configuracoes.csv", self.pasta / "resumo_por_video.csv")
        }
        self._json(self.pasta / "execucao.json", self.manifesto)

    def _preparar(self, linhas):
        self.por_video = deepcopy(linhas)
        ids = list(dict.fromkeys(linha["configuracao_id"] for linha in linhas))
        videos = list(dict.fromkeys(linha["video_id"] for linha in linhas))
        self.totais = []
        for identificador in ids:
            partes = [linha for linha in linhas if linha["configuracao_id"] == identificador]
            total = {campo: sum(parte[campo] for parte in partes) for campo in relatorio.CONTAGENS}
            total.update(configuracao_id=identificador, pasta_origem=partes[0]["pasta_origem"])
            self.totais.append(_recalcular_taxas(total))
        self.plano = {
            "versao": 1, "particao": "selecao", "rodada": "selecao", "algoritmo": "limiarizacao",
            "configuracoes": [{"id": i, "parametros": {"metodo": "manual"}} for i in ids],
            "quadros": [{"video_id": video, "quadro": 0} for video in videos],
        }
        caminho_plano = self.batch / "rodada.json"
        self._json(caminho_plano, self.plano)
        self._csv("resumo_configuracoes.csv", self.totais)
        self._csv("resumo_por_video.csv", self.por_video)
        self.manifesto = {
            "versao": 1, "tipo": "reavaliacao_individuos", "situacao": "concluida",
            "origem_batch": self.batch.relative_to(self.raiz).as_posix(),
            "criterios": deepcopy(CRITERIOS),
            "configuracoes_previstas": len(ids), "configuracoes_concluidas": len(ids),
            "quadros_por_configuracao": len(videos),
            "origens_sha256": {caminho_plano.relative_to(self.raiz).as_posix(): self._hash(caminho_plano)},
        }
        self._atualizar_hashes_saidas()

    def test_carrega_apenas_fixture_e_confere_soma_por_video(self):
        self._preparar([_linha_sintetica(video="13"), _linha_sintetica(video="29")])
        dados = relatorio._carregar(self.pasta)
        self.assertEqual(len(dados["linhas"]), 1)
        self.assertEqual(dados["linhas"][0]["quantidade_quadros"], 2)
        self.assertEqual(dados["quadros_por_video"], {"13": 1, "29": 1})
        self.assertEqual(dados["linhas"][0]["tp_individuos"], 2)

    def test_rejeita_soma_divergente_mesmo_com_taxas_e_hashes_atualizados(self):
        self._preparar([_linha_sintetica(video="13"), _linha_sintetica(video="29")])
        self.totais[0]["fp_individuos"] += 1
        _recalcular_taxas(self.totais[0])
        self._csv("resumo_configuracoes.csv", self.totais)
        self._atualizar_hashes_saidas()
        with self.assertRaisesRegex(ValueError, "Soma dos vídeos incompatível"):
            relatorio._carregar(self.pasta)

    def test_ordenacao_nao_confunde_floats_iguais_com_fracoes_iguais(self):
        grande = 10 ** 18
        self._preparar([
            _linha_sintetica("s001", tp=grande, fp=1, fn=0),
            _linha_sintetica("s002", tp=grande, fp=0, fn=0),
        ])
        dados = relatorio._carregar(self.pasta)
        self.assertEqual([linha["configuracao_id"] for linha in dados["linhas"]], ["s002", "s001"])
        self.assertFalse(dados["empate_corte"])

    def test_empate_no_corte_reconhece_fracoes_equivalentes(self):
        linhas = [_linha_sintetica(f"s{i:03d}", tp=3, fp=0, fn=1) for i in range(1, 5)]
        linhas.extend([
            _linha_sintetica("s005", tp=1, fp=0, fn=3),
            _linha_sintetica("s006", tp=2, fp=4, fn=2),
        ])
        self._preparar(linhas)
        dados = relatorio._carregar(self.pasta)
        self.assertTrue(dados["empate_corte"])
        self.assertEqual(relatorio._pontuacao(dados["linhas"][4]), Fraction(2, 5))
        self.assertEqual(relatorio._pontuacao(dados["linhas"][5]), Fraction(2, 5))

    def test_sem_casos_nao_e_empate_com_f1_zero(self):
        self._preparar([
            _linha_sintetica("s001", tp=0, fp=0, fn=0),
            _linha_sintetica("s002", tp=0, fp=1, fn=0),
        ])
        dados = relatorio._carregar(self.pasta)
        self.assertEqual([linha["configuracao_id"] for linha in dados["linhas"]], ["s002", "s001"])
        self.assertEqual(dados["linhas"][0]["f1_individuos"], 0.0)
        self.assertIsNone(dados["linhas"][1]["f1_individuos"])

    def test_rejeita_csv_adulterado_apesar_de_contagens_coerentes(self):
        self._preparar([_linha_sintetica()])
        # Ambos os CSV continuam coerentes entre si, mas deixam de corresponder
        # ao que o manifesto congelou ao concluir a reavaliação.
        self.totais[0]["fp_individuos"] += 1
        self.por_video[0]["fp_individuos"] += 1
        for linha in (self.totais[0], self.por_video[0]):
            _recalcular_taxas(linha)
        self._csv("resumo_configuracoes.csv", self.totais)
        self._csv("resumo_por_video.csv", self.por_video)
        with self.assertRaises(ValueError):
            relatorio._carregar(self.pasta)

    def test_rejeita_plano_adulterado_apesar_de_ids_inalterados(self):
        self._preparar([_linha_sintetica()])
        self.plano["configuracoes"][0]["parametros"]["metodo"] = "otsu"
        self._json(self.batch / "rodada.json", self.plano)
        with self.assertRaises(ValueError):
            relatorio._carregar(self.pasta)

    def test_rejeita_manifesto_com_quantidade_incompativel(self):
        self._preparar([_linha_sintetica()])
        self.manifesto["configuracoes_concluidas"] = 2
        self._json(self.pasta / "execucao.json", self.manifesto)
        with self.assertRaisesRegex(ValueError, "Quantidade de configurações"):
            relatorio._carregar(self.pasta)

    def test_rejeita_manifesto_com_versao_ou_criterios_alterados(self):
        self._preparar([_linha_sintetica()])
        original = deepcopy(self.manifesto)
        for campo in ("versao", "criterios"):
            adulterado = deepcopy(original)
            if campo == "versao":
                adulterado["versao"] = 2
            else:
                adulterado["criterios"]["limiar_iou"] = 0.4
            self._json(self.pasta / "execucao.json", adulterado)
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "critérios"):
                relatorio._carregar(self.pasta)

    def test_hash_ausente_nao_e_tratado_como_integridade_confirmada(self):
        self._preparar([_linha_sintetica()])
        self.manifesto["saidas_sha256"] = {}
        self._json(self.pasta / "execucao.json", self.manifesto)
        with self.assertRaisesRegex(ValueError, "hash"):
            relatorio._carregar(self.pasta)

    def test_rejeita_relatorio_fora_da_pasta_de_reavaliacao(self):
        with self.assertRaises(ValueError):
            relatorio._carregar(self.raiz / "outra_pasta")


if __name__ == "__main__":
    unittest.main()
