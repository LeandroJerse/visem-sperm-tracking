"""Seleção: catálogo, compatibilidade histórica, execução sintética e relatório."""

from collections import Counter
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import cv2

from algoritmos.classicos.watershed import configuracao_de_dict as ler_original
from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import avaliar, agregar
from analise import relatorio_selecao_watershed as pdf
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import arquivar_codigo, carregar_json, colunas_metricas
from scripts.limiarizacao.inspecionar_imagem import gravar_csv, ler_anotacoes
from scripts.watershed import executar_selecao as runner
from scripts.watershed import planejamento_selecao as desenho
from scripts.watershed import saidas_selecao as saidas
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, DIAGNOSTICO, bytes_json, sha
from scripts.testes.test_round2_watershed import imagem

RAIZ_REAL=desenho.RAIZ
PLANO_REAL=desenho.PLANO
def plano(): return carregar_json(PLANO_REAL.read_bytes())


def fixture_relatorio(raiz):
    """6.840 linhas fictícias; não executa detectores nem lê imagens da base."""
    p=plano();batch=raiz/"resultados/frame-to-frame/watershed/selecao/batch__sintetico"
    batch.mkdir(parents=True);gravar_json(batch/"plano.json",p)
    hashes={"scripts/watershed/selecao/plano.json":sha((batch/"plano.json").read_bytes())}
    for nome,o in p["origens"].items():
        alvo=batch/"origens"/nome;alvo.parent.mkdir(parents=True,exist_ok=True)
        blob=(RAIZ_REAL/o["arquivo"]).read_bytes();alvo.write_bytes(blob);hashes[o["arquivo"]]=sha(blob)
    for q in p["quadros"]:
        for t in ("imagem","anotacao"):hashes[q[t]]=q[t+"_sha256"]
    m={"versao":1,"algoritmo":"watershed","rodada":"selecao","etapa":"selecao_imagens","situacao":"concluida",
       "criterios":p["criterios"],"seed":42,"configuracoes_previstas":114,"configuracoes_concluidas":114,
       "quadros_por_configuracao":60,"avaliacoes_concluidas":6840,"plano_sha256":sha((batch/"plano.json").read_bytes()),
       "origens_sha256":hashes,"execucoes":[]}
    m["codigo"]=arquivar_codigo(batch,{n:(RAIZ_REAL/n).read_bytes() for n in runner.FONTES})
    an=[Objeto(i,0 if i<7 else (2 if i<9 else 1),i*20,0,10,10) for i in range(10)]
    linhas=[];resumos=[];videos=[]
    for idx,item in enumerate(p["configuracoes"]):
        pasta=batch/item["id"];pasta.mkdir();rel=pasta.relative_to(raiz).as_posix()
        m["execucoes"].append({"configuracao_id":item["id"],"pasta":rel})
        gravar_json(pasta/"configuracao.json",item["parametros"])
        locais=[];avals=[];params=item["parametros"];s=params["watershed"]["segmentacao"]
        for vi,v in enumerate(desenho.VIDEOS):
            n=(idx+vi)%10
            preds=[Objeto(i,2 if i%3==0 else an[i].classe,i*20,0,10,10) for i in range(n)]
            preds += [Objeto(20+i,0,300+i*20,0,10,10) for i in range(idx%4)]
            if idx%3==0:preds.append(an[9])
            a=avaliar(an,preds);lv=[]
            for q in (q for q in p["quadros"] if q["video_id"]==v):
                r={"configuracao_id":item["id"],"video_id":v,"quadro":q["quadro"],
                   "imagem":q["imagem"],"anotacao":q["anotacao"],"pasta_quadro":rel+f"/quadros/{v}_frame_{q['quadro']}",
                   **dict.fromkeys(DIAGNOSTICO,0),**colunas_metricas(a)}
                r.update(deteccoes=len(preds),regioes_candidatas=len(preds),tempo_detector_ns=1100000+idx*1000)
                t=None if s["metodo"]=="manual" else 120+vi
                meta={"limiar_otsu_original":t,"deslocamento_otsu":params["deslocamento_otsu"],
                      "limiar_efetivo":s["limiar_manual"] if t is None else t+params["deslocamento_otsu"],
                      "pixels_mascara":2400,"pixels_imagem":8000,"fracao_pixels_mascara":.3}
                dest=raiz/r["pasta_quadro"];dest.mkdir(parents=True)
                gravar_json(dest/"segmentacao.json",meta);r.update(meta)
                lv.append(r);locais.append(r);linhas.append(r);avals.append(a)
            videos.append(runner.comum.resumo(item,lv,[a]*len(lv),video_id=v))
        resumos.append(runner.comum.resumo(item,locais,avals,pasta_origem=rel))
        gravar_json(pasta/"avaliacao.json",agregar(avals))
    for nome,tabela in (("resumo_configuracoes.csv",resumos),("resumo_por_quadro.csv",linhas),
                       ("resumo_por_video.csv",videos),("ranking.csv",runner.comum.ordenar_por_f1(resumos))):
        gravar_csv(batch/nome,list(tabela[0]),tabela)
    gravar_json(batch/"controles.json",{"casos_conferidos":0,"casos":[]})
    m["saidas_sha256"]={x.relative_to(raiz).as_posix():sha(x.read_bytes()) for x in batch.rglob("*") if x.is_file()}
    gravar_json(batch/"execucao.json",m)
    return batch


class PlanoTest(unittest.TestCase):
    def test_catalogo_reproduzido_sem_descartar_variantes(self):
        p=plano();self.assertEqual(p,desenho.construir_plano())
        self.assertEqual(len(p["configuracoes"]),114)
        self.assertEqual(sum(len(c["origens"]) for c in p["configuracoes"]),136)
        self.assertEqual(Counter(c["parametros"]["watershed"]["segmentacao"]["metodo"] for c in p["configuracoes"]),{"manual":20,"otsu":94})
        self.assertEqual(len(p["origens"]),153);self.assertFalse(p["selecao_automatica"])
        self.assertEqual(len(p["quadros"]),60);self.assertEqual(p["exclusoes"],[])

    def test_tampering_catalogo_quadros_e_proveniencia_rejeitado(self):
        for mudar in (lambda p:p.update(seed=True),lambda p:p["configuracoes"].pop(),
                      lambda p:p["configuracoes"][0]["origens"].pop(),
                      lambda p:p["configuracoes"][0]["parametros"]["watershed"].update(fracao_semente=.123),
                      lambda p:p["quadros"][0].update(video_id="14"),
                      lambda p:p["quadros"][0].update(imagem_sha256="0"*64),
                      lambda p:p.update(selecao_automatica=True),lambda p:p["origens"].pop("round5_codigo.zip")):
            p=plano();mudar(p)
            with self.assertRaises((ValueError,KeyError)):desenho.validar_plano(p)

    def test_origens_arquivadas_podem_ser_conferidas_sem_base(self):
        p=plano();blobs={n:(RAIZ_REAL/o["arquivo"]).read_bytes() for n,o in p["origens"].items()}
        m=desenho.conferir_origens(p,blobs)
        self.assertEqual(m["avaliacoes_concluidas"],2492)
        for nome in ("round5_codigo.zip","round1_plano.json","round1/configuracoes/r1c01.json"):
            antes=blobs[nome];blobs[nome]=b"alterado"
            with self.assertRaises(ValueError):desenho.conferir_origens(p,blobs)
            blobs[nome]=antes

    def test_preflight_para_antes_detector_e_nao_cria_resultados(self):
        with patch.object(runner,"construir_plano",return_value={}),patch.object(runner,"executar_quadro") as detectar:
            with self.assertRaisesRegex(ValueError,"congelada"):runner.congelar_entradas()
            detectar.assert_not_called()

    def test_cli_conferir_e_somente_relatorio(self):
        with patch.object(runner,"congelar_entradas",return_value={"hashes":{}}),patch.object(runner,"processar") as detectar,redirect_stdout(StringIO()):
            self.assertEqual(runner.main(["--conferir"]),0);detectar.assert_not_called()
        with patch.object(pdf,"gerar_relatorio",return_value="teste.pdf") as gerar,redirect_stdout(StringIO()):
            self.assertEqual(runner.main(["--somente-relatorio","batch"]),0)
            gerar.assert_called_once_with(Path("batch"))


class ExecucaoTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="selecao_watershed_sintetica_")
        self.addCleanup(self.tmp.cleanup);self.raiz=Path(self.tmp.name).resolve()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for obj,key,value in ((runner.comum,"RAIZ",self.raiz),(saidas.original,"RAIZ",self.raiz),
                              (runner,"SAIDA",self.raiz/"resultados/frame-to-frame/watershed/selecao")):
            self.stack.enter_context(patch.object(obj,key,value))
        p=plano();groups={}
        for c in p["configuracoes"]:
            s=c["parametros"]["watershed"]["segmentacao"]
            groups.setdefault((s["metodo"],s["polaridade"]),c)
        # A grade real não contém Otsu escuro; exercitar também esse caminho
        # somente no ensaio sintético, sem alterar o catálogo congelado.
        self.assertEqual(len(groups),3)
        extra=deepcopy(groups[("otsu","claro")]);extra["id"]="s999"
        extra["parametros"]["watershed"]["segmentacao"]["polaridade"]="escuro"
        groups[("otsu","escuro")]=extra
        self.items=list(groups.values());self.assertEqual(len(self.items),4)
        p["configuracoes"]=self.items;p["quadros"]=p["quadros"][:2]
        ok,png=cv2.imencode(".png",imagem());self.assertTrue(ok)
        an=b"0 0.2 0.25 0.2 0.25\n"
        self.entradas=[{"quadro":q,"imagem_bytes":png.tobytes(),"anotacao_bytes":an,"anotacoes":ler_anotacoes(an)} for q in p["quadros"]]
        self.dados={"plano":p,"plano_bytes":bytes_json(p),"entradas":self.entradas,"hashes":{},"origens":{},
                    "codigo":{"sintetico.txt":b"Teste"},"dependencias":runner.comum.dependencias()}

    def rodar(self):
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):return runner.processar(self.dados)

    def test_manual_e_otsu_zero_ambas_polaridades_preservam_saidas(self):
        for item in self.items:
            e=runner.comum.decodificar(self.entradas[0])
            a=self.raiz/"original"/item["id"];b=self.raiz/"selecao"/item["id"]
            saidas.original.executar_quadro(e,item,ler_original(item["parametros"]["watershed"]),a)
            linha,_=saidas.executar_quadro(e,item,desenho.ler_configuracao(item["parametros"]),b)
            for nome in ARQUIVOS_CONTROLE:self.assertEqual((a/nome).read_bytes(),(b/nome).read_bytes())
            self.assertEqual(len(list(b.iterdir())),12)
            if item["parametros"]["watershed"]["segmentacao"]["metodo"]=="manual":
                self.assertIsNone(linha["limiar_otsu_original"])
            else:self.assertIsInstance(linha["limiar_otsu_original"],int)

    def test_execucao_repetida_preserva_resultados_e_tabelas(self):
        with patch.object(pdf,"gerar_relatorio",return_value="sintetico.pdf"):
            a=self.rodar();b=self.rodar()
        self.assertNotEqual(a,b)
        m=carregar_json((a/"execucao.json").read_bytes())
        self.assertEqual(m["etapa"],"selecao_imagens");self.assertEqual(m["avaliacoes_concluidas"],8)
        self.assertEqual(carregar_json((a/"controles.json").read_bytes())["casos_conferidos"],0)
        for nome,digest in m["saidas_sha256"].items():self.assertEqual(sha((self.raiz/nome).read_bytes()),digest)
        tabs=[pdf.base._csv((a/n).read_bytes()) for n in ("resumo_configuracoes.csv","resumo_por_quadro.csv","resumo_por_video.csv","ranking.csv")]
        pdf.base.conferir_tabelas(self.dados["plano"],*tabs)
        for ex in m["execucoes"]:self.assertIn("__cfg-",ex["pasta"])
        self.assertFalse(list(a.glob("*finalist*")))

    def test_interrupcao_e_pdf_falho_preservam_dados(self):
        with patch.object(runner,"executar_quadro",side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.rodar()
        estados=[carregar_json((b/"execucao.json").read_bytes())["situacao"] for b in runner.SAIDA.glob("batch__*")]
        self.assertEqual(estados,["interrompida"])
        with patch.object(pdf,"gerar_relatorio",side_effect=RuntimeError("Teste")):b=self.rodar()
        self.assertEqual(carregar_json((b/"execucao.json").read_bytes())["situacao"],"concluida")
        self.assertEqual(carregar_json((b/"relatorio.json").read_bytes())["situacao"],"falhou")


class RankingTest(unittest.TestCase):
    def test_empate_exato_na_quinta_vaga_sem_promocao(self):
        rows=[{"configuracao_id":f"s{i:03}","tp_individuos":10,"fp_individuos":i if i<5 else 5,"fn_individuos":0} for i in range(1,8)]
        rank=runner.comum.ordenar_por_f1(rows);limite=pdf.limite_cinco(rank)
        self.assertTrue(limite["empate"]);self.assertEqual(limite["ids_empatados"],["s005","s006","s007"])
        self.assertIn("EMPATE NO LIMITE",pdf.aviso({"limite_cinco":limite}))

    def test_fracoes_exatas_sem_casos_e_fp_sem_anotacao(self):
        n=10**20
        rows=[{"configuracao_id":"s001","tp_individuos":n,"fp_individuos":1,"fn_individuos":0},
              {"configuracao_id":"s002","tp_individuos":n,"fp_individuos":0,"fn_individuos":0},
              {"configuracao_id":"s003","tp_individuos":0,"fp_individuos":0,"fn_individuos":0},
              {"configuracao_id":"s004","tp_individuos":0,"fp_individuos":1,"fn_individuos":0}]
        rank=runner.comum.ordenar_por_f1(rows)
        self.assertEqual([r["configuracao_id"] for r in rank],["s002","s001","s004","s003"])
        self.assertIsNone(rank[-1]["posicao"]);self.assertEqual(rank[-2]["posicao"],3)
        self.assertEqual(pdf.limite_cinco(rank)["situacao"],"menos_de_cinco_definidos")


class RelatorioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="pdf_selecao_watershed_")
        cls.raiz=Path(cls.tmp.name).resolve();cls.batch=fixture_relatorio(cls.raiz)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for obj,key,value in ((pdf,"RAIZ",self.raiz),(pdf.base,"RAIZ",self.raiz),(pdf,"SAIDA",self.batch.parent)):
            self.stack.enter_context(patch.object(obj,key,value))

    def test_pdf_completo_oito_paginas_recuperacao_e_todos_ids(self):
        from reportlab.pdfgen.canvas import Canvas
        textos=[];original=Canvas.drawString
        def registrar(c,x,y,t,*args,**kwargs):
            textos.append(str(t));return original(c,x,y,t,*args,**kwargs)
        with patch.object(Canvas,"drawString",new=registrar):a=pdf.gerar_relatorio(self.batch)
        b=pdf.gerar_relatorio(self.batch);self.assertNotEqual(a,b)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b",b.read_bytes())),8)
        for c in plano()["configuracoes"]:self.assertIn(c["id"],"\n".join(textos))
        m=carregar_json((b.parent/"relatorio.json").read_bytes())
        self.assertFalse(m["selecao_automatica"]);self.assertEqual(m["pdf_sha256"],sha(b.read_bytes()))

    def test_rejeita_batch_incompleto_etapa_errada_e_metadado_alterado(self):
        for nome,mudar in (("execucao.json",lambda b:bytes_json({**carregar_json(b),"avaliacoes_concluidas":6839})),
                           ("execucao.json",lambda b:bytes_json({**carregar_json(b),"etapa":"desenvolvimento"})),
                           ("s001/quadros/13_frame_0/segmentacao.json",lambda b:b+b"alterado"),
                           ("origens/round5_codigo.zip",lambda b:b+b"alterado")):
            f=self.batch/nome;antes=f.read_bytes()
            try:
                f.write_bytes(mudar(antes))
                with self.assertRaises(ValueError):pdf.carregar(self.batch)
            finally:f.write_bytes(antes)

    def test_sem_base_e_rejeita_pasta_inconsistente_apesar_de_rehash(self):
        self.assertFalse((self.raiz/"bases_de_dados").exists())
        nome="resumo_por_quadro.csv";f=self.batch/nome;mf=self.batch/"execucao.json"
        antes=f.read_bytes();antesm=mf.read_bytes()
        try:
            rows=pdf.base._csv(antes);rows[0]["pasta_quadro"]="outro/quadro"
            gravar_csv(f,list(rows[0]),rows);m=carregar_json(antesm)
            m["saidas_sha256"][f.relative_to(self.raiz).as_posix()]=sha(f.read_bytes());gravar_json(mf,m)
            with self.assertRaisesRegex(ValueError,"Pasta de quadro"):pdf.carregar(self.batch)
        finally:f.write_bytes(antes);mf.write_bytes(antesm)

    def test_metadados_manuais_rejeitam_otsu_inventado(self):
        d=pdf.carregar(self.batch)
        manual=next(c for c in d["plano"]["configuracoes"] if c["parametros"]["watershed"]["segmentacao"]["metodo"]=="manual")
        r=next(r for r in d["quadros"] if r["configuracao_id"]==manual["id"])
        p={**d["plano"],"_batch_relativo":self.batch.relative_to(self.raiz).as_posix()}
        def ler(nome):
            b=(self.batch/nome).read_bytes()
            if nome.endswith("/segmentacao.json"):
                return bytes_json({**carregar_json(b),"limiar_otsu_original":123})
            return b
        with self.assertRaisesRegex(ValueError,"Otsu não calculado"):
            pdf.conferir_extras(p,[r],ler,{manual["id"]:manual["id"]})


if __name__=="__main__":unittest.main()
