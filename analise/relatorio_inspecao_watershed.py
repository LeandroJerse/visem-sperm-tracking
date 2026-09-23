"""PDF de diagnóstico do round0, gerado exclusivamente dos resultados salvos."""

from pathlib import Path

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_inspecao_blobs import CONTAGENS, _conferir_metricas, _csv, _json
from scripts.blobs.arquivos import gravar_json
from scripts.limiarizacao.inspecionar_imagem import agora, sha256

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round0"
DIAGNOSTICO = ("componentes", "sementes", "componentes_preservados", "regioes_candidatas",
              "deteccoes", "rejeitadas_area", "tempo_detector_ns")


def carregar(pasta):
    pasta = Path(pasta).resolve(strict=True)
    if pasta.parent != SAIDA.resolve() or not pasta.name.startswith("batch__"):
        raise ValueError("Informe um batch de watershed/round0.")
    m = _json((pasta / "execucao.json").read_bytes())
    if (m.get("situacao") != "concluida" or m.get("algoritmo") != "watershed"
            or m.get("rodada") != "round0" or m.get("criterios") != CRITERIOS
            or m.get("configuracoes_concluidas") != 8 or m.get("avaliacoes_concluidas") != 48):
        raise ValueError("Inspeção incompleta ou incompatível.")
    hashes = m.get("saidas_sha256", {})
    for nome, esperado in hashes.items():
        arquivo = (RAIZ / nome).resolve(strict=True)
        if not arquivo.is_relative_to(pasta) or sha256(arquivo.read_bytes()) != esperado:
            raise ValueError(f"Saída divergente: {nome}.")
    for nome in ("plano.json", "resumo_configuracoes.csv", "resumo_por_quadro.csv"):
        if (pasta / nome).relative_to(RAIZ).as_posix() not in hashes:
            raise ValueError(f"Saída não registrada: {nome}.")
    plano = _json((pasta / "plano.json").read_bytes())
    if sha256((pasta / "plano.json").read_bytes()) != m["plano_sha256"]:
        raise ValueError("Plano alterado.")
    ids = [c["id"] for c in plano["configuracoes"]]
    resumos = _csv((pasta / "resumo_configuracoes.csv").read_bytes())
    quadros = _csv((pasta / "resumo_por_quadro.csv").read_bytes())
    if ids != [f"w{i:02}" for i in range(1, 9)] or [r["configuracao_id"] for r in resumos] != ids or len(quadros) != 48:
        raise ValueError("Composição incompleta.")
    esperado = {(q["video_id"], str(q["quadro"])) for q in plano["quadros"]}
    if len(esperado) != 6:
        raise ValueError("A inspeção precisa de seis quadros distintos.")
    for r in resumos + quadros:
        _conferir_metricas(r)
        for k in DIAGNOSTICO:
            if int(r[k]) < 0:
                raise ValueError("Contagem negativa.")
        if int(r["deteccoes"]) + int(r["rejeitadas_area"]) != int(r["regioes_candidatas"]):
            raise ValueError("Candidatos não reconciliam.")
    for r in resumos:
        linhas = [q for q in quadros if q["configuracao_id"] == r["configuracao_id"]]
        if len(linhas) != 6 or {(q["video_id"], q["quadro"]) for q in linhas} != esperado or int(r["quantidade_quadros"]) != 6:
            raise ValueError("Quadros ausentes ou repetidos.")
        for k in (*CONTAGENS, *DIAGNOSTICO):
            if int(r[k]) != sum(int(q[k]) for q in linhas):
                raise ValueError(f"Agregação divergente: {k}.")
    return {"pasta": pasta, "manifesto": m, "plano": plano, "resumos": resumos, "quadros": quadros}


def escrever_pdf(caminho, dados):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas
    c = Canvas(str(caminho), pagesize=landscape(A4))
    c.setTitle("Watershed - inspeção round0")
    c.setAuthor("")
    largura, altura = landscape(A4)
    azul, cinza = colors.HexColor("#157a91"), colors.HexColor("#263d4a")

    def texto(x, y, t, tam=10, bold=False):
        c.setFillColor(cinza); c.setFont("Helvetica-Bold" if bold else "Helvetica", tam)
        c.drawString(x, y, str(t))

    def inicio(titulo, pagina):
        c.setFillColor(colors.HexColor("#edf4f7")); c.rect(0, altura-82, largura, 82, fill=1, stroke=0)
        texto(30, altura-25, "WATERSHED | INSPEÇÃO ROUND0", 10, True)
        texto(30, altura-51, titulo, 20, True)
        texto(30, altura-71, "8 configurações | 6 imagens de desenvolvimento | 48 avaliações | sem ranking", 9)
        texto(30, 20, "Diagnóstico inicial. As seis imagens não estimam o desempenho geral. Sem seleção de finalistas.", 8)
        texto(largura-48, 20, f"{pagina}/2", 8)

    def valor(v):
        return "sem casos" if v in (None, "") else f"{float(v):.3f}".replace(".", ",")

    inicio("Localização e classificação", 1)
    xs = [30, 270, 340, 410, 480, 560, 640, 730]
    for x, h in zip(xs, ["Configuração / F1", "Precisão", "Recall", "TP", "FP", "FN", "Cob. 2", "F1 aglom."]):
        texto(x, 489, h, 9, True)
    for i, r in enumerate(dados["resumos"]):
        y = 462 - i*26
        texto(30, y, r["configuracao_id"], 10, True)
        f1 = r["f1_individuos"]
        c.setFillColor(azul); c.rect(70, y-2, 130*float(f1 or 0), 11, fill=1, stroke=0)
        texto(207, y, valor(f1), 9)
        for x, campo in zip(xs[1:], ["precisao_individuos", "recall_individuos", "tp_individuos", "fp_individuos",
                                   "fn_individuos", "recall_classe_2", "f1_aglomerados"]):
            texto(x, y, r[campo] if campo.startswith(("tp_", "fp_", "fn_")) else valor(r[campo]), 9)
    texto(30, 243, "F1 de indivíduos em cada imagem", 12, True)
    quadros = dados["plano"]["quadros"]
    for i, q in enumerate(quadros):
        texto(155+i*100, 221, f"{q['video_id']}/{q['quadro']}", 9, True)
    for i, r in enumerate(dados["resumos"]):
        y=202-i*17
        texto(30, y, r["configuracao_id"], 9)
        por_q = {(x["video_id"], int(x["quadro"])): x for x in dados["quadros"] if x["configuracao_id"] == r["configuracao_id"]}
        for j, q in enumerate(quadros):
            texto(155+j*100, y, valor(por_q[q["video_id"], q["quadro"]]["f1_individuos"]), 9)
    texto(30, 57, "IoU >= 0,50; pares exclusivos. Classes 0/2 juntas; classe 1 separada. Contagens somadas antes do F1.", 9)
    texto(30, 42, "Trocas 0/2 ficam registradas em pares.csv e na matriz de classificação dos resumos.", 9)
    c.showPage()
    inicio("Parâmetros e diagnóstico da segmentação", 2)
    xs = [30, 88, 165, 225, 358, 445, 525, 625, 726]
    for x, h in zip(xs, ["ID", "Polaridade", "Semente", "Política", "Comp.", "Sementes", "Preservados", "Candidatos", "Aceitos"]):
        texto(x, 489, h, 8, True)
    for i, (item, r) in enumerate(zip(dados["plano"]["configuracoes"], dados["resumos"])):
        p=item["parametros"]; y=465-i*25
        vals=[item["id"], p["segmentacao"]["polaridade"], p["fracao_semente"],
              "preservar por área" if p["politica_aglomerados"] == "preservar_por_area" else "separar",
              r["componentes"], r["sementes"], r["componentes_preservados"], r["regioes_candidatas"], r["deteccoes"]]
        for x, v in zip(xs, vals): texto(x,y,v,9)
    texto(30, 257, "Cobertura por classe e classificação dos indivíduos localizados", 12, True)
    xs2=[30,145,265,385,510,670]
    for x,h in zip(xs2,["ID", "Cobertura 0", "Cobertura 2", "Cobertura 1", "Erros 0/2", "Acurácia cond."]):texto(x,235,h,9,True)
    for i,r in enumerate(dados["resumos"]):
        vals=[r["configuracao_id"],valor(r["recall_classe_0"]),valor(r["recall_classe_2"]),valor(r["recall_classe_1"]),
              f"{r['pares_incorretos']}/{r['pares_total']}",valor(r["acuracia_condicional"])]
        for x,v in zip(xs2,vals):texto(x,216-i*17,v,9)
    texto(30, 65, "Caixas envolvem os pixels de cada região. Preservar reúne o componente e não mantém seus filhos.", 9)
    texto(30, 50, "Veja comparacao.png, mascara.png, regioes_sementes.png e diagnostico.json em cada pasta de quadro.", 9)
    texto(30, 35, "Sementes brancas; cores das regiões identificam segmentos, não classes. Mapas numéricos em mapas.npz.", 9)
    c.save()
    return 2


def gerar_relatorio(pasta):
    dados = carregar(pasta)
    pasta = dados["pasta"]
    destino = pasta / "relatorios" / agora().strftime("%Y%m%dT%H%M%S%fZ")
    destino.mkdir(parents=True, exist_ok=False)
    pdf = destino / "relatorio.pdf"
    paginas = escrever_pdf(pdf, dados)
    registro = {"situacao": "concluida", "paginas": paginas, "pdf_sha256": sha256(pdf.read_bytes()),
                "manifesto_sha256": sha256((pasta / "execucao.json").read_bytes()),
                "codigo_relatorio_sha256": sha256(Path(__file__).read_bytes()),
                "criterios": CRITERIOS, "ordenacao": "ordem do plano, sem ranking"}
    gravar_json(destino / "relatorio.json", registro)
    gravar_json(pasta / "relatorio.json", {"situacao": "concluido", "arquivo": pdf.relative_to(RAIZ).as_posix()})
    return pdf
