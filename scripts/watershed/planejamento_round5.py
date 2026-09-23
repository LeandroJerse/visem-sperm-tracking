"""Refinamento aprovado após o round4, com controles e origens congeladas."""

from copy import deepcopy
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, POLITICAS, bytes_json, sha
from scripts.watershed.planejamento_round4 import validar_plano as validar_round4

ARQUIVO = "scripts/watershed/planejamento_round5.py"
ROUND4 = "resultados/frame-to-frame/watershed/round4/batch__20260921T184319705365Z"
MANIFESTO_SHA256 = "7cf41808e23347cbee1b43a3d79a115fe190b65461526fdb1f431276f0a275d7"
PLANO_ORIGEM_SHA256 = "8030f5ce1e1a591e0e85bd29105b40af1dc922693d0af942cf6f76fbd839daf3"
REFERENCIAS_SHA256 = "19baeff9f1c18b57b2944464846425bcf174abafd5d59368e2acb6edd9f078d4"
QUADROS_SHA256 = "5e530be0f85828a448ce8507743d48e3b0fd5f84a7a537bdd4452a490fcea0b3"
CONTROLES = ("r4c15", "r4c16", "r4c07", "r4c08", "r4c17", "r4c18")


def gerar_configuracoes(referencias, seed=42):
    if type(seed) is not int or seed != 42 or hash_configuracao(referencias) != REFERENCIAS_SHA256:
        raise ValueError("Referências ou seed diferentes do desenho do round5.")
    configs = []

    def adicionar(p, bloco, objetivo, controle=None, contraste=None):
        configs.append({"id": f"r5c{len(configs)+1:02}", "par_id": f"p{len(configs)//2+1:02}",
                        "bloco": bloco, "objetivo": objetivo, "referencia_round4": controle,
                        "contraste_com": contraste, "parametros": deepcopy(p),
                        "parametros_sha256": hash_configuracao(p)})

    for r in referencias:
        adicionar(r["parametros"], "controle", "Reproduzir os 178 quadros da referência do round4.", controle=r["id"])

    def par(bloco, objetivo, *, delta=-5, minimo=120, fechamento=5, referencia=1):
        for i, politica in enumerate(POLITICAS):
            p = deepcopy(referencias[0]["parametros"])
            s = p["watershed"]["segmentacao"]
            s["area_minima"] = minimo
            s["fechamento"]["tamanho"] = fechamento
            p["watershed"].update(fracao_semente=.50, politica_aglomerados=politica)
            p["deslocamento_otsu"] = delta
            adicionar(p, bloco, objetivo, contraste=f"r5c{referencia+i:02}")

    par("deslocamento_otsu", "Combinar Otsu -3 com semente 0,50.", delta=-3)
    par("fechamento", "Combinar fechamento 3 com semente 0,50.", fechamento=3)
    par("fechamento", "Combinar os três ajustes; comparar fechamento contra r5c07/r5c08.",
        delta=-3, fechamento=3, referencia=7)
    par("area", "Verificar o filtro de área 144 com semente 0,50.", minimo=144)
    return configs


def gerar_contrastes():
    """Comparações de um único parâmetro, em cada política de aglomerados."""
    pares = [(1, 7, "deslocamento_otsu"), (3, 7, "semente"),
             (1, 9, "fechamento"), (5, 9, "semente"),
             (7, 11, "fechamento"), (9, 11, "deslocamento_otsu"),
             (1, 13, "area")]
    return [{"referencia": f"r5c{a+i:02}", "nova": f"r5c{b+i:02}", "eixo": eixo}
            for a, b, eixo in pares for i in range(2)]


def validar_plano(p):
    from algoritmos.classicos.variantes_watershed import configuracao_de_dict
    fixos = {"versao": 1, "algoritmo": "watershed", "rodada": "round5", "etapa": "desenvolvimento",
             "particao": "desenvolvimento", "seed": 42, "criterios": CRITERIOS,
             "configuracoes_previstas": 14, "quadros_por_configuracao": 178,
             "avaliacoes_previstas": 2492, "controles_previstos": 6}
    if any(p.get(k) != v or type(p.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Plano incompatível com o round5.")
    if p["configuracoes"] != gerar_configuracoes(p["referencias_round4"], p["seed"]):
        raise ValueError("Configurações diferem do refinamento declarado.")
    if p.get("contrastes") != gerar_contrastes():
        raise ValueError("Contrastes diferem das comparações de um parâmetro aprovadas.")
    if hash_configuracao({k: p[k] for k in ("quadros", "exclusoes")}) != QUADROS_SHA256:
        raise ValueError("Os 178 quadros e as exclusões devem ser preservados.")
    if len({c["parametros_sha256"] for c in p["configuracoes"]}) != 14:
        raise ValueError("Configurações repetidas no round5.")
    for c in p["configuracoes"]:
        configuracao_de_dict(c["parametros"])
    for nome, digest in (("round4_execucao.json", MANIFESTO_SHA256), ("round4_plano.json", PLANO_ORIGEM_SHA256)):
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
    m4 = carregar_json(origens["round4_execucao.json"])
    p4 = validar_round4(carregar_json(origens["round4_plano.json"]))
    if (m4["situacao"] != "concluida" or m4["avaliacoes_concluidas"] != 3204
            or m4["configuracoes_concluidas"] != 18 or m4["criterios"] != CRITERIOS
            or m4["plano_sha256"] != sha(origens["round4_plano.json"])
            or m4["codigo"]["sha256_zip"] != sha(origens["round4_codigo.zip"])):
        raise ValueError("Round4 de referência incompleto ou incompatível.")
    for nome in ("round1_plano.json", "round2_plano.json", "round3_plano.json"):
        if sha(origens[nome]) != p4["origens"][nome]["sha256"]:
            raise ValueError(f"Plano histórico alterado: {nome}.")
    estatisticas = carregar_json(origens["estatisticas_round4.json"])
    if estatisticas["manifesto_sha256"] != sha(origens["round4_execucao.json"]) or estatisticas["situacao"] != "conferida":
        raise ValueError("Análise não corresponde à referência conferida.")
    por_id = {c["id"]: c for c in p4["configuracoes"]}
    refs = [{"id": i, "parametros": por_id[i]["parametros"]} for i in CONTROLES]
    if p["referencias_round4"] != refs or p["quadros"] != p4["quadros"] or p["exclusoes"] != p4["exclusoes"]:
        raise ValueError("Referências ou quadros diferem do round4.")
    p1, p2 = (carregar_json(origens[n]) for n in ("round1_plano.json", "round2_plano.json"))
    conhecidos = {hash_configuracao({"watershed": c["parametros"], "deslocamento_otsu": 0}) for c in p1["configuracoes"]}
    p3 = carregar_json(origens["round3_plano.json"])
    conhecidos.update(c["parametros_sha256"] for base in (p2, p3, p4) for c in base["configuracoes"])
    if sum(c["parametros_sha256"] in conhecidos for c in p["configuracoes"]) != 6:
        raise ValueError("O round5 deve incluir seis controles e oito configurações novas.")
    pastas = {r["configuracao_id"]: r["pasta"] for r in m4["execucoes"]}
    controles = {c["id"]: c for c in p["configuracoes"][:6]}
    for f in p["fontes_controles"]:
        ref = controles[f["configuracao_id"]]["referencia_round4"]
        nome = f"{pastas[ref]}/quadros/{f['video_id']}_frame_{f['quadro']}/{f['nome']}"
        if f["arquivo"] != nome or f["sha256"] != m4["saidas_sha256"].get(nome):
            raise ValueError("Controle difere do manifesto histórico do round4.")
    return m4


def construir_plano(raiz=RAIZ):
    caminhos = {"round4_plano.json": ROUND4 + "/plano.json", "round4_execucao.json": ROUND4 + "/execucao.json",
                "round4_codigo.zip": ROUND4 + "/codigo.zip", "round2_plano.json": ROUND4 + "/origens/round2_plano.json",
                "round1_plano.json": ROUND4 + "/origens/round1_plano.json",
                "round3_plano.json": ROUND4 + "/origens/round3_plano.json",
                "estatisticas_round4.json": "analise/estatisticas_round4_watershed.json"}
    blobs = {n: (raiz / f).read_bytes() for n, f in caminhos.items()}
    p4, m4 = (carregar_json(blobs[n]) for n in ("round4_plano.json", "round4_execucao.json"))
    por_id = {c["id"]: c for c in p4["configuracoes"]}
    refs = [{"id": i, "parametros": deepcopy(por_id[i]["parametros"])} for i in CONTROLES]
    configs = gerar_configuracoes(refs)
    pastas = {r["configuracao_id"]: r["pasta"] for r in m4["execucoes"]}
    fontes = []
    for item in configs[:6]:
        for q in p4["quadros"]:
            quadro = f"{q['video_id']}_frame_{q['quadro']}"
            for nome in ARQUIVOS_CONTROLE:
                arquivo = f"{pastas[item['referencia_round4']]}/quadros/{quadro}/{nome}"
                fontes.append({"configuracao_id": item["id"], "video_id": q["video_id"], "quadro": q["quadro"],
                               "nome": nome, "arquivo": arquivo, "sha256": m4["saidas_sha256"][arquivo],
                               "copia": f"controles/{item['id']}/{quadro}/{nome}"})
    p = {"versao": 1, "algoritmo": "watershed", "rodada": "round5", "etapa": "desenvolvimento",
         "particao": "desenvolvimento", "seed": 42, "uso_seed": "Grade dirigida determinística, sem sorteio.",
         "criterios": deepcopy(CRITERIOS), "configuracoes_previstas": 14, "quadros_por_configuracao": 178,
         "avaliacoes_previstas": 2492, "controles_previstos": 6, "referencias_round4": refs,
         "contrastes": gerar_contrastes(), "configuracoes": configs, "quadros": deepcopy(p4["quadros"]), "exclusoes": deepcopy(p4["exclusoes"]),
         "fontes_controles": fontes, "geracao": {"arquivo": ARQUIVO, "sha256": sha((raiz / ARQUIVO).read_bytes()), "versao": "1.0"},
         "origens": {n: {"arquivo": f, "sha256": sha(blobs[n])} for n, f in caminhos.items()}}
    validar_plano(p)
    conferir_origens(p, blobs)
    return p


if __name__ == "__main__":
    alvo = RAIZ / "scripts/watershed/rodadas/round5.json"
    conteudo = bytes_json(construir_plano())
    if alvo.exists():
        if alvo.read_bytes() != conteudo:
            raise SystemExit("Plano existente diferente; não será sobrescrito.")
        print("Plano existente reproduzido exatamente.")
    else:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("xb") as f:
            f.write(conteudo)
        print("Round5 preparado: 14 configurações, 178 quadros, 2.492 avaliações.")
