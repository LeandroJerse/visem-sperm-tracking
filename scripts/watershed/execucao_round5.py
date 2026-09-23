"""Round5 pelo mesmo comando, detector e estrutura de saídas das rodadas anteriores."""

from scripts.watershed import executar_rodada as comum
from scripts.watershed import execucao_round2 as base
from scripts.watershed import execucao_round4 as anterior
from scripts.watershed.planejamento_round5 import conferir_origens, construir_plano, validar_plano
from algoritmos.classicos.variantes_watershed import configuracao_de_dict

RAIZ = comum.RAIZ
PLANO = RAIZ / "scripts/watershed/rodadas/round5.json"
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round5"
FONTES = (*anterior.FONTES, "scripts/watershed/planejamento_round5.py",
          "scripts/watershed/execucao_round5.py", "analise/relatorio_round5_watershed.py")
# Apenas o comando e o relatório comuns mudam em relação ao código do round4.
FONTES_EVOLUIDAS = base.FONTES_EVOLUIDAS


def congelar_entradas(caminho=PLANO):
    return base.congelar_entradas(caminho, validar=validar_plano, construir=construir_plano,
                                 conferir=conferir_origens, fontes=FONTES, evoluidas=FONTES_EVOLUIDAS,
                                 referencia="round4")


def processar(dados):
    from analise.relatorio_round5_watershed import gerar_relatorio
    return comum.processar(dados, saida=SAIDA, ler_config=configuracao_de_dict,
                          executar_quadro=base.executar_quadro, nome_config=base.nome_configuracao,
                          relatorio=gerar_relatorio, referencia="round4")


def executar_argumentos(args):
    if args.somente_relatorio:
        from analise.relatorio_round5_watershed import gerar_relatorio
        print(gerar_relatorio(args.somente_relatorio))
    else:
        print("Conferindo plano, 178 imagens, controles e dependências do round5...", flush=True)
        dados = congelar_entradas()
        if args.conferir:
            print(f"Conferência concluída: 14 configurações, 178 imagens, {len(dados['hashes'])} origens íntegras. "
                  "1.068 casos de referência disponíveis. Detector não executado.")
        else:
            print(f"Rodada concluída: {processar(dados)}")
    return 0
