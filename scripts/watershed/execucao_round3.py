"""Round3 pelo mesmo comando e fluxo de saídas do round2."""

from scripts.watershed import executar_rodada as comum
from scripts.watershed import execucao_round2 as base
from scripts.watershed.planejamento_round3 import conferir_origens, construir_plano, validar_plano
from algoritmos.classicos.variantes_watershed import configuracao_de_dict

RAIZ = comum.RAIZ
PLANO = RAIZ / "scripts/watershed/rodadas/round3.json"
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round3"
FONTES = (*base.FONTES, "scripts/watershed/planejamento_round3.py",
          "scripts/watershed/execucao_round3.py", "analise/relatorio_round3_watershed.py")
FONTES_EVOLUIDAS = base.FONTES_EVOLUIDAS | {
    "scripts/watershed/execucao_round2.py", "analise/relatorio_round2_watershed.py"}


def congelar_entradas(caminho=PLANO):
    return base.congelar_entradas(caminho, validar=validar_plano, construir=construir_plano,
                                 conferir=conferir_origens, fontes=FONTES, evoluidas=FONTES_EVOLUIDAS,
                                 referencia="round2")


def processar(dados):
    from analise.relatorio_round3_watershed import gerar_relatorio
    return comum.processar(dados, saida=SAIDA, ler_config=configuracao_de_dict,
                          executar_quadro=base.executar_quadro, nome_config=base.nome_configuracao,
                          relatorio=gerar_relatorio, referencia="round2")


def executar_argumentos(args):
    if args.somente_relatorio:
        from analise.relatorio_round3_watershed import gerar_relatorio
        print(gerar_relatorio(args.somente_relatorio))
    else:
        print("Conferindo plano, 178 imagens, controles e dependências do round3...", flush=True)
        dados = congelar_entradas()
        if args.conferir:
            print(f"Conferência concluída: 24 configurações, 178 imagens, {len(dados['hashes'])} origens íntegras. "
                  "1.068 casos de referência disponíveis. Detector não executado.")
        else:
            print(f"Rodada concluída: {processar(dados)}")
    return 0
