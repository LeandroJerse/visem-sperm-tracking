"""Vídeos de seleção: fontes sintéticas, cinco aprovações fixas e nenhuma decodificação."""

from contextlib import contextmanager
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar
from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_selecao as s
from scripts.blobs import planejamento_videos as v
from scripts.blobs.executar_inspecao import colunas_metricas
from scripts.testes.test_planejamento_selecao_blobs import fontes_selecao_sinteticas, HASHES_RODADAS


RAIZ = Path(__file__).resolve().parents[2]


def serializar(dados):
    return json.dumps(dados, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")


def tabela(linhas):
    arquivo = StringIO(newline="")
    escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
    escritor.writeheader()
    escritor.writerows(linhas)
    return arquivo.getvalue().encode("utf-8-sig")


def fontes_videos_sinteticas(raiz: Path) -> dict[str, str]:
    """Cria somente bytes fictícios de mídia, anotações vazias e tabelas de casos vazios."""
    def gravar(nome, dados):
        arquivo = raiz / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(dados)

    fontes_selecao_sinteticas(raiz)
    selecao = s.gerar_plano(raiz)
    blob_selecao = serializar(selecao)
    gravar(v.PLANO_SELECAO, blob_selecao)
    gravar(v.BATCH_SELECAO + "/plano.json", blob_selecao)
    total = agregar([avaliar([], []) for _ in range(60)])
    saidas = {}
    execucoes = []
    resumos, videos, quadros = [], [], []
    for item in selecao["configuracoes"]:
        ident = item["id"]
        pasta = v._pasta_configuracao(item)
        execucoes.append({"configuracao_id": ident, "pasta": pasta})
        resumos.append({"configuracao_id": ident, "quantidade_quadros": 60, **colunas_metricas(total)})
        videos.extend({"configuracao_id": ident, "video_id": video} for video in v.VIDEOS)
        quadros.extend({"configuracao_id": ident, "video_id": video, "quadro": quadro} for video, quadro in s.ORDEM_QUADROS)
        if ident in v.IDS_APROVADOS:
            self_state = {"tipo": "selecao_blobs", "situacao": "concluida", "configuracao_id": ident,
                          "batch": v.BATCH_SELECAO, "plano_sha256": p._sha256(blob_selecao),
                          "configuracao_sha256": p.hash_configuracao(item), "quadros_concluidos": 60}
            for nome, dados in (("configuracao", item), ("avaliacao", total), ("execucao", self_state)):
                caminho = f"{pasta}/{nome}.json"; blob = serializar(dados)
                gravar(caminho, blob); saidas[caminho] = p._sha256(blob)
    fontes_csv = {
        "ranking.csv": [{"posicao": 1, "configuracao_id": ident} for ident in reversed(s.IDS)],
        "resumo_configuracoes.csv": resumos, "resumo_por_video.csv": videos, "resumo_por_quadro.csv": quadros,
    }
    for nome, linhas in fontes_csv.items():
        caminho = v.BATCH_SELECAO + "/" + nome; blob = tabela(linhas)
        gravar(caminho, blob); saidas[caminho] = p._sha256(blob)
    manifesto = {"versao": 1, "tipo": "selecao_blobs", "etapa": "selecao_imagens", "algoritmo": "blobs",
                 "rodada": "selecao", "particao": "selecao", "situacao": "concluida", "criterios": CRITERIOS,
                 "configuracoes_previstas": 119, "configuracoes_concluidas": 119, "quadros_por_configuracao": 60,
                 "avaliacoes_concluidas": 7140, "plano_sha256": p._sha256(blob_selecao),
                 "execucoes": execucoes, "saidas_sha256": saidas}
    gravar(v.BATCH_SELECAO + "/execucao.json", serializar(manifesto))
    # Somente a especificação JSON é lida do projeto; nenhuma mídia real é aberta.
    especificacao = p._json((RAIZ / v.PLANO_VIDEOS_LIMIARIZACAO).read_bytes())
    especificacao["configuracoes"] = [{"ignorar": "configuração do outro detector"}]
    especificacao["criterios_avaliacao"] = {"ignorar": "métrica antiga"}
    for video in especificacao["videos"]:
        conteudo = ("MP4 ficticio " + video["video_id"]).encode()
        gravar(video["arquivo"], conteudo); video["sha256"] = p._sha256(conteudo)
        for anotacao in video["anotacoes"]:
            gravar(anotacao["arquivo"], b""); anotacao["sha256"] = p._sha256(b"")
        for ref in video["referencias_alinhamento"]:
            conteudo = f"imagem sintetica {video['video_id']}/{ref['quadro']}".encode()
            gravar(ref["imagem"], conteudo); ref["sha256"] = p._sha256(conteudo)
    gravar(v.PLANO_VIDEOS_LIMIARIZACAO, serializar(especificacao))
    return {nome: p._sha256((raiz / caminho).read_bytes()) for nome, caminho in v.FONTES_FIXAS.items()}


class TestPlanejamentoVideosBlobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporario = TemporaryDirectory()
        cls.addClassCleanup(cls.temporario.cleanup)
        cls.raiz = Path(cls.temporario.name)
        with patch("cv2.VideoCapture", side_effect=AssertionError("Decodificação proibida")), \
                patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido")):
            cls.hashes = fontes_videos_sinteticas(cls.raiz)
            with patch.object(v, "HASHES_FONTES_FIXAS", cls.hashes):
                cls.modelo = v.gerar_plano(cls.raiz)

    def setUp(self):
        self.plano = deepcopy(self.modelo)
        fontes = patch.object(v, "HASHES_FONTES_FIXAS", self.hashes)
        fontes.start(); self.addCleanup(fontes.stop)
        for nome in ("cv2.VideoCapture", "cv2.imread", "cv2.imdecode", "cv2.SimpleBlobDetector_create",
                     "algoritmos.classicos.blobs.detectar", "algoritmos.classicos.variantes_blobs.detectar_escala"):
            proibido = patch(nome, side_effect=AssertionError("Decodificação ou detector proibido"))
            proibido.start(); self.addCleanup(proibido.stop)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            v.carregar_plano(serializar(plano))

    @contextmanager
    def trocar(self, nome, conteudo):
        caminho = self.raiz / nome
        antes = caminho.read_bytes(); caminho.write_bytes(conteudo)
        try:
            yield
        finally:
            caminho.write_bytes(antes)

    def test_ids_aprovados_8_campos_e_identidades_originais(self):
        plano = v.carregar_plano(serializar(self.plano))
        self.assertEqual([x["id"] for x in plano["configuracoes"]], list(v.IDS_APROVADOS))
        for c in plano["configuracoes"]:
            self.assertEqual(set(c), s.CAMPOS_CONFIGURACAO)
            self.assertEqual(p.hash_configuracao(c), v.IDENTIDADES_APROVADAS[c["id"]])
        self.assertEqual(plano["criterios"], CRITERIOS)

    def test_todos_quadros_metadados_e_20_referencias(self):
        self.assertEqual([x["video_id"] for x in self.plano["videos"]], ["13", "29", "52", "54"])
        self.assertEqual([x["quantidade_quadros"] for x in self.plano["videos"]], [1470,1470,1440,1470])
        self.assertEqual([x["fps"] for x in self.plano["videos"]], [49.0,49.0,48.0,49.0])
        self.assertEqual(sum(len(x["anotacoes"]) for x in self.plano["videos"]), 5850)
        self.assertEqual(sum(len(x["referencias_alinhamento"]) for x in self.plano["videos"]), 20)
        self.assertEqual(self.plano["geracao"]["avaliacoes_previstas"], 29250)

    def test_carregador_puro_sem_arquivos_ou_midias(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("I/O proibido")):
            self.assertEqual(v.carregar_plano(serializar(self.plano)), self.plano)

    def test_conferencia_22_fontes_e_bytes_vazios_nao_sao_ausencia(self):
        documentos = v.conferir_origens(self.plano, self.raiz)
        caminhos = v.caminhos_origens(self.plano)
        self.assertEqual(len(documentos), 22)
        self.assertEqual(set(documentos), set(caminhos))
        self.assertEqual(sum(Path(x).suffix==".csv" for x in caminhos.values()), 4)
        for nome, blob in documentos.items():self.assertEqual(blob, (self.raiz/caminhos[nome]).read_bytes())

    def test_determinismo_sem_sorteio_sem_mutacoes(self):
        antes = {str(x):p._sha256(x.read_bytes()) for x in self.raiz.rglob("*") if x.is_file()}
        estado = random.getstate()
        with patch("random.Random", side_effect=AssertionError("Sorteio proibido")):
            self.assertEqual(v.gerar_plano(self.raiz), self.plano)
        depois = {str(x):p._sha256(x.read_bytes()) for x in self.raiz.rglob("*") if x.is_file()}
        self.assertEqual(antes, depois); self.assertEqual(estado,random.getstate())

    def test_ranking_nao_define_ids_nem_metricas_herdadas(self):
        # O fixture tem ranking na ordem inversa e métricas antigas fictícias no plano limiar.
        self.assertEqual([x["id"] for x in v.gerar_plano(self.raiz)["configuracoes"]], list(v.IDS_APROVADOS))
        self.assertEqual(self.plano["criterios"], CRITERIOS)

    def test_id_ordem_ou_quantidade_nao_aprovada(self):
        for alterar in (lambda c:c.reverse(), lambda c:c.pop(), lambda c:c.append(c[0]),
                        lambda c:c[0].update(id="s001")):
            novo = deepcopy(self.plano); alterar(novo["configuracoes"]); self.rejeita(novo)

    def test_caixa_classe_parametros_backend_e_preprocessamento_congelados(self):
        alteracoes = (
            lambda c:c["caixa"].update(pixels=7),
            lambda c:c["parametros"]["classificacao"].update(area_minima_aglomerado=600),
            lambda c:c["parametros"].update(area_minima=48),
            lambda c:c["parametros"].update(distancia_minima=6),
            lambda c:c.update(preprocessamento={"metodo":"clahe","limite_contraste":2,"grade":[8,8]}),
        )
        for alterar in alteracoes:
            novo = deepcopy(self.plano); alterar(novo["configuracoes"][0]); self.rejeita(novo)
        novo = deepcopy(self.plano); novo["configuracoes"][3]["parametros"]["limiar_resposta"] = 0.12; self.rejeita(novo)

    def test_configuracao_rehash_nao_altera_identidade_aprovada(self):
        novo = deepcopy(self.plano); novo["configuracoes"][0]["caixa"]["pixels"] = 7
        novo["proveniencia"]["configuracoes"]["s052"]["configuracao_sha256"] = p.hash_configuracao(novo["configuracoes"][0])
        self.rejeita(novo)

    def test_contrato_mae_tolerancia_e_estado_pendente_fixos(self):
        for campo, valor in (("metodo","ignorar"),("tolerancia_igualdade_numerica",0.01),("base_indices",1),
                             ("situacao","conferido")):
            novo=deepcopy(self.plano);novo["alinhamento"][campo]=valor;self.rejeita(novo)

    def test_anotacoes_incompletas_duplicadas_ou_reordenadas(self):
        for alterar in (lambda a:a.pop(),lambda a:a.reverse(),lambda a:a[1].update(quadro=0),
                        lambda a:a[0].update(quadro=True),lambda a:a[0].update(arquivo="../fora.txt")):
            novo=deepcopy(self.plano);alterar(novo["videos"][0]["anotacoes"]);self.rejeita(novo)

    def test_referencias_e_metadados_nao_podem_ser_alterados(self):
        for campo,valor in (("fps",48.0),("largura",800),("altura",600),("quantidade_quadros",1469),
                            ("indice_inicial",1),("codec","outro"),("video_id","14")):
            novo=deepcopy(self.plano);novo["videos"][0][campo]=valor;self.rejeita(novo)
        novo=deepcopy(self.plano);novo["videos"][0]["metadados_mp4"]["taxa_constante"]=False;self.rejeita(novo)
        novo=deepcopy(self.plano);novo["videos"][0]["referencias_alinhamento"][4]["quadro"]=1468;self.rejeita(novo)

    def test_arquivo_anotado_ausente_interrompe_sem_exclusao(self):
        nome=self.plano["videos"][0]["anotacoes"][999]["arquivo"];path=self.raiz/nome;blob=path.read_bytes();path.unlink()
        try:
            with self.assertRaises(FileNotFoundError):v.conferir_origens(self.plano,self.raiz)
        finally:path.write_bytes(blob)

    def test_hashes_mp4_anotacao_e_jpeg_alterados(self):
        video=self.plano["videos"][0]
        for nome in (video["arquivo"],video["anotacoes"][5]["arquivo"],video["referencias_alinhamento"][0]["imagem"]):
            with self.trocar(nome,b"alterado"):
                with self.assertRaises(ValueError):v.conferir_origens(self.plano,self.raiz)

    def test_hashes_da_selecao_e_fontes_individuais(self):
        for nome in ("origem_selecao","execucao_selecao","ranking_selecao","resumo_por_quadro_selecao",
                     "configuracao_s052","avaliacao_s052","execucao_s052"):
            path=self.plano["proveniencia"]["fontes"][nome]["arquivo"]
            with self.trocar(path,b"corrompido"):
                with self.assertRaises(ValueError):v.conferir_origens(self.plano,self.raiz)

    def test_alias_de_origem_nao_pode_trocar_pasta_ou_fonte(self):
        novo=deepcopy(self.plano);novo["proveniencia"]["fontes"]["configuracao_s052"]["arquivo"]="../fora.json";self.rejeita(novo)
        novo=deepcopy(self.plano);novo["proveniencia"]["configuracoes"]["s052"]["pasta_selecao"]="outra";self.rejeita(novo)
        novo=deepcopy(self.plano);alias=novo["proveniencia"]["configuracoes"]["s052"]["desenvolvimento"]["origens"][0]
        alias["sha256_manifesto_execucao"]="0"*64
        v.carregar_plano(serializar(novo))
        with self.assertRaises(ValueError):v.conferir_origens(novo,self.raiz)

    def test_campos_extras_criterios_versao_seed_e_orcamento(self):
        for campo,valor in (("extra",1),("versao",True),("seed",43),("particao","final"),
                            ("etapa","desenvolvimento"),("criterios",{}),("politica_anotacoes_ausentes","ignorar")):
            novo=deepcopy(self.plano);novo[campo]=valor;self.rejeita(novo)
        novo=deepcopy(self.plano);novo["geracao"]["avaliacoes_previstas"]=29249;self.rejeita(novo)

    def test_json_duplicado_nan_e_tipo_invalido(self):
        for blob in (b'{"versao":1,"versao":1}',b'{"numero":NaN}',b'[]',"{}"):
            with self.assertRaises((TypeError,ValueError)):v.carregar_plano(blob)

    def test_planos_reais_de_desenvolvimento_e_selecao_preservados(self):
        self.assertEqual(tuple(p._sha256((RAIZ/f"scripts/blobs/rodadas/round{i}.json").read_bytes()) for i in range(1,6)),HASHES_RODADAS)
        self.assertEqual(p._sha256((RAIZ/v.PLANO_SELECAO).read_bytes()),"b33cdd0b1bb16386230bdf4f55a11bf94b57436ceeabe4c163f4aece885636a4")
        self.assertEqual(p._sha256((RAIZ/v.PLANO_VIDEOS_LIMIARIZACAO).read_bytes()),"ea797b01681b943e7a1f4c2442fe3cb2215e66d4425d4a23dd0af6bd3c784122")


if __name__ == "__main__":
    unittest.main()
