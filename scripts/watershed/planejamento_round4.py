"""Refinamento aprovado após o round3, com controles e origens congeladas."""

from copy import deepcopy
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, POLITICAS, bytes_json, sha
from scripts.watershed.planejamento_round3 import validar_plano as validar_round3

ARQUIVO = "scripts/watershed/planejamento_round4.py"
ROUND3 = "resultados/frame-to-frame/watershed/round3/batch__20260921T174126692210Z"
MANIFESTO_SHA256 = "783125bf502da7ce435d83a81d5c8dbf511f7b8f43488307d7c1896ba98508d8"
PLANO_ORIGEM_SHA256 = "1bd149c34ceac32257afd1ee34769401c00f8635ba9b3bab0f27c5f3b6aa5aca"
REFERENCIAS_SHA256 = "9956f07432f121e11f13f171bb98a8c4f41190ddcfacf1bf445dba7add1519fe"
QUADROS_SHA256 = "5e530be0f85828a448ce8507743d48e3b0fd5f84a7a537bdd4452a490fcea0b3"
CONTROLES = ("r3c01", "r3c02", "r3c17", "r3c18", "r3c21", "r3c22")


def gerar_configuracoes(referencias, seed=42):
    if type(seed) is not int or seed != 42 or hash_configuracao(referencias) != REFERENCIAS_SHA256:
        raise ValueError("Referências ou seed diferentes do desenho do round4.")
    configs = []

    def adicionar(p, bloco, objetivo, controle=None, contraste=None):
        configs.append({"id": f"r4c{len(configs)+1:02}", "par_id": f"p{len(configs)//2+1:02}",
                        "bloco": bloco, "objetivo": objetivo, "referencia_round3": controle,
                        "contraste_com": contraste, "parametros": deepcopy(p),
                        "parametros_sha256": hash_configuracao(p)})

    for r in referencias:
        adicionar(r["parametros"], "controle", "Reproduzir os 178 quadros da referência do round3.", controle=r["id"])

    def par(bloco, *, delta=-5, minimo=120, semente=.35, fechamento=5):
        for i, politica in enumerate(POLITICAS):
            p = deepcopy(referencias[2]["parametros"])
            s = p["watershed"]["segmentacao"]
            s["area_minima"] = minimo
            s["fechamento"]["tamanho"] = fechamento
            p["watershed"].update(fracao_semente=semente, politica_aglomerados=politica)
            p["deslocamento_otsu"] = delta
            adicionar(p, bloco, f"Contraste de {bloco} com Otsu -5 como referência; demais parâmetros fixos.",
                      contraste=f"r4c{3+i:02}")

    for delta in (-3, -7):
        par("deslocamento_otsu", delta=delta)
    for minimo in (132, 144):
        par("area", minimo=minimo)
    par("semente", semente=.50)
    par("fechamento", fechamento=3)
    return configs


def validar_plano(p):
    from algoritmos.classicos.variantes_watershed import configuracao_de_dict
    fixos = {"versao": 1, "algoritmo": "watershed", "rodada": "round4", "etapa": "desenvolvimento",
             "particao": "desenvolvimento", "seed": 42, "criterios": CRITERIOS,
             "configuracoes_previstas": 18, "quadros_por_configuracao": 178,
             "avaliacoes_previstas": 3204, "controles_previstos": 6}
    if any(p.get(k) != v or type(p.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Plano incompatível com o round4.")
    if p["configuracoes"] != gerar_configuracoes(p["referencias_round3"], p["seed"]):
        raise ValueError("Configurações diferem do refinamento declarado.")
    if hash_configuracao({k: p[k] for k in ("quadros", "exclusoes")}) != QUADROS_SHA256:
        raise ValueError("Os 178 quadros e as exclusões devem ser preservados.")
    if len({c["parametros_sha256"] for c in p["configuracoes"]}) != 18:
        raise ValueError("Configurações repetidas no round4.")
    for c in p["configuracoes"]:
        configuracao_de_dict(c["parametros"])
    for nome, digest in (("round3_execucao.json", MANIFESTO_SHA256), ("round3_plano.json", PLANO_ORIGEM_SHA256)):
        if p["origens"][nome]["sha256"] != digest:
            raise ValueError("Origem histórica diferente.")
    esperados = {(c["id"], q["video_id"], q["quadro"], n)
                 for c in p["configuracoes"][:6] for q in p["quadros"] for n in ARQUIVOS_CONTROLE}
    fontes = p["fontes_controles"]
    if len(fontes) != 4272 or {(f["configuracao_id"], f["video_id"], f["quadro"], f["nome"])
                             for f in fontes} != esperados:
        raise ValueError("Referências dos 1.068 casos de controle incompletas.")
    for f in fontes:
        if (f["copia"] != f"controles/{f['configuracao_id']}/{f['video_id']}_frame_{f['quadro']}/{f['nome']}"
                or len(f["sha256"]) != 64):
            raise ValueError("Referência de controle inválida.")
    return p


def conferir_origens(p, origens):
    for nome, ref in p["origens"].items():
        if sha(origens[nome]) != ref["sha256"]:
            raise ValueError(f"Origem alterada: {nome}.")
    m3 = carregar_json(origens["round3_execucao.json"])
    p3 = validar_round3(carregar_json(origens["round3_plano.json"]))
    if (m3["situacao"] != "concluida" or m3["avaliacoes_concluidas"] != 4272
            or m3["configuracoes_concluidas"] != 24 or m3["criterios"] != CRITERIOS
            or m3["plano_sha256"] != sha(origens["round3_plano.json"])
            or m3["codigo"]["sha256_zip"] != sha(origens["round3_codigo.zip"])):
        raise ValueError("Round3 de referência incompleto ou incompatível.")
    for nome in ("round1_plano.json", "round2_plano.json"):
        if sha(origens[nome]) != p3["origens"][nome]["sha256"]:
            raise ValueError(f"Plano histórico alterado: {nome}.")
    estatisticas = carregar_json(origens["estatisticas_round3.json"])
    if estatisticas["manifesto_sha256"] != sha(origens["round3_execucao.json"]) or estatisticas["situacao"] != "conferida":
        raise ValueError("Análise não corresponde à referência conferida.")
    por_id = {c["id"]: c for c in p3["configuracoes"]}
    refs = [{"id": i, "parametros": por_id[i]["parametros"]} for i in CONTROLES]
    if p["referencias_round3"] != refs or p["quadros"] != p3["quadros"] or p["exclusoes"] != p3["exclusoes"]:
        raise ValueError("Referências ou quadros diferem do round3.")
    p1, p2 = (carregar_json(origens[n]) for n in ("round1_plano.json", "round2_plano.json"))
    conhecidos = {hash_configuracao({"watershed": c["parametros"], "deslocamento_otsu": 0}) for c in p1["configuracoes"]}
    conhecidos.update(c["parametros_sha256"] for base in (p2, p3) for c in base["configuracoes"])
    if sum(c["parametros_sha256"] in conhecidos for c in p["configuracoes"]) != 6:
        raise ValueError("O round4 deve incluir seis controles e 12 configurações novas.")
    pastas = {r["configuracao_id"]: r["pasta"] for r in m3["execucoes"]}
    controles = {c["id"]: c for c in p["configuracoes"][:6]}
    for f in p["fontes_controles"]:
        ref = controles[f["configuracao_id"]]["referencia_round3"]
        nome = f"{pastas[ref]}/quadros/{f['video_id']}_frame_{f['quadro']}/{f['nome']}"
        if f["arquivo"] != nome or f["sha256"] != m3["saidas_sha256"].get(nome):
            raise ValueError("Controle difere do manifesto histórico do round3.")
    return m3


def construir_plano(raiz=RAIZ):
    caminhos = {"round3_plano.json": ROUND3 + "/plano.json", "round3_execucao.json": ROUND3 + "/execucao.json",
                "round3_codigo.zip": ROUND3 + "/codigo.zip", "round2_plano.json": ROUND3 + "/origens/round2_plano.json",
                "round1_plano.json": ROUND3 + "/origens/round1_plano.json",
                "estatisticas_round3.json": "analise/estatisticas_round3_watershed.json"}
    blobs = {n: (raiz / f).read_bytes() for n, f in caminhos.items()}
    p3, m3 = (carregar_json(blobs[n]) for n in ("round3_plano.json", "round3_execucao.json"))
    por_id = {c["id"]: c for c in p3["configuracoes"]}
    refs = [{"id": i, "parametros": deepcopy(por_id[i]["parametros"])} for i in CONTROLES]
    configs = gerar_configuracoes(refs)
    pastas = {r["configuracao_id"]: r["pasta"] for r in m3["execucoes"]}
    fontes = []
    for item in configs[:6]:
        for q in p3["quadros"]:
            quadro = f"{q['video_id']}_frame_{q['quadro']}"
            for nome in ARQUIVOS_CONTROLE:
                arquivo = f"{pastas[item['referencia_round3']]}/quadros/{quadro}/{nome}"
                fontes.append({"configuracao_id": item["id"], "video_id": q["video_id"], "quadro": q["quadro"],
                               "nome": nome, "arquivo": arquivo, "sha256": m3["saidas_sha256"][arquivo],
                               "copia": f"controles/{item['id']}/{quadro}/{nome}"})
    p = {"versao": 1, "algoritmo": "watershed", "rodada": "round4", "etapa": "desenvolvimento",
         "particao": "desenvolvimento", "seed": 42, "uso_seed": "Grade dirigida determinística, sem sorteio.",
         "criterios": deepcopy(CRITERIOS), "configuracoes_previstas": 18, "quadros_por_configuracao": 178,
         "avaliacoes_previstas": 3204, "controles_previstos": 6, "referencias_round3": refs,
         "configuracoes": configs, "quadros": deepcopy(p3["quadros"]), "exclusoes": deepcopy(p3["exclusoes"]),
         "fontes_controles": fontes, "geracao": {"arquivo": ARQUIVO, "sha256": sha((raiz / ARQUIVO).read_bytes()), "versao": "1.0"},
         "origens": {n: {"arquivo": f, "sha256": sha(blobs[n])} for n, f in caminhos.items()}}
    validar_plano(p)
    conferir_origens(p, blobs)
    return p


if __name__ == "__main__":
    alvo = RAIZ / "scripts/watershed/rodadas/round4.json"
    conteudo = bytes_json(construir_plano())
    if alvo.exists():
        if alvo.read_bytes() != conteudo:
            raise SystemExit("Plano existente diferente; não será sobrescrito.")
        print("Plano existente reproduzido exatamente.")
    else:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("xb") as f:
            f.write(conteudo)
        print("Round4 preparado: 18 configurações, 178 quadros, 3.204 avaliações.")
