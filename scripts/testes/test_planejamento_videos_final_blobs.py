"""Plano final: dados sintéticos, linhagem congelada e nenhuma decodificação."""

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar
from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_videos as anterior
from scripts.blobs import planejamento_videos_final as final
from scripts.blobs.executar_inspecao import colunas_metricas
from scripts.testes.test_planejamento_videos_blobs import fontes_videos_sinteticas, serializar, tabela


RAIZ = Path(__file__).resolve().parents[2]


def fontes_finais_sinteticas(raiz: Path):
    def gravar(nome, blob):
        path = raiz / nome
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)

    hashes_anteriores = fontes_videos_sinteticas(raiz)
    with patch.object(anterior, "HASHES_FONTES_FIXAS", hashes_anteriores):
        selecao = anterior.gerar_plano(raiz)
    blob_selecao = serializar(selecao)
    hash_selecao = p._sha256(blob_selecao)
    gravar(final.PLANO_VIDEOS_SELECAO, blob_selecao)
    gravar(final.BATCH_VIDEOS_SELECAO + "/plano.json", blob_selecao)
    fontes_hash, execucoes, totais, videos = {}, [], [], []
    metricas = agregar([avaliar([], [])])
    por_video = {}
    for vid in anterior.VIDEOS:
        por_video[vid] = deepcopy(metricas)
        por_video[vid]["quantidade_quadros"] = anterior.QUANTIDADES[vid]
    total = agregar(list(por_video.values()))
    total["quantidade_quadros"] = 5850
    for item in selecao["configuracoes"]:
        ident = item["id"]
        pasta = final._pasta_configuracao(item)
        execucoes.append({"configuracao_id": ident, "pasta": pasta})
        linha = {"configuracao_id": ident, "pasta_origem": pasta, "quantidade_quadros": 5850,
                 **colunas_metricas(total)}
        totais.append(linha)
        videos.extend({"configuracao_id": ident, "pasta_origem": pasta, "video_id": vid,
                       "quantidade_quadros": anterior.QUANTIDADES[vid], **colunas_metricas(por_video[vid])}
                      for vid in anterior.VIDEOS)
        saidas = []
        for vid in anterior.VIDEOS:
            arquivo = f"{pasta}/midia/{ident}__cfg-{p.hash_configuracao(item)[:12]}__video-{vid}.mp4"
            digest = p._sha256(f"comparativo ficticio {ident}/{vid}".encode())
            saidas.append({"video_id": vid, "arquivo": arquivo, "sha256": digest,
                           "quantidade_quadros": anterior.QUANTIDADES[vid], "fps": anterior.QUANTIDADES[vid]/30,
                           "largura": 1280, "altura": 584, "codec_solicitado": "mp4v",
                           "decodificacao_conferida": True})
            fontes_hash[arquivo] = digest
        estado = {"tipo": "videos_selecao_blobs", "particao": "selecao", "situacao": "concluida",
                  "criterios": CRITERIOS, "configuracao_id": ident, "quadros_concluidos": 5850,
                  "batch": final.BATCH_VIDEOS_SELECAO, "configuracao_sha256": p.hash_configuracao(item),
                  "plano_sha256": hash_selecao, "videos": saidas}
        avaliacao = {"criterios": CRITERIOS, "total": total, "por_video": por_video}
        for tipo, dado in (("configuracao", item), ("execucao", estado), ("avaliacao", avaliacao)):
            path = f"{pasta}/{tipo}.json"; blob = serializar(dado)
            gravar(path, blob); fontes_hash[path] = p._sha256(blob)
    for nome, linhas in (("resumo_configuracoes.csv", totais), ("resumo_por_video.csv", videos),
                          ("ranking.csv", [{"posicao": 1, **x} for x in reversed(totais)])):
        path = final.BATCH_VIDEOS_SELECAO + "/" + nome; blob = tabela(linhas)
        gravar(path, blob); fontes_hash[path] = p._sha256(blob)
    manifesto = {"versao": 1, "tipo": "videos_selecao_blobs", "etapa": "selecao_videos",
                 "particao": "selecao", "algoritmo": "blobs", "situacao": "concluida",
                 "criterios": CRITERIOS, "configuracoes_previstas": 5, "configuracoes_concluidas": 5,
                 "quadros_por_configuracao": 5850, "avaliacoes_concluidas": 29250,
                 "videos_previstos": 20, "videos_concluidos": 20, "alinhamento_conferido": True,
                 "plano_sha256": hash_selecao, "execucoes": execucoes, "saidas_sha256": fontes_hash}
    gravar(final.BATCH_VIDEOS_SELECAO + "/execucao.json", serializar(manifesto))
    especificacao = p._json((RAIZ / final.PLANO_FINAL_LIMIARIZACAO).read_bytes())
    especificacao["configuracoes"] = [{"ignorar": "outro detector"}]
    especificacao["criterios_avaliacao"] = {"ignorar": "outras métricas"}
    for video in especificacao["videos"]:
        blob = f"MP4 final ficticio {video['video_id']}".encode()
        gravar(video["arquivo"], blob); video["sha256"] = p._sha256(blob)
        for anotacao in video["anotacoes"]:
            gravar(anotacao["arquivo"], b""); anotacao["sha256"] = p._sha256(b"")
        for ref in video["referencias_alinhamento"]:
            blob = f"JPEG final ficticio {video['video_id']}/{ref['quadro']}".encode()
            gravar(ref["imagem"], blob); ref["sha256"] = p._sha256(blob)
    gravar(final.PLANO_FINAL_LIMIARIZACAO, serializar(especificacao))
    hashes = {nome: p._sha256((raiz / path).read_bytes()) for nome, path in final.FONTES_FIXAS.items()}
    return hashes_anteriores, hashes


class TestPlanejamentoVideosFinalBlobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporario = TemporaryDirectory()
        cls.addClassCleanup(cls.temporario.cleanup)
        cls.raiz = Path(cls.temporario.name)
        with patch("cv2.VideoCapture", side_effect=AssertionError("Decodificação proibida")), \
                patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido")):
            cls.hashes_anteriores, cls.hashes = fontes_finais_sinteticas(cls.raiz)
            with patch.object(anterior, "HASHES_FONTES_FIXAS", cls.hashes_anteriores), \
                    patch.object(final, "HASHES_FONTES_FIXAS", cls.hashes):
                cls.modelo = final.gerar_plano(cls.raiz)

    def setUp(self):
        self.plano = deepcopy(self.modelo)
        for objeto, nome, valor in ((anterior, "HASHES_FONTES_FIXAS", self.hashes_anteriores),
                                    (final, "HASHES_FONTES_FIXAS", self.hashes)):
            remendo = patch.object(objeto, nome, valor); remendo.start(); self.addCleanup(remendo.stop)
        for nome in ("cv2.VideoCapture", "cv2.imread", "cv2.imdecode", "cv2.SimpleBlobDetector_create",
                     "algoritmos.classicos.blobs.detectar", "algoritmos.classicos.variantes_blobs.detectar_escala"):
            remendo = patch(nome, side_effect=AssertionError("Mídia ou detector proibidos"))
            remendo.start(); self.addCleanup(remendo.stop)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            final.carregar_plano(serializar(plano))

    @contextmanager
    def trocar(self, nome, blob):
        path = self.raiz / nome; antes = path.read_bytes(); path.write_bytes(blob)
        try:
            yield
        finally:
            path.write_bytes(antes)

    def test_final_5910_quadros_29550_avaliacoes_e_20_referencias(self):
        self.assertEqual([x["video_id"] for x in self.plano["videos"]], ["14", "24", "38", "82"])
        self.assertEqual([x["quantidade_quadros"] for x in self.plano["videos"]], [1470, 1470, 1470, 1500])
        self.assertEqual([x["fps"] for x in self.plano["videos"]], [49.0, 49.0, 49.0, 50.0])
        self.assertEqual(sum(len(x["anotacoes"]) for x in self.plano["videos"]), 5910)
        self.assertEqual(sum(len(x["referencias_alinhamento"]) for x in self.plano["videos"]), 20)
        self.assertEqual(self.plano["geracao"]["avaliacoes_previstas"], 29550)

    def test_preserva_5_configuracoes_8_campos_identidades_e_criterios(self):
        origem = p._json((self.raiz / final.PLANO_VIDEOS_SELECAO).read_bytes())
        self.assertEqual(self.plano["configuracoes"], origem["configuracoes"])
        self.assertEqual(self.plano["proveniencia"]["configuracoes"], origem["proveniencia"]["configuracoes"])
        self.assertEqual(self.plano["criterios"], CRITERIOS)
        self.assertEqual([x["id"] for x in self.plano["configuracoes"]], list(final.IDS_APROVADOS))
        for item in self.plano["configuracoes"]:
            self.assertEqual(p.hash_configuracao(item), final.IDENTIDADES_APROVADAS[item["id"]])

    def test_43_fontes_7_csvs_preservados(self):
        docs = final.conferir_origens(self.plano, self.raiz)
        caminhos = final.caminhos_origens(self.plano)
        self.assertEqual(len(docs), 43)
        self.assertEqual(set(docs), set(caminhos))
        self.assertEqual(sum(Path(x).suffix == ".csv" for x in caminhos.values()), 7)
        for nome, blob in docs.items():
            self.assertEqual(blob, (self.raiz / caminhos[nome]).read_bytes())

    def test_carregador_puro_sem_io(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("I/O proibido")):
            self.assertEqual(final.carregar_plano(serializar(self.plano)), self.plano)

    def test_determinismo_sem_sortear_sem_mudar_fontes(self):
        antes = {str(x): p._sha256(x.read_bytes()) for x in self.raiz.rglob("*") if x.is_file()}
        estado = random.getstate()
        with patch("random.Random", side_effect=AssertionError("Sorteio proibido")):
            self.assertEqual(final.gerar_plano(self.raiz), self.plano)
        depois = {str(x): p._sha256(x.read_bytes()) for x in self.raiz.rglob("*") if x.is_file()}
        self.assertEqual(antes, depois); self.assertEqual(estado, random.getstate())

    def test_ranking_anterior_nao_promove_nem_troca_ids(self):
        # Ranking sintético invertido, com empate: identidade continua determinada pela aprovação.
        ranking = anterior._csv((self.raiz / final.FONTES_FIXAS["ranking_videos_selecao_blobs"]).read_bytes())
        self.assertNotEqual(ranking[0]["configuracao_id"], final.IDS_APROVADOS[0])
        self.assertEqual([x["id"] for x in final.gerar_plano(self.raiz)["configuracoes"]], list(final.IDS_APROVADOS))

    def test_rejeita_particao_tipo_criterios_ordem_e_alinhamento(self):
        for campo, valor in (("particao", "selecao"), ("tipo", "videos_selecao_blobs"),
                              ("etapa", "selecao_videos"), ("seed", 43), ("criterios", {})):
            novo = deepcopy(self.plano); novo[campo] = valor; self.rejeita(novo)
        novo = deepcopy(self.plano); novo["configuracoes"].reverse(); self.rejeita(novo)
        novo = deepcopy(self.plano); novo["alinhamento"]["situacao"] = "conferido"; self.rejeita(novo)

    def test_rejeita_reajuste_de_parametros_classes_caixa_e_backend(self):
        for alterar in (lambda c: c["caixa"].update(pixels=9),
                        lambda c: c["parametros"].update(area_minima=48),
                        lambda c: c["parametros"]["classificacao"].update(area_minima_aglomerado=700),
                        lambda c: c.update(metodo_detector="dog")):
            novo = deepcopy(self.plano); alterar(novo["configuracoes"][0]); self.rejeita(novo)

    def test_rejeita_mistura_de_videos_quadro_ausente_e_offset(self):
        for alterar in (lambda v: v.update(video_id="13"), lambda v: v.update(fps=48),
                        lambda v: v["anotacoes"].pop(), lambda v: v["anotacoes"][0].update(quadro=1),
                        lambda v: v["referencias_alinhamento"][4].update(quadro=1468)):
            novo = deepcopy(self.plano); alterar(novo["videos"][0]); self.rejeita(novo)

    def test_rejeita_origem_externa_omitida_ou_hash_fixado_trocado(self):
        for alterar in (lambda f: f.pop("configuracao_video_s052"),
                        lambda f: f["configuracao_video_s052"].update(arquivo="../fora.json"),
                        lambda f: f["execucao_videos_selecao_blobs"].update(sha256="0" * 64)):
            novo = deepcopy(self.plano); alterar(novo["proveniencia"]["fontes"]); self.rejeita(novo)

    def test_bytes_corrompidos_mp4_rotulo_jpeg_e_proveniencia(self):
        video = self.plano["videos"][0]
        fontes = self.plano["proveniencia"]["fontes"]
        caminhos = [video["arquivo"], video["anotacoes"][3]["arquivo"],
                    video["referencias_alinhamento"][0]["imagem"],
                    fontes["execucao_videos_selecao_blobs"]["arquivo"], fontes["avaliacao_video_s052"]["arquivo"]]
        for nome in caminhos:
            with self.trocar(nome, b"alterado"):
                with self.assertRaises(ValueError):
                    final.conferir_origens(self.plano, self.raiz)

    def test_anotacao_vazia_valida_ausencia_interrompe(self):
        nome = self.plano["videos"][0]["anotacoes"][9]["arquivo"]
        path = self.raiz / nome; self.assertEqual(path.read_bytes(), b"")
        path.unlink()
        try:
            with self.assertRaises(FileNotFoundError):
                final.conferir_origens(self.plano, self.raiz)
        finally:
            path.write_bytes(b"")

    def test_manifesto_incompleto_e_metrica_incoerente_rejeitados_mesmo_com_rehash(self):
        for nome, alterar in (("execucao_videos_selecao_blobs", lambda d: d.update(situacao="falhou")),
                               ("avaliacao_video_s052", lambda d: d["total"]["por_grupo"]["individuos"].update(fp=1))):
            novo = deepcopy(self.plano)
            caminho = novo["proveniencia"]["fontes"][nome]["arquivo"]
            dados = p._json((self.raiz / caminho).read_bytes()); alterar(dados)
            blob = serializar(dados); digest = p._sha256(blob)
            novo["proveniencia"]["fontes"][nome]["sha256"] = digest
            hashes = {**self.hashes}
            if nome in hashes:
                hashes[nome] = digest
            with ExitStack() as pilha:
                pilha.enter_context(self.trocar(caminho, blob))
                if nome != "execucao_videos_selecao_blobs":
                    fonte_manifesto = novo["proveniencia"]["fontes"]["execucao_videos_selecao_blobs"]
                    manifesto = p._json((self.raiz / fonte_manifesto["arquivo"]).read_bytes())
                    manifesto["saidas_sha256"][caminho] = digest
                    blob_manifesto = serializar(manifesto)
                    fonte_manifesto["sha256"] = p._sha256(blob_manifesto)
                    hashes["execucao_videos_selecao_blobs"] = fonte_manifesto["sha256"]
                    pilha.enter_context(self.trocar(fonte_manifesto["arquivo"], blob_manifesto))
                pilha.enter_context(patch.object(final, "HASHES_FONTES_FIXAS", hashes))
                with self.assertRaises(ValueError):
                    final.conferir_origens(novo, self.raiz)

    def test_planos_reais_anteriores_preservados(self):
        self.assertEqual(p._sha256((RAIZ / final.PLANO_VIDEOS_SELECAO).read_bytes()),
                         "cc36923b5a846023e8ee538ea25a8e1ce09791a7ee5f798310165749b512b8ed")
        self.assertEqual(p._sha256((RAIZ / final.PLANO_FINAL_LIMIARIZACAO).read_bytes()),
                         "b9e4186f6bad088f3fd676bac150a86cd3359656c5363b09ee393df1d1ba294a")


if __name__ == "__main__":
    unittest.main()
