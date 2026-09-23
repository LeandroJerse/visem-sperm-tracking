"""Plano dos cinco watershed aprovados nos vídeos completos de seleção."""

from copy import deepcopy
from io import BytesIO
from pathlib import Path
import sys
from zipfile import ZipFile

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.watershed.planejamento import bytes_json, sha
from scripts.watershed.planejamento_selecao import igual, ler, caminho_interno, ler_configuracao

ARQUIVO = "scripts/watershed/planejamento_videos.py"
PLANO = RAIZ / "scripts/watershed/videos/plano_selecao.json"
BATCH = "resultados/frame-to-frame/watershed/selecao/batch__20260921T203527246803Z"
IDS = ("s063", "s064", "s061", "s062", "s098")
PARAMETROS = (
    "459234c1d83ca96fe5a61b0edb02421329da0ec30b030400eada1f1900210a53",
    "cb7798f2dd6598af52c7625d936287b94c4ee75a0d5aae1f939303b6015b9760",
    "b818926eb25d4f1df30a0c5efb5a48644c7fbd3bc1ce49e6e2e5a6f68e240760",
    "dc030f88063c859c54e3475bfe4668d78659dc0bd9f48150e37eb591d7d43a90",
    "cf93e2b008c749100166a87eb8067a2429d1d024343a811155c5976941f2dc04",
)
FIXAS = {
    "origem_videos_limiarizacao": ("scripts/limiarizacao/videos/plano_selecao.json",
        "ea797b01681b943e7a1f4c2442fe3cb2215e66d4425d4a23dd0af6bd3c784122"),
    "origem_selecao": (BATCH + "/plano.json", "53306bf1fdefbae9d28b3cad24f001b8801f7c4d48b4790b92ecf308567592e6"),
    "execucao_selecao": (BATCH + "/execucao.json", "812ae98e41e9734a3bd3dc65d1ef7aeab6bcb1ecd47070a5bd4fd7d3278f5aba"),
    "codigo_selecao": (BATCH + "/codigo.zip", "b3a253f16b1ba4c5f931ffa64b17db03f7655f7cda4245c7d1a46aed10b6bd61"),
    "estatisticas_selecao": ("analise/estatisticas_selecao_watershed.json",
        "b3ecc9bf1efeae333cd18b69dcd77805cb2c49e72215d9801a5842911b782fef"),
    "ranking_selecao": (BATCH + "/ranking.csv", "1014dacbfda470ffad5db41e0d645ba4977a94447dcce6942fd538cf0b920b80"),
    "resumo_configuracoes_selecao": (BATCH + "/resumo_configuracoes.csv",
        "186a21e21d2a0b16ab6e53fb5a7b61a014bba3c1ab99dfc6abe88f23cb34e697"),
    "resumo_por_video_selecao": (BATCH + "/resumo_por_video.csv",
        "4b2ce7c69cb089afef524b2449057a9f84f14af49ae5e7323b625bda55d86747"),
    "resumo_por_quadro_selecao": (BATCH + "/resumo_por_quadro.csv",
        "1bdc8fe4ac4f9342bea4669350b541d78f1661fcdbf928748a2256267428c200"),
}
FIXOS = {"versao": 1, "algoritmo": "watershed", "tipo": "videos_selecao_watershed",
         "etapa": "selecao_videos", "particao": "selecao", "seed": 42,
         "criterios": CRITERIOS, "politica_anotacoes_ausentes": "erro"}
DECISAO = "O pesquisador aprovou s063, s064, s061, s062 e s098, nesta ordem, para vídeos completos de seleção."
VIDEOS_SHA = "a0c26dfd241f34861f74bbe20e379765e1b7aafc769f3422c68fa78899026ec6"
GERACAO = {"arquivo": ARQUIVO, "configuracoes": 5, "videos": 4, "quadros_por_configuracao": 5850,
           "avaliacoes": 29250, "aleatoriedade_utilizada": False}
REGRAS = [
    "Conservar parâmetros, caixas, classes e critérios da seleção em imagens, sem nova busca.",
    "Vídeos 13, 29, 52 e 54 completos: 5.850 quadros por configuração e 29.250 avaliações.",
    "Conferir alinhamento MAE antes de detectar; todas as configurações recebem os mesmos pixels.",
    "Somar TP, FP e FN para calcular F1 de indivíduos 0/2; classificar incorretamente 0/2 não desfaz a localização.",
    "Avaliar aglomerados separadamente; manter cobertura por classe, erros 0/2 e empates explícitos.",
    "Anotação ausente interrompe; anotação existente vazia é válida. Nenhum deslocamento temporal automático.",
    "Áreas segmentadas, caixas, centroides e índice/FPS são medidas por quadro, sem identidade persistente ou velocidade.",
    "Os mesmos vídeos forneceram as imagens de seleção; esta etapa amplia a cobertura temporal, sem independência estatística.",
    "Vídeos finais 14, 24, 38 e 82 serão preparados após revisão conjunta desta etapa. O histórico de exposição é preservado.",
    "Execução pelo pesquisador; guardar codigo.zip, origens e plano. Seed sozinha não garante reprodução.",
]


def caminhos_origens(plano):
    return {n: f["arquivo"] for n, f in plano["proveniencia"]["fontes"].items()}


def validar_plano(p):
    if set(p) != set(FIXOS) | {"configuracoes", "videos", "alinhamento", "proveniencia", "geracao", "regras"}:
        raise ValueError("Campos inesperados no plano de vídeos.")
    for k, v in FIXOS.items():
        igual(p[k], v, k)
    igual(p["regras"], REGRAS, "regras congeladas")
    igual(hash_configuracao(p["videos"]), VIDEOS_SHA, "todos os vídeos, anotações e referências")
    igual([c["id"] for c in p["configuracoes"]], list(IDS), "cinco IDs aprovadas e ordem")
    for c, digest in zip(p["configuracoes"], PARAMETROS):
        igual(c["parametros_sha256"], digest, "identidade aprovada")
        igual(hash_configuracao(c["parametros"]), digest, "parâmetros congelados")
        ler_configuracao(c["parametros"])
    prov = p["proveniencia"]
    igual(prov["decisao"], DECISAO, "aprovação posterior à auditoria")
    igual(prov["ids_aprovados"], list(IDS), "aprovação")
    igual(prov["configuracoes_congeladas"], True, "parâmetros congelados")
    fontes = prov["fontes"]
    if set(fontes) != set(FIXAS) | {f"{t}_{i}" for i in IDS for t in ("configuracao", "avaliacao")}:
        raise ValueError("Proveniência deve conter as 19 fontes.")
    for n, f in fontes.items():
        caminho_interno(f["arquivo"])
        if not isinstance(f["sha256"], str) or len(f["sha256"]) != 64 or any(x not in "0123456789abcdef" for x in f["sha256"]):
            raise ValueError("SHA256 inválido.")
        if n in FIXAS:
            igual(f, dict(zip(("arquivo", "sha256"), FIXAS[n])), "fonte auditada")
    for k, v in GERACAO.items():
        igual(p["geracao"][k], v, "geração")
    return p


def carregar_plano(blob):
    return validar_plano(carregar_json(blob))


def conferir_documentos(p, documentos):
    """Verifica cópias arquivadas sem depender das antigas pastas de resultados."""
    validar_plano(p)
    fontes = p["proveniencia"]["fontes"]
    igual(sorted(documentos), sorted(fontes), "cópias de origem")
    for n, blob in documentos.items():
        igual(sha(blob), fontes[n]["sha256"], "hash da origem " + n)
    m = carregar_json(documentos["execucao_selecao"])
    for k, v in {"situacao": "concluida", "configuracoes_concluidas": 114,
                 "avaliacoes_concluidas": 6840, "quadros_por_configuracao": 60,
                 "plano_sha256": FIXAS["origem_selecao"][1], "criterios": CRITERIOS}.items():
        igual(m[k], v, "seleção concluída")
    anterior = carregar_json(documentos["origem_selecao"])
    por_id = {c["id"]: c for c in anterior["configuracoes"]}
    pastas = {e["configuracao_id"]: e["pasta"] for e in m["execucoes"]}
    for c in p["configuracoes"]:
        igual(c, por_id[c["id"]], "configuração e linhagem da seleção")
        igual(carregar_json(documentos["configuracao_" + c["id"]]), c["parametros"], "parâmetros executados")
        for t in ("configuracao", "avaliacao"):
            f = fontes[f"{t}_{c['id']}"]
            igual(f["arquivo"], pastas[c["id"]] + "/" + t + ".json", "origem da candidata")
            igual(f["sha256"], m["saidas_sha256"][f["arquivo"]], "manifesto de origem")
    geometria = carregar_json(documentos["origem_videos_limiarizacao"])
    igual(p["videos"], geometria["videos"], "vídeos compartilhados")
    igual(p["alinhamento"], geometria["alinhamento"], "alinhamento compartilhado")
    igual(sha(documentos["codigo_selecao"]), m["codigo"]["sha256_zip"], "código de seleção")
    with ZipFile(BytesIO(documentos["codigo_selecao"])) as z:
        igual(sorted(z.namelist()), sorted(m["codigo"]["sha256_arquivos"]), "fontes arquivadas")
        for nome, digest in m["codigo"]["sha256_arquivos"].items():
            igual(sha(z.read(nome)), digest, "código arquivado " + nome)


def conferir_origens(p, raiz):
    documentos = {n: ler(raiz, f["arquivo"], f["sha256"])
                  for n, f in p["proveniencia"]["fontes"].items()}
    conferir_documentos(p, documentos)
    igual(sha(ler(raiz, ARQUIVO)), p["geracao"]["sha256"], "gerador congelado")
    return documentos


def construir_plano(raiz=RAIZ):
    documentos = {n: ler(raiz, path, digest) for n, (path, digest) in FIXAS.items()}
    anterior = carregar_json(documentos["origem_selecao"])
    m = carregar_json(documentos["execucao_selecao"])
    geometria = carregar_json(documentos["origem_videos_limiarizacao"])
    catalogo = {c["id"]: c for c in anterior["configuracoes"]}
    pastas = {e["configuracao_id"]: e["pasta"] for e in m["execucoes"]}
    fontes = {n: {"arquivo": path, "sha256": digest} for n, (path, digest) in FIXAS.items()}
    for i in IDS:
        for t in ("configuracao", "avaliacao"):
            nome, arquivo = f"{t}_{i}", pastas[i] + "/" + t + ".json"
            digest = m["saidas_sha256"][arquivo]
            fontes[nome] = {"arquivo": arquivo, "sha256": digest}
            documentos[nome] = ler(raiz, arquivo, digest)
    p = {**deepcopy(FIXOS), "configuracoes": [deepcopy(catalogo[i]) for i in IDS],
         "videos": deepcopy(geometria["videos"]), "alinhamento": deepcopy(geometria["alinhamento"]),
         "proveniencia": {"decisao": DECISAO, "ids_aprovados": list(IDS),
                          "configuracoes_congeladas": True, "fontes": fontes},
         "geracao": {**GERACAO, "sha256": sha(ler(raiz, ARQUIVO))}, "regras": list(REGRAS)}
    conferir_documentos(p, documentos)
    return p


if __name__ == "__main__":
    blob = bytes_json(construir_plano())
    PLANO.parent.mkdir(parents=True, exist_ok=True)
    if PLANO.exists() and PLANO.read_bytes() != blob:
        raise SystemExit("O plano existente é diferente. Não foi sobrescrito.")
    if not PLANO.exists():
        PLANO.write_bytes(blob)
    print(PLANO)

