"""Round4: contrastes de limiar, área, semente e fechamento em resultados salvos."""

from pathlib import Path

from analise import relatorio_rodada_watershed as base
from analise.relatorio_round2_watershed import conferir_segmentacao
from scripts.watershed.planejamento_round4 import conferir_origens, validar_plano

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round4"


def conferir_extras(p, quadros, ler, pastas):
    conferir_segmentacao(p, quadros, ler, pastas, conferir_fontes=conferir_origens)


def carregar(pasta):
    return base.carregar(pasta, rodada="round4", quantidade=18, avaliacoes=3204, casos_controle=1068,
                         validador=validar_plano, saida=SAIDA, conferir_extra=conferir_extras)


def pagina_contrastes(dados, texto, inicio, cabecalho, valor):
    inicio("Refinamentos próximos de Otsu -5", 5)
    resumos = {r["configuracao_id"]: r for r in dados["resumos"]}
    texto(30,487,"Cada linha altera um parâmetro frente ao controle r4c03/r4c04, na mesma política. Delta = nova menos controle.",9,True)
    xs = [30,96,165,255,325,397,475,563,651,737]
    cabecalho(xs,["Controle","Nova","Alteração","Regra","F1 novo","Delta F1","Delta TP","Delta FP","Delta FN","Peq."],461)
    novos = [c for c in dados["plano"]["configuracoes"] if c["contraste_com"]]
    for i, item in enumerate(novos):
        p = item["parametros"]; w = p["watershed"]
        if item["bloco"] == "area":
            alteracao = f"Área {w['segmentacao']['area_minima']}"
        elif item["bloco"] == "semente":
            alteracao = f"Semente {w['fracao_semente']:.2f}"
        elif item["bloco"] == "fechamento":
            tamanho = w["segmentacao"]["fechamento"]["tamanho"]
            alteracao = f"Fech. {tamanho}x{tamanho}"
        else:
            alteracao = f"Otsu {p['deslocamento_otsu']:+d}"
        a, b = resumos[item["contraste_com"]], resumos[item["id"]]
        delta = ("s/c" if any(r["f1_individuos"] in (None, "") for r in (a,b)) else
                 f"{float(b['f1_individuos'])-float(a['f1_individuos']):+.6f}")
        vals = [item["contraste_com"], item["id"], alteracao,
                "S" if w["politica_aglomerados"] == "separar" else "P", valor(b["f1_individuos"]), delta,
                *[f"{int(b[k])-int(a[k]):+d}" for k in ("tp_individuos", "fp_individuos", "fn_individuos")],
                f"{b['localizadas_classe_2']}/{b['anotacoes_classe_2']}"]
        for x, v in zip(xs, vals):
            texto(x,440-i*23,v,8)
    texto(30,137,"Controles: r4c01/r4c02 mantêm Otsu 0; r4c03/r4c04 usam -5 e semente 0,35; r4c05/r4c06 usam -5 e 0,75.",8)
    texto(30,111,"Peq. = pequenos localizados/anotados. Trocas 0/2 permanecem erros de classificação separados.",8)
    texto(30,94,"Área mínima 132/144 impede emitir classe 2; com mínimo 120, somente regiões de 120 pixels podem recebê-la.",8)
    texto(30,77,"A área mínima altera o filtro; limiar, sementes e fechamento podem alterar candidatos, caixas e pareamentos.",8)
    texto(30,60,"Comparações descritivas de desenvolvimento. As posições não selecionam finalistas nem demonstram significância.",8)
    texto(30,43,"Limiares e frações de máscara ficam em segmentacao.json e resumo_por_quadro.csv. Critérios preservados.",8)


def gerar_relatorio(pasta):
    return base.gerar_relatorio(pasta, carregador=carregar, codigo_relatorio=__file__, pagina_extra=pagina_contrastes)
