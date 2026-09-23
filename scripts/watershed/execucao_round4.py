"""Round4 pelo mesmo comando, detector e estrutura de saídas das rodadas anteriores."""

from scripts.watershed import executar_rodada as comum
from scripts.watershed import execucao_round2 as base
from scripts.watershed import execucao_round3 as anterior
from scripts.watershed.planejamento_round4 import conferir_origens, construir_plano, validar_plano
from algoritmos.classicos.variantes_watershed import configuracao_de_dict

RAIZ = comum.RAIZ
PLANO = RAIZ / "scripts/watershed/rodadas/round4.json"
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round4"
FONTES = (*anterior.FONTES, "scripts/watershed/planejamento_round4.py",
          "scripts/watershed/execucao_round4.py", "analise/relatorio_round4_watershed.py")
# Apenas o comando e o relatório comuns mudam em relação ao código do round3.
FONTES_EVOLUIDAS = base.FONTES_EVOLUIDAS


def congelar_entradas(caminho=PLANO):
    return base.congelar_entradas(caminho, validar=validar_plano, construir=construir_plano,
                                 conferir=conferir_origens, fontes=FONTES, evoluidas=FONTES_EVOLUIDAS,
                                 referencia="round3")


def processar(dados):
    from analise.relatorio_round4_watershed import gerar_relatorio
    return comum.processar(dados, saida=SAIDA, ler_config=configuracao_de_dict,
                          executar_quadro=base.executar_quadro, nome_config=base.nome_configuracao,
                          relatorio=gerar_relatorio, referencia="round3")


def executar_argumentos(args):
    if args.somente_relatorio:
        from analise.relatorio_round4_watershed import gerar_relatorio
        print(gerar_relatorio(args.somente_relatorio))
    else:
        print("Conferindo plano, 178 imagens, controles e dependências do round4...", flush=True)
        dados = congelar_entradas()
        if args.conferir:
            print(f"Conferência concluída: 18 configurações, 178 imagens, {len(dados['hashes'])} origens íntegras. "
                  "1.068 casos de referência disponíveis. Detector não executado.")
        else:
            print(f"Rodada concluída: {processar(dados)}")
    return 0
