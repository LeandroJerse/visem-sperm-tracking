"""PDF do round2: tabelas fictícias completas, sem executar detectores."""

from contextlib import ExitStack
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import avaliar, agregar
from analise import relatorio_round2_watershed as pdf
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import arquivar_codigo, colunas_metricas, carregar_json
from scripts.limiarizacao.inspecionar_imagem import gravar_csv
from scripts.watershed import executar_rodada as runner
from scripts.watershed import planejamento as desenho
from scripts.watershed import planejamento_round2 as desenho2
from scripts.watershed.planejamento import bytes_json
from scripts.testes.test_round2_watershed import plano

def montar_relatorio_sintetico(raiz, plano_override=None, origens_builder=None):
    """Tabelas fictícias completas para testar agregação/PDF sem rodar detecção."""
    p=plano() if plano_override is None else deepcopy(plano_override)
    quantidade=len(p["configuracoes"])
    ncontroles=sum(c["bloco"]=="controle" for c in p["configuracoes"])
    referencia=f"referencia_round{int(p['rodada'].removeprefix('round'))-1}"
    batch=raiz/f"resultados/frame-to-frame/watershed/{p['rodada']}/batch__sintetico"
    batch.mkdir(parents=True)
    p["origens"] = {}
    (batch/"origens").mkdir()
    p["fontes_controles"]=[]
    m={"versao":1,"situacao":"concluida","algoritmo":"watershed","rodada":p["rodada"],"criterios":runner.CRITERIOS,
       "configuracoes_previstas":quantidade,"configuracoes_concluidas":quantidade,"quadros_por_configuracao":178,
       "avaliacoes_concluidas":quantidade*178,"execucoes":[],"dependencias":{},"seed":42}
    m["codigo"]=arquivar_codigo(batch,{"teste.txt":b'Arquivo sintetico, sem resultados experimentais'})
    quadros,resumos,videos,controles=[],[],[],[]
    anotacoes=[Objeto(i,0 if i<7 else (2 if i<9 else 1),i*20,0,10,10) for i in range(10)]
    for idx,item in enumerate(p["configuracoes"]):
        pasta=batch/item["id"];pasta.mkdir();rel=pasta.relative_to(raiz).as_posix()
        m["execucoes"].append({"configuracao_id":item["id"],"pasta":rel})
        gravar_json(pasta/"configuracao.json",item["parametros"])
        locais,avaliacoes=[],[]
        for vi,v in enumerate(desenho.VIDEOS):
            n=(idx+vi)%10
            preds=[Objeto(i,2 if i%3==0 else anotacoes[i].classe,i*20,0,10,10) for i in range(n)]
            preds += [Objeto(20+i,0,300+i*20,0,10,10) for i in range(idx%4)]
            if idx%3==0:preds.append(anotacoes[9])
            a=avaliar(anotacoes,preds)
            linhas_v=[]
            for q in (q for q in p["quadros"] if q["video_id"]==v):
                r={"configuracao_id":item["id"],"video_id":v,"quadro":q["quadro"],
                   "imagem":q["imagem"],"anotacao":q["anotacao"],"pasta_quadro":rel+f"/quadros/{v}_frame_{q['quadro']}",
                   **dict.fromkeys(desenho.DIAGNOSTICO,0),**colunas_metricas(a)}
                r.update(deteccoes=len(preds),regioes_candidatas=len(preds),tempo_detector_ns=1100000+idx*1000)
                meta = {"limiar_otsu_original": 120 + vi, "deslocamento_otsu": item["parametros"]["deslocamento_otsu"],
                        "limiar_efetivo": 120 + vi + item["parametros"]["deslocamento_otsu"],
                        "pixels_mascara": 2400, "pixels_imagem": 8000, "fracao_pixels_mascara": 0.3}
                r.update(meta)
                dest = raiz / r["pasta_quadro"]; dest.mkdir(parents=True)
                gravar_json(dest / "segmentacao.json", meta)
                linhas_v.append(r);locais.append(r);quadros.append(r);avaliacoes.append(a)
            videos.append(runner.resumo(item,linhas_v,[a]*len(linhas_v),video_id=v))
        resumos.append(runner.resumo(item,locais,avaliacoes,pasta_origem=rel))
        gravar_json(pasta/"avaliacao.json",agregar(avaliacoes))
        if idx<ncontroles:
            for q in p["quadros"]:
                sub=f"{q['video_id']}_frame_{q['quadro']}";dest=pasta/"quadros"/sub;dest.mkdir(parents=True, exist_ok=True)
                hashes={}
                for nome in desenho.ARQUIVOS_CONTROLE:
                    b=f"Sintético {item['id']} {sub} {nome}".encode()
                    (dest/nome).write_bytes(b)
                    copia=f"controles/{item['id']}/{sub}/{nome}"
                    alvo=batch/"origens"/copia;alvo.parent.mkdir(parents=True,exist_ok=True);alvo.write_bytes(b)
                    digest=desenho.sha(b);hashes[nome]=digest
                    p["fontes_controles"].append({"configuracao_id":item["id"],"video_id":q["video_id"],"quadro":q["quadro"],
                        "nome":nome,"arquivo":f"sintetico/{item[referencia]}/quadros/{sub}/{nome}","sha256":digest,"copia":copia})
                controles.append({"configuracao_id":item["id"],"video_id":q["video_id"],"quadro":q["quadro"],
                                  "situacao":"identico","sha256":hashes})
    for nome,tabela in (("resumo_por_quadro.csv",quadros),("resumo_configuracoes.csv",resumos),
                         ("resumo_por_video.csv",videos),("ranking.csv",runner.ordenar_por_f1(resumos))):
        gravar_csv(batch/nome,list(tabela[0]),tabela)
    gravar_json(batch/"controles.json",{"casos_conferidos":ncontroles*178,"casos":controles})
    # Origens inteiramente sintéticas. Só o hash do manifesto fictício é
    # substituído nos testes; a grade de 32 e os 178 identificadores são reais.
    codigo = BytesIO()
    with ZipFile(codigo, "w") as z: z.writestr("teste.txt", "Sintetico")
    p1 = carregar_json((desenho2.RAIZ / desenho2.ROUND1 / "plano.json").read_bytes())
    p1_bytes = bytes_json(p1)
    m1 = {"situacao": "concluida", "avaliacoes_concluidas": 8544, "criterios": runner.CRITERIOS,
          "plano_sha256": desenho.sha(p1_bytes), "codigo": {"sha256_zip": desenho.sha(codigo.getvalue())},
          "execucoes": [{"configuracao_id": c[referencia], "pasta": "sintetico/"+c[referencia]}
                       for c in p["configuracoes"][:4]],
          "saidas_sha256": {f["arquivo"]: f["sha256"] for f in p["fontes_controles"]}}
    blobs = {"proposta.json": (desenho2.RAIZ / desenho2.PROPOSTA).read_bytes(),
             "round1_plano.json": p1_bytes, "round1_execucao.json": bytes_json(m1), "round1_codigo.zip": codigo.getvalue()}
    if origens_builder is not None:
        blobs = origens_builder(p, codigo.getvalue())
    for nome, blob in blobs.items():
        (batch/"origens"/nome).write_bytes(blob)
        p["origens"][nome] = {"arquivo": "sintetico/"+nome, "sha256": desenho.sha(blob)}
    gravar_json(batch/"plano.json",p);m["plano_sha256"]=desenho.sha((batch/"plano.json").read_bytes())
    m["saidas_sha256"]={f.relative_to(raiz).as_posix():desenho.sha(f.read_bytes()) for f in batch.rglob('*') if f.is_file()}
    gravar_json(batch/"execucao.json",m)
    return batch


class RelatorioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="pdf_round2_sintetico_")
        cls.raiz = Path(cls.tmp.name).resolve()
        cls.batch = montar_relatorio_sintetico(cls.raiz)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(pdf.base, "RAIZ", self.raiz))
        self.stack.enter_context(patch.object(pdf, "SAIDA", self.batch.parent))
        digest = desenho.sha((self.batch/"origens/round1_execucao.json").read_bytes())
        self.stack.enter_context(patch.object(desenho2, "MANIFESTO_SHA256", digest))

    def test_pdf_completo_cinco_paginas_recuperacao_sem_sobrescrever(self):
        dados = pdf.carregar(self.batch)
        self.assertEqual(len(dados["quadros"]), 5696)
        self.assertEqual(len(dados["videos"]), 384)
        self.assertEqual(dados["controles"]["casos_conferidos"], 712)
        primeiro = pdf.gerar_relatorio(self.batch); segundo = pdf.gerar_relatorio(self.batch)
        self.assertNotEqual(primeiro, segundo)
        self.assertTrue(primeiro.read_bytes().startswith(b"%PDF-"))
        r = carregar_json((segundo.parent/"relatorio.json").read_bytes())
        self.assertEqual(r["paginas"], 5)
        self.assertEqual(r["pdf_sha256"], desenho.sha(segundo.read_bytes()))

    def test_recusa_incompleto_e_arquivo_modificado(self):
        for nome, mudar, mensagem in (
            ("execucao.json", lambda b: bytes_json({**carregar_json(b), "avaliacoes_concluidas": 5695}), "incompleta"),
            ("resumo_por_video.csv", lambda b: b + b"alterado", "Saída alterada"),
            ("r2c01/quadros/11_frame_0/predicoes.txt", lambda b: b + b"alterado", "Saída alterada"),
            ("r2c01/quadros/11_frame_0/segmentacao.json", lambda b: b + b"alterado", "Saída alterada"),
        ):
            f = self.batch / nome; blob = f.read_bytes()
            try:
                f.write_bytes(mudar(blob))
                with self.assertRaisesRegex(ValueError, mensagem): pdf.carregar(self.batch)
            finally:
                f.write_bytes(blob)

    def test_metrica_sem_casos_e_erro_de_agregacao(self):
        dados = pdf.carregar(self.batch)
        r = dados["resumos"][0]
        r["tempo_detector_ns"] = str(int(r["tempo_detector_ns"]) + 1)
        with self.assertRaisesRegex(ValueError, "Agregação divergente"):
            pdf.base.conferir_tabelas(dados["plano"], dados["resumos"], dados["quadros"], dados["videos"], dados["ranking"])

    def test_metadados_incoerentes_mesmo_com_hash_atualizado(self):
        caminho = "r2c01/quadros/11_frame_0/segmentacao.json"
        f, manifest = self.batch/caminho, self.batch/"execucao.json"
        blob, mb = f.read_bytes(), manifest.read_bytes()
        for alteracao in ({"limiar_efetivo": 121}, {"pixels_mascara": 9000},
                          {"fracao_pixels_mascara": 0.2}, {"deslocamento_otsu": True}):
            try:
                m = carregar_json(blob); m.update(alteracao); gravar_json(f, m)
                reg = carregar_json(mb); reg["saidas_sha256"][f.relative_to(self.raiz).as_posix()] = desenho.sha(f.read_bytes())
                gravar_json(manifest, reg)
                with self.assertRaises(ValueError): pdf.carregar(self.batch)
            finally:
                f.write_bytes(blob); manifest.write_bytes(mb)

    def test_controle_referenciado_fora_do_manifesto_historico(self):
        p = carregar_json((self.batch/"plano.json").read_bytes())
        origens = {n: (self.batch/"origens"/n).read_bytes() for n in p["origens"]}
        p["fontes_controles"][0]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "manifesto histórico"):
            desenho2.conferir_origens(p, origens)


if __name__ == "__main__": unittest.main()
