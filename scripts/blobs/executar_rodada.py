"""Executa planos congelados de blobs, preservando origens e cada tentativa."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter_ns

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar
from scripts.blobs.arquivos import gravar_json, substituir_arquivo
from scripts.blobs.executar_inspecao import (
    CAMPOS_BLOBS, CAMPOS_CAIXA, FONTES_CODIGO as FONTES_INSPECAO,
    arquivar_codigo, carregar_json, colunas_metricas, objetos, preparar_imagens,
)
from scripts.limiarizacao.inspecionar_imagem import (
    CAMPOS_ANOTACAO, CAMPOS_DETECCAO, CAMPOS_ORIGEM, agora, desenhar_painel,
    ler_anotacoes, sha256, versoes_dependencias,
)

SAIDA = RAIZ / "resultados/frame-to-frame/blobs"
FONTES_CODIGO = tuple(dict.fromkeys((*FONTES_INSPECAO,
    "scripts/blobs/executar_rodada.py", "scripts/blobs/planejamento.py",
    "algoritmos/classicos/caixas_blobs.py", "analise/relatorio_rodada_blobs.py",
    "scripts/blobs/arquivos.py",
    "scripts/blobs/planejamento_round2.py", "scripts/blobs/planejamento_round3.py",
    "scripts/blobs/planejamento_round4.py",
    "scripts/blobs/planejamento_round5.py",
    "algoritmos/classicos/variantes_blobs.py",
)))
TEMPOS = ("preprocessamento", "detector", "adaptacao", "pipeline")
CAMPOS_ORIGINAIS = [f"original_{c}" for c in CAMPOS_CAIXA]


def relativo(caminho: Path) -> str:
    return caminho.resolve().relative_to(RAIZ.resolve()).as_posix()


def caminho_interno(nome: str, diretorio: Path | None = None) -> Path:
    if not isinstance(nome, str) or not nome or "\\" in nome:
        raise ValueError("Caminho relativo inválido.")
    entrada = Path(nome)
    if entrada.is_absolute() or ".." in entrada.parts or entrada.as_posix() != nome:
        raise ValueError(f"Caminho relativo inválido: {nome}.")
    caminho = (RAIZ / entrada).resolve(strict=True)
    if (not caminho.is_relative_to(RAIZ.resolve())
            or not caminho.is_relative_to((diretorio or RAIZ).resolve())
            or not caminho.is_file()):
        raise ValueError(f"Arquivo fora do diretório permitido: {nome}.")
    return caminho


def hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def gravar_tabela(caminho: Path, campos: list[str], registros) -> None:
    """Troca somente um resumo desta execução, sem truncar a versão anterior."""
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(registros)
    substituir_arquivo(temporario, caminho)


def acrescentar_linha(caminho: Path, linha: dict) -> None:
    novo = not caminho.exists()
    with caminho.open("a", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linha))
        if novo:
            escritor.writeheader()
        escritor.writerow(linha)


def congelar_entradas(caminho_plano: Path) -> dict:
    """Confere plano, fontes e todos os arquivos antes de criar resultados."""
    from scripts.blobs.planejamento import carregar_plano
    caminho_plano = Path(caminho_plano).expanduser().resolve(strict=True)
    if not caminho_plano.is_relative_to(RAIZ.resolve()) or not caminho_plano.is_file():
        raise ValueError("O plano deve ser um arquivo dentro do projeto.")
    conteudo = caminho_plano.read_bytes()
    plano = carregar_plano(conteudo)
    hashes = {relativo(caminho_plano): sha256(conteudo)}
    origens = {}
    campos_origens = ["origem_desenvolvimento", "origem_inspecao"]
    if plano["versao"] >= 2:
        campos_origens.append("origem_round1")
    if plano["versao"] >= 3:
        campos_origens.append("origem_round2")
    if plano["versao"] >= 4:
        campos_origens.append("origem_round3")
    if plano["versao"] == 5:
        campos_origens.append("origem_round4")
    for campo in campos_origens:
        origem = plano[campo]
        blob = caminho_interno(origem["plano"]).read_bytes()
        if sha256(blob) != origem["sha256"]:
            raise ValueError(f"Hash divergente no plano de {campo}.")
        hashes[origem["plano"]] = sha256(blob)
        origens[campo] = blob
    desenvolvimento = carregar_json(origens["origem_desenvolvimento"])
    if any(desenvolvimento.get(k) != v for k, v in (
            ("algoritmo", "limiarizacao"), ("rodada", "round1"),
            ("particao", "desenvolvimento"))):
        raise ValueError("Origem não corresponde ao desenvolvimento acordado.")
    fontes_quadros = desenvolvimento.get("quadros", [])
    por_chave = {(q["video_id"], q["quadro"]): q for q in fontes_quadros}
    chaves = {(q["video_id"], q["quadro"]) for q in plano["quadros"]}
    if len(fontes_quadros) != 178 or set(por_chave) != chaves:
        raise ValueError("A origem deve conter os mesmos 178 quadros, sem repetições.")
    from scripts.blobs.executar_inspecao import carregar_plano as carregar_inspecao
    inspecao = carregar_inspecao(origens["origem_inspecao"])
    if inspecao["origem_desenvolvimento"] != plano["origem_desenvolvimento"]:
        raise ValueError("Inspeção e rodada usam origens de desenvolvimento diferentes.")
    if plano["versao"] == 5:
        from scripts.blobs.planejamento_round5 import validar_origens_round5
        validar_origens_round5(plano, origens["origem_round1"], origens["origem_round2"],
                              origens["origem_round3"], origens["origem_round4"])
    elif plano["versao"] == 4:
        from scripts.blobs.planejamento_round4 import validar_origens_round4
        validar_origens_round4(plano, origens["origem_round1"], origens["origem_round2"],
                              origens["origem_round3"])
    elif plano["versao"] == 3:
        from scripts.blobs.planejamento_round3 import validar_origens_round3
        validar_origens_round3(plano, origens["origem_round1"], origens["origem_round2"])
    elif plano["versao"] == 2:
        from scripts.blobs.planejamento_round2 import validar_origem_round1
        validar_origem_round1(plano, origens["origem_round1"])
    else:
        por_referencia = {c["id"]: c["parametros"] for c in inspecao["configuracoes"]}
        for item in plano["configuracoes"]:
            if item["bloco"] == "controle" and (
                    item["referencia"] not in por_referencia
                    or item["parametros"] != por_referencia[item["referencia"]]):
                raise ValueError("Controle não reproduz os parâmetros de sua referência do round0.")
    entradas = []
    for quadro in plano["quadros"]:
        referencia = por_chave[quadro["video_id"], quadro["quadro"]]
        entrada = {"quadro": quadro}
        for tipo in ("imagem", "anotacao"):
            if (quadro[tipo] != referencia[tipo]
                    or quadro[f"{tipo}_sha256"] != referencia[f"sha256_{tipo}"]):
                raise ValueError("Quadro diverge do manifesto de desenvolvimento.")
            blob = caminho_interno(quadro[tipo], RAIZ / "bases_de_dados").read_bytes()
            digest = sha256(blob)
            if digest != quadro[f"{tipo}_sha256"]:
                raise ValueError(f"Hash divergente: {quadro[tipo]}.")
            hashes[quadro[tipo]] = digest
            entrada[f"{tipo}_bytes"] = blob
        entrada["anotacoes"] = ler_anotacoes(entrada["anotacao_bytes"])
        entradas.append(entrada)
    codigo = {nome: caminho_interno(nome).read_bytes() for nome in FONTES_CODIGO}
    return {"plano": plano, "plano_bytes": conteudo, "origens": origens,
            "hashes": hashes, "entradas": entradas, "codigo": codigo}


def decodificar_entrada(entrada: dict, cv2, np) -> dict:
    # Os JPEGs congelados ficam em memória; imagens decodificadas são descartadas
    # após cada quadro, evitando guardar 178 matrizes grandes simultaneamente.
    preparada = {**entrada, "anotacoes": [dict(a) for a in entrada["anotacoes"]]}
    preparar_imagens([preparada], cv2, np)
    return preparada


def conferir_ambiente_e_imagens(dados: dict) -> dict:
    import cv2
    import numpy as np
    import scipy
    import reportlab
    from algoritmos.classicos.blobs import configuracao_de_dict, parametros_opencv
    from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
    from algoritmos.classicos.variantes_blobs import (
        configuracao_escala_de_dict, parametros_escala, validar_preprocessamento,
    )
    efetivos, todos_backend, adicionais = {}, {}, {}
    for item in dados["plano"]["configuracoes"]:
        configuracao_caixa_de_dict(item["caixa"])
        metodo = item.get("metodo", "simpleblob")
        preprocessamento = validar_preprocessamento(item.get("preprocessamento", {"metodo": "nenhum"}))
        if preprocessamento["metodo"] == "clahe":
            cv2.createCLAHE(clipLimit=preprocessamento["limite_contraste"],
                            tileGridSize=tuple(preprocessamento["grade"]))
        if metodo == "simpleblob":
            valores = parametros_opencv(configuracao_de_dict(item["parametros"]))
            backend = cv2.SimpleBlobDetector_Params()
            for nome, valor in valores.items():
                if not hasattr(backend, nome):
                    raise RuntimeError(f"OpenCV sem suporte a {nome}; confira requirements-blobs.txt.")
                setattr(backend, nome, valor)
            cv2.SimpleBlobDetector_create(backend)  # Valida parâmetros; não detecta objetos.
            efetivos[item["id"]] = valores
        else:
            import skimage
            from skimage.feature import blob_log, blob_dog
            import inspect
            valores = parametros_escala(configuracao_escala_de_dict(metodo, item["parametros"]))
            # Confere assinatura do backend sem processar imagens.
            inspect.signature(blob_log if metodo == "log" else blob_dog).bind(None, **valores)
            adicionais["scikit_image_importado"] = skimage.__version__
        todos_backend[item["id"]] = {
            "metodo": metodo, "preprocessamento": preprocessamento, "parametros": valores,
            "polaridade": item["parametros"]["polaridade"],
            "classificacao": item["parametros"]["classificacao"],
        }
    for entrada in dados["entradas"]:
        decodificar_entrada(entrada, cv2, np)
    return {"parametros_opencv": efetivos, "parametros_backend": todos_backend,
            "dependencias": {**versoes_dependencias(), "numpy_importado": np.__version__,
                             "opencv_importado": cv2.__version__, "scipy_importado": scipy.__version__,
                             "reportlab_importado": reportlab.Version, **adicionais}}


def preparar_detector(item: dict):
    """Seleciona implementação explicitamente, sem executar a detecção."""
    metodo = item.get("metodo", "simpleblob")
    if metodo == "simpleblob":
        from algoritmos.classicos.blobs import configuracao_de_dict, detectar
        return configuracao_de_dict(item["parametros"]), detectar
    from algoritmos.classicos.variantes_blobs import configuracao_escala_de_dict, detectar_escala
    return configuracao_escala_de_dict(metodo, item["parametros"]), detectar_escala


def executar_quadro(entrada: dict, config, caixa_config, item: dict,
                    pasta: Path, cv2, np, detectar) -> tuple[dict, dict]:
    from algoritmos.classicos.caixas_blobs import adaptar_caixas
    from algoritmos.classicos.variantes_blobs import aplicar_preprocessamento, validar_preprocessamento
    preparada = decodificar_entrada(entrada, cv2, np)
    quadro, imagem, anotacoes = preparada["quadro"], preparada["imagem"], preparada["anotacoes"]
    origem = {k: quadro[k] for k in ("imagem", "anotacao", "video_id", "quadro")}
    origem["tempo_segundos"] = None
    pasta.mkdir(parents=True, exist_ok=False)
    metodo = item.get("metodo", "simpleblob")
    preproc = validar_preprocessamento(item.get("preprocessamento", {"metodo": "nenhum"}))
    inicio = perf_counter_ns()
    if preproc["metodo"] == "nenhum":
        inicio_detector = inicio
        entrada_detector = imagem.copy()
    else:
        entrada_detector = aplicar_preprocessamento(imagem, preproc)
        inicio_detector = perf_counter_ns()
    original = detectar(entrada_detector, config)
    fim_detector = perf_counter_ns()
    resultado = adaptar_caixas(original, caixa_config)
    fim_adaptacao = perf_counter_ns()
    tempos = {"tempo_preprocessamento_ns": inicio_detector - inicio,
              "tempo_detector_ns": fim_detector - inicio_detector,
              "tempo_adaptacao_ns": fim_adaptacao - fim_detector,
              "tempo_pipeline_ns": fim_adaptacao - inicio}
    registros, originais = list(resultado.registros()), list(original.registros())
    variantes = "metodo" in item
    for registro, bruto in zip(registros, originais):
        registro.update({f"original_{c}": bruto[c] for c in CAMPOS_CAIXA})
        registro["modo_caixa"] = item["caixa"]["modo"]
        if variantes:
            registro.update(metodo_detector=metodo, preprocessamento=preproc["metodo"])
            registro.setdefault("sigma_blob_px", None)
    avaliacao = avaliar(objetos(anotacoes, "indice_anotacao"), objetos(registros, "indice_deteccao"))
    altura, largura = imagem.shape[:2]
    gravar_json(pasta / "avaliacao.json", {"origem": origem,
        "configuracao_id": item["id"], "caixa": item["caixa"],
        "metodo_detector": metodo, "preprocessamento": preproc, **tempos,
        "dimensoes": {"largura": largura, "altura": altura}, **avaliacao})
    gravar_tabela(pasta / "anotacoes.csv", CAMPOS_ORIGEM + CAMPOS_ANOTACAO,
                 ({**origem, **a} for a in anotacoes))
    gravar_tabela(pasta / "deteccoes.csv",
                 CAMPOS_ORIGEM + CAMPOS_DETECCAO + CAMPOS_BLOBS + CAMPOS_ORIGINAIS + ["modo_caixa"]
                 + (["metodo_detector", "preprocessamento", "sigma_blob_px"] if variantes else []),
                 ({**origem, **r} for r in registros))
    with (pasta / "predicoes.txt").open("x", encoding="utf-8") as arquivo:
        linhas = resultado.linhas_yolo()
        arquivo.write("\n".join(linhas) + ("\n" if linhas else ""))
    campos_pares = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao",
                    "iou", "grupo", "classe_correta"]
    gravar_tabela(pasta / "pares.csv", CAMPOS_ORIGEM + campos_pares,
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
    gravar_tabela(pasta / "pendentes.csv", CAMPOS_ORIGEM + ["tipo", "indice", "classe", "grupo"] + CAMPOS_CAIXA,
                 pendentes)
    colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR) if imagem.ndim == 2 else imagem
    painel = np.concatenate((
        desenhar_painel(cv2, np, colorida, anotacoes, f"Anotacoes: {len(anotacoes)}"),
        desenhar_painel(cv2, np, colorida, registros,
                       f"Deteccoes: {len(registros)} | {item['id']} {metodo} {preproc['metodo']} {item['caixa']['modo']}")), axis=1)
    sucesso, png = cv2.imencode(".png", painel)
    if not sucesso:
        raise ValueError("Falha ao gerar comparação PNG.")
    with (pasta / "comparacao.png").open("xb") as arquivo:
        arquivo.write(png.tobytes())
    if preproc["metodo"] == "clahe":
        sucesso, processada = cv2.imencode(".png", entrada_detector)
        if not sucesso:
            raise ValueError("Falha ao salvar a imagem após CLAHE.")
        with (pasta / "preprocessamento.png").open("xb") as arquivo:
            arquivo.write(processada.tobytes())
    linha = {"configuracao_id": item["id"], **origem, "pasta_quadro": relativo(pasta),
             "quantidade_anotacoes": len(anotacoes), "quantidade_deteccoes": len(registros),
             "imagem_largura_px": largura, "imagem_altura_px": altura,
             **tempos, **colunas_metricas(avaliacao)}
    return linha, avaliacao


def resumo(item: dict, linhas: list[dict], avaliacoes: list[dict], **extras) -> dict:
    return {"configuracao_id": item["id"], **extras,
            "quantidade_quadros": len(linhas),
            **{f"tempo_{t}_total_ns": sum(x.get(f"tempo_{t}_ns", 0) for x in linhas) for t in TEMPOS},
            **colunas_metricas(agregar(avaliacoes))}


def ordenar_por_f1(resumos: list[dict]) -> list[dict]:
    """Ordenação descritiva; ID só organiza a apresentação de empates exatos."""
    def pontuacao(linha):
        denominador = 2 * linha["tp_individuos"] + linha["fp_individuos"] + linha["fn_individuos"]
        return Fraction(2 * linha["tp_individuos"], denominador) if denominador else None

    linhas = sorted(resumos, key=lambda r: (
        pontuacao(r) is None, -(pontuacao(r) or 0), r["configuracao_id"]))
    retorno, anterior, posto = [], object(), None
    for indice, linha in enumerate(linhas, 1):
        valor = pontuacao(linha)
        if valor is None:
            posto = None
        elif valor != anterior:
            posto = indice
        retorno.append({"posicao": posto, **linha})
        anterior = valor
    return retorno


def atualizar_relatorio(pasta: Path) -> Path:
    """Atualiza o apontador do último relatório; preserva PDFs e métricas anteriores."""
    from analise.relatorio_rodada_blobs import gerar_relatorio
    pasta = Path(pasta).expanduser().resolve(strict=True)
    if (pasta.parent.parent != SAIDA.resolve()
            or not pasta.is_relative_to(RAIZ.resolve())
            or not re.fullmatch(r"round[1-5]", pasta.parent.name)
            or not pasta.name.startswith("batch__")):
        raise ValueError("Informe uma pasta batch da rodada de blobs.")
    try:
        pdf = gerar_relatorio(pasta)
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {
            "situacao": "falhou", "erro": f"{type(erro).__name__}: {erro}"})
        raise
    gravar_json(pasta / "relatorio.json", {"situacao": "concluido", "arquivo": relativo(pdf)})
    return pdf


def executar(caminho_plano: Path) -> Path:
    print("Conferindo plano, dependências e todas as entradas...", flush=True)
    return executar_dados(congelar_entradas(caminho_plano))


def executar_dados(dados: dict, *, tipo: str = "rodada_blobs",
                   etapa: str = "desenvolvimento", particao: str = "desenvolvimento",
                   interpretacao: str = "Desenvolvimento. Configurações congeladas; não seleciona finalistas nem ajusta parâmetros durante a execução.",
                   relatorio=None, nomear=None) -> Path:
    """Executa entradas já congeladas; rodadas e seleção compartilham as mesmas saídas."""
    import cv2
    import numpy as np
    from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
    from scripts.blobs.planejamento import hash_configuracao, nome_configuracao
    nomear = nomear or nome_configuracao
    relatorio = relatorio or atualizar_relatorio
    ambiente = conferir_ambiente_e_imagens(dados)
    plano = dados["plano"]
    inicio = agora()
    identificador = inicio.strftime("%Y%m%dT%H%M%S%fZ")
    saida = (SAIDA / plano["rodada"]).resolve()
    if not saida.is_relative_to(RAIZ.resolve()) or not saida.is_relative_to(SAIDA.resolve()):
        raise ValueError("Saída fora da pasta de blobs do projeto.")
    pasta = saida / f"batch__{identificador}"
    manifesto = {
        "versao": plano["versao"], "tipo": tipo, "etapa": etapa, "algoritmo": "blobs",
        "rodada": plano["rodada"], "particao": particao, "situacao": "em_andamento",
        "inicio_utc": inicio.isoformat(), "criterios": CRITERIOS,
        "plano_sha256": sha256(dados["plano_bytes"]), "origens_sha256": dados["hashes"],
        "configuracoes_previstas": len(plano["configuracoes"]), "configuracoes_concluidas": 0,
        "quadros_por_configuracao": len(plano["quadros"]), "avaliacoes_concluidas": 0,
        "execucoes": [], "saidas_sha256": {}, **ambiente,
        "registro_relatorio": "relatorio.json", "seed": plano["seed"],
        "aleatoriedade_utilizada": False,
        "interpretacao": interpretacao,
        "identidade_objetos": "Índice do candidato original local ao quadro, preservado na adaptação; sem rastreamento.",
        "medidas": "Centro, diâmetro e área circular brutos preservados; área da caixa não representa área segmentada.",
        "unidades": {"comprimento": "pixel", "area_estimada": "pixel quadrado",
                     "tempos": "nanossegundo", "coordenadas_normalizadas": "fração da dimensão da imagem"},
    }
    pasta.mkdir(parents=True, exist_ok=False)
    atual, pasta_atual = None, None
    resumos, videos = [], []
    try:
        gravar_json(pasta / "execucao.json", manifesto)
        (pasta / "plano.json").write_bytes(dados["plano_bytes"])
        for nome, blob in dados["origens"].items():
            (pasta / f"{nome}.json").write_bytes(blob)
        manifesto["codigo"] = arquivar_codigo(pasta, dados["codigo"])
        for numero, item in enumerate(plano["configuracoes"], 1):
            config, detectar = preparar_detector(item)
            caixa_config = configuracao_caixa_de_dict(item["caixa"])
            nome = nomear(item)
            pasta_atual = (saida / f"{nome}__{identificador}").resolve()
            if pasta_atual.parent != saida:
                raise ValueError("Pasta da configuração fora da rodada.")
            pasta_atual.mkdir(exist_ok=False)
            print(f"{plano['rodada']} | configuração {numero}/{len(plano['configuracoes'])}: {nome}", flush=True)
            atual = {"tipo": tipo, "situacao": "em_andamento", "configuracao_id": item["id"],
                     "batch": relativo(pasta), "plano_sha256": manifesto["plano_sha256"],
                     "configuracao_sha256": hash_configuracao(item),
                     "inicio_utc": agora().isoformat(), "quadros_concluidos": 0}
            gravar_json(pasta_atual / "execucao.json", atual)
            gravar_json(pasta_atual / "configuracao.json", item)
            gravar_json(pasta_atual / "configuracao_backend.json", ambiente["parametros_backend"][item["id"]])
            if item["id"] in ambiente["parametros_opencv"]:
                gravar_json(pasta_atual / "configuracao_opencv.json", ambiente["parametros_opencv"][item["id"]])
            linhas, avaliacoes = [], []
            por_video = defaultdict(lambda: ([], []))
            for entrada in dados["entradas"]:
                q = entrada["quadro"]
                atual["quadro_em_andamento"] = {"video_id": q["video_id"], "quadro": q["quadro"]}
                gravar_json(pasta_atual / "execucao.json", atual)
                destino = pasta_atual / "quadros" / f"{q['video_id']}_frame_{q['quadro']}"
                linha, avaliacao = executar_quadro(entrada, config, caixa_config, item, destino, cv2, np, detectar)
                linhas.append(linha)
                avaliacoes.append(avaliacao)
                por_video[q["video_id"]][0].append(linha)
                por_video[q["video_id"]][1].append(avaliacao)
                acrescentar_linha(pasta_atual / "resumo_por_quadro.csv", linha)
                acrescentar_linha(pasta / "resumo_por_quadro.csv", linha)
                atual["quadros_concluidos"] += 1
                manifesto["avaliacoes_concluidas"] += 1
                atual.pop("quadro_em_andamento")
                gravar_json(pasta_atual / "execucao.json", atual)
                if atual["quadros_concluidos"] % 25 == 0:
                    print(f"  {atual['quadros_concluidos']}/{len(plano['quadros'])} quadros salvos", flush=True)
            total = agregar(avaliacoes)
            gravar_json(pasta_atual / "avaliacao.json", total)
            resumos.append(resumo(item, linhas, avaliacoes, pasta_origem=relativo(pasta_atual),
                                  bloco=item["bloco"], modo_caixa=item["caixa"]["modo"],
                                  perfil_forma=item["perfil_forma"]))
            for video, (linhas_video, avaliacoes_video) in sorted(por_video.items(), key=lambda p: int(p[0])):
                videos.append(resumo(item, linhas_video, avaliacoes_video, video_id=video))
            gravar_tabela(pasta / "resumo_configuracoes.csv", list(resumos[0]), resumos)
            gravar_tabela(pasta / "resumo_por_video.csv", list(videos[0]), videos)
            ranking = ordenar_por_f1(resumos)
            gravar_tabela(pasta / "ranking.csv", list(ranking[0]), ranking)
            atual.update(situacao="concluida", fim_utc=agora().isoformat())
            gravar_json(pasta_atual / "execucao.json", atual)
            print("  Registrando integridade dos arquivos desta configuração...", flush=True)
            for arquivo in sorted(pasta_atual.rglob("*")):
                if arquivo.is_file():
                    manifesto["saidas_sha256"][relativo(arquivo)] = hash_arquivo(arquivo)
            manifesto["execucoes"].append({"configuracao_id": item["id"], "pasta": relativo(pasta_atual)})
            manifesto["configuracoes_concluidas"] += 1
            gravar_json(pasta / "execucao.json", manifesto)
            atual = None
        for arquivo in sorted(pasta.iterdir()):
            if arquivo.is_file() and arquivo.name != "execucao.json":
                manifesto["saidas_sha256"][relativo(arquivo)] = hash_arquivo(arquivo)
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
        print(f"Execução incompleta preservada em: {pasta}", file=sys.stderr)
        raise
    # Relatório é uma saída posterior: falhar aqui não desfaz métricas concluídas.
    try:
        relatorio(pasta)
    except Exception as erro:
        print(f"Aviso: métricas concluídas; PDF não gerado: {erro}", file=sys.stderr)
    return pasta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Executa uma rodada congelada de blobs; padrão round1.")
    origem = parser.add_mutually_exclusive_group()
    origem.add_argument("--rodada", help="round1 a round5; o plano deve estar preparado.")
    origem.add_argument("--plano", type=Path, help="Plano salvo dentro do projeto.")
    origem.add_argument("--somente-relatorio", type=Path, metavar="BATCH", help="Regenera o PDF sem repetir detecções.")
    parser.add_argument("--conferir", action="store_true", help="Confere dependências, plano e entradas, sem detecção nem resultados.")
    args = parser.parse_args(argv)
    try:
        if args.somente_relatorio:
            if args.conferir:
                parser.error("--conferir não se aplica a --somente-relatorio.")
            print(f"Relatório: {atualizar_relatorio(args.somente_relatorio)}")
            return 0
        rodada = args.rodada or "round1"
        if not re.fullmatch(r"round[1-5]", rodada):
            raise ValueError("Informe round1 a round5; round0 tem executor próprio.")
        caminho = args.plano or RAIZ / "scripts/blobs/rodadas" / f"{rodada}.json"
        if not caminho.is_file():
            raise ValueError(f"Plano ainda não preparado: {caminho}")
        if not args.plano and carregar_json(caminho.read_bytes()).get("rodada") != rodada:
            raise ValueError("O plano encontrado não corresponde à rodada solicitada.")
        if args.conferir:
            dados = congelar_entradas(caminho)
            conferir_ambiente_e_imagens(dados)
            plano = dados["plano"]
            print(f"Conferência concluída: {plano['rodada']}, {len(plano['configuracoes'])} configurações, "
                  f"{len(plano['quadros'])} quadros, {len(plano['configuracoes']) * len(plano['quadros'])} avaliações previstas.")
            print("Nenhuma detecção executada; nenhuma pasta de resultados criada.")
        else:
            pasta = executar(caminho)
            print(f"Rodada concluída em: {pasta}")
        return 0
    except (ValueError, OSError, RuntimeError, ImportError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
