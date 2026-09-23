"""Congela a proposta aprovada do round2, sem executar imagens."""

from copy import deepcopy
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.watershed.planejamento import ARQUIVOS_CONTROLE, bytes_json, sha

ARQUIVO = "scripts/watershed/planejamento_round2.py"
PROPOSTA = "analise/proposta_round2_watershed.json"
PROPOSTA_SHA256 = "b5447b81186264624d65b04d15ce36c0387228bd05ef95c83fbf16c21aa85afc"
DESENHO_SHA256 = "32d80207638a0ec51afe257a250040fa2a942d8e9b242d078588b89a36e9ce28"
ROUND1 = "resultados/frame-to-frame/watershed/round1/batch__20260921T143759308685Z"
MANIFESTO_SHA256 = "2ce386aadf306f6415489cbb6edb1a0b916908647f090b4a457d84c4f5772e9e"


def configuracoes(proposta):
    return [{"id": x["id"], "par_id": x["par_id"], "bloco": x["bloco"], "objetivo": x["hipotese"],
             "referencia_round1": x["referencia_round1"],
             "parametros": {"watershed": deepcopy(x["parametros_watershed"]),
                            "deslocamento_otsu": x["deslocamento_otsu"]},
             "parametros_sha256": x["configuracao_sha256"]} for x in proposta["configuracoes"]]


def validar_plano(p):
    from algoritmos.classicos.variantes_watershed import configuracao_de_dict
    fixos = {"versao": 1, "algoritmo": "watershed", "rodada": "round2", "etapa": "desenvolvimento",
             "particao": "desenvolvimento", "seed": 42, "criterios": CRITERIOS,
             "configuracoes_previstas": 32, "quadros_por_configuracao": 178, "avaliacoes_previstas": 5696}
    if any(p.get(k) != v or type(p.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Plano incompatível com o round2 aprovado.")
    desenho = {k: p[k] for k in ("configuracoes", "quadros", "exclusoes", "criterios")}
    if sha(json.dumps(desenho, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")) != DESENHO_SHA256:
        raise ValueError("Configurações, imagens ou critérios diferem da proposta aprovada.")
    for item in p["configuracoes"]:
        configuracao_de_dict(item["parametros"])
        if hash_configuracao(item["parametros"]) != item["parametros_sha256"]:
            raise ValueError("Hash de configuração inválido.")
    if p["origens"]["proposta.json"]["sha256"] != PROPOSTA_SHA256:
        raise ValueError("Proposta de origem diferente.")
    if p["origens"]["round1_execucao.json"]["sha256"] != MANIFESTO_SHA256:
        raise ValueError("Manifesto do round1 diferente.")
    fontes = p["fontes_controles"]
    esperado = {(c["id"], q["video_id"], q["quadro"], n)
                for c in p["configuracoes"][:4] for q in p["quadros"] for n in ARQUIVOS_CONTROLE}
    if len(fontes) != 2848 or {(f["configuracao_id"], f["video_id"], f["quadro"], f["nome"])
                             for f in fontes} != esperado:
        raise ValueError("São necessários 712 casos de controle, com quatro arquivos cada.")
    for f in fontes:
        copia = f"controles/{f['configuracao_id']}/{f['video_id']}_frame_{f['quadro']}/{f['nome']}"
        if f["copia"] != copia or len(f["sha256"]) != 64:
            raise ValueError("Referência de controle inválida.")
    return p


def conferir_origens(p, origens):
    """Vincula os controles aos hashes registrados na execução histórica."""
    for nome, ref in p["origens"].items():
        if sha(origens[nome]) != ref["sha256"]:
            raise ValueError(f"Origem alterada: {nome}.")
    proposta = carregar_json(origens["proposta.json"])
    m1 = carregar_json(origens["round1_execucao.json"])
    p1 = carregar_json(origens["round1_plano.json"])
    if (m1["situacao"] != "concluida" or m1["avaliacoes_concluidas"] != 8544
            or m1["criterios"] != CRITERIOS or m1["plano_sha256"] != sha(origens["round1_plano.json"])
            or m1["codigo"]["sha256_zip"] != sha(origens["round1_codigo.zip"])):
        raise ValueError("Round1 incompleto ou incompatível.")
    if p["configuracoes"] != configuracoes(proposta) or p["quadros"] != p1["quadros"] or p["exclusoes"] != p1["exclusoes"]:
        raise ValueError("Plano não preserva a proposta e os quadros do round1.")
    refs = {c["id"]: c for c in p1["configuracoes"]}
    pastas = {r["configuracao_id"]: r["pasta"] for r in m1["execucoes"]}
    controles = {c["id"]: c for c in p["configuracoes"][:4]}
    for c in controles.values():
        if c["parametros"] != {"watershed": refs[c["referencia_round1"]]["parametros"], "deslocamento_otsu": 0}:
            raise ValueError("Parâmetros do controle divergem do round1.")
    for f in p["fontes_controles"]:
        ref = controles[f["configuracao_id"]]["referencia_round1"]
        nome = f"{pastas[ref]}/quadros/{f['video_id']}_frame_{f['quadro']}/{f['nome']}"
        if f["arquivo"] != nome or f["sha256"] != m1["saidas_sha256"].get(nome):
            raise ValueError("Controle não corresponde ao manifesto histórico.")
    return m1


def construir_plano(raiz=RAIZ):
    fontes = {"proposta.json": PROPOSTA, "round1_plano.json": ROUND1 + "/plano.json",
              "round1_execucao.json": ROUND1 + "/execucao.json", "round1_codigo.zip": ROUND1 + "/codigo.zip"}
    blobs = {n: (raiz / f).read_bytes() for n, f in fontes.items()}
    proposta = carregar_json(blobs["proposta.json"])
    m1 = carregar_json(blobs["round1_execucao.json"])
    configs = configuracoes(proposta)
    pastas = {r["configuracao_id"]: r["pasta"] for r in m1["execucoes"]}
    controles = []
    for item in configs[:4]:
        for q in proposta["quadros"]:
            quadro = f"{q['video_id']}_frame_{q['quadro']}"
            for nome in ARQUIVOS_CONTROLE:
                arquivo = f"{pastas[item['referencia_round1']]}/quadros/{quadro}/{nome}"
                controles.append({"configuracao_id": item["id"], "video_id": q["video_id"], "quadro": q["quadro"],
                                  "nome": nome, "arquivo": arquivo, "sha256": m1["saidas_sha256"][arquivo],
                                  "copia": f"controles/{item['id']}/{quadro}/{nome}"})
    p = {"versao": 1, "algoritmo": "watershed", "rodada": "round2", "etapa": "desenvolvimento",
         "particao": "desenvolvimento", "seed": 42, "uso_seed": "Grade dirigida determinística, sem sorteio.",
         "criterios": deepcopy(CRITERIOS), "configuracoes_previstas": 32, "quadros_por_configuracao": 178,
         "avaliacoes_previstas": 5696, "configuracoes": configs, "quadros": deepcopy(proposta["quadros"]),
         "exclusoes": deepcopy(proposta["exclusoes"]), "fontes_controles": controles,
         "geracao": {"arquivo": ARQUIVO, "sha256": sha((raiz / ARQUIVO).read_bytes()), "versao": "1.0"},
         "origens": {n: {"arquivo": f, "sha256": sha(blobs[n])} for n, f in fontes.items()}}
    validar_plano(p)
    conferir_origens(p, blobs)
    return p


if __name__ == "__main__":
    alvo = RAIZ / "scripts/watershed/rodadas/round2.json"
    conteudo = bytes_json(construir_plano())
    if alvo.exists():
        if alvo.read_bytes() != conteudo:
            raise SystemExit("Plano existente diferente; não será sobrescrito.")
        print("Plano existente reproduzido exatamente.")
    else:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("xb") as f:
            f.write(conteudo)
        print("Round2 preparado: 32 configurações, 178 quadros, 5.696 avaliações.")
