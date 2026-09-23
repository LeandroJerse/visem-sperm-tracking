"""Round3: ranking e contrastes locais, usando somente resultados salvos."""

from pathlib import Path

from analise import relatorio_rodada_watershed as base
from analise.relatorio_round2_watershed import conferir_segmentacao
from scripts.watershed.planejamento_round3 import conferir_origens, validar_plano

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round3"


def conferir_extras(p, quadros, ler, pastas):
    conferir_segmentacao(p, quadros, ler, pastas, conferir_fontes=conferir_origens)


def carregar(pasta):
    return base.carregar(pasta, rodada="round3", quantidade=24, avaliacoes=4272, casos_controle=1068,
                         validador=validar_plano, saida=SAIDA, conferir_extra=conferir_extras)


def pagina_contrastes(dados, texto, inicio, cabecalho, valor):
    inicio("Refinamentos: uma alteração por contraste", 5)
    resumos = {r["configuracao_id"]: r for r in dados["resumos"]}
    texto(30,487,"Delta = configuração nova menos seu controle na mesma rodada. Políticas e demais parâmetros iguais.",9,True)
    xs = [30,96,165,255,325,397,475,563,651,737]
    cabecalho(xs,["Controle","Nova","Alteração","Regra","F1 novo","Delta F1","Delta TP","Delta FP","Delta FN","Peq."],461)
    novos = [c for c in dados["plano"]["configuracoes"] if c["contraste_com"]]
    for i, item in enumerate(novos):
        p = item["parametros"]; w = p["watershed"]
        if item["bloco"] == "area":
            alteracao = f"Área {w['segmentacao']['area_minima']}"
        elif item["bloco"] == "semente":
            alteracao = f"Semente {w['fracao_semente']:.2f}"
        else:
            alteracao = f"Otsu {p['deslocamento_otsu']:+d}"
        a, b = resumos[item["contraste_com"]], resumos[item["id"]]
        delta = ("s/c" if any(r["f1_individuos"] in (None, "") for r in (a,b)) else
                 f"{float(b['f1_individuos'])-float(a['f1_individuos']):+.5f}")
        vals = [item["contraste_com"], item["id"], alteracao,
                "S" if w["politica_aglomerados"] == "separar" else "P", valor(b["f1_individuos"]), delta,
                *[f"{int(b[k])-int(a[k]):+d}" for k in ("tp_individuos", "fp_individuos", "fn_individuos")],
                f"{b['localizadas_classe_2']}/{b['anotacoes_classe_2']}"]
        for x, v in zip(xs, vals):
            texto(x,440-i*18,v,8)
    texto(30,111,"Peq. = pequenos localizados/anotados. Trocas 0/2 permanecem erros de classificação separados.",8)
    texto(30,94,"Área 132 impede emitir classe 2; área 120 permite somente regiões de 120 pixels; área 108 permite 108 a 120.",8)
    texto(30,77,"As sementes 0,35 / 0,50 / 0,60 / 0,75 também podem ser comparadas com área 120 e Otsu sem ajuste.",8)
    texto(30,60,"Comparações descritivas de desenvolvimento: diferenças pequenas não demonstram superioridade em dados reservados.",8)
    texto(30,43,"Limiares e frações de máscara ficam em segmentacao.json e resumo_por_quadro.csv. Sem mudança das métricas.",8)


def gerar_relatorio(pasta):
    return base.gerar_relatorio(pasta, carregador=carregar, codigo_relatorio=__file__, pagina_extra=pagina_contrastes)
