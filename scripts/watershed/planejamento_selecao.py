"""Catálogo completo e reproduzível de watershed nas imagens de seleção."""

from collections import Counter
from copy import deepcopy
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import ZipFile

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao
from scripts.watershed.planejamento import bytes_json, sha

ARQUIVO = "scripts/watershed/planejamento_selecao.py"
PLANO = RAIZ / "scripts/watershed/selecao/plano.json"
VIDEOS = ("13", "29", "52", "54")
ORDEM_QUADROS = [(v, q) for v in VIDEOS for q in range(0, 1401, 100)]
QUANTIDADES = (48, 32, 24, 18, 14)
BATCHES = ("20260921T143759308685Z", "20260921T161513364669Z", "20260921T174126692210Z",
           "20260921T184319705365Z", "20260921T193215730860Z")
MANIFESTOS = (
    "2ce386aadf306f6415489cbb6edb1a0b916908647f090b4a457d84c4f5772e9e",
    "3c80035a54d010ee5edd218bdeaf0c2a790ab6c4fff700a5cf6c9929509a4b15",
    "783125bf502da7ce435d83a81d5c8dbf511f7b8f43488307d7c1896ba98508d8",
    "7cf41808e23347cbee1b43a3d79a115fe190b65461526fdb1f431276f0a275d7",
    "d46bf807874537c579054ba92f6d2240e2cc743f0773bdbe242dcf92800d410e")
PLANOS = (
    "d5d2b177ae32e805e557cffe43756ccfb64014699b59e5649c97a50383144884",
    "a9653774b39e29d84c95430ca5e921ec3203de8880c861c3e52e02450dc873e8",
    "1bd149c34ceac32257afd1ee34769401c00f8635ba9b3bab0f27c5f3b6aa5aca",
    "8030f5ce1e1a591e0e85bd29105b40af1dc922693d0af942cf6f76fbd839daf3",
    "8b6cf62be5b286f9c21e7262bfe23ae64a696d240f176d8e8645fedafe081d9b")
QUADROS_ORIGEM = "scripts/limiarizacao/selecao/plano.json"
QUADROS_ORIGEM_SHA = "20bacd6e77cc704db33f9b5525d6a8040b7987854130584ff1c9e7cb65a2980a"
ANALISE = "analise/estatisticas_round5_watershed.json"
ANALISE_SHA = "72cd1217562a0e04cdf189fbf4721f51286c733635129e65b85b5c1ecddbeaf9"
CATALOGO_SHA = "7a2c9e885f6b799433e2500e6c412199705f3970941006a2d0cb0995e95d7988"
QUADROS_SHA = "2582cd9d6bf5cf5d0574234a0fa2614b113f48225c420386afe9ec8855d3cd7e"


def igual(a, b, contexto):
    if hash_configuracao(a) != hash_configuracao(b):
        raise ValueError(f"Valor incompatível: {contexto}.")


def caminho_interno(nome):
    if not isinstance(nome, str):
        raise ValueError("Caminho deve ser texto.")
    p = PurePosixPath(nome)
    if not isinstance(nome, str) or "\\" in nome or ":" in nome or p.is_absolute() or ".." in p.parts or p.as_posix() != nome:
        raise ValueError("Caminho deve ser relativo e interno ao projeto.")


def ler(raiz, nome, digest=None):
    caminho_interno(nome)
    path = (raiz / nome).resolve(strict=True)
    if not path.is_relative_to(raiz.resolve()) or not path.is_file():
        raise ValueError("Origem fora do projeto.")
    blob = path.read_bytes()
    if digest is not None and sha(blob) != digest:
        raise ValueError(f"Origem alterada: {nome}.")
    return blob


def normalizar(parametros, numero):
    # Otsu original e Otsu com deslocamento zero têm a mesma implementação.
    return ({"watershed": deepcopy(parametros), "deslocamento_otsu": 0}
            if numero == 1 else deepcopy(parametros))


def ler_configuracao(parametros):
    from algoritmos.classicos.watershed import configuracao_de_dict as original
    from algoritmos.classicos.variantes_watershed import configuracao_de_dict as variante
    if not isinstance(parametros, dict) or set(parametros) != {"watershed", "deslocamento_otsu"}:
        raise ValueError("Parâmetros de seleção inválidos.")
    if parametros["watershed"]["segmentacao"]["metodo"] == "manual":
        igual(parametros["deslocamento_otsu"], 0, "manual não recebe deslocamento Otsu")
        return original(parametros["watershed"])
    return variante(parametros)


def catalogo(planos, manifestos):
    itens, por_hash = [], {}
    for numero, (plano, manifesto) in enumerate(zip(planos, manifestos), 1):
        execucoes = manifesto["execucoes"]
        igual([x["configuracao_id"] for x in execucoes], [c["id"] for c in plano["configuracoes"]], "execuções de origem")
        for c, e in zip(plano["configuracoes"], execucoes):
            parametros = normalizar(c["parametros"], numero)
            digest = hash_configuracao(parametros)
            if digest not in por_hash:
                item = {"id": f"s{len(itens)+1:03}", "bloco": "selecao",
                        "parametros": parametros, "parametros_sha256": digest, "origens": []}
                itens.append(item); por_hash[digest] = item
            arquivo = e["pasta"] + "/configuracao.json"
            por_hash[digest]["origens"].append({"rodada": f"round{numero}", "configuracao_id": c["id"],
                "pasta": e["pasta"], "arquivo": arquivo, "sha256": manifesto["saidas_sha256"][arquivo],
                "copia": f"round{numero}/configuracoes/{c['id']}.json"})
    return itens


def quadros_referencia(blob):
    p = carregar_json(blob)
    for k, v in {"algoritmo":"limiarizacao", "rodada":"selecao", "particao":"selecao",
                 "seed":42, "exclusoes":[], "politica_anotacoes_ausentes":"erro"}.items():
        igual(p[k], v, "origem das imagens")
    return [{k:q[k] for k in ("video_id","quadro","imagem","anotacao")} |
            {"imagem_sha256":q["sha256_imagem"], "anotacao_sha256":q["sha256_anotacao"]} for q in p["quadros"]]


def validar_plano(p):
    fixos = {"versao":1, "algoritmo":"watershed", "rodada":"selecao", "etapa":"selecao_imagens",
             "particao":"selecao", "seed":42, "criterios":CRITERIOS, "configuracoes_previstas":114,
             "quadros_por_configuracao":60, "avaliacoes_previstas":6840, "fontes_controles":[],
             "exclusoes":[], "politica_anotacoes_ausentes":"erro", "selecao_automatica":False}
    for k, v in fixos.items(): igual(p.get(k), v, k)
    igual(hash_configuracao(p["configuracoes"]), CATALOGO_SHA, "catálogo congelado")
    igual(hash_configuracao(p["quadros"]), QUADROS_SHA, "60 quadros congelados")
    igual([(q["video_id"],q["quadro"]) for q in p["quadros"]], ORDEM_QUADROS, "ordem dos quadros")
    igual([c["id"] for c in p["configuracoes"]], [f"s{i:03}" for i in range(1,115)], "IDs")
    if len({c["parametros_sha256"] for c in p["configuracoes"]}) != 114:
        raise ValueError("Catálogo com repetições.")
    for c in p["configuracoes"]:
        igual(hash_configuracao(c["parametros"]), c["parametros_sha256"], "hash da configuração")
        ler_configuracao(c["parametros"])
    if sum(len(c["origens"]) for c in p["configuracoes"]) != 136:
        raise ValueError("Proveniência incompleta.")
    esperados = {"quadros_selecao.json", "analise_round5.json"}
    for n in range(1,6):
        esperados.update(f"round{n}_{s}" for s in ("plano.json","execucao.json","codigo.zip"))
        igual(p["origens"][f"round{n}_execucao.json"]["sha256"], MANIFESTOS[n-1], "manifesto histórico")
        igual(p["origens"][f"round{n}_plano.json"]["sha256"], PLANOS[n-1], "plano histórico")
    esperados.update(o["copia"] for c in p["configuracoes"] for o in c["origens"])
    if set(p["origens"]) != esperados:
        raise ValueError("Cópias de origem incompletas ou inesperadas.")
    igual(p["origens"]["quadros_selecao.json"], {"arquivo":QUADROS_ORIGEM,"sha256":QUADROS_ORIGEM_SHA}, "origem dos quadros")
    igual(p["origens"]["analise_round5.json"], {"arquivo":ANALISE,"sha256":ANALISE_SHA}, "análise conferida")
    for nome, o in p["origens"].items():
        caminho_interno(nome); caminho_interno(o["arquivo"])
        if re.fullmatch("[0-9a-f]{64}", o["sha256"]) is None:
            raise ValueError("Hash inválido.")
    return p


def conferir_origens(p, origens):
    """Verifica também cópias arquivadas, sem depender da base de imagens."""
    for nome, ref in p["origens"].items():
        igual(sha(origens[nome]), ref["sha256"], f"origem {nome}")
    planos, manifestos = [], []
    for numero, quantidade in enumerate(QUANTIDADES,1):
        plano = carregar_json(origens[f"round{numero}_plano.json"])
        m = carregar_json(origens[f"round{numero}_execucao.json"])
        for k,v in {"situacao":"concluida", "algoritmo":"watershed", "rodada":f"round{numero}",
                    "etapa":"desenvolvimento", "criterios":CRITERIOS, "configuracoes_concluidas":quantidade,
                    "configuracoes_previstas":quantidade, "quadros_por_configuracao":178,
                    "avaliacoes_concluidas":quantidade*178, "plano_sha256":PLANOS[numero-1]}.items():
            igual(m.get(k),v,f"manifesto round{numero}: {k}")
        batch = f"resultados/frame-to-frame/watershed/round{numero}/batch__{BATCHES[numero-1]}"
        for suffix in ("plano.json","execucao.json","codigo.zip"):
            igual(p["origens"][f"round{numero}_{suffix}"]["arquivo"], batch+"/"+suffix, "caminho histórico")
        igual(m["saidas_sha256"][batch+"/plano.json"], PLANOS[numero-1], "plano arquivado")
        codigo = origens[f"round{numero}_codigo.zip"]
        igual(sha(codigo), m["codigo"]["sha256_zip"], "ZIP histórico")
        igual(m["saidas_sha256"][batch+"/codigo.zip"], sha(codigo), "ZIP no manifesto")
        with ZipFile(BytesIO(codigo)) as z:
            if len(z.namelist()) != len(m["codigo"]["sha256_arquivos"]):
                raise ValueError("ZIP histórico incompleto.")
            igual({n:sha(z.read(n)) for n in z.namelist()}, m["codigo"]["sha256_arquivos"], "código histórico")
        igual(m["codigo"]["sha256_arquivos"][plano["geracao"]["arquivo"]], plano["geracao"]["sha256"], "gerador histórico")
        if len(plano["configuracoes"]) != quantidade:
            raise ValueError("Plano histórico incompleto.")
        planos.append(plano); manifestos.append(m)
    igual(p["configuracoes"], catalogo(planos,manifestos), "linhagem das 136 execuções")
    for c in p["configuracoes"]:
        for o in c["origens"]:
            igual(p["origens"][o["copia"]], {"arquivo":o["arquivo"],"sha256":o["sha256"]}, "arquivo de configuração")
            numero = int(o["rodada"].removeprefix("round"))
            salvo = carregar_json(origens[o["copia"]])
            igual(normalizar(salvo,numero), c["parametros"], "parâmetros efetivamente executados")
            batch = f"resultados/frame-to-frame/watershed/{o['rodada']}/batch__{BATCHES[numero-1]}"
            if PurePosixPath(o["pasta"]).parent.as_posix() != batch:
                raise ValueError("Configuração fora do batch de origem.")
    igual(p["quadros"], quadros_referencia(origens["quadros_selecao.json"]), "mesmas imagens da seleção anterior")
    estatisticas = carregar_json(origens["analise_round5.json"])
    igual(estatisticas["situacao"], "conferida", "análise concluída")
    igual(estatisticas["manifesto_sha256"], MANIFESTOS[4], "análise do round5")
    igual(estatisticas["configuracoes_distintas"], 114, "catálogo analisado")
    return manifestos[-1]


def construir_plano(raiz=RAIZ):
    caminhos = {"quadros_selecao.json":QUADROS_ORIGEM, "analise_round5.json":ANALISE}
    blobs = {n:ler(raiz,f) for n,f in caminhos.items()}
    planos, manifestos = [], []
    for numero, instante in enumerate(BATCHES,1):
        batch = f"resultados/frame-to-frame/watershed/round{numero}/batch__{instante}"
        for sufixo in ("plano.json","execucao.json","codigo.zip"):
            n=f"round{numero}_{sufixo}"; caminhos[n]=batch+"/"+sufixo
            blobs[n]=ler(raiz,caminhos[n])
        planos.append(carregar_json(blobs[f"round{numero}_plano.json"]))
        manifestos.append(carregar_json(blobs[f"round{numero}_execucao.json"]))
    configs = catalogo(planos,manifestos)
    for c in configs:
        for o in c["origens"]:
            caminhos[o["copia"]]=o["arquivo"]
            blobs[o["copia"]]=ler(raiz,o["arquivo"],o["sha256"])
    p={"versao":1,"algoritmo":"watershed","rodada":"selecao","etapa":"selecao_imagens","particao":"selecao",
       "seed":42,"uso_seed":"Catálogo determinístico por primeira aparição; nenhum sorteio.",
       "criterios":deepcopy(CRITERIOS),"configuracoes_previstas":114,"quadros_por_configuracao":60,
       "avaliacoes_previstas":6840,"selecao_automatica":False,"politica_anotacoes_ausentes":"erro",
       "quadros":quadros_referencia(blobs["quadros_selecao.json"]),"exclusoes":[],"fontes_controles":[],
       "configuracoes":configs,"geracao":{"arquivo":ARQUIVO,"sha256":sha(ler(raiz,ARQUIVO)),"versao":"1.0"},
       "origens":{n:{"arquivo":f,"sha256":sha(blobs[n])} for n,f in caminhos.items()},
       "observacoes":["Todas as configurações distintas das cinco rodadas, inclusive as de baixo desempenho.",
          "Otsu sem ajuste equivale a deslocamento zero; manual continua manual.",
          "Imagens já utilizadas em outros detectores; não são dados inéditos para a pesquisa.",
          "F1 exato de indivíduos; empates explícitos e revisão conjunta antes dos vídeos.",
          "Sem novos ajustes, repetições de desenvolvimento ou escolha automática das cinco finalistas."]}
    validar_plano(p); conferir_origens(p,blobs)
    return p


if __name__ == "__main__":
    blob=bytes_json(construir_plano())
    if PLANO.exists():
        if PLANO.read_bytes()!=blob: raise SystemExit("Plano existente diferente; não será sobrescrito.")
        print("Plano reproduzido exatamente.")
    else:
        PLANO.parent.mkdir(parents=True,exist_ok=True)
        with PLANO.open("xb") as f: f.write(blob)
        print("Seleção preparada: 114 configurações, 60 imagens, 6.840 avaliações.")
