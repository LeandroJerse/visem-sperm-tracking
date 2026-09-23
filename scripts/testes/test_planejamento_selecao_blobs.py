"""Seleção integral reproduzível com planos, manifestos e entradas sintéticos."""

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_selecao as s
from scripts.blobs.planejamento_round2 import gerar_round2
from scripts.blobs.planejamento_round3 import gerar_round3
from scripts.blobs.planejamento_round4 import gerar_round4
from scripts.blobs.planejamento_round5 import gerar_round5
from scripts.testes.test_planejamento_blobs import fontes_sinteticas


RAIZ = Path(__file__).resolve().parents[2]
HASHES_RODADAS = (
    "59eba7c3ca133b45c5b581860677add18675a2458fbc65d28d267cf5883b2b69",
    "29a9ae0de042b1da2a5b5563d9834565e5b8a8069a53e302793389b7435755da",
    "1b362082bd1fa22b2885a8b3f898c5116c2a34f4915de8c3f7cf374a457bce46",
    "f5d69b234435e2dfa64e681dc44eaac651fcf7a4eb9667a21e03a46ad62e154e",
    "bfd27624ff6f84bcd5e80c96195449b6762ecb74fc3c23b5c0478495b387032f",
)


def serializar(dados):
    return json.dumps(dados, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")


def fontes_selecao_sinteticas(raiz: Path) -> None:
    """Cria apenas entradas mínimas; os bytes de imagem não são decodificados."""
    def gravar(nome, conteudo):
        arquivo = raiz / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(conteudo)

    dev, inspecao = fontes_sinteticas()
    gravar(p.ORIGEM_DESENVOLVIMENTO, dev)
    gravar(p.ORIGEM_INSPECAO, inspecao)
    b1 = serializar(p.gerar_round1(dev, inspecao))
    b2 = serializar(gerar_round2(b1))
    b3 = serializar(gerar_round3(b1, b2))
    b4 = serializar(gerar_round4(b1, b2, b3))
    b5 = serializar(gerar_round5(b1, b2, b3, b4))
    for numero, conteudo in enumerate((b1, b2, b3, b4, b5), 1):
        gravar(f"scripts/blobs/rodadas/round{numero}.json", conteudo)
    for numero, conteudo in enumerate((b1, b2, b3, b4, b5), 1):
        plano = p.carregar_plano(conteudo)
        rodada = plano["rodada"]
        batch = s.BATCHES[rodada]
        saidas = {}

        def saida(nome, blob):
            gravar(nome, blob)
            saidas[nome] = p._sha256(blob)

        saida(batch + "/plano.json", conteudo)
        entradas = {f"scripts/blobs/rodadas/{rodada}.json": p._sha256(conteudo)}
        for campo in (k for k in plano if k.startswith("origem_")):
            origem = plano[campo]
            blob = (raiz / origem["plano"]).read_bytes()
            saida(batch + "/" + campo + ".json", blob)
            entradas[origem["plano"]] = p._sha256(blob)
        gerador = plano["geracao"]["arquivo_gerador"]
        codigo = (RAIZ / gerador).read_bytes()
        buffer = BytesIO()
        with ZipFile(buffer, "w") as arquivo:
            arquivo.writestr(gerador, codigo)
        zip_bytes = buffer.getvalue()
        saida(batch + "/codigo.zip", zip_bytes)
        execucoes = []
        for item in plano["configuracoes"]:
            pasta = f"resultados/frame-to-frame/blobs/{rodada}/{p.nome_configuracao(item)}__{batch.split('batch__')[1]}"
            saida(pasta + "/configuracao.json", serializar(item))
            estado = {"tipo": "rodada_blobs", "situacao": "concluida", "configuracao_id": item["id"],
                      "batch": batch, "plano_sha256": p._sha256(conteudo), "quadros_concluidos": 178,
                      "configuracao_sha256": p.hash_configuracao(item)}
            saida(pasta + "/execucao.json", serializar(estado))
            execucoes.append({"configuracao_id": item["id"], "pasta": pasta})
        n = len(execucoes)
        manifesto = {"versao": numero, "tipo": "rodada_blobs", "algoritmo": "blobs", "situacao": "concluida",
                     "etapa": "desenvolvimento", "particao": "desenvolvimento", "rodada": rodada,
                     "criterios": CRITERIOS, "configuracoes_previstas": n, "configuracoes_concluidas": n,
                     "quadros_por_configuracao": 178, "avaliacoes_concluidas": n * 178,
                     "plano_sha256": p._sha256(conteudo), "dependencias": {"python": "sintetico"},
                     "execucoes": execucoes, "saidas_sha256": saidas, "origens_sha256": entradas,
                     "codigo": {"sha256_zip": p._sha256(zip_bytes), "sha256_arquivos": {gerador: p._sha256(codigo)}}}
        gravar(batch + "/execucao.json", serializar(manifesto))
    quadros = []
    for video, quadro in s.ORDEM_QUADROS:
        item = {"video_id": video, "quadro": quadro}
        for tipo, pasta, sufixo in (("imagem", "images", "jpg"), ("anotacao", "labels", "txt")):
            nome = f"bases_de_dados/visem_tracking/dataset/Train/{video}/{pasta}/{video}_frame_{quadro}.{sufixo}"
            blob = f"imagem sintetica {video}/{quadro}".encode() if tipo == "imagem" else b""
            gravar(nome, blob)
            item[tipo] = nome
            item[f"sha256_{tipo}"] = p._sha256(blob)
        quadros.append(item)
    referencia = {"versao": 1, "seed": 42, "algoritmo": "limiarizacao", "rodada": "selecao", "particao": "selecao",
                  "politica_anotacoes_ausentes": "erro", "exclusoes": [], "quadros": quadros,
                  "criterios_avaliacao": {"antigo": "macro-F1; não deve ser herdado"}}
    gravar(s.ORIGEM_QUADROS, serializar(referencia))


class TestPlanejamentoSelecaoBlobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporario = TemporaryDirectory()
        cls.addClassCleanup(cls.temporario.cleanup)
        cls.raiz = Path(cls.temporario.name)
        with patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido")):
            fontes_selecao_sinteticas(cls.raiz)
            cls.modelo = s.gerar_plano(cls.raiz)

    def setUp(self):
        self.plano = deepcopy(self.modelo)
        for nome in ("cv2.SimpleBlobDetector_create", "algoritmos.classicos.blobs.detectar",
                     "algoritmos.classicos.variantes_blobs.detectar_escala"):
            proibido = patch(nome, side_effect=AssertionError("Detector proibido"))
            proibido.start()
            self.addCleanup(proibido.stop)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            s.carregar_plano(serializar(plano))

    @contextmanager
    def trocar(self, nome, conteudo):
        path = self.raiz / nome
        original = path.read_bytes()
        path.write_bytes(conteudo)
        try:
            yield
        finally:
            path.write_bytes(original)

    def test_catalogo_119_identidades_136_origens_e_tres_metodos(self):
        plano = s.carregar_plano(serializar(self.plano))
        self.assertEqual([x["id"] for x in plano["configuracoes"]], list(s.IDS))
        self.assertEqual(Counter(x["metodo"] for x in plano["configuracoes"]), {"simpleblob": 84, "log": 13, "dog": 22})
        self.assertEqual(len({p.hash_configuracao(x) for x in plano["configuracoes"]}), 119)
        self.assertEqual(sum(len(x["origens"]) for x in plano["proveniencia"].values()), 136)
        self.assertEqual(plano["geracao"]["avaliacoes_previstas"], 7140)

    def test_primeira_ocorrencia_preserva_parametros_e_hash_legado(self):
        for item in self.plano["configuracoes"]:
            origem = self.plano["proveniencia"][item["id"]]["primeira_origem"]
            anterior = p.carregar_plano((self.raiz / f"scripts/blobs/rodadas/{origem['rodada']}.json").read_bytes())
            fonte = next(x for x in anterior["configuracoes"] if x["id"] == origem["configuracao_id"])
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(fonte))
            self.assertEqual(item["parametros"], fonte["parametros"])
            self.assertEqual(item["caixa"], fonte["caixa"])
            for campo in ("bloco", "perfil_forma", "referencia"):
                self.assertEqual(item[campo], fonte[campo])
        self.assertEqual(self.plano["configuracoes"][0]["preprocessamento"], {"metodo": "nenhum"})

    def test_60_jpegs_120_hashes_e_anotacao_vazia_permitida(self):
        self.assertEqual([(q["video_id"], q["quadro"]) for q in self.plano["quadros"]], list(s.ORDEM_QUADROS))
        for q in self.plano["quadros"]:
            for campo in ("imagem", "anotacao"):
                self.assertEqual(p._sha256((self.raiz / q[campo]).read_bytes()), q[campo + "_sha256"])
        self.assertEqual(self.plano["criterios"], CRITERIOS)
        self.assertNotIn("macro_f1", self.plano["criterios"])

    def test_carregador_puro_nao_le_arquivos(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("I/O proibido")):
            self.assertEqual(s.carregar_plano(serializar(self.plano)), self.plano)

    def test_reproducao_identica_sem_random_e_sem_mutar_arquivos(self):
        estado = random.getstate()
        antes = {str(x.relative_to(self.raiz)): p._sha256(x.read_bytes()) for x in self.raiz.rglob("*") if x.is_file()}
        with patch("random.Random", side_effect=AssertionError("Sorteio proibido")):
            self.assertEqual(s.gerar_plano(self.raiz), self.plano)
            self.assertEqual(s.gerar_plano(self.raiz), self.plano)
        depois = {str(x.relative_to(self.raiz)): p._sha256(x.read_bytes()) for x in self.raiz.rglob("*") if x.is_file()}
        self.assertEqual(antes, depois)
        self.assertEqual(estado, random.getstate())

    def test_13_fontes_exatas_para_arquivar(self):
        documentos = s.conferir_origens(self.plano, self.raiz)
        caminhos = s.caminhos_origens(self.plano)
        self.assertEqual(set(documentos), set(caminhos))
        self.assertEqual(len(documentos), 13)
        for nome, conteudo in documentos.items():
            self.assertEqual(conteudo, (self.raiz / caminhos[nome]).read_bytes())

    def test_esquema_estrito_criterios_seed_e_orcamento(self):
        for campo, valor in (("versao", True), ("etapa", "desenvolvimento"), ("rodada", "round5"),
                             ("seed", 43), ("politica_anotacoes_ausentes", "ignorar"), ("exclusoes", [1]),
                             ("criterios", {"macro_f1": True}), ("extra", 0)):
            with self.subTest(campo=campo):
                novo = deepcopy(self.plano); novo[campo] = valor; self.rejeita(novo)
        for campo in ("quantidade_configuracoes", "quantidade_origens", "avaliacoes_previstas"):
            novo = deepcopy(self.plano); novo["geracao"][campo] += 1; self.rejeita(novo)

    def test_json_duplicado_nan_tipos_inadequados(self):
        for conteudo in (b'{"versao":1,"versao":1}', b'{"v":NaN}', b'[]', "{}"):
            with self.assertRaises((ValueError, TypeError)):
                s.carregar_plano(conteudo)

    def test_configuracao_duplicada_ou_ordem_alterada(self):
        novo = deepcopy(self.plano)
        novo["configuracoes"][1] = deepcopy(novo["configuracoes"][0])
        novo["configuracoes"][1]["id"] = "s002"
        self.rejeita(novo)
        novo = deepcopy(self.plano)
        novo["configuracoes"][0], novo["configuracoes"][1] = novo["configuracoes"][1], novo["configuracoes"][0]
        self.rejeita(novo)

    def test_qualquer_parametro_alterado_exige_nova_identidade(self):
        for campo, valor in (("caixa", {"modo": "margem", "pixels": 9}),
                             ("preprocessamento", {"metodo": "clahe", "limite_contraste": 2.0, "grade": [8, 8]})):
            novo = deepcopy(self.plano); novo["configuracoes"][0][campo] = valor; self.rejeita(novo)

    def test_hash_atualizado_nao_permite_mudar_configuracao_da_fonte(self):
        novo = deepcopy(self.plano)
        novo["configuracoes"][0]["parametros"]["distancia_minima"] = 4
        novo["proveniencia"]["s001"]["configuracao_sha256"] = p.hash_configuracao(novo["configuracoes"][0])
        s.carregar_plano(serializar(novo))
        with self.assertRaises(ValueError):
            s.conferir_origens(novo, self.raiz)

    def test_alias_ausente_duplicado_ou_fora_de_ordem(self):
        ident = next(k for k,v in self.plano["proveniencia"].items() if len(v["origens"]) > 1)
        novo = deepcopy(self.plano); novo["proveniencia"][ident]["origens"].pop(); self.rejeita(novo)
        novo = deepcopy(self.plano); novo["proveniencia"]["s002"]["origens"] = novo["proveniencia"]["s001"]["origens"]; self.rejeita(novo)
        novo = deepcopy(self.plano); novo["proveniencia"][ident]["origens"].reverse(); self.rejeita(novo)

    def test_primeira_origem_ou_pasta_adulterada(self):
        novo = deepcopy(self.plano); novo["proveniencia"]["s001"]["primeira_origem"]["rodada"] = "round5"; self.rejeita(novo)
        for nome in ("../externo", "C:/externo", "resultados/frame-to-frame/blobs/round1/inexistente"):
            novo = deepcopy(self.plano); novo["proveniencia"]["s001"]["origens"][0]["pasta_execucao"] = nome; self.rejeita(novo)

    def test_frame_faltante_duplicado_reordenado_ou_outro_video(self):
        for operacao in (lambda q:q.pop(), lambda q:q.append(q[0]), lambda q:q.reverse(),
                         lambda q:q[0].update(video_id="11")):
            novo = deepcopy(self.plano); operacao(novo["quadros"]); self.rejeita(novo)

    def test_hash_imagem_ou_anotacao_alterado_e_ausencia_nao_excluida(self):
        for tipo in ("imagem", "anotacao"):
            nome = self.plano["quadros"][0][tipo]
            with self.trocar(nome, b"alterado"):
                with self.assertRaises(ValueError):
                    s.conferir_origens(self.plano, self.raiz)
            arquivo = self.raiz / nome
            conteudo = arquivo.read_bytes(); arquivo.unlink()
            try:
                with self.assertRaises(FileNotFoundError):
                    s.conferir_origens(self.plano, self.raiz)
            finally:
                arquivo.write_bytes(conteudo)

    def test_hash_plano_ou_manifesto_de_origem_modificado(self):
        fonte = self.plano["origens_rodadas"][0]
        for nome in (fonte["plano"], fonte["batch"] + "/execucao.json", s.ORIGEM_QUADROS):
            with self.trocar(nome, (self.raiz / nome).read_bytes() + b" "):
                with self.assertRaises(ValueError):
                    s.conferir_origens(self.plano, self.raiz)

    def test_batch_parcial_rejeitado_mesmo_com_hash_atualizado(self):
        fonte = self.plano["origens_rodadas"][0]
        nome = fonte["batch"] + "/execucao.json"
        m = p._json((self.raiz / nome).read_bytes()); m["situacao"] = "falhou"
        blob = serializar(m)
        novo = deepcopy(self.plano); novo["origens_rodadas"][0]["manifesto_sha256"] = p._sha256(blob)
        with self.trocar(nome, blob):
            with self.assertRaises(ValueError):
                s.conferir_origens(novo, self.raiz)

    def test_configuracao_nao_concluida_rejeitada_mesmo_rehash_manifestos(self):
        fonte = self.plano["origens_rodadas"][0]
        nome = fonte["batch"] + "/execucao.json"
        m = p._json((self.raiz / nome).read_bytes())
        caminho = m["execucoes"][0]["pasta"] + "/execucao.json"
        estado = p._json((self.raiz / caminho).read_bytes()); estado["quadros_concluidos"] = 177
        blob_estado = serializar(estado); m["saidas_sha256"][caminho] = p._sha256(blob_estado)
        blob = serializar(m)
        novo = deepcopy(self.plano); novo["origens_rodadas"][0]["manifesto_sha256"] = p._sha256(blob)
        with self.trocar(nome, blob), self.trocar(caminho, blob_estado):
            with self.assertRaises(ValueError):
                s.conferir_origens(novo, self.raiz)

    def test_zip_e_copia_plano_adulterados(self):
        batch = self.plano["origens_rodadas"][0]["batch"]
        for nome in (batch + "/codigo.zip", batch + "/plano.json", batch + "/origem_inspecao.json"):
            with self.trocar(nome, b"corrompido"):
                with self.assertRaises(ValueError):
                    s.conferir_origens(self.plano, self.raiz)

    def test_plano_estrutural_rejeita_origens_falsas_e_contagens(self):
        for campo, valor in (("configuracoes_concluidas", 47), ("quadros_por_configuracao", 177),
                             ("avaliacoes_concluidas", 1), ("plano_sha256", "x"),
                             ("batch", "../fora"), ("dependencias", {})):
            novo = deepcopy(self.plano); novo["origens_rodadas"][0][campo] = valor; self.rejeita(novo)

    def test_nomes_distintos_e_informativos_incluem_clahe_log_dog(self):
        nomes = [s.nome_configuracao(x) for x in self.plano["configuracoes"]]
        self.assertEqual(len(set(nomes)), 119)
        for item, nome in zip(self.plano["configuracoes"], nomes):
            self.assertIn(item["id"], nome)
            self.assertIn(item["metodo"], nome)
            self.assertIn(item["preprocessamento"]["metodo"], nome)
            self.assertIn(p.hash_configuracao(item)[:12], nome)
            self.assertLess(len(nome), 120)
        for ident in ("r1c01", "s000", "s120", "../s001"):
            item = deepcopy(self.plano["configuracoes"][0]); item["id"] = ident
            with self.assertRaises(ValueError):s.nome_configuracao(item)

    def test_cinco_planos_historicos_permanecem_intactos(self):
        self.assertEqual(tuple(p._sha256((RAIZ / f"scripts/blobs/rodadas/round{i}.json").read_bytes()) for i in range(1,6)),
                         HASHES_RODADAS)


if __name__ == "__main__":
    unittest.main()
