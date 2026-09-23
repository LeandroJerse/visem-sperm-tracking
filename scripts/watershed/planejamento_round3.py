"""Refinamento dirigido do round3; congela parâmetros e referências salvas."""

from copy import deepcopy
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, POLITICAS, bytes_json, sha
from scripts.watershed.planejamento_round2 import validar_plano as validar_round2

ARQUIVO = "scripts/watershed/planejamento_round3.py"
ROUND2 = "resultados/frame-to-frame/watershed/round2/batch__20260921T161513364669Z"
MANIFESTO_SHA256 = "3c80035a54d010ee5edd218bdeaf0c2a790ab6c4fff700a5cf6c9929509a4b15"
PLANO_ORIGEM_SHA256 = "a9653774b39e29d84c95430ca5e921ec3203de8880c861c3e52e02450dc873e8"
REFERENCIAS_SHA256 = "96b3c41d12b685c1ca7233f8363202b98defa9099c4147b24ed4265a7ba7efb5"
QUADROS_SHA256 = "5e530be0f85828a448ce8507743d48e3b0fd5f84a7a537bdd4452a490fcea0b3"
CONTROLES = ("r2c09", "r2c10", "r2c31", "r2c32", "r2c11", "r2c12")


def gerar_configuracoes(referencias, seed=42):
    if type(seed) is not int or seed != 42 or hash_configuracao(referencias) != REFERENCIAS_SHA256:
        raise ValueError("Referências ou seed diferentes do desenho do round3.")
    configs = []

    def adicionar(p, bloco, objetivo, referencia=None, controle=None):
        configs.append({"id": f"r3c{len(configs)+1:02}", "par_id": f"p{len(configs)//2+1:02}",
                        "bloco": bloco, "objetivo": objetivo, "referencia_round2": controle,
                        "contraste_com": referencia, "parametros": deepcopy(p),
                        "parametros_sha256": hash_configuracao(p)})

    for r in referencias:
        adicionar(r["parametros"], "controle", "Reproduzir os 178 quadros da referência do round2.", controle=r["id"])

    def par(minimo, semente, delta, bloco, referencia):
        for i, politica in enumerate(POLITICAS):
            p = deepcopy(referencias[0]["parametros"])
            p["watershed"]["segmentacao"]["area_minima"] = minimo
            p["watershed"].update(fracao_semente=semente, politica_aglomerados=politica)
            p["deslocamento_otsu"] = delta
            adicionar(p, bloco, f"Contraste de {bloco} contra a referência, com os demais parâmetros fixos.",
                      referencia=f"r3c{referencia+i:02}")

    for semente, ref in ((.35, 1), (.75, 5)):
        for minimo in (108, 132):
            par(minimo, semente, 0, "area", ref)
    par(120, .60, 0, "semente", 3)
    for semente, ref in ((.35, 1), (.75, 5)):
        for delta in (-5, 5):
            par(120, semente, delta, "deslocamento_otsu", ref)
    return configs


def validar_plano(p):
    from algoritmos.classicos.variantes_watershed import configuracao_de_dict
    fixos = {"versao": 1, "algoritmo": "watershed", "rodada": "round3", "etapa": "desenvolvimento",
             "particao": "desenvolvimento", "seed": 42, "criterios": CRITERIOS,
             "configuracoes_previstas": 24, "quadros_por_configuracao": 178,
             "avaliacoes_previstas": 4272, "controles_previstos": 6}
    if any(p.get(k) != v or type(p.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Plano incompatível com o round3.")
    if p["configuracoes"] != gerar_configuracoes(p["referencias_round2"], p["seed"]):
        raise ValueError("Configurações diferem do refinamento declarado.")
    if hash_configuracao({k: p[k] for k in ("quadros", "exclusoes")}) != QUADROS_SHA256:
        raise ValueError("Os 178 quadros e as exclusões devem ser preservados.")
    if len({c["parametros_sha256"] for c in p["configuracoes"]}) != 24:
        raise ValueError("Configurações repetidas no round3.")
    for c in p["configuracoes"]:
        configuracao_de_dict(c["parametros"])
    for nome, digest in (("round2_execucao.json", MANIFESTO_SHA256), ("round2_plano.json", PLANO_ORIGEM_SHA256)):
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
    m2 = carregar_json(origens["round2_execucao.json"])
    p2 = validar_round2(carregar_json(origens["round2_plano.json"]))
    if (m2["situacao"] != "concluida" or m2["avaliacoes_concluidas"] != 5696
            or m2["configuracoes_concluidas"] != 32 or m2["criterios"] != CRITERIOS
            or m2["plano_sha256"] != sha(origens["round2_plano.json"])
            or m2["codigo"]["sha256_zip"] != sha(origens["round2_codigo.zip"])):
        raise ValueError("Round2 de referência incompleto ou incompatível.")
    if sha(origens["round1_plano.json"]) != p2["origens"]["round1_plano.json"]["sha256"]:
        raise ValueError("Plano histórico do round1 alterado.")
    estatisticas = carregar_json(origens["estatisticas_round2.json"])
    if estatisticas["manifesto_sha256"] != sha(origens["round2_execucao.json"]) or estatisticas["situacao"] != "conferida":
        raise ValueError("Análise não corresponde à referência conferida.")
    por_id = {c["id"]: c for c in p2["configuracoes"]}
    refs = [{"id": i, "parametros": por_id[i]["parametros"]} for i in CONTROLES]
    if p["referencias_round2"] != refs or p["quadros"] != p2["quadros"] or p["exclusoes"] != p2["exclusoes"]:
        raise ValueError("Referências ou quadros diferem do round2.")
    p1 = carregar_json(origens["round1_plano.json"])
    conhecidos = {hash_configuracao({"watershed": c["parametros"], "deslocamento_otsu": 0}) for c in p1["configuracoes"]}
    conhecidos.update(c["parametros_sha256"] for c in p2["configuracoes"])
    if sum(c["parametros_sha256"] in conhecidos for c in p["configuracoes"]) != 6:
        raise ValueError("O round3 deve incluir seis controles e 18 configurações novas.")
    pastas = {r["configuracao_id"]: r["pasta"] for r in m2["execucoes"]}
    controles = {c["id"]: c for c in p["configuracoes"][:6]}
    for f in p["fontes_controles"]:
        ref = controles[f["configuracao_id"]]["referencia_round2"]
        nome = f"{pastas[ref]}/quadros/{f['video_id']}_frame_{f['quadro']}/{f['nome']}"
        if f["arquivo"] != nome or f["sha256"] != m2["saidas_sha256"].get(nome):
            raise ValueError("Controle difere do manifesto histórico do round2.")
    return m2


def construir_plano(raiz=RAIZ):
    caminhos = {"round2_plano.json": ROUND2 + "/plano.json", "round2_execucao.json": ROUND2 + "/execucao.json",
                "round2_codigo.zip": ROUND2 + "/codigo.zip", "round1_plano.json": ROUND2 + "/origens/round1_plano.json",
                "estatisticas_round2.json": "analise/estatisticas_round2_watershed.json"}
    blobs = {n: (raiz / f).read_bytes() for n, f in caminhos.items()}
    p2, m2 = (carregar_json(blobs[n]) for n in ("round2_plano.json", "round2_execucao.json"))
    por_id = {c["id"]: c for c in p2["configuracoes"]}
    refs = [{"id": i, "parametros": deepcopy(por_id[i]["parametros"])} for i in CONTROLES]
    configs = gerar_configuracoes(refs)
    pastas = {r["configuracao_id"]: r["pasta"] for r in m2["execucoes"]}
    fontes = []
    for item in configs[:6]:
        for q in p2["quadros"]:
            quadro = f"{q['video_id']}_frame_{q['quadro']}"
            for nome in ARQUIVOS_CONTROLE:
                arquivo = f"{pastas[item['referencia_round2']]}/quadros/{quadro}/{nome}"
                fontes.append({"configuracao_id": item["id"], "video_id": q["video_id"], "quadro": q["quadro"],
                               "nome": nome, "arquivo": arquivo, "sha256": m2["saidas_sha256"][arquivo],
                               "copia": f"controles/{item['id']}/{quadro}/{nome}"})
    p = {"versao": 1, "algoritmo": "watershed", "rodada": "round3", "etapa": "desenvolvimento",
         "particao": "desenvolvimento", "seed": 42, "uso_seed": "Grade dirigida determinística, sem sorteio.",
         "criterios": deepcopy(CRITERIOS), "configuracoes_previstas": 24, "quadros_por_configuracao": 178,
         "avaliacoes_previstas": 4272, "controles_previstos": 6, "referencias_round2": refs,
         "configuracoes": configs, "quadros": deepcopy(p2["quadros"]), "exclusoes": deepcopy(p2["exclusoes"]),
         "fontes_controles": fontes, "geracao": {"arquivo": ARQUIVO, "sha256": sha((raiz / ARQUIVO).read_bytes()), "versao": "1.0"},
         "origens": {n: {"arquivo": f, "sha256": sha(blobs[n])} for n, f in caminhos.items()}}
    validar_plano(p)
    conferir_origens(p, blobs)
    return p


if __name__ == "__main__":
    alvo = RAIZ / "scripts/watershed/rodadas/round3.json"
    conteudo = bytes_json(construir_plano())
    if alvo.exists():
        if alvo.read_bytes() != conteudo:
            raise SystemExit("Plano existente diferente; não será sobrescrito.")
        print("Plano existente reproduzido exatamente.")
    else:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("xb") as f:
            f.write(conteudo)
        print("Round3 preparado: 24 configurações, 178 quadros, 4.272 avaliações.")
