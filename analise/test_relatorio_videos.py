"""Conferências sintéticas do relatório de vídeos, sem base real ou renderização."""

from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analise.avaliacao_individuos import CRITERIOS
from analise import relatorio_videos as relatorio


def _taxas(linha):
    def dividir(a, b):
        return a / b if b else None

    for grupo in ("individuos", "aglomerados"):
        tp, fp, fn = (linha[f"{campo}_{grupo}"] for campo in ("tp", "fp", "fn"))
        linha[f"precisao_{grupo}"] = dividir(tp, tp + fp)
        linha[f"recall_{grupo}"] = dividir(tp, tp + fn)
        linha[f"f1_{grupo}"] = dividir(2 * tp, 2 * tp + fp + fn)
        linha[f"situacao_f1_{grupo}"] = "definido" if tp + fp + fn else "sem_casos"
    for classe in (0, 2, 1):
        linha[f"recall_classe_{classe}"] = dividir(
            linha[f"localizadas_classe_{classe}"], linha[f"anotacoes_classe_{classe}"],
        )
    linha["acuracia_condicional"] = dividir(linha["pares_corretos"], linha["pares_total"])
    return linha


class TesteRelatorioVideos(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name).resolve()
        self.pasta = self.raiz / "resultados/videos/limiarizacao/selecao/batch__sintetico"
        self.pasta.mkdir(parents=True)
        substituicao = patch.object(relatorio, "RAIZ", self.raiz)
        substituicao.start()
        self.addCleanup(substituicao.stop)
        self.ids = sorted(relatorio.CONFIGURACOES)
        self.videos = sorted(relatorio.VIDEOS, key=int)
        self.partes = []
        for identificador in self.ids:
            origem = self.pasta / identificador
            origem.mkdir()
            for indice, video in enumerate(self.videos, 1):
                linha = {campo: 0 for campo in relatorio.CONTAGENS}
                linha.update(
                    configuracao_id=identificador, pasta_origem=origem.relative_to(self.raiz).as_posix(),
                    video_id=video, quantidade_quadros=indice,
                    tp_individuos=indice, fp_individuos=indice, fn_individuos=indice,
                    pares_corretos=indice, pares_total=indice, matriz_0_0=indice,
                    anotacoes_classe_0=2 * indice, localizadas_classe_0=indice,
                    perdidas_classe_0=indice,
                )
                self.partes.append(_taxas(linha))
        self.plano = {
            "versao": 1, "tipo": "videos_selecao", "particao": "selecao",
            "configuracoes": [{"id": i, "parametros": {"metodo": "manual"}} for i in self.ids],
            "videos": [{"video_id": v, "quantidade_quadros": i}
                       for i, v in enumerate(self.videos, 1)],
        }
        self._json(self.pasta / "plano.json", self.plano)
        self.manifesto = {
            "tipo": "selecao_videos", "versao": 1, "situacao": "concluida",
            "criterios": deepcopy(CRITERIOS), "configuracoes_previstas": 5,
            "configuracoes_concluidas": 5, "quadros_por_configuracao": 10,
            "plano_sha256": self._hash(self.pasta / "plano.json"),
            "origens_sha256": {},
        }
        self._agregar()
        self._salvar()

    def _hash(self, caminho):
        return hashlib.sha256(caminho.read_bytes()).hexdigest()

    def _json(self, caminho, valor):
        caminho.write_text(json.dumps(valor, ensure_ascii=False, allow_nan=False), encoding="utf-8")

    def _agregar(self):
        self.totais = []
        for identificador in self.ids:
            partes = [p for p in self.partes if p["configuracao_id"] == identificador]
            linha = {campo: sum(p[campo] for p in partes) for campo in relatorio.CONTAGENS}
            linha.update(configuracao_id=identificador, pasta_origem=partes[0]["pasta_origem"])
            self.totais.append(_taxas(linha))

    def _csv(self, nome, linhas):
        campos = ["configuracao_id", "pasta_origem", *relatorio.CONTAGENS, *relatorio.TAXAS,
                  "situacao_f1_individuos", "situacao_f1_aglomerados"]
        if nome == "resumo_por_video.csv":
            campos.insert(0, "video_id")
        with (self.pasta / nome).open("w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(linhas)

    def _salvar(self):
        self._csv("resumo_configuracoes.csv", self.totais)
        self._csv("resumo_por_video.csv", self.partes)
        self.manifesto["saidas_sha256"] = {
            caminho.relative_to(self.raiz).as_posix(): self._hash(caminho)
            for caminho in (self.pasta / "resumo_configuracoes.csv", self.pasta / "resumo_por_video.csv")
        }
        self._json(self.pasta / "execucao.json", self.manifesto)

    def _salvar_plano(self):
        self._json(self.pasta / "plano.json", self.plano)
        self.manifesto["plano_sha256"] = self._hash(self.pasta / "plano.json")
        self._json(self.pasta / "execucao.json", self.manifesto)

    def _preparar_final(self):
        """Cria outra fixture, sem mover ou substituir os arquivos da seleção."""
        finais = sorted(relatorio.VIDEOS_FINAIS, key=int)
        substituicoes = dict(zip(self.videos, finais))
        self.pasta = self.raiz / "resultados/videos/limiarizacao/final/batch__sintetico"
        self.pasta.mkdir(parents=True)
        for identificador in self.ids:
            (self.pasta / identificador).mkdir()
        for linha in self.partes:
            linha["video_id"] = substituicoes[linha["video_id"]]
            linha["pasta_origem"] = (self.pasta / linha["configuracao_id"]).relative_to(self.raiz).as_posix()
        self.videos = finais
        self.plano.update(tipo="videos_final", particao="final")
        for video in self.plano["videos"]:
            video["video_id"] = substituicoes[video["video_id"]]
        self.manifesto["tipo"] = "final_videos"
        self._salvar_plano()
        self._agregar()
        self._salvar()

    def test_carrega_videos_com_duracoes_diferentes_e_sem_ler_midias(self):
        dados = relatorio._carregar(self.pasta)
        self.assertEqual(dados["quantidade_quadros"], 10)
        self.assertEqual(dados["quadros_por_video"], {"13": 1, "29": 2, "52": 3, "54": 4})
        self.assertEqual(len(dados["linhas"]), 5)
        self.assertEqual(len(dados["por_video"]), 20)
        self.assertEqual(len(dados["hashes"]), 4)
        self.assertEqual(dados["linhas"][0]["tp_individuos"], 10)
        self.assertEqual(dados["particao"], "selecao")
        # As fixtures não têm vídeos nem anotações originais: o leitor consome
        # somente manifesto, plano e tabelas já calculadas.

    def test_carrega_final_com_os_mesmos_candidatos_e_outros_videos(self):
        self._preparar_final()
        dados = relatorio._carregar(self.pasta)
        self.assertEqual(dados["particao"], "final")
        self.assertEqual(dados["execucao"]["tipo"], "final_videos")
        self.assertEqual(dados["quadros_por_video"], {"14": 1, "24": 2, "38": 3, "82": 4})
        self.assertEqual(set(dados["configuracoes"]), relatorio.CONFIGURACOES)
        self.assertEqual(dados["quantidade_quadros"], 10)
        self.assertEqual(len(dados["por_video"]), 20)

    def test_rejeita_tipo_de_execucao_da_outra_etapa_em_ambas_as_pastas(self):
        self.manifesto["tipo"] = "final_videos"
        self._json(self.pasta / "execucao.json", self.manifesto)
        with self.assertRaisesRegex(ValueError, "etapa da pasta"):
            relatorio._carregar(self.pasta)
        self._preparar_final()
        self.manifesto["tipo"] = "selecao_videos"
        self._json(self.pasta / "execucao.json", self.manifesto)
        with self.assertRaisesRegex(ValueError, "etapa da pasta"):
            relatorio._carregar(self.pasta)

    def test_rejeita_tipo_e_particao_do_plano_cruzados(self):
        for final in (False, True):
            if final:
                self._preparar_final()
            original = deepcopy(self.plano)
            alteracoes = [{"tipo": "videos_selecao" if final else "videos_final"},
                          {"particao": "selecao" if final else "final"}, {"versao": 2}]
            for alteracao in alteracoes:
                self.plano = {**original, **alteracao}
                self._salvar_plano()
                with self.subTest(final=final, alteracao=alteracao), \
                        self.assertRaisesRegex(ValueError, "plano incompatível com a etapa"):
                    relatorio._carregar(self.pasta)
            self.plano = original

    def test_rejeita_video_da_selecao_no_plano_final(self):
        self._preparar_final()
        self.plano["videos"][0]["video_id"] = "13"
        self._salvar_plano()
        with self.assertRaisesRegex(ValueError, "Vídeo inesperado"):
            relatorio._carregar(self.pasta)

    def test_rejeita_resumo_da_selecao_em_batch_final(self):
        self._preparar_final()
        for linha in self.partes:
            if linha["video_id"] == "14":
                linha["video_id"] = "13"
        self._salvar()
        with self.assertRaisesRegex(ValueError, "Resumo por vídeo"):
            relatorio._carregar(self.pasta)

    def test_rejeita_pasta_origem_da_selecao_no_relatorio_final(self):
        self._preparar_final()
        for linha in self.partes:
            linha["pasta_origem"] = (
                self.raiz / "resultados/videos/limiarizacao/selecao/batch__sintetico"
                / linha["configuracao_id"]
            ).relative_to(self.raiz).as_posix()
        self._agregar()
        self._salvar()
        with self.assertRaisesRegex(ValueError, "dentro do batch"):
            relatorio._carregar(self.pasta)

    def test_final_nao_reutiliza_textos_de_selecao_ou_promete_novos_ajustes(self):
        textos = relatorio.ETAPAS["final"]
        self.assertEqual(textos["rotulo"], "Avaliação final")
        self.assertIn("congeladas", textos["rodape"])
        self.assertIn("não orientam novos ajustes ou seleção", textos["decisao"])
        self.assertIn("14, 24, 38 e 82", textos["encerramento"])
        self.assertNotIn("precede", textos["encerramento"])
        self.assertIn("sem novos ajustes", textos["interpretacao"])

    def test_rejeita_hash_alterado_e_hash_ausente(self):
        original = deepcopy(self.manifesto)
        for hashes in ({}, {k: "0" * 64 for k in original["saidas_sha256"]}):
            self.manifesto["saidas_sha256"] = hashes
            self._json(self.pasta / "execucao.json", self.manifesto)
            with self.subTest(hashes=hashes), self.assertRaisesRegex(ValueError, "hash"):
                relatorio._carregar(self.pasta)

    def test_rejeita_plano_alterado_sem_atualizar_hash(self):
        self.plano["configuracoes"][0]["parametros"]["metodo"] = "otsu"
        self._json(self.pasta / "plano.json", self.plano)
        with self.assertRaisesRegex(ValueError, "Plano alterado"):
            relatorio._carregar(self.pasta)

    def test_rejeita_batch_incompleto_e_criterio_diferente(self):
        original = deepcopy(self.manifesto)
        casos = [{"situacao": "falhou"}, {"configuracoes_concluidas": 4},
                 {"versao": 2}, {"criterios": {"limiar_iou": .4}},
                 {"quadros_por_configuracao": 9}]
        for alteracao in casos:
            self._json(self.pasta / "execucao.json", {**original, **alteracao})
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                relatorio._carregar(self.pasta)

    def test_rejeita_candidato_e_video_fora_do_escopo(self):
        original = deepcopy(self.plano)
        self.plano["configuracoes"][0]["id"] = "s085"
        self._salvar_plano()
        with self.assertRaisesRegex(ValueError, "Configuração inesperada"):
            relatorio._carregar(self.pasta)
        self.plano = deepcopy(original)
        self.plano["videos"][0]["video_id"] = "14"
        self._salvar_plano()
        with self.assertRaisesRegex(ValueError, "Vídeo inesperado"):
            relatorio._carregar(self.pasta)

    def test_rejeita_resumo_por_video_incompleto_ou_repetido(self):
        original = deepcopy(self.partes)
        for partes in (original[:-1], original[:-1] + [original[0]]):
            self.partes = partes
            self._salvar()
            with self.subTest(quantidade=len(partes)), self.assertRaisesRegex(ValueError, "Resumo por vídeo"):
                relatorio._carregar(self.pasta)

    def test_rejeita_soma_divergente_com_taxas_e_hashes_validos(self):
        self.totais[0]["fp_individuos"] += 1
        _taxas(self.totais[0])
        self._salvar()
        with self.assertRaisesRegex(ValueError, "Soma dos vídeos incompatível"):
            relatorio._carregar(self.pasta)

    def test_rejeita_suportes_diferentes_entre_configuracoes(self):
        linha = self.partes[0]
        linha["fn_individuos"] += 1
        linha["anotacoes_classe_0"] += 1
        linha["perdidas_classe_0"] += 1
        _taxas(linha)
        self._agregar()
        self._salvar()
        with self.assertRaisesRegex(ValueError, "anotações diferentes"):
            relatorio._carregar(self.pasta)

    def test_rejeita_pasta_origem_fora_do_batch(self):
        for linha in self.partes:
            if linha["configuracao_id"] == self.ids[0]:
                linha["pasta_origem"] = "resultados/videos/limiarizacao/selecao"
        self._agregar()
        self._salvar()
        with self.assertRaisesRegex(ValueError, "dentro do batch"):
            relatorio._carregar(self.pasta)

    def test_rejeita_quantidade_parcial_de_quadros_mesmo_com_soma_coerente(self):
        self.partes[0]["quantidade_quadros"] = 0
        self._agregar()
        self._salvar()
        with self.assertRaisesRegex(ValueError, "quantidade inesperada de quadros"):
            relatorio._carregar(self.pasta)

    def test_preserva_sem_casos_como_nulo(self):
        for linha in self.partes:
            for campo in relatorio.CONTAGENS:
                if campo != "quantidade_quadros":
                    linha[campo] = 0
            _taxas(linha)
        self._agregar()
        self._salvar()
        dados = relatorio._carregar(self.pasta)
        self.assertTrue(all(l["f1_individuos"] is None for l in dados["linhas"]))
        self.assertTrue(all(l["acuracia_condicional"] is None for l in dados["linhas"]))

    def test_ordena_por_fracao_exata_sem_transformar_empate_em_escolha(self):
        grande = 10 ** 18
        for linha in self.partes:
            linha.update(tp_individuos=grande, fp_individuos=0, fn_individuos=0,
                         pares_corretos=grande, pares_total=grande, matriz_0_0=grande,
                         anotacoes_classe_0=grande, localizadas_classe_0=grande, perdidas_classe_0=0)
            if linha["configuracao_id"] == self.ids[0]:
                linha["fp_individuos"] = 1
            _taxas(linha)
        self._agregar()
        self._salvar()
        dados = relatorio._carregar(self.pasta)
        self.assertEqual(len({l["f1_individuos"] for l in dados["linhas"]}), 1)
        self.assertEqual([l["configuracao_id"] for l in dados["linhas"]], self.ids[1:] + self.ids[:1])
        self.assertNotIn("vencedor", dados)
        self.assertNotIn("selecionadas", dados)

    def test_rejeita_pasta_de_frames_e_batch_aninhado(self):
        for pasta in (self.raiz / "resultados/frame-to-frame/limiarizacao/selecao/batch__x",
                      self.pasta / "batch__aninhado"):
            with self.subTest(pasta=pasta), self.assertRaises(ValueError):
                relatorio._carregar(pasta)

    def _conferir_falha_pdf(self):
        for nome in ("relatorio_videos.py", "relatorio_individuos.py", "relatorio_rodada.py",
                     "avaliacao_individuos.py", "avaliacao_deteccao.py"):
            caminho = self.raiz / "analise" / nome
            caminho.parent.mkdir(exist_ok=True)
            caminho.write_text("# fixture\n", encoding="utf-8")
        antes = (self.pasta / "execucao.json").read_bytes()
        with patch.object(relatorio, "verificar_dependencias", return_value={}), \
             patch.object(relatorio, "_escrever_pdf", side_effect=RuntimeError("falha sintética")):
            with self.assertRaisesRegex(RuntimeError, "falha sintética"):
                relatorio.gerar_relatorio(self.pasta)
        self.assertEqual((self.pasta / "execucao.json").read_bytes(), antes)
        pastas = list((self.pasta / "relatorios").iterdir())
        self.assertEqual(len(pastas), 1)
        registro = json.loads((pastas[0] / "relatorio.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["situacao"], "falhou")
        self.assertIn("falha sintética", registro["erro"])
        self.assertEqual(registro["tipo"], self.manifesto["tipo"])
        self.assertEqual(registro["particao"], self.plano["particao"])
        self.assertEqual((pastas[0] / "execucao_origem.json").read_bytes(), antes)

    def test_falha_do_pdf_tem_registro_proprio_sem_alterar_execucao(self):
        self._conferir_falha_pdf()

    def test_falha_do_pdf_final_preserva_manifesto_e_tipo_da_etapa(self):
        self._preparar_final()
        self._conferir_falha_pdf()


if __name__ == "__main__":
    unittest.main()
