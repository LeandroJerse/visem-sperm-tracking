"""Organiza cópias de proveniência sem alterar resultados ou relatórios históricos."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from scripts.blobs.arquivos import gravar_json


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _bytes(dados: dict) -> bytes:
    return (json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _existe(caminho: Path) -> bool:
    return caminho.exists() or caminho.is_symlink()


def _interno(caminho: Path, pasta: Path, *, arquivo: bool = False) -> Path:
    resolvido = caminho.resolve(strict=arquivo)
    if (not resolvido.is_relative_to(pasta) or caminho.is_symlink()
            or (hasattr(caminho, "is_junction") and caminho.is_junction())
            or (arquivo and not caminho.is_file())):
        raise ValueError("Caminho deve permanecer dentro do batch, sem links.")
    return caminho


def _mover(origem: Path, destino: Path) -> None:
    if _existe(destino):
        raise ValueError(f"Destino já existe: {destino.name}.")
    origem.rename(destino)


def organizar_origens(pasta: Path, raiz: Path) -> dict:
    """Migra as 22 cópias; repetições apenas conferem a organização existente.

    O manifesto anterior e o mapa dos caminhos ficam no histórico. PDFs e suas
    referências continuam intactos; o mapa permite localizar as fontes antigas.
    Todas as condições são verificadas antes do primeiro movimento. Falhas antes
    da troca atômica do manifesto revertem os movimentos já efetuados.
    """
    raiz = Path(raiz).resolve(strict=True)
    pasta = Path(pasta).resolve(strict=True)
    esperada = (raiz / "resultados/videos/blobs/selecao").resolve()
    if (not esperada.is_relative_to(raiz) or pasta.parent != esperada
            or not pasta.is_dir() or not pasta.name.startswith("batch__")):
        raise ValueError("Informe um batch de vídeos de seleção de blobs dentro do projeto.")
    relativo = lambda p: p.relative_to(raiz).as_posix()
    manifesto_path = _interno(pasta / "execucao.json", pasta, arquivo=True)
    manifesto_bytes = manifesto_path.read_bytes()
    manifesto = json.loads(manifesto_bytes)
    if (manifesto.get("tipo") != "videos_selecao_blobs"
            or manifesto.get("situacao") != "concluida"):
        raise ValueError("A organização exige uma execução de vídeos concluída.")
    layout = manifesto.get("pasta_origens", ".")
    if layout not in (".", "origens"):
        raise ValueError("Pasta de origens desconhecida.")
    saidas = manifesto.get("saidas_sha256", {})
    plano_path = _interno(pasta / "plano.json", pasta, arquivo=True)
    plano_bytes = plano_path.read_bytes()
    if (_sha(plano_bytes) != manifesto.get("plano_sha256")
            or saidas.get(relativo(plano_path)) != _sha(plano_bytes)):
        raise ValueError("Hash do plano divergente.")
    fontes = json.loads(plano_bytes).get("proveniencia", {}).get("fontes", {})
    if not isinstance(fontes, dict) or len(fontes) != 22:
        raise ValueError("O plano deve conter as 22 fontes de proveniência.")
    destino = _interno(pasta / "origens", pasta)
    historico = _interno(destino / "historico_organizacao", pasta)
    anterior_path, registro_path = historico / "manifesto_anterior.json", historico / "registro.json"
    movimentos, mapa = [], []
    for nome, fonte in sorted(fontes.items()):
        if not isinstance(nome, str) or re.fullmatch(r"[A-Za-z0-9_]+", nome) is None:
            raise ValueError("Nome de origem inválido.")
        extensao = Path(fonte["arquivo"]).suffix
        digest = fonte["sha256"]
        if (extensao not in (".json", ".csv") or not isinstance(digest, str)
                or re.fullmatch(r"[a-f0-9]{64}", digest) is None):
            raise ValueError("Formato ou hash da origem inválido.")
        antigo = _interno(pasta / (nome + extensao), pasta)
        novo = _interno(destino / antigo.name, pasta)
        atual = novo if layout == "origens" else antigo
        _interno(atual, pasta, arquivo=True)
        if (_sha(atual.read_bytes()) != digest or saidas.get(relativo(atual)) != digest
                or manifesto.get("origens_sha256", {}).get(fonte["arquivo"]) != digest):
            raise ValueError(f"Hash da origem divergente: {nome}.")
        if _existe(antigo if layout == "origens" else novo):
            raise ValueError(f"Destino ou cópia duplicada já existe: {nome}.")
        movimentos.append((antigo, novo))
        mapa.append({"origem": relativo(antigo), "destino": relativo(novo), "sha256": digest})

    if layout == "origens":
        if _existe(historico):
            _interno(anterior_path, pasta, arquivo=True)
            _interno(registro_path, pasta, arquivo=True)
            anterior_bytes, registro_bytes = anterior_path.read_bytes(), registro_path.read_bytes()
            registro = json.loads(registro_bytes)
            if (registro.get("mapeamento") != mapa
                    or registro.get("manifesto_anterior") != {"arquivo": relativo(anterior_path), "sha256": _sha(anterior_bytes)}
                    or saidas.get(relativo(anterior_path)) != _sha(anterior_bytes)
                    or saidas.get(relativo(registro_path)) != _sha(registro_bytes)):
                raise ValueError("Histórico de organização incompatível com as origens.")
            anterior = json.loads(anterior_bytes)
            reconstituido = deepcopy(anterior)
            reconstituido["pasta_origens"] = "origens"
            for item in mapa:
                if reconstituido["saidas_sha256"].pop(item["origem"], None) != item["sha256"]:
                    raise ValueError("Manifesto anterior diverge do mapeamento.")
                reconstituido["saidas_sha256"][item["destino"]] = item["sha256"]
            reconstituido["saidas_sha256"].update({relativo(anterior_path): _sha(anterior_bytes),
                                                 relativo(registro_path): _sha(registro_bytes)})
            if reconstituido != manifesto:
                raise ValueError("Manifesto atual diverge da migração registrada.")
        return {"alterado": False, "arquivos_movidos": 0, "arquivos_conferidos": 22,
                "pasta_origens": "origens", "manifesto_sha256": _sha(manifesto_bytes)}

    temporario_manifesto = manifesto_path.with_suffix(".json.tmp")
    if (_existe(historico) or _existe(temporario_manifesto)
            or (_existe(destino) and not destino.is_dir())):
        raise ValueError("Destino de histórico ou arquivo temporário já existe.")
    registro = {"versao": 1, "tipo": "organizacao_origens_blobs",
                "data_utc": datetime.now(timezone.utc).isoformat(),
                "manifesto_anterior": {"arquivo": relativo(anterior_path), "sha256": _sha(manifesto_bytes)},
                "mapeamento": mapa,
                "preservacao": "Somente localização das cópias e índice de saídas alterados; plano, resultados, código arquivado e relatórios preservados."}
    registro_bytes = _bytes(registro)
    novo_manifesto = deepcopy(manifesto)
    novo_manifesto["pasta_origens"] = "origens"
    for item in mapa:
        novo_manifesto["saidas_sha256"].pop(item["origem"])
        novo_manifesto["saidas_sha256"][item["destino"]] = item["sha256"]
    novo_manifesto["saidas_sha256"].update({relativo(anterior_path): _sha(manifesto_bytes),
                                          relativo(registro_path): _sha(registro_bytes)})
    destino_existia = destino.exists()
    destino_criado = historico_criado = gravando_manifesto = False
    movidos, criados = [], []
    try:
        if not destino_existia:
            destino.mkdir(exist_ok=False)
            destino_criado = True
        historico.mkdir(exist_ok=False)
        historico_criado = True
        for caminho, blob in ((anterior_path, manifesto_bytes), (registro_path, registro_bytes)):
            with caminho.open("xb") as arquivo:
                criados.append(caminho)
                arquivo.write(blob)
        for antigo, novo in movimentos:
            _mover(antigo, novo)
            movidos.append((antigo, novo))
        for item in mapa:
            if _sha((raiz / item["destino"]).read_bytes()) != item["sha256"]:
                raise ValueError("Origem alterada durante a organização.")
        if manifesto_path.read_bytes() != manifesto_bytes:
            raise ValueError("Manifesto alterado durante a organização.")
        gravando_manifesto = True
        gravar_json(manifesto_path, novo_manifesto)
    except BaseException as erro:
        falhas = []
        for antigo, novo in reversed(movidos):
            try:
                _mover(novo, antigo)
            except Exception as reversao:
                falhas.append(f"{antigo.name}: {reversao}")
        if falhas:
            raise RuntimeError("Organização interrompida; histórico preservado, reversão incompleta: " + "; ".join(falhas)) from erro
        if gravando_manifesto and temporario_manifesto.is_file():
            temporario_manifesto.unlink()
        for criado in reversed(criados):
            if criado.is_file():
                criado.unlink()
        if historico_criado:
            historico.rmdir()
        if destino_criado:
            destino.rmdir()
        raise
    return {"alterado": True, "arquivos_movidos": 22, "arquivos_conferidos": 22,
            "pasta_origens": "origens", "manifesto_sha256": _sha(manifesto_path.read_bytes()),
            "historico": relativo(historico)}
