"""Desenho reproduzível do round1 de watershed; não executa o detector."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs.executar_inspecao import carregar_json, hash_configuracao

ARQUIVO = "scripts/watershed/planejamento.py"
DESENVOLVIMENTO = "scripts/limiarizacao/rodadas/round1.json"
ROUND0 = "resultados/frame-to-frame/watershed/round0/batch__20260921T135941123246Z"
VIDEOS = ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60")
CHAVES = {(v, q) for v in VIDEOS for q in range(0, 1401, 100)} - {("23", 900), ("23", 1100)}
POLITICAS = ("separar", "preservar_por_area")
ARQUIVOS_CONTROLE = ("predicoes.txt", "deteccoes.csv", "avaliacao.json", "diagnostico.json")
DIAGNOSTICO = ("componentes", "sementes", "componentes_preservados", "regioes_candidatas",
              "deteccoes", "rejeitadas_area", "tempo_detector_ns")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def bytes_json(dados):
    return (json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def gerar_configuracoes(referencias, seed=42):
    """22 bases novas em pares; eixos exploratórios balanceados com seed fixa."""
    if type(seed) is not int or seed != 42:
        raise ValueError("Round1 utiliza seed 42.")
    rng = random.Random(seed)
    configs = []
    for i, referencia in enumerate(referencias, 1):
        p = deepcopy(referencia["parametros"])
        configs.append({"id": f"r1c{i:02}", "bloco": "controle", "par_id": f"p{(i+1)//2:02}",
                        "objetivo": f"Reproduzir {referencia['id']} nos seis quadros comuns ao round0.",
                        "referencia_round0": referencia["id"], "parametros": p,
                        "parametros_sha256": hash_configuracao(p)})
    base = deepcopy(referencias[2]["parametros"])

    def adicionar(p, bloco, objetivo):
        par = f"p{len(configs)//2+1:02}"
        for politica in POLITICAS:
            valores = deepcopy(p); valores["politica_aglomerados"] = politica
            configs.append({"id": f"r1c{len(configs)+1:02}", "bloco": bloco, "par_id": par,
                            "objetivo": objetivo, "referencia_round0": None, "parametros": valores,
                            "parametros_sha256": hash_configuracao(valores)})

    def operacao(tamanho=3, iteracoes=0, forma="elipse"):
        return {"forma": forma, "tamanho": tamanho, "iteracoes": iteracoes}

    # Contrastes locais: somente área mínima ou fração da semente varia.
    for minimo in (12, 24, 48, 72):
        p = deepcopy(base); p["segmentacao"]["area_minima"] = minimo
        adicionar(p, "exploracao_clara", f"Filtro mínimo {minimo} px; comparar com controles de semente 0,75.")
    for fracao in (.35, .9):
        p = deepcopy(base); p["segmentacao"]["area_minima"] = 48; p["fracao_semente"] = fracao
        adicionar(p, "exploracao_clara", "Efeito das sementes com área mínima 48 e máscara fixa.")
    perfis = [
        (operacao(), operacao()),
        (operacao(), operacao(3, 1)),
        (operacao(), operacao(3, 1, "retangulo")),
        (operacao(), operacao(5, 1)),
        (operacao(3, 1), operacao(3, 1)),
        (operacao(3, 1), operacao(5, 1, "retangulo")),
    ]
    for abertura, fechamento in perfis:
        p = deepcopy(base)
        p["segmentacao"].update(area_minima=24, abertura=abertura, fechamento=fechamento)
        adicionar(p, "exploracao_clara", "Explorar morfologia; Otsu, área mínima 24, semente 0,75 e limite 900 fixos.")
    eixos = [[12, 12, 24, 24, 48, 72], [.35, .5, .5, .75, .75, .9],
             [600, 600, 900, 900, 1200, 1200], deepcopy(perfis)]
    for eixo in eixos:
        rng.shuffle(eixo)
    for i, limiar in enumerate((100, 125, 150, 175, 200, 225)):
        p = deepcopy(base)
        p["segmentacao"].update(metodo="manual", limiar_manual=limiar, area_minima=eixos[0][i],
                                abertura=eixos[3][i][0], fechamento=eixos[3][i][1])
        p["fracao_semente"] = eixos[1][i]
        p["segmentacao"]["classificacao"]["area_minima_aglomerado"] = eixos[2][i]
        adicionar(p, "exploracao_clara", "Busca conjunta de limiar manual, morfologia, sementes e limite de aglomerado.")
    escuros = [[3, 12, 24, 48], [.35, .5, .75, .9], [600, 900, 900, 1200],
               [(operacao(), operacao()), (operacao(), operacao(3, 1)),
                (operacao(3, 1), operacao()), (operacao(3, 1), operacao(3, 1))]]
    for eixo in escuros:
        rng.shuffle(eixo)
    for i, limiar in enumerate((40, 60, 80, 100)):
        p = deepcopy(base)
        p["segmentacao"].update(metodo="manual", polaridade="escuro", limiar_manual=limiar,
                                area_minima=escuros[0][i], abertura=escuros[3][i][0], fechamento=escuros[3][i][1])
        p["fracao_semente"] = escuros[1][i]
        p["segmentacao"]["classificacao"]["area_minima_aglomerado"] = escuros[2][i]
        adicionar(p, "exploracao_escura", "Limiar escuro baixo e morfologia moderada para investigar objetos ausentes na máscara clara.")
    return configs


def validar_plano(plano):
    from algoritmos.classicos.watershed import configuracao_de_dict
    fixos = {"versao": 1, "algoritmo": "watershed", "rodada": "round1", "etapa": "desenvolvimento",
             "particao": "desenvolvimento", "seed": 42, "criterios": CRITERIOS,
             "quadros_por_configuracao": 178, "configuracoes_previstas": 48}
    if any(plano.get(k) != v or type(plano.get(k)) is not type(v) for k,v in fixos.items()):
        raise ValueError("Plano incompatível com o round1 aprovado.")
    refs = plano["referencias_round0"]
    if [r["id"] for r in refs] != [f"w{i:02}" for i in range(1,5)]:
        raise ValueError("Controles precisam corresponder a w01 a w04.")
    configs = plano["configuracoes"]
    if configs != gerar_configuracoes(refs, plano["seed"]):
        raise ValueError("Configurações divergem da geração declarada.")
    if len(configs) != 48 or len({c["parametros_sha256"] for c in configs}) != 48:
        raise ValueError("São necessárias 48 configurações distintas.")
    if Counter(c["bloco"] for c in configs) != {"controle":4,"exploracao_clara":36,"exploracao_escura":8}:
        raise ValueError("Orçamento por bloco divergente.")
    for item in configs:
        configuracao_de_dict(item["parametros"])
    quadros = plano["quadros"]
    if len(quadros) != 178 or {(q["video_id"],q["quadro"]) for q in quadros} != CHAVES:
        raise ValueError("Composição dos 178 quadros alterada ou repetida.")
    for q in quadros:
        if type(q["quadro"]) is not int or type(q["video_id"]) is not str:
            raise ValueError("Identificação de quadro inválida.")
        for tipo, subpasta, ext in (("imagem","images","jpg"),("anotacao","labels","txt")):
            esperado=f"bases_de_dados/visem_tracking/dataset/Train/{q['video_id']}/{subpasta}/{q['video_id']}_frame_{q['quadro']}.{ext}"
            if q[tipo] != esperado or len(q[f"{tipo}_sha256"]) != 64:
                raise ValueError("Caminho ou hash incompatível com o quadro.")
    if [(q["video_id"],q["quadro"]) for q in plano["exclusoes"]] != [("23",900),("23",1100)]:
        raise ValueError("Exclusões históricas alteradas.")
    return plano


def construir_plano(raiz=RAIZ):
    """Lê somente planos e registros já existentes; não abre imagens."""
    b = raiz / ROUND0
    original = carregar_json((raiz/DESENVOLVIMENTO).read_bytes())
    p0 = carregar_json((b/"plano.json").read_bytes())
    m0 = carregar_json((b/"execucao.json").read_bytes())
    refs = deepcopy(p0["configuracoes"][:4])
    origens = {}
    for nome,arquivo in (("desenvolvimento.json",DESENVOLVIMENTO), ("round0_plano.json",ROUND0+"/plano.json"),
                         ("round0_execucao.json",ROUND0+"/execucao.json"),("round0_codigo.zip",ROUND0+"/codigo.zip")):
        origens[nome] = {"arquivo":arquivo,"sha256":sha((raiz/arquivo).read_bytes())}
    quadros = [{"video_id":q["video_id"],"quadro":q["quadro"],"imagem":q["imagem"],"anotacao":q["anotacao"],
                "imagem_sha256":q["sha256_imagem"],"anotacao_sha256":q["sha256_anotacao"]} for q in original["quadros"]]
    configs = gerar_configuracoes(refs)
    fontes_controles = []
    pastas = {r["configuracao_id"]:r["pasta"] for r in m0["execucoes"]}
    for item in configs[:4]:
        for q in p0["quadros"]:
            quadro=f"{q['video_id']}_frame_{q['quadro']}"
            for nome in ARQUIVOS_CONTROLE:
                arquivo=f"{pastas[item['referencia_round0']]}/quadros/{quadro}/{nome}"
                fontes_controles.append({"configuracao_id":item["id"],"video_id":q["video_id"],"quadro":q["quadro"],
                    "nome":nome,"arquivo":arquivo,"sha256":m0["saidas_sha256"][arquivo],
                    "copia":f"controles/{item['id']}/{quadro}/{nome}"})
    p={"versao":1,"algoritmo":"watershed","rodada":"round1","etapa":"desenvolvimento","particao":"desenvolvimento",
       "seed":42,"criterios":deepcopy(CRITERIOS),"quadros_por_configuracao":178,"configuracoes_previstas":48,
       "geracao":{"arquivo":ARQUIVO,"sha256":sha((raiz/ARQUIVO).read_bytes()),"versao":"1.0",
                   "estrategia":"contrastes dirigidos e eixos exploratórios balanceados; políticas aos pares"},
       "origens":origens,"referencias_round0":refs,"quadros":quadros,"exclusoes":deepcopy(original["exclusoes"]),
       "configuracoes":configs,"fontes_controles":fontes_controles}
    return validar_plano(p)


if __name__ == "__main__":
    alvo=RAIZ/"scripts/watershed/rodadas/round1.json"
    conteudo=bytes_json(construir_plano())
    alvo.parent.mkdir(parents=True,exist_ok=True)
    if alvo.exists():
        if alvo.read_bytes()!=conteudo:
            raise SystemExit("O plano existente difere. Preserve-o; não será sobrescrito.")
        print("Plano existente reproduzido exatamente.")
    else:
        with alvo.open("xb") as f:f.write(conteudo)
        print(f"Plano salvo: {alvo}. 48 configurações; 8.544 avaliações previstas.")
