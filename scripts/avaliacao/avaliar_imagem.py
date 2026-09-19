"""Avalia caixas já exportadas, sem executar novamente o detector."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import platform
import subprocess
import sys


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_deteccao import Objeto, avaliar


CAMPOS_CAIXA = ["caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"]
CAMPOS_NORM = ["caixa_centro_x_norm", "caixa_centro_y_norm", "caixa_largura_norm", "caixa_altura_norm"]
CAMPOS_ORIGEM = ["imagem", "anotacao", "video_id", "quadro", "tempo_segundos"]
CAMPOS_MEDIDAS = ["area_pixels", "area_caixa_px2", "alongamento_caixa", "ocupacao_caixa", "intensidade_media"]
CAMPOS_PARES = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao", "iou"]


def agora() -> datetime:
    return datetime.now(timezone.utc)


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def gravar_json(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporario.replace(caminho)


def gravar_csv(caminho: Path, campos: list[str], registros) -> None:
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(registros)


def rejeitar_constante(valor: str):
    raise ValueError(f"O manifesto contém número não finito: {valor}.")


def objeto_json(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError(f"Campo JSON repetido: {chave}.")
        objeto[chave] = valor
    return objeto


def validar_manifesto(conteudo: bytes) -> dict:
    dados = json.loads(conteudo.decode("utf-8-sig"), parse_constant=rejeitar_constante, object_pairs_hook=objeto_json)
    if not isinstance(dados, dict) or dados.get("situacao") != "concluida":
        raise ValueError("A execução de detecção precisa estar marcada como concluida.")
    dimensoes = dados.get("dimensoes")
    if not isinstance(dimensoes, dict):
        raise ValueError("Dimensões da imagem ausentes no manifesto.")
    for chave in ("largura", "altura"):
        if type(dimensoes.get(chave)) is not int or dimensoes[chave] <= 0:
            raise ValueError(f"Dimensão inválida: {chave}.")
    origem = dados.get("origem")
    if not isinstance(origem, dict) or any(chave not in origem for chave in CAMPOS_ORIGEM):
        raise ValueError("Identificação da origem incompleta no manifesto.")
    if not all(isinstance(origem[chave], str) and origem[chave] for chave in ("imagem", "anotacao")):
        raise ValueError("Os caminhos de origem precisam estar preenchidos no manifesto.")
    for campo in ("quantidade_anotacoes", "quantidade_deteccoes"):
        if type(dados.get(campo)) is not int or dados[campo] < 0:
            raise ValueError(f"Contagem inválida no manifesto: {campo}.")
    return dados


def ler_objetos(conteudo: bytes, manifesto: dict, anotacao: bool):
    nome = "anotacoes.csv" if anotacao else "deteccoes.csv"
    campo_indice = "indice_anotacao" if anotacao else "indice_deteccao"
    obrigatorios = {campo_indice, "classe", *CAMPOS_CAIXA, *CAMPOS_NORM, *CAMPOS_ORIGEM}
    if not anotacao:
        obrigatorios.update(("imagem_largura_px", "imagem_altura_px"))
    leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")), strict=True)
    colunas = leitor.fieldnames or []
    if len(colunas) != len(set(colunas)) or not obrigatorios.issubset(colunas):
        raise ValueError(f"Cabeçalho inválido em {nome}. Campos exigidos: {sorted(obrigatorios)}.")
    largura, altura = manifesto["dimensoes"]["largura"], manifesto["dimensoes"]["altura"]
    objetos, registros = [], {}
    for numero, linha in enumerate(leitor, start=2):
        try:
            if None in linha or any(valor is None for valor in linha.values()):
                raise ValueError("Quantidade de colunas incorreta.")
            for campo in CAMPOS_ORIGEM:
                esperado = manifesto["origem"][campo]
                if linha[campo] != ("" if esperado is None else str(esperado)):
                    raise ValueError(f"Origem divergente no campo {campo}.")
            if linha["classe"] not in ("0", "1", "2"):
                raise ValueError("Classe deve ser 0, 1 ou 2.")
            indice = int(linha[campo_indice])
            if indice < 0 or indice in registros:
                raise ValueError("Índice negativo ou repetido.")
            caixa = [float(linha[campo]) for campo in CAMPOS_CAIXA]
            normalizada = [float(linha[campo]) for campo in CAMPOS_NORM]
            if not all(math.isfinite(valor) for valor in caixa + normalizada):
                raise ValueError("Coordenadas devem ser finitas.")
            x, y, w, h = caixa
            cx, cy, wn, hn = normalizada
            if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < wn <= 1 and 0 < hn <= 1 and w > 0 and h > 0):
                raise ValueError("Dimensões da caixa inválidas.")
            if (x < -largura * 1e-8 or y < -altura * 1e-8
                    or x + w > largura * (1 + 1e-8) or y + h > altura * (1 + 1e-8)):
                raise ValueError("Caixa ultrapassa a imagem.")
            reconstruida = [(cx - wn / 2) * largura, (cy - hn / 2) * altura, wn * largura, hn * altura]
            if not all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6) for a, b in zip(caixa, reconstruida)):
                raise ValueError("Coordenadas em pixels e normalizadas divergem.")
            if not anotacao and (int(linha["imagem_largura_px"]) != largura or int(linha["imagem_altura_px"]) != altura):
                raise ValueError("Dimensões da imagem divergem do manifesto.")
            objetos.append(Objeto(indice, int(linha["classe"]), x, y, w, h))
            registros[indice] = linha
        except (ValueError, TypeError) as erro:
            raise ValueError(f"{nome}, linha {numero}: {erro}") from erro
    quantidade = manifesto["quantidade_anotacoes" if anotacao else "quantidade_deteccoes"]
    if len(objetos) != quantidade:
        raise ValueError(f"{nome}: há {len(objetos)} objetos, mas o manifesto informa {quantidade}.")
    return objetos, registros


def codigo_avaliador() -> dict:
    arquivos = [Path(__file__).resolve(), RAIZ / "analise" / "avaliacao_deteccao.py"]
    resultado = {"sha256_arquivos": {caminho.relative_to(RAIZ).as_posix(): sha256(caminho.read_bytes()) for caminho in arquivos},
                 "commit": None, "arvore_modificada": None}
    try:
        opcoes = {"cwd": RAIZ, "capture_output": True, "text": True, "timeout": 5, "check": True}
        resultado["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], **opcoes).stdout.strip()
        resultado["arvore_modificada"] = bool(subprocess.run(["git", "status", "--porcelain"], **opcoes).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return resultado


def tabelas_detalhadas(pasta: Path, resultado: dict, anotacoes: dict, deteccoes: dict) -> None:
    for chave, sufixo in (("principal", "classe"), ("localizacao", "localizacao")):
        avaliacao = resultado[chave]
        campos = [*CAMPOS_PARES, "classe_correta", *CAMPOS_MEDIDAS]
        gravar_csv(pasta / f"pares_{sufixo}.csv", campos, (
            {**par, "classe_correta": par["classe_anotacao"] == par["classe_deteccao"],
             **{campo: deteccoes[par["indice_deteccao"]].get(campo, "") for campo in CAMPOS_MEDIDAS}}
            for par in avaliacao["pares"]
        ))
        pendentes = []
        for tipo, indices, registros in (
            ("falso_positivo", avaliacao["deteccoes_sem_par"], deteccoes),
            ("falso_negativo", avaliacao["anotacoes_sem_par"], anotacoes),
        ):
            for indice in indices:
                linha = registros[indice]
                pendentes.append({
                    "tipo": tipo, "indice": indice, "classe": linha["classe"],
                    **{campo: linha[campo] for campo in CAMPOS_CAIXA},
                    **{campo: linha.get(campo, "") for campo in CAMPOS_MEDIDAS},
                })
        gravar_csv(pasta / f"pendentes_{sufixo}.csv", ["tipo", "indice", "classe", *CAMPOS_CAIXA, *CAMPOS_MEDIDAS], pendentes)


def texto_numero(valor) -> str:
    return "sem casos" if valor is None else f"{valor:.6f}"


def resumir(resultado: dict) -> str:
    linhas = ["Avaliação de uma imagem — IoU >= 0,50; correspondência um para um.",
              "Principal: localização e classe corretas."]
    for classe, metricas in resultado["principal"]["por_classe"].items():
        linhas.append(
            f"Classe {classe}: TP={metricas['tp']}, FP={metricas['fp']}, FN={metricas['fn']}; "
            f"precisão={texto_numero(metricas['precisao'])}; recall={texto_numero(metricas['recall'])}; "
            f"F1={texto_numero(metricas['f1'])}."
        )
    macro = resultado["principal"]["macro_f1"]
    linhas.append("Macro-F1 das três classes: " + (f"{macro:.6f}." if macro is not None else "indefinido; há classe sem casos."))
    local = resultado["localizacao"]["metricas"]
    linhas.extend([
        "", "Auxiliar: somente localização, com pareamento independente.",
        f"TP={local['tp']}, FP={local['fp']}, FN={local['fn']}; "
        f"precisão={texto_numero(local['precisao'])}; recall={texto_numero(local['recall'])}; F1={texto_numero(local['f1'])}.",
        f"Classes divergentes nos pares auxiliares: {resultado['localizacao']['pares_com_classe_incorreta']}.",
        "Os pares auxiliares não modificam as contagens principais.",
        "Esta imagem isolada não seleciona configurações. O ranking requer o conjunto acordado.",
    ])
    return "\n".join(linhas) + "\n"


def executar(caminho: Path) -> Path:
    pasta_origem = caminho.expanduser().resolve(strict=True)
    permitida = (RAIZ / "resultados" / "frame-to-frame").resolve()
    if not pasta_origem.is_dir() or not pasta_origem.is_relative_to(permitida):
        raise ValueError("Informe uma pasta de execução dentro de resultados/frame-to-frame/ deste projeto.")
    entradas = {nome: (pasta_origem / nome).read_bytes() for nome in ("execucao.json", "anotacoes.csv", "deteccoes.csv")}
    manifesto = validar_manifesto(entradas["execucao.json"])
    anotacoes, registros_anotacoes = ler_objetos(entradas["anotacoes.csv"], manifesto, True)
    deteccoes, registros_deteccoes = ler_objetos(entradas["deteccoes.csv"], manifesto, False)
    try:
        import scipy
        import numpy as np
    except ModuleNotFoundError as erro:
        raise ValueError("Instale as dependências: python -m pip install -r analise/requirements.txt") from erro
    inicio = agora()
    # Uma avaliação nova não altera os arquivos nem as avaliações anteriores.
    pasta = (pasta_origem / "avaliacoes" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not pasta.is_relative_to(pasta_origem):
        raise ValueError("A pasta de avaliações precisa permanecer dentro da execução original.")
    relatorio = {
        "situacao": "em_andamento", "inicio_utc": inicio.isoformat(), "fim_utc": None,
        "execucao_origem": str(pasta_origem), "origem": manifesto["origem"],
        "algoritmo": manifesto.get("algoritmo"), "configuracao_sha256": manifesto.get("configuracao_sha256"),
        "dimensoes": manifesto["dimensoes"], "codigo_detector": manifesto.get("codigo"),
        "sha256_entradas": {nome: sha256(conteudo) for nome, conteudo in entradas.items()},
        "codigo_avaliador": codigo_avaliador(),
        "dependencias": {"python": platform.python_version(), "scipy": scipy.__version__, "numpy": np.__version__},
        "metricas_calculadas": False,
    }
    pasta.mkdir(parents=True, exist_ok=False)
    try:
        gravar_json(pasta / "avaliacao.json", relatorio)
        resultado = avaliar(anotacoes, deteccoes)
        tabelas_detalhadas(pasta, resultado, registros_anotacoes, registros_deteccoes)
        metricas = [
            {"avaliacao": "principal", "classe": classe, **valores}
            for classe, valores in resultado["principal"]["por_classe"].items()
        ]
        metricas.append({"avaliacao": "localizacao", "classe": "todas", **resultado["localizacao"]["metricas"]})
        gravar_csv(pasta / "metricas.csv", ["avaliacao", "classe", "tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1"], metricas)
        (pasta / "resumo.txt").write_text(resumir(resultado), encoding="utf-8")
        relatorio.update({"situacao": "concluida", "fim_utc": agora().isoformat(),
                          "metricas_calculadas": True, "resultados": resultado})
        gravar_json(pasta / "avaliacao.json", relatorio)
    except BaseException as erro:
        relatorio.update({"situacao": "falhou", "fim_utc": agora().isoformat(), "erro": f"{type(erro).__name__}: {erro}"})
        try:
            gravar_json(pasta / "avaliacao.json", relatorio)
        except OSError:
            pass
        print(f"Avaliação incompleta em: {pasta}", file=sys.stderr)
        raise
    print(resumir(resultado))
    return pasta


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia uma detecção já salva, sem executar o detector.")
    parser.add_argument("--execucao", type=Path, required=True, help="Pasta com execucao.json, anotacoes.csv e deteccoes.csv.")
    args = parser.parse_args()
    try:
        pasta = executar(args.execucao)
    except KeyboardInterrupt:
        print("Avaliação interrompida.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"Avaliação salva em: {pasta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
