"""Inspeção fixa de blobs em seis imagens de desenvolvimento; não faz busca."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter_ns
from zipfile import ZIP_DEFLATED, ZipFile


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar
from scripts.limiarizacao.inspecionar_imagem import (
    CAMPOS_ANOTACAO, CAMPOS_DETECCAO, CAMPOS_ORIGEM, agora, desenhar_painel,
    gravar_csv, gravar_json, identificar_origem, ler_anotacoes,
    objeto_sem_duplicatas, rejeitar_constante, sha256, verificar_chaves,
    versoes_dependencias,
)


PLANO = RAIZ / "scripts/blobs/inspecao/round0.json"
ORIGEM_DESENVOLVIMENTO = "scripts/limiarizacao/rodadas/round1.json"
SAIDA = RAIZ / "resultados/frame-to-frame/blobs/round0"
VIDEOS_DESENVOLVIMENTO = ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60")
CAMPOS_BLOBS = [
    "centro_blob_x_px", "centro_blob_y_px", "diametro_blob_px",
    "area_estimada_blob_px2", "origem_medidas", "caixa_recortada_na_borda",
]
CAMPOS_METRICAS = [
    *[f"{c}_{g}" for g in ("individuos", "aglomerados")
      for c in ("tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1")],
    *[f"{c}_classe_{k}" for k in (0, 2, 1)
      for c in ("anotacoes", "localizadas", "perdidas", "recall")],
    "pares_corretos", "pares_incorretos", "pares_total", "acuracia_condicional",
    "matriz_0_0", "matriz_0_2", "matriz_2_0", "matriz_2_2",
]
CAMPOS_CAIXA = ["caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"]
FONTES_CODIGO = (
    "scripts/blobs/executar_inspecao.py", "analise/relatorio_inspecao_blobs.py",
    "scripts/limiarizacao/inspecionar_imagem.py",
    "algoritmos/__init__.py", "algoritmos/classicos/__init__.py",
    "algoritmos/classicos/blobs.py", "algoritmos/classicos/comum.py",
    "algoritmos/classicos/classificacao.py", "analise/__init__.py",
    "analise/avaliacao_deteccao.py", "analise/avaliacao_individuos.py",
    "algoritmos/classicos/requirements.txt", "algoritmos/classicos/requirements-blobs.txt", "analise/requirements.txt",
    "analise/requirements-relatorio.txt",
)


def carregar_json(conteudo: bytes) -> dict:
    return json.loads(conteudo.decode("utf-8-sig"), parse_constant=rejeitar_constante,
                      object_pairs_hook=objeto_sem_duplicatas)


def relativo(caminho: Path) -> str:
    return caminho.resolve().relative_to(RAIZ.resolve()).as_posix()


def caminho_interno(nome: str, diretorio: Path | None = None) -> Path:
    if not isinstance(nome, str) or not nome or "\\" in nome:
        raise ValueError("Informe um caminho relativo com separadores '/'.")
    entrada = Path(nome)
    if entrada.is_absolute() or ".." in entrada.parts or entrada.as_posix() != nome:
        raise ValueError(f"Caminho relativo inválido: {nome}.")
    caminho = (RAIZ / entrada).resolve(strict=True)
    limite = (diretorio or RAIZ).resolve()
    if (not caminho.is_relative_to(RAIZ.resolve())
            or not caminho.is_relative_to(limite) or not caminho.is_file()):
        raise ValueError(f"Arquivo fora do diretório permitido: {nome}.")
    return caminho


def hash_configuracao(parametros: dict) -> str:
    return sha256(json.dumps(parametros, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8"))


def carregar_plano(conteudo: bytes) -> dict:
    plano = carregar_json(conteudo)
    verificar_chaves(plano, {
        "versao", "algoritmo", "etapa", "rodada", "particao", "seed",
        "origem_desenvolvimento", "quadros", "configuracoes", "observacoes",
    }, "plano")
    if type(plano["versao"]) is not int or plano["versao"] != 1:
        raise ValueError("Versão de plano incompatível.")
    for campo, esperado in (("algoritmo", "blobs"), ("etapa", "inspecao"),
                            ("rodada", "round0"), ("particao", "desenvolvimento")):
        if plano[campo] != esperado:
            raise ValueError(f"O plano de inspeção exige {campo}={esperado}.")
    if type(plano["seed"]) is not int or plano["seed"] < 0:
        raise ValueError("Seed deve ser inteiro não negativo; não há sorteio nesta etapa.")
    verificar_chaves(plano["origem_desenvolvimento"], {"plano", "sha256"}, "origem")
    if plano["origem_desenvolvimento"]["plano"] != ORIGEM_DESENVOLVIMENTO:
        raise ValueError("A origem deve ser o plano round1 de desenvolvimento da limiarização.")
    digest_origem = plano["origem_desenvolvimento"]["sha256"]
    if not isinstance(digest_origem, str) or not re.fullmatch(r"[0-9a-f]{64}", digest_origem):
        raise ValueError("Hash do plano de desenvolvimento inválido.")
    if (not isinstance(plano["observacoes"], list)
            or any(not isinstance(x, str) or not x.strip() for x in plano["observacoes"])):
        raise ValueError("Observações devem ser uma lista de textos não vazios.")
    if not isinstance(plano["quadros"], list) or len(plano["quadros"]) != 6:
        raise ValueError("A inspeção round0 exige exatamente seis quadros.")
    if not isinstance(plano["configuracoes"], list) or len(plano["configuracoes"]) != 2:
        raise ValueError("A inspeção round0 exige exatamente duas configurações.")
    chaves, arquivos = set(), set()
    for quadro in plano["quadros"]:
        verificar_chaves(quadro, {"video_id", "quadro", "imagem", "anotacao",
                                  "imagem_sha256", "anotacao_sha256", "objetivo"}, "quadro")
        if (not isinstance(quadro["video_id"], str) or quadro["video_id"] not in VIDEOS_DESENVOLVIMENTO
                or type(quadro["quadro"]) is not int or quadro["quadro"] < 0):
            raise ValueError("Vídeo ou índice inválido para desenvolvimento.")
        chave = (quadro["video_id"], quadro["quadro"])
        if chave in chaves:
            raise ValueError("Quadro repetido no plano.")
        chaves.add(chave)
        if not isinstance(quadro["objetivo"], str) or not quadro["objetivo"].strip():
            raise ValueError("Cada quadro precisa de um objetivo de inspeção.")
        for tipo, subpasta, extensao in (("imagem", "images", "jpg"), ("anotacao", "labels", "txt")):
            esperado = (f"bases_de_dados/visem_tracking/dataset/Train/{quadro['video_id']}/"
                        f"{subpasta}/{quadro['video_id']}_frame_{quadro['quadro']}.{extensao}")
            if quadro[tipo] != esperado or quadro[tipo] in arquivos:
                raise ValueError("Imagem/anotação incompatível com o quadro, ou repetida.")
            arquivos.add(quadro[tipo])
            digest = quadro[f"{tipo}_sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Hash de imagem/anotação inválido.")
    from algoritmos.classicos.blobs import configuracao_de_dict, parametros_opencv
    ids, hashes = set(), set()
    for item in plano["configuracoes"]:
        verificar_chaves(item, {"id", "parametros"}, "configuração")
        if not isinstance(item["id"], str) or not re.fullmatch(r"b[0-9]{2}", item["id"]):
            raise ValueError("IDs devem ter o formato b01, b02, ...")
        config = configuracao_de_dict(item["parametros"])
        # Números equivalentes (3 e 3.0) e o mesmo arredondamento float32
        # não constituem configurações distintas.
        digest = hash_configuracao({"opencv": parametros_opencv(config), "classificacao": {
            k: float(v) for k, v in item["parametros"]["classificacao"].items()
        }})
        if item["id"] in ids or digest in hashes:
            raise ValueError("ID ou configuração repetida no plano.")
        ids.add(item["id"])
        hashes.add(digest)
    return plano


def congelar_entradas(caminho_plano: Path) -> dict:
    """Lê e confere todas as entradas antes de criar qualquer saída."""
    caminho_plano = caminho_plano.expanduser().resolve(strict=True)
    if not caminho_plano.is_relative_to(RAIZ.resolve()) or not caminho_plano.is_file():
        raise ValueError("O plano deve ser um arquivo dentro do projeto.")
    conteudo = caminho_plano.read_bytes()
    plano = carregar_plano(conteudo)
    origem = plano["origem_desenvolvimento"]
    origem_bytes = caminho_interno(origem["plano"]).read_bytes()
    if sha256(origem_bytes) != origem["sha256"]:
        raise ValueError("Hash divergente no plano de desenvolvimento.")
    desenvolvimento = carregar_json(origem_bytes)
    if (desenvolvimento.get("particao") != "desenvolvimento"
            or desenvolvimento.get("algoritmo") != "limiarizacao"
            or desenvolvimento.get("rodada") != "round1"):
        raise ValueError("A origem não identifica o desenvolvimento esperado.")
    origem_quadros = desenvolvimento.get("quadros")
    if not isinstance(origem_quadros, list):
        raise ValueError("Origem sem composição de quadros.")
    por_chave = {(x["video_id"], x["quadro"]): x for x in origem_quadros}
    esperadas = {(v, q) for v in VIDEOS_DESENVOLVIMENTO for q in range(0, 1401, 100)}
    esperadas -= {("23", 900), ("23", 1100)}
    if len(origem_quadros) != 178 or set(por_chave) != esperadas:
        raise ValueError("A origem deve preservar os mesmos 178 quadros de desenvolvimento.")
    hashes = {relativo(caminho_plano): sha256(conteudo), origem["plano"]: sha256(origem_bytes)}
    congelados = []
    for quadro in plano["quadros"]:
        chave = (quadro["video_id"], quadro["quadro"])
        if chave not in por_chave:
            raise ValueError("Quadro fora dos 178 casos anotados de desenvolvimento.")
        referencia = por_chave[chave]
        dados = {"quadro": quadro}
        for tipo in ("imagem", "anotacao"):
            if (quadro[tipo] != referencia[tipo]
                    or quadro[f"{tipo}_sha256"] != referencia[f"sha256_{tipo}"]):
                raise ValueError("Quadro não corresponde ao manifesto de desenvolvimento.")
            arquivo = caminho_interno(quadro[tipo], RAIZ / "bases_de_dados")
            blob = arquivo.read_bytes()
            if sha256(blob) != quadro[f"{tipo}_sha256"]:
                raise ValueError(f"Hash divergente: {quadro[tipo]}.")
            hashes[quadro[tipo]] = sha256(blob)
            dados[f"{tipo}_bytes"] = blob
        dados["anotacoes"] = ler_anotacoes(dados["anotacao_bytes"])
        congelados.append(dados)
    codigo = {nome: caminho_interno(nome).read_bytes() for nome in FONTES_CODIGO}
    return {"plano": plano, "plano_bytes": conteudo, "origem_bytes": origem_bytes,
            "entradas": congelados, "hashes": hashes, "codigo": codigo}


def colunas_metricas(resultado: dict) -> dict:
    linha = {}
    for grupo in ("individuos", "aglomerados"):
        for campo in ("tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1"):
            linha[f"{campo}_{grupo}"] = resultado["por_grupo"][grupo][campo]
    for classe in (0, 2, 1):
        for campo in ("anotacoes", "localizadas", "perdidas", "recall"):
            linha[f"{campo}_classe_{classe}"] = resultado["cobertura_por_classe"][str(classe)][campo]
    classificacao = resultado["classificacao_individuos"]
    linha.update(pares_corretos=classificacao["pares_corretos"],
                 pares_incorretos=classificacao["pares_incorretos"],
                 pares_total=classificacao["total"],
                 acuracia_condicional=classificacao["acuracia_condicional"])
    for i, real in enumerate((0, 2)):
        for j, prevista in enumerate((0, 2)):
            linha[f"matriz_{real}_{prevista}"] = classificacao["matriz_confusao"][i][j]
    return linha


def objetos(registros: list[dict], campo_indice: str) -> list[Objeto]:
    return [Objeto(r[campo_indice], r["classe"], *(r[c] for c in CAMPOS_CAIXA)) for r in registros]


def nome_configuracao(item: dict) -> str:
    p = item["parametros"]
    def numero(x):
        return format(x, "g").replace(".", "p")
    return (f"{item['id']}__blobs-{p['polaridade']}-t{numero(p['limiar_minimo'])}"
            f"a{numero(p['limiar_maximo'])}-p{numero(p['passo_limiar'])}"
            f"-r{p['repetibilidade_minima']}__cfg-{hash_configuracao(p)[:12]}")


def arquivar_codigo(pasta: Path, fontes: dict[str, bytes]) -> dict:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as arquivo:
        for nome, conteudo in sorted(fontes.items()):
            arquivo.writestr(nome, conteudo)
    with (pasta / "codigo.zip").open("xb") as arquivo:
        arquivo.write(buffer.getvalue())
    registro = {"sha256_arquivos": {n: sha256(b) for n, b in fontes.items()},
                "sha256_zip": sha256(buffer.getvalue()), "commit": None, "arvore_modificada": None}
    try:
        opcoes = {"cwd": RAIZ, "capture_output": True, "text": True, "timeout": 5, "check": True}
        registro["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], **opcoes).stdout.strip()
        registro["arvore_modificada"] = bool(subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"], **opcoes).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return registro


def preparar_imagens(entradas: list[dict], cv2, np) -> None:
    for entrada in entradas:
        imagem = cv2.imdecode(np.frombuffer(entrada["imagem_bytes"], dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if (imagem is None or imagem.dtype != np.uint8 or imagem.ndim not in (2, 3)
                or (imagem.ndim == 3 and imagem.shape[2] != 3)):
            raise ValueError(f"Imagem inválida, esperado uint8 em cinza ou BGR: {entrada['quadro']['imagem']}.")
        altura, largura = imagem.shape[:2]
        if not altura or not largura:
            raise ValueError("Imagem vazia.")
        for a in entrada["anotacoes"]:
            a.update(caixa_x_px=(a["caixa_centro_x_norm"] - a["caixa_largura_norm"] / 2) * largura,
                     caixa_y_px=(a["caixa_centro_y_norm"] - a["caixa_altura_norm"] / 2) * altura,
                     caixa_largura_px=a["caixa_largura_norm"] * largura,
                     caixa_altura_px=a["caixa_altura_norm"] * altura)
        entrada["imagem"] = imagem


def executar_quadro(entrada: dict, config, item: dict, pasta: Path, cv2, np, detectar) -> tuple[dict, dict]:
    quadro, imagem, anotacoes = entrada["quadro"], entrada["imagem"], entrada["anotacoes"]
    origem = identificar_origem(Path(quadro["imagem"]), Path(quadro["anotacao"]))
    origem.update(imagem=quadro["imagem"], anotacao=quadro["anotacao"])
    pasta.mkdir(parents=True, exist_ok=False)
    inicio = perf_counter_ns()
    resultado = detectar(imagem.copy(), config)
    duracao = perf_counter_ns() - inicio
    registros = list(resultado.registros())
    avaliacao = avaliar(objetos(anotacoes, "indice_anotacao"), objetos(registros, "indice_deteccao"))
    altura, largura = imagem.shape[:2]
    gravar_json(pasta / "avaliacao.json", {"origem": origem, "objetivo": quadro["objetivo"],
                                           "dimensoes": {"largura": largura, "altura": altura}, **avaliacao})
    gravar_csv(pasta / "anotacoes.csv", CAMPOS_ORIGEM + CAMPOS_ANOTACAO,
               ({**origem, **r} for r in anotacoes))
    gravar_csv(pasta / "deteccoes.csv", CAMPOS_ORIGEM + CAMPOS_DETECCAO + CAMPOS_BLOBS,
               ({**origem, **r} for r in registros))
    linhas = resultado.linhas_yolo()
    with (pasta / "predicoes.txt").open("x", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas) + ("\n" if linhas else ""))
    campos_pares = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao",
                    "iou", "grupo", "classe_correta"]
    gravar_csv(pasta / "pares.csv", CAMPOS_ORIGEM + campos_pares,
               ({**origem, **par} for par in avaliacao["pares"]))
    pendentes = []
    for tipo, lista, indice, chave in (("FN", anotacoes, "indice_anotacao", "anotacoes_sem_par"),
                                      ("FP", registros, "indice_deteccao", "deteccoes_sem_par")):
        por_indice = {r[indice]: r for r in lista}
        for numero in avaliacao[chave]:
            r = por_indice[numero]
            pendentes.append({**origem, "tipo": tipo, "indice": numero, "classe": r["classe"],
                              "grupo": "aglomerados" if r["classe"] == 1 else "individuos",
                              **{c: r[c] for c in CAMPOS_CAIXA}})
    gravar_csv(pasta / "pendentes.csv", CAMPOS_ORIGEM + ["tipo", "indice", "classe", "grupo"] + CAMPOS_CAIXA,
               pendentes)
    colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR) if imagem.ndim == 2 else imagem
    painel = np.concatenate((
        desenhar_painel(cv2, np, colorida, anotacoes, f"Anotacoes: {len(anotacoes)}"),
        desenhar_painel(cv2, np, colorida, registros,
                       f"Deteccoes: {len(registros)} | blobs {item['id']}")), axis=1)
    sucesso, png = cv2.imencode(".png", painel)
    if not sucesso:
        raise ValueError("Falha ao gerar comparação PNG.")
    with (pasta / "comparacao.png").open("xb") as arquivo:
        arquivo.write(png.tobytes())
    linha = {"configuracao_id": item["id"], **origem, "pasta_quadro": relativo(pasta),
             "objetivo": quadro["objetivo"], "quantidade_anotacoes": len(anotacoes),
             "quantidade_deteccoes": len(registros), "tempo_detector_ns": duracao,
             "imagem_largura_px": largura, "imagem_altura_px": altura,
             **colunas_metricas(avaliacao)}
    return linha, avaliacao


def executar(caminho_plano: Path = PLANO) -> Path:
    import cv2
    import numpy as np
    import scipy
    from algoritmos.classicos.blobs import configuracao_de_dict, detectar, parametros_opencv
    dados = congelar_entradas(caminho_plano)
    preparar_imagens(dados["entradas"], cv2, np)
    plano = dados["plano"]
    configuracoes = [(item, configuracao_de_dict(item["parametros"])) for item in plano["configuracoes"]]
    efetivos = {item["id"]: parametros_opencv(config) for item, config in configuracoes}
    inicio = agora()
    identificador = inicio.strftime("%Y%m%dT%H%M%S%fZ")
    pasta = (SAIDA / f"inspecao__{identificador}").resolve()
    if not SAIDA.resolve().is_relative_to(RAIZ.resolve()) or not pasta.is_relative_to(SAIDA.resolve()):
        raise ValueError("Saída fora da pasta round0 de blobs.")
    manifesto = {
        "versao": 1, "tipo": "inspecao_blobs", "etapa": "inspecao", "algoritmo": "blobs",
        "rodada": "round0", "particao": "desenvolvimento", "situacao": "em_andamento",
        "inicio_utc": inicio.isoformat(), "criterios": CRITERIOS,
        "plano_sha256": sha256(dados["plano_bytes"]), "origens_sha256": dados["hashes"],
        "configuracoes_previstas": 2, "configuracoes_concluidas": 0,
        "quadros_por_configuracao": 6, "execucoes": [],
        "dependencias": {**versoes_dependencias(), "numpy_importado": np.__version__,
                         "opencv_importado": cv2.__version__, "scipy_importado": scipy.__version__},
        "parametros_opencv": efetivos, "registro_relatorio": "relatorio.json",
        "interpretacao": "Inspeção round0, sem ranking, ajuste automático, seleção ou promoção de configurações.",
        "seed": plano["seed"], "aleatoriedade_utilizada": False,
        "identidade_objetos": "Índices locais por quadro, sem trajetórias ou velocidade.",
        "medidas": "Centro, diâmetro e área de disco são estimativas de keypoints; não são centroide nem área segmentada.",
        "unidades": {"comprimento": "pixel", "area_estimada": "pixel quadrado", "tempo_detector": "nanossegundo",
                     "coordenadas_normalizadas": "fração da dimensão da imagem"},
    }
    pasta.mkdir(parents=True, exist_ok=False)
    atual, pasta_atual = None, None
    try:
        gravar_json(pasta / "execucao.json", manifesto)
        (pasta / "plano.json").write_bytes(dados["plano_bytes"])
        (pasta / "origem_desenvolvimento.json").write_bytes(dados["origem_bytes"])
        manifesto["codigo"] = arquivar_codigo(pasta, dados["codigo"])
        linhas_quadros, resumos, pastas = [], [], []
        for item, config in configuracoes:
            pasta_atual = (SAIDA / f"{nome_configuracao(item)}__{identificador}").resolve()
            if not pasta_atual.is_relative_to(SAIDA.resolve()):
                raise ValueError("Pasta da configuração fora de round0.")
            pasta_atual.mkdir(exist_ok=False)
            pastas.append(pasta_atual)
            atual = {"tipo": "inspecao_blobs", "situacao": "em_andamento", "configuracao_id": item["id"],
                     "batch": relativo(pasta), "plano_sha256": manifesto["plano_sha256"],
                     "configuracao_sha256": hash_configuracao(item["parametros"]),
                     "parametros_opencv": efetivos[item["id"]], "inicio_utc": agora().isoformat(),
                     "quadros_concluidos": 0}
            gravar_json(pasta_atual / "execucao.json", atual)
            gravar_json(pasta_atual / "configuracao.json", item["parametros"])
            gravar_json(pasta_atual / "configuracao_opencv.json", efetivos[item["id"]])
            avaliacoes, linhas_config = [], []
            for entrada in dados["entradas"]:
                quadro = entrada["quadro"]
                destino = pasta_atual / "quadros" / f"{quadro['video_id']}_frame_{quadro['quadro']}"
                linha, avaliacao = executar_quadro(entrada, config, item, destino, cv2, np, detectar)
                linhas_config.append(linha)
                linhas_quadros.append(linha)
                avaliacoes.append(avaliacao)
                atual["quadros_concluidos"] += 1
                gravar_json(pasta_atual / "execucao.json", atual)
            total = agregar(avaliacoes)
            resumo = {"configuracao_id": item["id"], "pasta_origem": relativo(pasta_atual),
                      "quantidade_quadros": len(avaliacoes),
                      "tempo_detector_total_ns": sum(x["tempo_detector_ns"] for x in linhas_config),
                      **colunas_metricas(total)}
            gravar_json(pasta_atual / "avaliacao.json", total)
            gravar_csv(pasta_atual / "resumo_por_quadro.csv", list(linhas_config[0]), linhas_config)
            resumos.append(resumo)
            atual.update(situacao="concluida", fim_utc=agora().isoformat())
            gravar_json(pasta_atual / "execucao.json", atual)
            manifesto["execucoes"].append({"configuracao_id": item["id"], "pasta": relativo(pasta_atual)})
            manifesto["configuracoes_concluidas"] += 1
            gravar_json(pasta / "execucao.json", manifesto)
            atual = None
        gravar_csv(pasta / "resumo_configuracoes.csv", list(resumos[0]), resumos)
        gravar_csv(pasta / "resumo_por_quadro.csv", list(linhas_quadros[0]), linhas_quadros)
        arquivos = [p for origem in [pasta, *pastas] for p in origem.rglob("*")
                    if p.is_file() and p != pasta / "execucao.json"]
        manifesto["saidas_sha256"] = {relativo(p): sha256(p.read_bytes()) for p in sorted(arquivos)}
        manifesto.update(situacao="concluida", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", manifesto)
    except BaseException as erro:
        falha = {"situacao": "falhou", "fim_utc": agora().isoformat(), "erro": f"{type(erro).__name__}: {erro}"}
        manifesto.update(falha)
        try:
            gravar_json(pasta / "execucao.json", manifesto)
            if atual is not None and pasta_atual is not None:
                atual.update(falha)
                gravar_json(pasta_atual / "execucao.json", atual)
        except OSError:
            pass
        print(f"Inspeção incompleta preservada em: {pasta}", file=sys.stderr)
        raise
    # O relatório é posterior à conclusão das métricas; falhas não invalidam o lote.
    try:
        from analise.relatorio_inspecao_blobs import gerar_relatorio
        pdf = gerar_relatorio(pasta)
        registro = {"situacao": "concluido", "arquivo": relativo(pdf)}
    except Exception as erro:
        registro = {"situacao": "falhou", "erro": f"{type(erro).__name__}: {erro}"}
        print(f"Aviso: métricas concluídas; PDF não gerado: {erro}", file=sys.stderr)
    gravar_json(pasta / "relatorio.json", registro)
    return pasta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspeção round0: seis imagens, duas configurações de blobs; sem busca ou ranking.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--plano", type=Path, help="Plano de inspeção; padrão scripts/blobs/inspecao/round0.json.")
    grupo.add_argument("--somente-relatorio", type=Path, metavar="PASTA", help="Gera novo PDF a partir de inspeção concluída, sem detectar.")
    args = parser.parse_args(argv)
    try:
        if args.somente_relatorio is not None:
            from analise.relatorio_inspecao_blobs import gerar_relatorio
            print(f"Relatório salvo em: {gerar_relatorio(args.somente_relatorio)}")
        else:
            pasta = executar(args.plano or PLANO)
            print(f"Inspeção concluída em: {pasta}")
            print("Abra as comparações nas pastas irmãs das configurações. Round0 não seleciona finalistas.")
    except KeyboardInterrupt:
        print("Inspeção interrompida; resultados parciais preservados.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
