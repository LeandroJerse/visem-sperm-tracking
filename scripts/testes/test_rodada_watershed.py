"""Planejamento, integridade e execução: dados sintéticos, sem experimentos reais."""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import avaliar, agregar
from analise import relatorio_rodada_watershed as pdf
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import arquivar_codigo, colunas_metricas, carregar_json
from scripts.limiarizacao.inspecionar_imagem import gravar_csv, ler_anotacoes
from scripts.watershed import executar_rodada as runner
from scripts.watershed import planejamento as desenho

PLANO_REAL = runner.PLANO


def plano():
    return carregar_json(PLANO_REAL.read_bytes())


def montar_relatorio_sintetico(raiz):
    """48×178 linhas fictícias para testar a agregação/PDF sem rodar detecção."""
    p=plano(); batch=raiz/"resultados/frame-to-frame/watershed/round1/batch__sintetico"
    batch.mkdir(parents=True)
    p["origens"]={"teste.json":{"arquivo":"teste.json","sha256":desenho.sha(b'{}')}}
    (batch/"origens").mkdir();(batch/"origens/teste.json").write_bytes(b'{}')
    p["fontes_controles"]=[]
    m={"versao":1,"situacao":"concluida","algoritmo":"watershed","rodada":"round1","criterios":runner.CRITERIOS,
       "configuracoes_previstas":48,"configuracoes_concluidas":48,"quadros_por_configuracao":178,
       "avaliacoes_concluidas":8544,"execucoes":[],"dependencias":{},"seed":42}
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
                linhas_v.append(r);locais.append(r);quadros.append(r);avaliacoes.append(a)
            videos.append(runner.resumo(item,linhas_v,[a]*len(linhas_v),video_id=v))
        resumos.append(runner.resumo(item,locais,avaliacoes,pasta_origem=rel))
        gravar_json(pasta/"avaliacao.json",agregar(avaliacoes))
        if idx<4:
            for q in p["quadros"][:6]:
                sub=f"{q['video_id']}_frame_{q['quadro']}";dest=pasta/"quadros"/sub;dest.mkdir(parents=True)
                hashes={}
                for nome in desenho.ARQUIVOS_CONTROLE:
                    b=f"Sintético {item['id']} {sub} {nome}".encode()
                    (dest/nome).write_bytes(b)
                    copia=f"controles/{item['id']}/{sub}/{nome}"
                    alvo=batch/"origens"/copia;alvo.parent.mkdir(parents=True,exist_ok=True);alvo.write_bytes(b)
                    digest=desenho.sha(b);hashes[nome]=digest
                    p["fontes_controles"].append({"configuracao_id":item["id"],"video_id":q["video_id"],"quadro":q["quadro"],
                        "nome":nome,"arquivo":"sintetico/"+copia,"sha256":digest,"copia":copia})
                controles.append({"configuracao_id":item["id"],"video_id":q["video_id"],"quadro":q["quadro"],
                                  "situacao":"identico","sha256":hashes})
    for nome,tabela in (("resumo_por_quadro.csv",quadros),("resumo_configuracoes.csv",resumos),
                         ("resumo_por_video.csv",videos),("ranking.csv",runner.ordenar_por_f1(resumos))):
        gravar_csv(batch/nome,list(tabela[0]),tabela)
    gravar_json(batch/"controles.json",{"casos_conferidos":24,"casos":controles})
    gravar_json(batch/"plano.json",p);m["plano_sha256"]=desenho.sha((batch/"plano.json").read_bytes())
    m["saidas_sha256"]={f.relative_to(raiz).as_posix():desenho.sha(f.read_bytes()) for f in batch.rglob('*') if f.is_file()}
    gravar_json(batch/"execucao.json",m)
    return batch


class PlanejamentoTest(unittest.TestCase):
    def test_reproducao_composicao_pares_e_controles(self):
        p=plano();desenho.validar_plano(p)
        self.assertEqual(p,desenho.construir_plano())
        self.assertEqual(p["configuracoes"],desenho.gerar_configuracoes(p["referencias_round0"],42))
        for i in range(0,48,2):
            a,b=deepcopy(p["configuracoes"][i:i+2]);pa=a["parametros"];pb=b["parametros"]
            self.assertEqual(pa.pop("politica_aglomerados"),"separar")
            self.assertEqual(pb.pop("politica_aglomerados"),"preservar_por_area")
            self.assertEqual(pa,pb);self.assertEqual(a["par_id"],b["par_id"])
        self.assertEqual(len({x["parametros_sha256"] for x in p["configuracoes"]}),48)
        self.assertEqual(len(p["fontes_controles"]),96)

    def test_recusa_alteracoes_fora_do_plano(self):
        for mudar in (
            lambda p:p.update(seed=43),
            lambda p:p["configuracoes"][4]["parametros"]["segmentacao"].update(area_minima=10),
            lambda p:p["quadros"][0].update(video_id="14"),
            lambda p:p["quadros"].__setitem__(1,deepcopy(p["quadros"][0])),
            lambda p:p.update(exclusoes=[]),
        ):
            p=plano();mudar(p)
            with self.assertRaises(ValueError):desenho.validar_plano(p)

    def test_empate_exato_sem_preferencia_de_classe_e_sem_casos(self):
        def r(id,tp,fp,fn,classe0=0):
            return dict(configuracao_id=id,tp_individuos=tp,fp_individuos=fp,fn_individuos=fn,localizadas_classe_0=classe0)
        ran=runner.ordenar_por_f1([r('c',0,0,0),r('b',2,2,2,99),r('a',1,1,1),r('d',0,5,0)])
        self.assertEqual([(r['configuracao_id'],r['posicao']) for r in ran],[('a',1),('b',1),('d',3),('c',None)])

    def test_conferencia_para_antes_de_detector_ou_saida_se_plano_mudar(self):
        with patch.object(runner,"construir_plano",return_value={}),patch.object(runner.inspecao,"executar_quadro") as detectar:
            with self.assertRaisesRegex(ValueError,"origens congeladas"):runner.congelar_entradas()
            detectar.assert_not_called()


class ExecucaoTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="watershed_round1_sintetico_");self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name).resolve();self.saida=self.raiz/"resultados/frame-to-frame/watershed/round1"
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner,"RAIZ",self.raiz))
        self.stack.enter_context(patch.object(runner,"SAIDA",self.saida))
        self.stack.enter_context(patch.object(runner.inspecao,"RAIZ",self.raiz))
        p=plano();p["configuracoes"]=p["configuracoes"][:2];p["quadros"]=p["quadros"][:2]
        p["fontes_controles"]=[]
        im=np.zeros((80,100),np.uint8);im[10:30,10:30]=230;im[50:56,60:66]=200
        ok,png=cv2.imencode('.png',im);assert ok
        entradas=[{"quadro":q,"imagem_bytes":png.tobytes(),"anotacao_bytes":b'0 0.2 0.25 0.2 0.25\n',
                   "anotacoes":ler_anotacoes(b'0 0.2 0.25 0.2 0.25\n')} for q in p["quadros"]]
        for item in p["configuracoes"]:
            from algoritmos.classicos.watershed import configuracao_de_dict
            for e in entradas:
                q=e["quadro"];dest=self.raiz/"referencia"/item["id"]/f"{q['video_id']}_{q['quadro']}"
                runner.inspecao.executar_quadro(runner.decodificar(e),item,configuracao_de_dict(item["parametros"]),dest)
                for n in desenho.ARQUIVOS_CONTROLE:
                    p["fontes_controles"].append({"configuracao_id":item["id"],"video_id":q["video_id"],"quadro":q["quadro"],
                                                "nome":n,"sha256":desenho.sha((dest/n).read_bytes())})
        self.dados={"plano":p,"plano_bytes":desenho.bytes_json(p),"entradas":entradas,"origens":{},"hashes":{},
                    "codigo":{"teste.txt":b'Sintetico'},"dependencias":runner.dependencias()}

    def rodar(self):
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):return runner.processar(self.dados)

    def test_execucao_sintetica_controles_e_repeticao_sem_sobrescrever(self):
        with patch.object(pdf,"gerar_relatorio",return_value="sintetico.pdf"):
            pasta=self.rodar();segunda=self.rodar()
        self.assertNotEqual(pasta,segunda)
        m=carregar_json((pasta/"execucao.json").read_bytes())
        self.assertEqual(m["situacao"],"concluida");self.assertEqual(m["avaliacoes_concluidas"],4)
        for n,h in m['saidas_sha256'].items():self.assertEqual(desenho.sha((self.raiz/n).read_bytes()),h)
        ctrl=carregar_json((pasta/'controles.json').read_bytes());self.assertEqual(ctrl['casos_conferidos'],4)
        tabelas=[pdf._csv((pasta/n).read_bytes()) for n in ('resumo_configuracoes.csv','resumo_por_quadro.csv','resumo_por_video.csv','ranking.csv')]
        pdf.conferir_tabelas(self.dados['plano'],*tabelas)
        self.assertNotIn('imagem',self.dados['entradas'][0])
        self.assertEqual(len(list(pasta.rglob('mapas.npz'))),4)

    def test_falha_controle_preserva_parcial(self):
        self.dados['plano']['fontes_controles'][0]['sha256']='0'*64
        with patch.object(pdf,'gerar_relatorio') as gerar:
            with self.assertRaisesRegex(ValueError,'diverge do round0'):self.rodar()
            gerar.assert_not_called()
        batch=next(self.saida.glob('batch__*'));m=carregar_json((batch/'execucao.json').read_bytes())
        self.assertEqual(m['situacao'],'falhou');self.assertEqual(m['avaliacoes_concluidas'],0)
        self.assertTrue(list(batch.rglob('deteccoes.csv')))

    def test_interrupcao_preserva_saida_e_nao_gera_pdf(self):
        with patch.object(runner.inspecao,'executar_quadro',side_effect=KeyboardInterrupt),patch.object(pdf,'gerar_relatorio') as gerar:
            with self.assertRaises(KeyboardInterrupt):self.rodar()
            gerar.assert_not_called()
        batch=next(self.saida.glob('batch__*'));m=carregar_json((batch/'execucao.json').read_bytes())
        self.assertEqual(m['situacao'],'interrompida');self.assertEqual(m['avaliacoes_concluidas'],0)

    def test_falha_pdf_nao_invalida_metricas(self):
        with patch.object(pdf,'gerar_relatorio',side_effect=RuntimeError('teste')):batch=self.rodar()
        self.assertEqual(carregar_json((batch/'execucao.json').read_bytes())['situacao'],'concluida')
        self.assertEqual(carregar_json((batch/'relatorio.json').read_bytes())['situacao'],'falhou')


class RelatorioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='pdf_round1_sintetico_');cls.raiz=Path(cls.tmp.name).resolve()
        cls.batch=montar_relatorio_sintetico(cls.raiz)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(pdf,'RAIZ',self.raiz))
        self.stack.enter_context(patch.object(pdf,'SAIDA',self.batch.parent))

    def test_pdf_completo_regeneracao_e_integridade(self):
        dados=pdf.carregar(self.batch)
        self.assertEqual(len(dados['quadros']),8544);self.assertEqual(len(dados['videos']),576)
        primeiro=pdf.gerar_relatorio(self.batch);segundo=pdf.gerar_relatorio(self.batch)
        self.assertNotEqual(primeiro,segundo);self.assertTrue(primeiro.read_bytes().startswith(b'%PDF-'))
        registro=carregar_json((segundo.parent/'relatorio.json').read_bytes())
        self.assertEqual(registro['paginas'],4)
        self.assertEqual(registro['pdf_sha256'],desenho.sha(segundo.read_bytes()))

    def test_recusa_tabela_alterada(self):
        f=self.batch/'resumo_por_video.csv';blob=f.read_bytes()
        try:
            f.write_bytes(blob+b'alterado')
            with self.assertRaisesRegex(ValueError,'Saída alterada'):pdf.carregar(self.batch)
        finally:f.write_bytes(blob)

    def test_recusa_incompleto(self):
        f=self.batch/'execucao.json';blob=f.read_bytes()
        try:
            m=carregar_json(blob);m['avaliacoes_concluidas']=8543;gravar_json(f,m)
            with self.assertRaisesRegex(ValueError,'incompleta'):pdf.carregar(self.batch)
        finally:f.write_bytes(blob)

    def test_recusa_agregacao_errada_e_quadro_duplicado(self):
        dados=pdf.carregar(self.batch)
        args=[dados[k] for k in ('resumos','quadros','videos','ranking')]
        alterados=deepcopy(args);alterados[0][0]['tempo_detector_ns']=str(int(alterados[0][0]['tempo_detector_ns'])+1)
        with self.assertRaisesRegex(ValueError,'Agregação divergente'):pdf.conferir_tabelas(dados['plano'],*alterados)
        alterados=deepcopy(args);alterados[1][1]=deepcopy(alterados[1][0])
        with self.assertRaisesRegex(ValueError,'Quadros ausentes'):pdf.conferir_tabelas(dados['plano'],*alterados)

    def test_recusa_controle_modificado(self):
        f=next((self.batch/'r1c01').rglob('predicoes.txt'));b=f.read_bytes()
        try:
            f.write_bytes(b'alterado')
            with self.assertRaisesRegex(ValueError,'Saída alterada'):pdf.carregar(self.batch)
        finally:f.write_bytes(b)


if __name__=='__main__':unittest.main()
