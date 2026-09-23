"""Relatório de seleção, sem nova detecção ou promoção automática de finalistas."""

from collections import Counter
from fractions import Fraction
from pathlib import Path
import statistics

from analise import relatorio_rodada_watershed as base
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import carregar_json
from scripts.limiarizacao.inspecionar_imagem import agora
from scripts.watershed.planejamento import sha
from scripts.watershed.planejamento_selecao import conferir_origens, igual, validar_plano, VIDEOS

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/selecao"


def pontuacao(r):
    tp,fp,fn = (int(r[k+"_individuos"]) for k in ("tp","fp","fn"))
    return Fraction(2*tp,2*tp+fp+fn) if 2*tp+fp+fn else None


def limite_cinco(ranking):
    definidos=[r for r in ranking if pontuacao(r) is not None]
    if len(definidos)<5:
        return {"situacao":"menos_de_cinco_definidos","empate":False,"ids_empatados":[]}
    quinto=pontuacao(definidos[4])
    empate=len(definidos)>5 and quinto==pontuacao(definidos[5])
    return {"situacao":"empate_no_limite" if empate else "sem_empate_no_limite","empate":empate,
            "ids_empatados":[r["configuracao_id"] for r in definidos if pontuacao(r)==quinto] if empate else []}


def conferir_extras(p, quadros, ler, pastas):
    conferir_origens(p,{n:ler("origens/"+n) for n in p["origens"]})
    configs={c["id"]:c["parametros"] for c in p["configuracoes"]}
    mascaras, otsus = {}, {}
    for r in quadros:
        params=configs[r["configuracao_id"]];s=params["watershed"]["segmentacao"]
        rel=f"{pastas[r['configuracao_id']]}/quadros/{r['video_id']}_frame_{r['quadro']}"
        if r["pasta_quadro"] != (RAIZ / p["_batch_relativo"] / rel).relative_to(RAIZ).as_posix():
            raise ValueError("Pasta de quadro divergente.")
        meta=carregar_json(ler(rel+"/segmentacao.json"))
        campos={"limiar_otsu_original","deslocamento_otsu","limiar_efetivo","pixels_mascara","pixels_imagem","fracao_pixels_mascara"}
        if set(meta)!=campos:
            raise ValueError("Metadados de segmentação incompletos.")
        if any(type(meta[k]) is not int for k in ("pixels_mascara","pixels_imagem","deslocamento_otsu")):
            raise ValueError("Contagens ou deslocamento inválidos.")
        pixels,total=meta["pixels_mascara"],meta["pixels_imagem"]
        if not total>0 or not 0<=pixels<=total or meta["fracao_pixels_mascara"]!=pixels/total:
            raise ValueError("Fração de máscara inválida.")
        igual(meta["deslocamento_otsu"],params["deslocamento_otsu"],"deslocamento da seleção")
        if s["metodo"]=="manual":
            igual(meta["limiar_otsu_original"],None,"Otsu não calculado no método manual")
            igual(meta["limiar_efetivo"],s["limiar_manual"],"limiar manual")
        else:
            t=meta["limiar_otsu_original"]
            if type(t) is not int or not 0<=t<=255:
                raise ValueError("Limiar Otsu inválido.")
            igual(meta["limiar_efetivo"],min(255,max(0,t+params["deslocamento_otsu"])),"limiar ajustado")
            chave=(r["video_id"],r["quadro"])
            if otsus.setdefault(chave,t)!=t: raise ValueError("Otsu original mudou entre configurações.")
        if any(r[k]!=("" if v is None else str(v)) for k,v in meta.items()):
            raise ValueError("Metadados divergem da tabela.")
        # Filtros de área, sementes e política não alteram a máscara de entrada.
        chave=(r["video_id"],r["quadro"],s["polaridade"],meta["limiar_efetivo"],
               tuple(sorted(s["abertura"].items())),tuple(sorted(s["fechamento"].items())))
        if mascaras.setdefault(chave,(pixels,total))!=(pixels,total):
            raise ValueError("Máscaras de mesma parametrização divergem.")


def carregar(pasta):
    pasta=Path(pasta).expanduser().resolve(strict=True)
    # O caminho local auxilia apenas a conferência de pastas, sem alterar o plano salvo.
    def extras(p,quadros,ler,pastas):
        conferir_extras({**p,"_batch_relativo":pasta.relative_to(RAIZ).as_posix()},quadros,ler,pastas)
    d=base.carregar(pasta,rodada="selecao",quantidade=114,avaliacoes=6840,casos_controle=0,
        validador=validar_plano,saida=SAIDA,conferir_extra=extras,quadros_por_configuracao=60,etapa="selecao_imagens")
    m,p=d["manifesto"],d["plano"]
    igual(m["codigo"]["sha256_arquivos"][p["geracao"]["arquivo"]],p["geracao"]["sha256"],"gerador arquivado")
    for q in p["quadros"]:
        for tipo in ("imagem","anotacao"):
            igual(m["origens_sha256"].get(q[tipo]),q[tipo+"_sha256"],"hash da entrada")
    for o in p["origens"].values():
        igual(m["origens_sha256"].get(o["arquivo"]),o["sha256"],"hash da origem")
    d["limite_cinco"]=limite_cinco(d["ranking"])
    return d


def aviso(d):
    limite=d["limite_cinco"]
    if limite["empate"]:
        return "EMPATE NO LIMITE DE CINCO: revisão conjunta necessária. Nenhuma configuração foi promovida automaticamente."
    if limite["situacao"]=="menos_de_cinco_definidos":
        return "MENOS DE CINCO F1 DEFINIDOS: revisar os casos disponíveis antes de escolher finalistas."
    return "Ranking para revisão conjunta: as cinco finalistas ainda precisam ser aprovadas antes dos vídeos."


def escrever_pdf(caminho,d):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import simpleSplit
    c=Canvas(str(caminho),pagesize=landscape(A4))
    c.setTitle("Watershed | Seleção em imagens");c.setAuthor("Pesquisa de detecção em microscopia")
    w,h=landscape(A4); ranking=d["ranking"]
    configs={x["id"]:x for x in d["plano"]["configuracoes"]}
    por_video={(r["configuracao_id"],r["video_id"]):r for r in d["videos"]}
    def texto(x,y,t,tam=9,bold=False,cor="#263d4a"):
        c.setFillColor(HexColor(cor));c.setFont("Helvetica-Bold" if bold else "Helvetica",tam);c.drawString(x,y,str(t))
    def paragrafo(t,y,tam=8):
        for linha in simpleSplit(t,"Helvetica",tam,w-60):
            texto(30,y,linha,tam);y-=tam+4
        return y-5
    def inicio(titulo,pagina):
        c.setFillColor(HexColor("#edf4f7"));c.rect(0,h-82,w,82,fill=1,stroke=0)
        texto(30,h-25,"WATERSHED | SELEÇÃO EM IMAGENS",10,True)
        texto(30,h-51,titulo,20,True)
        texto(30,h-71,"114 configurações | 60 imagens | vídeos 13, 29, 52 e 54 | 6.840 avaliações | seed 42",9)
        texto(30,20,"Seleção para revisão conjunta; não é avaliação final nem escolha automática.",8)
        texto(w-48,20,f"{pagina}/8",8)
    def valor(v):
        return "s/c" if v in (None,"") else f"{float(v):.6f}".replace(".",",")
    def cols(xs,nomes,y=487):
        for x,n in zip(xs,nomes):texto(x,y,n,8,True)
    inicio("Localização de indivíduos: visão geral",1)
    paragrafo(aviso(d),490,9)
    xs=[30,91,237,303,377,451,524,598,673,745]
    cols(xs,["Pos./ID","F1 indivíduos","F1","Precisão","Recall","TP","FP","FN","F1 agl.","ms/img"],450)
    for i,r in enumerate(ranking[:10]):
        y=428-i*21
        texto(30,y,f"{r['posicao'] or '-'} {r['configuracao_id']}",8,True)
        f=pontuacao(r)
        c.setFillColor(HexColor("#e8eef1"));c.rect(100,y-2,118,9,fill=1,stroke=0)
        if f is not None:
            c.setFillColor(HexColor("#157a91"));c.rect(100,y-2,118*float(f),9,fill=1,stroke=0)
        vals=[valor(r[k]) for k in ("f1_individuos","precisao_individuos","recall_individuos")]
        vals += [r[k] for k in ("tp_individuos","fp_individuos","fn_individuos")]
        vals += [valor(r["f1_aglomerados"]),f"{int(r['tempo_detector_ns'])/int(r['quantidade_quadros'])/1e6:.1f}"]
        for x,v in zip(xs[2:],vals):texto(x,y,v,8)
    fs=[float(pontuacao(r)) for r in ranking if pontuacao(r) is not None]
    texto(30,212,"Distribuição descritiva entre configurações",12,True)
    if fs:
        q1,med,q3=statistics.quantiles(fs,n=4,method="inclusive") if len(fs)>1 else [fs[0]]*3
        for x,n,v in zip([30,187,344,501,658],["Mínimo","Q1","Mediana","Q3","Máximo"],[min(fs),q1,med,q3,max(fs)]):
            c.setFillColor(HexColor("#edf4f7"));c.rect(x,146,142,49,fill=1,stroke=0)
            texto(x+10,180,n,9);texto(x+10,157,valor(v),16,True)
    y=129
    for t in [f"{len(fs)}/114 F1 definidos. Catálogo: 20 configurações manuais e 94 Otsu; repetições históricas removidas.",
        "F1 de indivíduos 0+2 = 2TP/(2TP+FP+FN), após somar os 60 quadros. IoU >= 0,50; pares exclusivos.",
        "Trocas 0/2 são erros de classificação separados. Aglomerados têm avaliação própria. s/c = sem casos, nunca zero.",
        "Empates usam frações exatas; ID só ordena a exibição. Quartis e variação por vídeo não são testes de significância.",
        "Tempo: detector e diagnósticos internos; exclui leitura, avaliação, gravação e PDF. Imagens já usadas em outros detectores."]:
        y=paragrafo(t,y,8)
    c.showPage()
    for bloco in range(3):
        subset=ranking[bloco*40:(bloco+1)*40]
        inicio(f"Ranking completo | linhas {bloco*40+1} a {bloco*40+len(subset)}",2+bloco)
        for metade in range(2):
            x=30+metade*399
            xs=[x,x+35,x+85,x+142,x+163,x+185,x+221,x+257,x+294,x+337]
            cols(xs,["Pos.","ID","Limiar","Pol.","Reg.","Sem.","Mín.","Fec.","Origem","F1"])
            for j,r in enumerate(subset[metade*20:(metade+1)*20]):
                item=configs[r["configuracao_id"]];p=item["parametros"];ww=p["watershed"];s=ww["segmentacao"]
                lim=f"M{s['limiar_manual']}" if s["metodo"]=="manual" else f"O{p['deslocamento_otsu']:+d}"
                vals=[r["posicao"] or "-",item["id"],lim,"C" if s["polaridade"]=="claro" else "E",
                      "S" if ww["politica_aglomerados"]=="separar" else "P",ww["fracao_semente"],
                      s["area_minima"],s["fechamento"]["tamanho"],item["origens"][0]["configuracao_id"],valor(r["f1_individuos"])]
                y=465-j*17
                if j%2==0:
                    c.setFillColor(HexColor("#f0f5f7"));c.rect(x-3,y-4,391,16,fill=1,stroke=0)
                for xx,v in zip(xs,vals):texto(xx,y,v,7.5)
        y=104
        for t in ["M = limiar manual; O = Otsu e deslocamento. Pol.: C claro, E escuro. Reg.: S separar, P preservar por área.",
                  "Sem. = fração da semente; Mín. = área mínima; Fec. = tamanho do fechamento (pode estar desligado).",
                  "Origem = primeira aparição; todas as 136 origens e parâmetros completos estão no plano.json. Não houve novo ajuste.",
                  "Mesmas caixas das regiões, classes e métricas do desenvolvimento. Arredondamento não determina posições ou empates."]:
            y=paragrafo(t,y,8)
        c.showPage()
    for bloco in range(4):
        subset=ranking[bloco*30:(bloco+1)*30]
        inicio(f"Cobertura e vídeos | linhas {bloco*30+1} a {bloco*30+len(subset)}",5+bloco)
        xs=[30,74,108,144,183,250,315,379,438,496,564,632,700,765]
        cols(xs,["ID","TP","FP","FN","Cob. 0","Cob. 2","Cob. 1","Erro 0/2","Ac. cond.","V13","V29","V52","V54","F1 agl."])
        for j,r in enumerate(subset):
            y=467-j*11.5
            if j%2==0:
                c.setFillColor(HexColor("#f0f5f7"));c.rect(28,y-3,w-56,11.5,fill=1,stroke=0)
            vals=[r["configuracao_id"],*[r[k+"_individuos"] for k in ("tp","fp","fn")],
                  *[f"{r[f'localizadas_classe_{k}']}/{r[f'anotacoes_classe_{k}']}" for k in (0,2,1)],
                  f"{r['pares_incorretos']}/{r['pares_total']}",valor(r["acuracia_condicional"])]
            vals += [valor(por_video[r["configuracao_id"],v]["f1_individuos"]) for v in VIDEOS]
            vals += [valor(r["f1_aglomerados"])]
            for coluna,(xx,v) in enumerate(zip(xs,vals)):
                cor="#263d4a"
                if 9<=coluna<=12:
                    f=por_video[r["configuracao_id"],VIDEOS[coluna-9]]["f1_individuos"]
                    if f not in (None,""):
                        f=float(f)
                        c.setFillColor(Color(.93-.85*f,.96-.48*f,.97-.40*f))
                        c.rect(xx-3,y-3,64,11.5,fill=1,stroke=0)
                        if f>.65:cor="#ffffff"
                texto(xx,y,v,7.5,cor=cor)
        y=105
        for t in ["Cobertura = localizados/anotados, por classe original. Erro 0/2 = classes trocadas/indivíduos pareados.",
                  "Ac. cond. exclui objetos perdidos e falsas detecções; valor alto não garante boa classificação dos pequenos.",
                  "V13/V29/V52/V54: F1 em 15 quadros/vídeo; escala fixa de 0 (claro) a 1 (escuro). Quadros do mesmo vídeo são correlacionados.",
                  "Fontes conferidas: plano, origens, código arquivado, tabelas e metadados. PDF não relê JPEGs, máscaras ou caixas."]:
            y=paragrafo(t,y,8)
        c.showPage()
    c.save()
    return 8


def gerar_relatorio(pasta):
    import reportlab
    d=carregar(pasta)
    destino=d["pasta"]/"relatorios"/agora().strftime("%Y%m%dT%H%M%S%fZ")
    destino.mkdir(parents=True,exist_ok=False)
    pdf=destino/"relatorio.pdf"
    try:
        paginas=escrever_pdf(pdf,d)
        registro={"situacao":"concluida","paginas":paginas,"pdf_sha256":sha(pdf.read_bytes()),
            "manifesto_sha256":d["manifesto_sha256"],"fontes_sha256":d["hashes"],
            "codigo_relatorio_sha256":sha(Path(__file__).read_bytes()),"reportlab":reportlab.Version,
            "criterios":d["plano"]["criterios"],"limite_cinco":d["limite_cinco"],"selecao_automatica":False,
            "ordenacao":"F1 exato de indivíduos; empates compartilham posição; ID apenas organiza apresentação.",
            "escopo_conferencia":"Planos, origens, código arquivado, resumos, ranking e segmentação. Não reexecuta detector nem relê mídias."}
        gravar_json(destino/"relatorio.json",registro)
        gravar_json(d["pasta"]/"relatorio.json",{"situacao":"concluido","arquivo":pdf.relative_to(RAIZ).as_posix()})
    except Exception as erro:
        gravar_json(destino/"relatorio.json",{"situacao":"falhou","erro":str(erro)})
        raise
    return pdf
