"""Preparação e execução do round2 pelo comando executar_rodada.py."""

from pathlib import Path

from algoritmos.classicos.variantes_watershed import configuracao_de_dict
from scripts.blobs.executar_inspecao import carregar_json
from scripts.limiarizacao.inspecionar_imagem import ler_anotacoes
from scripts.watershed import executar_rodada as comum
from scripts.watershed.planejamento import sha
from scripts.watershed.planejamento_round2 import conferir_origens, construir_plano, validar_plano
from scripts.watershed.saidas_round2 import executar_quadro

RAIZ = comum.RAIZ
PLANO = RAIZ / "scripts/watershed/rodadas/round2.json"
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round2"
FONTES = (*comum.FONTES, "algoritmos/classicos/variantes_watershed.py",
          "scripts/watershed/planejamento_round2.py", "scripts/watershed/execucao_round2.py",
          "scripts/watershed/saidas_round2.py", "analise/relatorio_round2_watershed.py")
# Alterações de infraestrutura necessárias para aceitar a segunda rodada.
# O detector, o escritor histórico e as métricas permanecem byte a byte iguais.
FONTES_EVOLUIDAS = {"scripts/watershed/executar_rodada.py", "analise/relatorio_rodada_watershed.py"}


def congelar_entradas(caminho=PLANO, *, validar=None, construir=None, conferir=None,
                     fontes=None, evoluidas=None, referencia="round1"):
    validar = validar_plano if validar is None else validar
    construir = construir_plano if construir is None else construir
    conferir = conferir_origens if conferir is None else conferir
    fontes = FONTES if fontes is None else fontes
    evoluidas = FONTES_EVOLUIDAS if evoluidas is None else evoluidas
    caminho = Path(caminho).resolve(strict=True)
    if not caminho.is_relative_to(RAIZ.resolve()):
        raise ValueError("Plano fora do projeto.")
    blob = caminho.read_bytes()
    p = validar(carregar_json(blob))
    if p != construir(RAIZ):
        raise ValueError("Plano difere da proposta congelada ou de suas origens.")
    hashes = {comum.relativo(caminho): sha(blob)}

    def ler(nome, digest):
        b = comum.interno(nome).read_bytes()
        if sha(b) != digest:
            raise ValueError(f"Arquivo alterado: {nome}.")
        hashes[nome] = digest
        return b

    origens = {nome: ler(ref["arquivo"], ref["sha256"]) for nome, ref in p["origens"].items()}
    m1 = conferir(p, origens)
    codigo = {nome: comum.interno(nome).read_bytes() for nome in fontes}
    for nome, digest in m1["codigo"]["sha256_arquivos"].items():
        if nome not in evoluidas and (nome not in codigo or sha(codigo[nome]) != digest):
            raise ValueError(f"Código histórico alterado: {nome}. Revisar compatibilidade.")
    deps = comum.dependencias()
    for nome in ("python", "numpy", "opencv", "scipy", "scikit-image"):
        if deps[nome] != m1["dependencias"][nome]:
            raise ValueError(f"Versão de {nome} diferente do {referencia} ({m1['dependencias'][nome]}).")
    for fonte in p["fontes_controles"]:
        origens[fonte["copia"]] = ler(fonte["arquivo"], fonte["sha256"])
    entradas = []
    for q in p["quadros"]:
        imagem = ler(q["imagem"], q["imagem_sha256"])
        anotacao = ler(q["anotacao"], q["anotacao_sha256"])
        entrada = {"quadro": q, "imagem_bytes": imagem, "anotacao_bytes": anotacao,
                   "anotacoes": ler_anotacoes(anotacao)}
        comum.decodificar(entrada)
        entradas.append(entrada)
    return {"plano": p, "plano_bytes": blob, "entradas": entradas, "origens": origens,
            "hashes": hashes, "codigo": codigo, "dependencias": deps}


def nome_configuracao(item, config, instante):
    p, delta = config.watershed, config.deslocamento_otsu
    s = p.segmentacao
    politica = "preservar" if p.politica_aglomerados == "preservar_por_area" else "separar"
    ajuste = f"m{abs(delta)}" if delta < 0 else f"p{delta}"
    return (f"{item['id']}__otsu-d{ajuste}-claro-s{p.fracao_semente:g}-{politica}"
            f"-amin{s.area_minima}-fec{s.fechamento.tamanho}__cfg-{item['parametros_sha256'][:12]}__{instante}")


def processar(dados):
    from analise.relatorio_round2_watershed import gerar_relatorio
    return comum.processar(dados, saida=SAIDA, ler_config=configuracao_de_dict,
                          executar_quadro=executar_quadro, nome_config=nome_configuracao,
                          relatorio=gerar_relatorio, referencia="round1")


def executar_argumentos(args):
    if args.somente_relatorio:
        from analise.relatorio_round2_watershed import gerar_relatorio
        print(gerar_relatorio(args.somente_relatorio))
    else:
        print("Conferindo plano, 178 imagens, controles e dependências do round2...", flush=True)
        dados = congelar_entradas()
        if args.conferir:
            print(f"Conferência concluída: 32 configurações, 178 imagens, {len(dados['hashes'])} origens íntegras. "
                  "712 casos de referência disponíveis. Detector não executado.")
        else:
            print(f"Rodada concluída: {processar(dados)}")
    return 0
