"""Relatório descritivo do round1, calculado apenas com resultados salvos."""

from collections import defaultdict
from io import BytesIO
from pathlib import Path
import statistics
from zipfile import ZipFile

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_inspecao_blobs import CONTAGENS, _conferir_metricas, _csv, _inteiro
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import carregar_json, colunas_metricas
from scripts.limiarizacao.inspecionar_imagem import agora
from scripts.watershed.executar_rodada import ordenar_por_f1
from scripts.watershed.planejamento import DIAGNOSTICO, sha, validar_plano

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round1"


def conferir_tabelas(plano, resumos, quadros, videos, ranking):
    ids = [c["id"] for c in plano["configuracoes"]]
    chaves = {(q["video_id"], str(q["quadro"])): q for q in plano["quadros"]}
    vids = {v for v, _ in chaves}
    if [r["configuracao_id"] for r in resumos] != ids:
        raise ValueError("Configurações ausentes, repetidas ou fora de ordem.")
    previstas = {(i, v, q) for i in ids for v, q in chaves}
    if (len(quadros) != len(previstas)
            or {(r["configuracao_id"], r["video_id"], r["quadro"]) for r in quadros} != previstas):
        raise ValueError("Quadros ausentes, repetidos ou fora do plano.")
    if (len(videos) != len(ids)*len(vids)
            or {(r["configuracao_id"],r["video_id"]) for r in videos} != {(i,v) for i in ids for v in vids}):
        raise ValueError("Vídeos ausentes ou repetidos.")
    for r in resumos + quadros + videos:
        _conferir_metricas(r)
        for campo in DIAGNOSTICO:
            _inteiro(r[campo])
        if int(r["deteccoes"]) + int(r["rejeitadas_area"]) != int(r["regioes_candidatas"]):
            raise ValueError("Candidatos não reconciliam.")
        if int(r["deteccoes"]) != sum(int(r[f"{k}_{g}"]) for k in ("tp","fp") for g in ("individuos","aglomerados")):
            raise ValueError("Detecções divergem da avaliação.")
    por_config, por_video, por_quadro = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in quadros:
        ref = chaves[r["video_id"], r["quadro"]]
        if any(r[k] != ref[k] for k in ("imagem", "anotacao")):
            raise ValueError("Imagem/anotação diverge do plano.")
        por_config[r["configuracao_id"]].append(r)
        por_video[r["configuracao_id"],r["video_id"]].append(r)
        por_quadro[r["video_id"],r["quadro"]].append(r)
    for resumo in resumos + videos:
        grupo = (por_video[resumo["configuracao_id"],resumo["video_id"]] if "video_id" in resumo
                 else por_config[resumo["configuracao_id"]])
        if int(resumo["quantidade_quadros"]) != len(grupo):
            raise ValueError("Quantidade de quadros divergente.")
        for k in (*CONTAGENS, *DIAGNOSTICO):
            if int(resumo[k]) != sum(int(r[k]) for r in grupo):
                raise ValueError(f"Agregação divergente: {k}.")
    for grupo in por_quadro.values():
        for classe in (0,1,2):
            if len({r[f"anotacoes_classe_{classe}"] for r in grupo}) != 1:
                raise ValueError("Anotações não são iguais entre configurações.")
    esperado = ordenar_por_f1(resumos)
    esperado = [{k: "" if v is None else str(v) for k,v in r.items()} for r in esperado]
    if ranking != esperado:
        raise ValueError("Ranking diverge das contagens; empates exatos devem compartilhar posição.")


def carregar(pasta, *, rodada="round1", quantidade=48, avaliacoes=8544, casos_controle=24,
             validador=validar_plano, saida=None, conferir_extra=None,
             quadros_por_configuracao=178, etapa="desenvolvimento"):
    saida = SAIDA if saida is None else saida
    pasta = Path(pasta).expanduser().resolve(strict=True)
    if not pasta.is_relative_to(RAIZ.resolve()) or pasta.parent != saida.resolve() or not pasta.name.startswith("batch__"):
        raise ValueError(f"Informe um batch de watershed/{rodada}.")
    manifesto_bytes = (pasta / "execucao.json").read_bytes()
    m = carregar_json(manifesto_bytes)
    if (m.get("situacao") != "concluida" or m.get("versao") != 1 or m.get("algoritmo") != "watershed"
            or m.get("rodada") != rodada or m.get("criterios") != CRITERIOS
            or m.get("configuracoes_previstas") != quantidade or m.get("configuracoes_concluidas") != quantidade
            or m.get("quadros_por_configuracao") != quadros_por_configuracao
            or m.get("etapa", "desenvolvimento") != etapa or m.get("avaliacoes_concluidas") != avaliacoes):
        raise ValueError("Rodada incompleta ou incompatível.")
    hashes = {}

    def ler(nome):
        alvo = (pasta / nome).resolve(strict=True)
        if not alvo.is_relative_to(pasta) or not alvo.is_file():
            raise ValueError("Saída fora do batch.")
        b = alvo.read_bytes(); rel = alvo.relative_to(RAIZ).as_posix()
        if m["saidas_sha256"].get(rel) != sha(b):
            raise ValueError(f"Saída alterada ou sem hash: {nome}.")
        hashes[rel] = sha(b)
        return b

    pbytes = ler("plano.json")
    p = validador(carregar_json(pbytes))
    if sha(pbytes) != m["plano_sha256"]:
        raise ValueError("Plano alterado.")
    codigo = ler("codigo.zip")
    if sha(codigo) != m["codigo"]["sha256_zip"]:
        raise ValueError("Arquivo de código alterado.")
    with ZipFile(BytesIO(codigo)) as z:
        if (len(z.namelist()) != len(m["codigo"]["sha256_arquivos"])
                or {n:sha(z.read(n)) for n in z.namelist()} != m["codigo"]["sha256_arquivos"]):
            raise ValueError("Conteúdo do arquivo de código divergente.")
    for nome, origem in p["origens"].items():
        if sha(ler("origens/"+nome)) != origem["sha256"]:
            raise ValueError("Cópia de origem alterada.")
    resumos, quadros, videos, ranking = [_csv(ler(n)) for n in
        ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv", "ranking.csv")]
    conferir_tabelas(p, resumos, quadros, videos, ranking)
    por_id = {r["configuracao_id"]:r for r in resumos}
    execucoes = m["execucoes"]
    if [x["configuracao_id"] for x in execucoes] != [i["id"] for i in p["configuracoes"]]:
        raise ValueError("Manifesto não contém as configurações do plano.")
    pastas = {}
    for item, execucao in zip(p["configuracoes"], execucoes):
        destino = (RAIZ / execucao["pasta"]).resolve(strict=True)
        if destino.parent != pasta or por_id[item["id"]]["pasta_origem"] != execucao["pasta"]:
            raise ValueError("Pasta de configuração incompatível.")
        rel = destino.relative_to(pasta).as_posix(); pastas[item["id"]] = rel
        if carregar_json(ler(rel+"/configuracao.json")) != item["parametros"]:
            raise ValueError("Configuração salva diverge do plano.")
        agregado = colunas_metricas(carregar_json(ler(rel+"/avaliacao.json")))
        if any(por_id[item["id"]][k] != ("" if v is None else str(v)) for k,v in agregado.items()):
            raise ValueError("Avaliação agregada diverge do resumo.")
    controles = carregar_json(ler("controles.json"))
    esperados = {}
    for f in p["fontes_controles"]:
        chave = f["configuracao_id"],f["video_id"],f["quadro"]
        nome = f"{pastas[chave[0]]}/quadros/{chave[1]}_frame_{chave[2]}/{f['nome']}"
        if sha(ler(nome)) != f["sha256"] or sha(ler("origens/"+f["copia"])) != f["sha256"]:
            raise ValueError("Controle não reproduzido ou referência alterada.")
        esperados.setdefault(chave, {})[f["nome"]] = f["sha256"]
    if controles["casos_conferidos"] != casos_controle or len(controles["casos"]) != casos_controle:
        raise ValueError("Conferência dos controles incompleta.")
    obtidos = {(r["configuracao_id"],r["video_id"],r["quadro"]):r["sha256"] for r in controles["casos"]
               if r["situacao"] == "identico"}
    if obtidos != esperados:
        raise ValueError("Registro de controles divergente.")
    if conferir_extra is not None:
        conferir_extra(p, quadros, ler, pastas)
    return {"pasta":pasta, "plano":p, "manifesto":m, "manifesto_sha256":sha(manifesto_bytes),
            "resumos":resumos, "quadros":quadros, "videos":videos, "ranking":ranking, "hashes":hashes,
            "controles":controles}


def escrever_pdf(caminho, dados, *, pagina_extra=None):
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas
    c = Canvas(str(caminho), pagesize=landscape(A4))
    rodada = dados["plano"]["rodada"]
    round2 = rodada in ("round2", "round3", "round4", "round5")
    referencia = {"round1": "round0", "round2": "round1", "round3": "round2", "round4": "round3", "round5": "round4"}[rodada]
    controles = [i["id"] for i in dados["plano"]["configuracoes"] if i["bloco"] == "controle"]
    casos_controle = len(dados["plano"]["fontes_controles"]) // 4
    quantidade = len(dados["plano"]["configuracoes"])
    paginas = 5 if round2 else 4
    c.setTitle(f"Watershed | Desenvolvimento {rodada}"); c.setAuthor("Projeto de detecção em microscopia")
    largura, altura = landscape(A4)
    azul, cinza = HexColor("#157a91"), HexColor("#263d4a")
    ranking = dados["ranking"]; melhores = ranking[:10]
    itens = {r["id"]:r for r in dados["plano"]["configuracoes"]}
    resumos = {r["configuracao_id"]:r for r in dados["resumos"]}

    def texto(x,y,t,tam=9,bold=False,cor=cinza):
        c.setFillColor(cor); c.setFont("Helvetica-Bold" if bold else "Helvetica",tam)
        c.drawString(x,y,str(t))

    def inicio(titulo,pagina):
        c.setFillColor(HexColor("#edf4f7")); c.rect(0,altura-82,largura,82,fill=1,stroke=0)
        texto(30,altura-25,f"WATERSHED | DESENVOLVIMENTO {rodada.upper()}",10,True)
        texto(30,altura-51,titulo,20,True)
        aval = f"{quantidade*178:,}".replace(",", ".")
        texto(30,altura-71,f"{quantidade} configurações | 178 imagens | 12 vídeos de origem | {aval} avaliações | seed 42",9)
        texto(30,20,"Desenvolvimento: resultados descritivos. A seleção de finalistas ocorre em outra partição.",8)
        texto(largura-48,20,f"{pagina}/{paginas}",8)

    def valor(v):
        precisao = 6 if rodada in ("round3", "round4", "round5") else 3
        return "s/c" if v in (None,"") else f"{float(v):.{precisao}f}".replace(".",",")

    def cabecalho(xs,nomes,y=487):
        for x,n in zip(xs,nomes): texto(x,y,n,8,True)

    inicio("Localização de indivíduos: visão geral",1)
    xs = [30,83,235,290,366,440,510,585,660,739]
    cabecalho(xs,["Pos. / ID","F1 indivíduos","F1","Precisão","Recall","TP","FP","FN","F1 aglom.","ms/img"])
    for i,r in enumerate(melhores):
        y=462-i*24
        texto(30,y,f"{r['posicao']} {r['configuracao_id']}",8,True)
        c.setFillColor(HexColor("#e8eef1")); c.rect(93,y-2,125,10,fill=1,stroke=0)
        c.setFillColor(azul); c.rect(93,y-2,125*float(r["f1_individuos"] or 0),10,fill=1,stroke=0)
        vals=[valor(r[k]) for k in ("f1_individuos","precisao_individuos","recall_individuos")]
        vals += [r[k] for k in ("tp_individuos","fp_individuos","fn_individuos")]
        vals += [valor(r["f1_aglomerados"]),f"{int(r['tempo_detector_ns'])/int(r['quantidade_quadros'])/1e6:.1f}"]
        for x,v in zip(xs[2:],vals): texto(x,y,v,9)
    valores = sorted(float(r["f1_individuos"]) for r in ranking if r["f1_individuos"] not in (None,""))
    texto(30,204,"Distribuição do F1 entre as configurações testadas",12,True)
    if valores:
        q1,med,q3 = statistics.quantiles(valores,n=4,method="inclusive") if len(valores)>1 else [valores[0]]*3
        for x,n,v in zip([30,187,344,501,658],["Mínimo","Q1","Mediana","Q3","Máximo"],[min(valores),q1,med,q3,max(valores)]):
            c.setFillColor(HexColor("#edf4f7"));c.rect(x,134,142,53,fill=1,stroke=0)
            texto(x+10,170,n,9);texto(x+10,146,valor(v),17,True)
    texto(30,114,f"{len(valores)}/{quantidade} F1 definidos. Quartis interpolados; configurações não são amostras independentes.")
    texto(30,96,"F1 = 2TP/(2TP+FP+FN), após somar os 178 quadros. IoU >= 0,50; correspondência exclusiva.")
    texto(30,78,"Classes 0 e 2 agrupadas; aglomerados separados. Erros 0/2 são registrados sem retirar o acerto de localização.")
    texto(30,60,"s/c = sem casos (TP=FP=FN=0). Empates exatos mantêm posição; ID organiza apenas a exibição.")
    texto(30,42,"Tempo: somente detector e diagnósticos internos; exclui leitura, avaliação, imagens, tabelas e PDF.",8)
    c.showPage()

    inicio("Variação por vídeo e cobertura das classes",2)
    vids=sorted({r["video_id"] for r in dados["videos"]},key=int)
    por_video={(r["configuracao_id"],r["video_id"]):r for r in dados["videos"]}
    texto(30,487,"F1 por vídeo de origem: mesmas dez configurações da página anterior",10,True)
    for j,v in enumerate(vids):texto(114+j*56,466,v,9,True)
    for i,r in enumerate(melhores):
        y=445-i*18;texto(30,y,r["configuracao_id"],9,True)
        for j,v in enumerate(vids):
            f=por_video[r["configuracao_id"],v]["f1_individuos"];n=float(f or 0)
            c.setFillColor(Color(.93-.85*n,.96-.48*n,.97-.40*n));c.rect(103+j*56,y-4,52,17,fill=1,stroke=0)
            texto(114+j*56,y,valor(f),8,cor=HexColor("#ffffff") if n>.65 else cinza)
    texto(30,259,"Escala de 0 (claro) a 1 (escuro). Vídeo 23: 13 quadros; demais: 15. Contagens somadas em cada vídeo.",8)
    xs=[30,130,253,376,499,619,728]
    cabecalho(xs,["ID","Cobertura 0","Cobertura 2","Cobertura 1","Erros 0/2","Acurácia cond.","F1 aglom."],231)
    for i,r in enumerate(melhores):
        vals=[r["configuracao_id"],*[f"{r[f'localizadas_classe_{k}']}/{r[f'anotacoes_classe_{k}']}" for k in (0,2,1)],
              f"{r['pares_incorretos']}/{r['pares_total']}",valor(r["acuracia_condicional"]),valor(r["f1_aglomerados"])]
        for x,v in zip(xs,vals):texto(x,210-i*15,v,9)
    texto(30,49,"Cobertura = localizados/anotados. Acurácia condicional avalia classe somente nos indivíduos localizados.",8)
    texto(30,35,"Quadros de um mesmo vídeo são correlacionados. Esta página não constitui teste de significância.",8)
    c.showPage()

    inicio("Todas as configurações: ranking da rodada",3)
    por_coluna = (quantidade + 1) // 2
    for metade in range(2):
        x0=30+metade*399
        xs=[x0,x0+40,x0+89,x0+141,x0+178,x0+218,x0+259,x0+300,x0+345]
        cabecalho(xs,["Pos.","ID","Ajuste" if round2 else "Limiar","Fec." if round2 else "Pol.","Regra","Sem.","Mín.","Agl.","F1"])
        for j,r in enumerate(ranking[metade*por_coluna:(metade+1)*por_coluna]):
            params=itens[r["configuracao_id"]]["parametros"]
            p=params["watershed"] if round2 else params;s=p["segmentacao"]
            vals=[r["posicao"],r["configuracao_id"],f"{params['deslocamento_otsu']:+d}" if round2 else ("Otsu" if s["metodo"]=="otsu" else s["limiar_manual"]),
                  s["fechamento"]["tamanho"] if round2 else ("C" if s["polaridade"]=="claro" else "E"),"P" if p["politica_aglomerados"]=="preservar_por_area" else "S",
                  p["fracao_semente"],s["area_minima"],s["classificacao"]["area_minima_aglomerado"],valor(r["f1_individuos"])]
            y=466-j*(20 if round2 else 15)
            if j%2==0:
                c.setFillColor(HexColor("#f0f5f7"));c.rect(x0-3,y-4,387,15,fill=1,stroke=0)
            for x,v in zip(xs,vals):texto(x,y,"s/c" if v in (None,"") else v,8)
    texto(30,94,("Ajuste = deslocamento de Otsu; Fec. = fechamento retangular. " if round2 else "Pol.: C = claro; E = escuro. ") +
          "Regra: S = separar; P = preservar. Sem. = fração da semente.",8)
    texto(30,77,"Mín. = área mínima aceita; Agl. = área mínima para aglomerado (px²). Máximo 5.000; pequeno até 120; conexão 8.")
    texto(30,60,f"Parâmetros completos: plano.json e configuracao.json. {controles[0]} a {controles[-1]} são controles.")
    texto(30,43,"Classificação 0/2 não desempata este ranking. Posição não representa seleção para vídeo.",8)
    c.showPage()

    inicio("Políticas de aglomerados: contrastes em pares",4)
    xs=[30,71,156,242,323,405,489,565,642,728]
    cabecalho(xs,["Par","Separar","Preservar","F1 sep.","F1 pres.","Delta F1","Delta TP","Delta FP","Delta FN","Delta TP ag."])
    pares=defaultdict(list)
    for item in dados["plano"]["configuracoes"]:pares[item["par_id"]].append(item)
    for i,(par,it) in enumerate(pares.items()):
        s,p=sorted(it,key=lambda x:(x["parametros"]["watershed"] if round2 else x["parametros"])["politica_aglomerados"]!="separar")
        a,b=resumos[s["id"]],resumos[p["id"]]
        casas_delta = 6 if rodada in ("round4", "round5") else 3
        delta="s/c" if any(x["f1_individuos"] in (None,"") for x in (a,b)) else f"{float(b['f1_individuos'])-float(a['f1_individuos']):+.{casas_delta}f}"
        vals=[par,s["id"],p["id"],valor(a["f1_individuos"]),valor(b["f1_individuos"]),delta,
              *[f"{int(b[k])-int(a[k]):+d}" for k in ("tp_individuos","fp_individuos","fn_individuos","tp_aglomerados")]]
        for x,v in zip(xs,vals):texto(x,465-i*(21 if round2 else 15),v,8)
    texto(30,91,"Delta = preservar menos separar; cada par mantém todos os demais parâmetros e os mesmos 178 quadros.")
    texto(30,74,f"Controles: {dados['controles']['casos_conferidos']}/{casos_controle} casos idênticos ao {referencia} em caixas, detecções, avaliações e diagnósticos.",8)
    texto(30,57,"PDF confere tabelas, agregações, parâmetros, código arquivado e controles; não reavalia imagens nem todas as mídias.",8)
    texto(30,40,"Contrastes não garantem melhoria em vídeos reservados; a escolha final continua em outra partição." if round2 else
          "A busca manual varia vários eixos em conjunto: seus efeitos individuais não podem ser atribuídos isoladamente.",8)
    if round2:
        c.showPage()
        if pagina_extra is None:
            from analise.relatorio_round2_watershed import pagina_otsu
            pagina_extra = pagina_otsu
        pagina_extra(dados, texto, inicio, cabecalho, valor)
    c.save()
    return paginas


def gerar_relatorio(pasta, *, carregador=None, codigo_relatorio=None, pagina_extra=None):
    dados=(carregar if carregador is None else carregador)(pasta);pasta=dados["pasta"]
    destino=pasta/"relatorios"/agora().strftime("%Y%m%dT%H%M%S%fZ")
    destino.mkdir(parents=True,exist_ok=False)
    pdf=destino/"relatorio.pdf"
    paginas=escrever_pdf(pdf,dados,pagina_extra=pagina_extra)
    import reportlab
    registro={"situacao":"concluida","paginas":paginas,"pdf_sha256":sha(pdf.read_bytes()),
              "manifesto_sha256":dados["manifesto_sha256"],"fontes_sha256":dados["hashes"],
              "codigo_relatorio_sha256":sha(Path(__file__).read_bytes()),"reportlab":reportlab.Version,
              "criterios":CRITERIOS,"ordenacao":"F1 exato de indivíduos; empates compartilham posição",
              "escopo_conferencia":f"fontes do PDF e {dados['controles']['casos_conferidos']} controles; mídias restantes não relidas"}
    if codigo_relatorio is not None:
        registro["codigo_relatorio_adicional_sha256"] = sha(Path(codigo_relatorio).read_bytes())
    gravar_json(destino/"relatorio.json",registro)
    gravar_json(pasta/"relatorio.json",{"situacao":"concluido","arquivo":pdf.relative_to(RAIZ).as_posix()})
    return pdf
