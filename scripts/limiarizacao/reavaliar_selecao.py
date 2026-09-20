"""Reavalia caixas salvas da seleção: indivíduos (0/2) e aglomerados (1)."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
import json
from pathlib import Path
import platform
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise import avaliacao_individuos as avaliador
from analise.relatorio_rodada import _carregar, _inteiro, _json
from scripts.avaliacao.avaliar_imagem import (
    CAMPOS_ORIGEM, agora, gravar_csv, gravar_json, ler_objetos, sha256,
)


PASTA_SELECAO = Path("resultados/frame-to-frame/limiarizacao/selecao")
BATCH_PADRAO = RAIZ / PASTA_SELECAO / "batch__20260920T012713968145Z"
PLANO_APROVADO_SHA256 = "20bacd6e77cc704db33f9b5525d6a8040b7987854130584ff1c9e7cb65a2980a"
VIDEOS = ("13", "29", "52", "54")
IDS = tuple(f"s{i:03d}" for i in range(1, 123))
CHAVES_QUADROS = {(video, quadro) for video in VIDEOS for quadro in range(0, 1401, 100)}
GRUPOS = ("individuos", "aglomerados")
CLASSES = (0, 2, 1)
CAMPOS_METRICAS = [
    *[f"{campo}_{grupo}" for grupo in GRUPOS
      for campo in ("tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1")],
    *[f"{campo}_classe_{classe}" for classe in CLASSES
      for campo in ("anotacoes", "localizadas", "perdidas", "recall")],
    "pares_corretos", "pares_incorretos", "pares_total", "acuracia_condicional",
    "matriz_0_0", "matriz_0_2", "matriz_2_0", "matriz_2_2",
]
CAMPOS_RESUMO = ["configuracao_id", "pasta_origem", "quantidade_quadros", *CAMPOS_METRICAS]
CAMPOS_RANKING = [
    "posicao_visual", "rank_f1_individuos", "quantidade_empatadas", "empate_no_corte_5",
    "sem_casos", "f1_numerador", "f1_denominador", *CAMPOS_RESUMO,
]
CAMPOS_PARES = [
    *CAMPOS_ORIGEM, "indice_anotacao", "indice_deteccao", "classe_anotacao",
    "classe_deteccao", "iou", "grupo", "classe_correta",
]
CAMPOS_PENDENTES = [*CAMPOS_ORIGEM, "tipo", "indice", "classe", "grupo"]
FONTES_CODIGO = (
    "scripts/limiarizacao/reavaliar_selecao.py",
    "scripts/avaliacao/avaliar_imagem.py",
    "analise/__init__.py",
    "analise/avaliacao_deteccao.py",
    "analise/avaliacao_individuos.py",
    "analise/relatorio_rodada.py",
    "analise/relatorio_individuos.py",
)
REGRAS_RANKING = {
    "principal": "F1 de indivíduos (classes 0 e 2 agrupadas), por contagens agregadas.",
    "empate": "Fração exata 2*TP/(2*TP+FP+FN); rank denso. Não há desempate por outra métrica.",
    "ordem_visual": "ID crescente dentro do empate, sem decidir promoção.",
    "empate_no_corte_5": "Verdadeiro para todo o grupo empatado que ocupa posições dos dois lados do corte 5/6.",
    "sem_casos": "TP=FP=FN=0: F1 e rank ausentes, linhas após as configurações com F1 definido.",
    "classificacao": "Trocas 0/2 são diagnóstico secundário condicionado aos indivíduos pareados.",
    "decisao": "Nenhuma configuração é promovida automaticamente; as cinco finalistas exigem discussão.",
}


def _relativo(caminho: Path) -> str:
    return caminho.resolve().relative_to(RAIZ.resolve()).as_posix()


def _ler(caminho: Path, hashes: dict[str, str], *, congelados: bool = False) -> bytes:
    caminho = caminho.resolve(strict=True)
    if (not caminho.is_relative_to((RAIZ / PASTA_SELECAO).resolve())
            or caminho.suffix.lower() not in (".json", ".csv") or not caminho.is_file()):
        raise ValueError("A reavaliação lê somente CSV/JSON dentro dos resultados de seleção.")
    conteudo = caminho.read_bytes()
    nome = _relativo(caminho)
    digest = sha256(conteudo)
    if (congelados and nome not in hashes) or (nome in hashes and hashes[nome] != digest):
        raise ValueError(f"A entrada mudou durante a reavaliação: {nome}.")
    hashes[nome] = digest
    return conteudo


def _csv(conteudo: bytes) -> tuple[list[str], list[dict]]:
    leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")), strict=True)
    campos = leitor.fieldnames
    if not campos or len(campos) != len(set(campos)):
        raise ValueError("CSV sem cabeçalho válido ou com colunas duplicadas.")
    linhas = list(leitor)
    if any(None in linha or any(valor is None for valor in linha.values()) for linha in linhas):
        raise ValueError("CSV contém linhas com quantidade de colunas divergente.")
    return campos, linhas


def _chave(linha: dict) -> tuple[str, int]:
    return str(linha["video_id"]), _inteiro(linha["quadro"], "quadro")


def _separar(campos: list[str], linhas: list[dict], previstas: set) -> dict:
    if not set(CAMPOS_ORIGEM).issubset(campos):
        raise ValueError("Tabela de objetos sem identificação completa da origem.")
    grupos = defaultdict(list)
    for linha in linhas:
        chave = _chave(linha)
        if chave not in previstas:
            raise ValueError(f"Tabela contém quadro não previsto: {chave}.")
        grupos[chave].append(linha)
    return grupos


def _conteudo_quadro(campos: list[str], linhas: list[dict]) -> bytes:
    buffer = StringIO(newline="")
    escritor = csv.DictWriter(buffer, fieldnames=campos)
    escritor.writeheader()
    escritor.writerows(linhas)
    return buffer.getvalue().encode("utf-8")


def _assinatura_anotacoes(anotacoes, largura: int, altura: int) -> tuple:
    return (largura, altura, tuple(sorted(
        (o.indice, o.classe, o.x, o.y, o.largura, o.altura) for o in anotacoes
    )))


def _carregar_configuracao(dados: dict, identificador: str, *, congelados: bool = False) -> list[dict]:
    resumo = dados["totais_por_id"][identificador]
    pasta = (RAIZ / resumo["pasta"]).resolve(strict=True)
    hashes = dados["origens_sha256"]

    def ler(nome: str) -> bytes:
        return _ler(pasta / nome, hashes, congelados=congelados)

    registro = _json(ler("execucao.json"))
    parametros = _json(ler("configuracao.json"))
    hash_parametros = sha256(json.dumps(parametros, sort_keys=True, separators=(",", ":"),
                                        allow_nan=False).encode("utf-8"))
    if (parametros != dados["configuracoes"][identificador]["parametros"]
            or hash_parametros != registro.get("configuracao_sha256")):
        raise ValueError(f"Parâmetros salvos divergentes em {identificador}.")
    campos_quadros, linhas_quadros = _csv(ler("por_quadro.csv"))
    obrigatorios = {*CAMPOS_ORIGEM, "imagem_largura_px", "imagem_altura_px",
                    "quantidade_anotacoes", "quantidade_deteccoes",
                    *[f"{nome}_classe_{c}" for c in CLASSES for nome in ("anotacoes", "deteccoes")]}
    if not obrigatorios.issubset(campos_quadros):
        raise ValueError(f"Resumo de quadros incompleto em {identificador}.")
    por_chave = {_chave(linha): linha for linha in linhas_quadros}
    if len(por_chave) != len(linhas_quadros) or set(por_chave) != CHAVES_QUADROS:
        raise ValueError(f"Os 60 quadros devem estar completos e sem repetição em {identificador}.")
    campos_a, linhas_a = _csv(ler("anotacoes.csv"))
    campos_d, linhas_d = _csv(ler("deteccoes.csv"))
    if "algoritmo" not in campos_d or any(l["algoritmo"] != "limiarizacao" for l in linhas_d):
        raise ValueError(f"Algoritmo das detecções divergente em {identificador}.")
    grupos_a = _separar(campos_a, linhas_a, CHAVES_QUADROS)
    grupos_d = _separar(campos_d, linhas_d, CHAVES_QUADROS)
    resultado = []
    contagens = defaultdict(Counter)
    for previsto in dados["plano"]["quadros"]:
        chave = _chave(previsto)
        linha = por_chave[chave]
        origem = {campo: linha[campo] for campo in CAMPOS_ORIGEM}
        if (origem["imagem"] != previsto["imagem"] or origem["anotacao"] != previsto["anotacao"]
                or origem["tempo_segundos"] != ""):
            raise ValueError(f"Origem do quadro divergente em {identificador}/{chave}.")
        largura = _inteiro(linha["imagem_largura_px"], "largura")
        altura = _inteiro(linha["imagem_altura_px"], "altura")
        if largura == 0 or altura == 0:
            raise ValueError("As dimensões do quadro devem ser positivas.")
        manifesto = {
            "situacao": "concluida", "origem": origem,
            "dimensoes": {"largura": largura, "altura": altura},
            "quantidade_anotacoes": _inteiro(linha["quantidade_anotacoes"], "quantidade_anotacoes"),
            "quantidade_deteccoes": _inteiro(linha["quantidade_deteccoes"], "quantidade_deteccoes"),
        }
        anotacoes, _ = ler_objetos(_conteudo_quadro(campos_a, grupos_a[chave]), manifesto, anotacao=True)
        deteccoes, _ = ler_objetos(_conteudo_quadro(campos_d, grupos_d[chave]), manifesto, anotacao=False)
        for nome, objetos in (("anotacoes", anotacoes), ("deteccoes", deteccoes)):
            if {o.indice for o in objetos} != set(range(len(objetos))):
                raise ValueError(f"Índices devem ser contíguos em {identificador}/{chave}/{nome}.")
            atuais = Counter(o.classe for o in objetos)
            for classe in CLASSES:
                if atuais[classe] != _inteiro(linha[f"{nome}_classe_{classe}"], "contagem por classe"):
                    raise ValueError(f"Contagem por classe divergente em {identificador}/{chave}/{nome}.")
                contagens[(chave[0], nome)][classe] += atuais[classe]
        assinatura = _assinatura_anotacoes(anotacoes, largura, altura)
        if chave in dados["anotacoes_referencia"] and assinatura != dados["anotacoes_referencia"][chave]:
            raise ValueError(f"Anotações ou dimensões diferem entre configurações no quadro {chave}.")
        dados["anotacoes_referencia"][chave] = assinatura
        resultado.append({"origem": origem, "anotacoes": anotacoes, "deteccoes": deteccoes})
    for video in VIDEOS:
        antigo = dados["por_video"][(identificador, video)]
        for classe in CLASSES:
            if (contagens[(video, "anotacoes")][classe] != antigo[f"tp_classe_{classe}"] + antigo[f"fn_classe_{classe}"]
                    or contagens[(video, "deteccoes")][classe] != antigo[f"tp_classe_{classe}"] + antigo[f"fp_classe_{classe}"]):
                raise ValueError(f"Caixas e resumos salvos divergem em {identificador}/{video}/classe {classe}.")
    return resultado


def _prevalidar_caminhos(pasta: Path) -> dict[str, str]:
    """Restringe também as leituras do carregador compartilhado à seleção."""
    hashes = {}
    execucao = _json(_ler(pasta / "execucao.json", hashes))
    for nome in ("rodada.json", "resumo_configuracoes.csv", "resumo_por_video.csv"):
        _ler(pasta / nome, hashes)
    if hashes[_relativo(pasta / "rodada.json")] != PLANO_APROVADO_SHA256:
        raise ValueError("O plano salvo não é o plano aprovado das 122 candidatas.")
    registros = execucao.get("execucoes")
    if not isinstance(registros, list):
        raise ValueError("A lista de execuções do batch está ausente.")
    for item in registros:
        if not isinstance(item, dict) or not isinstance(item.get("pasta"), str):
            raise ValueError("Pasta de configuração inválida no manifesto.")
        _ler(RAIZ / item["pasta"] / "execucao.json", hashes)
    return hashes


def prevalidar(pasta: Path) -> dict:
    """Valida todas as entradas antes de permitir o primeiro pareamento."""
    pasta = pasta.expanduser().resolve(strict=True)
    if not pasta.is_relative_to((RAIZ / PASTA_SELECAO).resolve()):
        raise ValueError("Informe um batch dentro de resultados/frame-to-frame/limiarizacao/selecao.")
    hashes_iniciais = _prevalidar_caminhos(pasta)
    dados = _carregar(pasta)
    for nome, digest in dados["origens_sha256"].items():
        if hashes_iniciais.get(nome) != digest:
            raise ValueError("As entradas do batch mudaram durante a prevalidação.")
    plano = dados["plano"]
    if (plano.get("particao") != "selecao" or plano.get("algoritmo") != "limiarizacao"
            or plano.get("rodada") != "selecao" or plano.get("seed") != 42
            or dados["execucao"].get("etapa") != "selecao_imagens"
            or plano.get("exclusoes") != [] or dados["execucao"].get("exclusoes") != []
            or list(dados["configuracoes"]) != list(IDS)
            or len(plano["quadros"]) != 60 or {_chave(q) for q in plano["quadros"]} != CHAVES_QUADROS):
        raise ValueError("A reavaliação exige a seleção completa: s001–s122 e os 60 quadros acordados, sem exclusões.")
    dados["totais_por_id"] = {r["configuracao_id"]: r for r in dados["totais"]}
    dados["anotacoes_referencia"] = {}
    for identificador in IDS:
        _carregar_configuracao(dados, identificador)
    return dados


def _colunas_metricas(resultado: dict) -> dict:
    linha = {}
    for grupo in GRUPOS:
        for campo in ("tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1"):
            linha[f"{campo}_{grupo}"] = resultado["por_grupo"][grupo][campo]
    for classe in CLASSES:
        for campo in ("anotacoes", "localizadas", "perdidas", "recall"):
            linha[f"{campo}_classe_{classe}"] = resultado["cobertura_por_classe"][str(classe)][campo]
    classificacao = resultado["classificacao_individuos"]
    linha.update({
        "pares_corretos": classificacao["pares_corretos"],
        "pares_incorretos": classificacao["pares_incorretos"],
        "pares_total": classificacao["total"],
        "acuracia_condicional": classificacao["acuracia_condicional"],
    })
    for i, real in enumerate((0, 2)):
        for j, prevista in enumerate((0, 2)):
            linha[f"matriz_{real}_{prevista}"] = classificacao["matriz_confusao"][i][j]
    return linha


def construir_ranking(linhas: list[dict]) -> list[dict]:
    """Ordena frações exatas; nenhuma métrica secundária desfaz empates."""
    def fracao(linha: dict) -> Fraction | None:
        tp, fp, fn = (_inteiro(linha[f"{c}_individuos"], c) for c in ("tp", "fp", "fn"))
        return Fraction(2 * tp, 2 * tp + fp + fn) if tp + fp + fn else None

    valores = {r["configuracao_id"]: fracao(r) for r in linhas}
    if len(valores) != len(linhas):
        raise ValueError("Configuração repetida no ranking.")
    frequencias = Counter(valores.values())
    definidos = sorted({v for v in valores.values() if v is not None}, reverse=True)
    ranks = {valor: i + 1 for i, valor in enumerate(definidos)}
    ordenadas = sorted(linhas, key=lambda r: (
        valores[r["configuracao_id"]] is None,
        -valores[r["configuracao_id"]] if valores[r["configuracao_id"]] is not None else 0,
        r["configuracao_id"],
    ))
    corte = None
    if len(ordenadas) > 5:
        quinto = valores[ordenadas[4]["configuracao_id"]]
        sexto = valores[ordenadas[5]["configuracao_id"]]
        if quinto is not None and quinto == sexto:
            corte = quinto
    return [{
        "posicao_visual": i + 1,
        "rank_f1_individuos": ranks.get(valores[r["configuracao_id"]]),
        "quantidade_empatadas": frequencias[valores[r["configuracao_id"]]] if valores[r["configuracao_id"]] is not None else 0,
        "empate_no_corte_5": valores[r["configuracao_id"]] is not None and valores[r["configuracao_id"]] == corte,
        "sem_casos": valores[r["configuracao_id"]] is None,
        "f1_numerador": valores[r["configuracao_id"]].numerator if valores[r["configuracao_id"]] is not None else None,
        "f1_denominador": valores[r["configuracao_id"]].denominator if valores[r["configuracao_id"]] is not None else None,
        **r,
    } for i, r in enumerate(ordenadas)]


def _arquivar_codigo(pasta: Path) -> dict:
    hashes = {}
    with ZipFile(pasta / "codigo.zip", "x", compression=ZIP_DEFLATED) as arquivo:
        for nome in FONTES_CODIGO:
            conteudo = (RAIZ / nome).read_bytes()
            arquivo.writestr(nome, conteudo)
            hashes[nome] = sha256(conteudo)
    codigo = {"sha256_arquivos": hashes, "sha256_zip": sha256((pasta / "codigo.zip").read_bytes()),
              "commit": None, "arvore_modificada": None}
    try:
        codigo["commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        codigo["arvore_modificada"] = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return codigo


def _versoes() -> dict:
    resultado = {"python": platform.python_version()}
    for pacote in ("numpy", "scipy", "matplotlib", "reportlab"):
        try:
            resultado[pacote] = version(pacote)
        except PackageNotFoundError:
            resultado[pacote] = None
    return resultado


def gerar_relatorio(pasta: Path) -> Path:
    from analise.relatorio_individuos import gerar_relatorio as gerar
    pasta = pasta.expanduser().resolve(strict=True)
    if (not pasta.is_relative_to((RAIZ / PASTA_SELECAO).resolve())
            or pasta.parent.name != "reavaliacoes_individuos" or not pasta.is_dir()):
        raise ValueError("Informe uma pasta de reavaliação dentro dos resultados de seleção.")
    try:
        pdf = gerar(pasta)
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {
            "situacao": "falhou", "erro": f"{type(erro).__name__}: {erro}", "fim_utc": agora().isoformat(),
        })
        raise
    gravar_json(pasta / "relatorio.json", {
        "situacao": "concluido", "arquivo": _relativo(pdf), "fim_utc": agora().isoformat(),
    })
    return pdf


def reavaliar(pasta_batch: Path) -> Path:
    dados = prevalidar(pasta_batch)
    inicio = agora()
    destino = dados["pasta"] / "reavaliacoes_individuos"
    if destino.resolve().parent != dados["pasta"]:
        raise ValueError("O destino da reavaliação precisa permanecer dentro do batch de origem.")
    pasta = destino / inicio.strftime("%Y%m%dT%H%M%S%fZ")
    pasta.mkdir(parents=True, exist_ok=False)
    registro = {
        "tipo": "reavaliacao_individuos", "versao": 1, "situacao": "em_andamento",
        "origem_batch": _relativo(dados["pasta"]), "criterios": avaliador.CRITERIOS,
        "regras_ranking": REGRAS_RANKING, "configuracoes_previstas": len(IDS),
        "configuracoes_concluidas": 0, "quadros_por_configuracao": 60,
        "inicio_utc": inicio.isoformat(), "fim_utc": None,
        "origens_sha256": dict(dados["origens_sha256"]), "dependencias": _versoes(),
        "registro_relatorio": "relatorio.json",
    }
    manifesto = pasta / "execucao.json"
    gravar_json(manifesto, registro)
    try:
        registro["codigo"] = _arquivar_codigo(pasta)
        gravar_json(manifesto, registro)
        resumos, por_video = [], []
        for identificador in IDS:
            quadros = _carregar_configuracao(dados, identificador, congelados=True)
            pasta_config = pasta / identificador
            pasta_config.mkdir(exist_ok=False)
            resultados, linhas_quadros, pares, pendentes = [], [], [], []
            resultados_video = defaultdict(list)
            for quadro in quadros:
                origem = quadro["origem"]
                resultado = avaliador.avaliar(quadro["anotacoes"], quadro["deteccoes"])
                resultados.append(resultado)
                resultados_video[origem["video_id"]].append(resultado)
                linhas_quadros.append({**origem, **_colunas_metricas(resultado)})
                pares.extend({**origem, **par} for par in resultado["pares"])
                for tipo, campo, objetos in (
                    ("fn", "anotacoes_sem_par", quadro["anotacoes"]),
                    ("fp", "deteccoes_sem_par", quadro["deteccoes"]),
                ):
                    por_indice = {o.indice: o for o in objetos}
                    for indice in resultado[campo]:
                        classe = por_indice[indice].classe
                        pendentes.append({**origem, "tipo": tipo, "indice": indice, "classe": classe,
                                          "grupo": "aglomerados" if classe == 1 else "individuos"})
            agregado = avaliador.agregar(resultados)
            pasta_origem = dados["totais_por_id"][identificador]["pasta"]
            identidade = {"configuracao_id": identificador, "pasta_origem": pasta_origem}
            resumo = {**identidade, "quantidade_quadros": agregado["quantidade_quadros"],
                      **_colunas_metricas(agregado)}
            resumos.append(resumo)
            for video in VIDEOS:
                total_video = avaliador.agregar(resultados_video[video])
                por_video.append({**identidade, "video_id": video,
                                  "quantidade_quadros": total_video["quantidade_quadros"],
                                  **_colunas_metricas(total_video)})
            gravar_json(pasta_config / "avaliacao.json", {**identidade, **agregado})
            gravar_csv(pasta_config / "por_quadro.csv", [*CAMPOS_ORIGEM, *CAMPOS_METRICAS], linhas_quadros)
            gravar_csv(pasta_config / "pares.csv", CAMPOS_PARES, pares)
            gravar_csv(pasta_config / "pendentes.csv", CAMPOS_PENDENTES, pendentes)
            registro["configuracoes_concluidas"] += 1
            gravar_json(manifesto, registro)
            print(f"{identificador}: {registro['configuracoes_concluidas']}/{len(IDS)} configurações reavaliadas.")
        # Confere também os metadados/CSV já consumidos, antes de concluir.
        for nome in tuple(dados["origens_sha256"]):
            _ler(RAIZ / nome, dados["origens_sha256"], congelados=True)
        ranking = construir_ranking(resumos)
        gravar_csv(pasta / "resumo_configuracoes.csv", CAMPOS_RESUMO, resumos)
        gravar_csv(pasta / "resumo_por_video.csv", ["video_id", *CAMPOS_RESUMO], por_video)
        gravar_csv(pasta / "ranking.csv", CAMPOS_RANKING, ranking)
        arquivos_saida = [pasta / nome for nome in ("resumo_configuracoes.csv", "resumo_por_video.csv", "ranking.csv")]
        arquivos_saida.extend(pasta / identificador / nome for identificador in IDS
                              for nome in ("avaliacao.json", "por_quadro.csv", "pares.csv", "pendentes.csv"))
        registro.update({"situacao": "concluida", "fim_utc": agora().isoformat(),
                         "saidas_sha256": {_relativo(arquivo): sha256(arquivo.read_bytes()) for arquivo in arquivos_saida},
                         "empate_no_corte_5": any(r["empate_no_corte_5"] for r in ranking),
                         "configuracoes_sem_casos": [r["configuracao_id"] for r in ranking if r["sem_casos"]]})
        gravar_json(manifesto, registro)
    except BaseException as erro:
        registro.update({"situacao": "falhou", "fim_utc": agora().isoformat(),
                         "erro": f"{type(erro).__name__}: {erro}"})
        gravar_json(manifesto, registro)
        raise
    try:
        pdf = gerar_relatorio(pasta)
        print(f"Relatório: {pdf}")
    except Exception as erro:
        print(f"Métricas concluídas; o PDF não foi gerado: {erro}", file=sys.stderr)
        print(f'Para gerar somente o PDF: python scripts/limiarizacao/reavaliar_selecao.py --somente-relatorio "{pasta}"', file=sys.stderr)
    return pasta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    opcoes = parser.add_mutually_exclusive_group()
    opcoes.add_argument("--batch", type=Path, help="Batch completo de seleção; o padrão é fixo, sem busca pelo mais recente.")
    opcoes.add_argument("--somente-relatorio", type=Path, metavar="PASTA_REAVALIACAO",
                        help="Gera novo PDF das métricas salvas, sem recalcular pareamentos.")
    args = parser.parse_args(argv)
    try:
        if args.somente_relatorio is not None:
            print(f"Relatório: {gerar_relatorio(args.somente_relatorio)}")
        else:
            print(f"Reavaliação salva em: {reavaliar(args.batch if args.batch is not None else BATCH_PADRAO)}")
    except (ValueError, OSError, csv.Error, KeyError, TypeError, ImportError) as erro:
        parser.exit(1, f"Erro: {erro}\n")


if __name__ == "__main__":
    main()
