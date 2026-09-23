"""Round5: combinações e contrastes controlados em resultados salvos."""

from pathlib import Path

from analise import relatorio_rodada_watershed as base
from analise.relatorio_round2_watershed import conferir_segmentacao
from scripts.watershed.planejamento_round5 import conferir_origens, validar_plano

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round5"


def conferir_extras(p, quadros, ler, pastas):
    conferir_segmentacao(p, quadros, ler, pastas, conferir_fontes=conferir_origens)


def carregar(pasta):
    return base.carregar(pasta, rodada="round5", quantidade=14, avaliacoes=2492, casos_controle=1068,
                         validador=validar_plano, saida=SAIDA, conferir_extra=conferir_extras)


def pagina_contrastes(dados, texto, inicio, cabecalho, valor):
    inicio("Combinações com comparações controladas", 5)
    resumos = {r["configuracao_id"]: r for r in dados["resumos"]}
    configs = {c["id"]: c for c in dados["plano"]["configuracoes"]}
    texto(30,487,"Cada linha muda um parâmetro na mesma política. Delta = nova menos referência; ganhos não são somados.",9,True)
    xs = [30,96,165,255,325,397,475,563,651,737]
    cabecalho(xs,["Referência","Nova","Alteração","Regra","F1 novo","Delta F1","Delta TP","Delta FP","Delta FN","Peq."],461)
    for i, contraste in enumerate(dados["plano"]["contrastes"]):
        ref, nova = contraste["referencia"], contraste["nova"]
        p = configs[nova]["parametros"]; w = p["watershed"]
        eixo = contraste["eixo"]
        if eixo == "area":
            alteracao = f"Área {w['segmentacao']['area_minima']}"
        elif eixo == "semente":
            alteracao = f"Semente {w['fracao_semente']:.2f}"
        elif eixo == "fechamento":
            t = w["segmentacao"]["fechamento"]["tamanho"]
            alteracao = f"Fech. {t}x{t}"
        else:
            alteracao = f"Otsu {p['deslocamento_otsu']:+d}"
        a, b = resumos[ref], resumos[nova]
        delta = ("s/c" if any(r["f1_individuos"] in (None, "") for r in (a,b)) else
                 f"{float(b['f1_individuos'])-float(a['f1_individuos']):+.6f}")
        vals = [ref, nova, alteracao, "S" if w["politica_aglomerados"] == "separar" else "P",
                valor(b["f1_individuos"]), delta,
                *[f"{int(b[k])-int(a[k]):+d}" for k in ("tp_individuos", "fp_individuos", "fn_individuos")],
                f"{b['localizadas_classe_2']}/{b['anotacoes_classe_2']}"]
        for x, v in zip(xs, vals):
            texto(x,440-i*20,v,8)
    texto(30,137,"São 14 comparações sobre oito configurações novas; repetir uma configuração na tabela não acrescenta execuções.",8)
    texto(30,115,"r5c01/02, 07/08, 09/10 e 11/12 cruzam Otsu -5/-3 com fechamento 5/3, fixando semente 0,50 e área 120.",8)
    texto(30,97,"r5c03/04 e 05/06 isolam a mudança de semente. r5c13/14 verificam área 144 contra r5c01/02.",8)
    texto(30,79,"Peq. = pequenos localizados/anotados. Trocas 0/2 são registradas separadamente; mínimo 144 impede emitir classe 2.",8)
    texto(30,61,"Comparações descritivas de desenvolvimento: não selecionam finalistas nem demonstram significância.",8)
    texto(30,43,"Mesmos 178 quadros, caixas e critérios. A seleção em outros quadros ocorre após a análise desta rodada.",8)


def gerar_relatorio(pasta):
    return base.gerar_relatorio(pasta, carregador=carregar, codigo_relatorio=__file__, pagina_extra=pagina_contrastes)
