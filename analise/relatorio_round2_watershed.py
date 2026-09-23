"""Round2: mesmo relatório comparativo, com auditoria do ajuste de Otsu."""

from collections import defaultdict
import math
from pathlib import Path
import statistics

from analise import relatorio_rodada_watershed as base
from scripts.blobs.executar_inspecao import carregar_json
from scripts.watershed.planejamento_round2 import conferir_origens, validar_plano

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round2"
CAMPOS_SEGMENTACAO = ("limiar_otsu_original", "deslocamento_otsu", "limiar_efetivo",
                      "pixels_mascara", "pixels_imagem", "fracao_pixels_mascara")


def conferir_segmentacao(p, quadros, ler, pastas, *, conferir_fontes=conferir_origens):
    origens = {nome: ler("origens/" + nome) for nome in p["origens"]}
    conferir_fontes(p, origens)
    configs = {c["id"]: c["parametros"] for c in p["configuracoes"]}
    otsu_por_imagem, mascara_por_parametros = {}, {}
    for r in quadros:
        config = configs[r["configuracao_id"]]
        nome = f"{pastas[r['configuracao_id']]}/quadros/{r['video_id']}_frame_{r['quadro']}/segmentacao.json"
        m = carregar_json(ler(nome))
        if set(m) != set(CAMPOS_SEGMENTACAO):
            raise ValueError("Metadados de segmentação incompletos.")
        if any(type(m[k]) is not int for k in CAMPOS_SEGMENTACAO[:-1]):
            raise ValueError("Limiar e contagens de pixels devem ser inteiros.")
        t, delta, efetivo = (m[k] for k in CAMPOS_SEGMENTACAO[:3])
        if not 0 <= t <= 255 or delta != config["deslocamento_otsu"] or efetivo != min(255, max(0, t + delta)):
            raise ValueError("Limiar ajustado incoerente com a configuração.")
        pixels, total, fracao = (m[k] for k in CAMPOS_SEGMENTACAO[3:])
        if (total <= 0 or not 0 <= pixels <= total or type(fracao) not in (float, int)
                or not math.isfinite(fracao) or fracao != pixels / total):
            raise ValueError("Fração de máscara inválida.")
        if any(r[k] != str(m[k]) for k in CAMPOS_SEGMENTACAO):
            raise ValueError("Metadados divergem da tabela por quadro.")
        chave = r["video_id"], r["quadro"]
        if otsu_por_imagem.setdefault(chave, (t, total)) != (t, total):
            raise ValueError("Otsu original ou tamanho da imagem mudou entre configurações.")
        # Área, sementes e política não mudam a máscara que alimenta o watershed.
        chave_mascara = (*chave, delta, config["watershed"]["segmentacao"]["fechamento"]["tamanho"])
        if mascara_por_parametros.setdefault(chave_mascara, pixels) != pixels:
            raise ValueError("Máscaras de mesma parametrização têm contagens diferentes.")


def carregar(pasta):
    return base.carregar(pasta, rodada="round2", quantidade=32, avaliacoes=5696, casos_controle=712,
                         validador=validar_plano, saida=SAIDA, conferir_extra=conferir_segmentacao)


def pagina_otsu(dados, texto, inicio, cabecalho, valor):
    inicio("Ajuste de Otsu: contrastes e máscaras", 5)
    resumos = {r["configuracao_id"]: r for r in dados["resumos"]}
    por_config = defaultdict(list)
    for r in dados["quadros"]:
        por_config[r["configuracao_id"]].append(r)
    texto(30,487,"Comparação com ajuste zero: r2c11 (separar) e r2c12 (preservar). Demais parâmetros idênticos.",9,True)
    xs = [30,94,156,224,296,374,450,526,604,704]
    cabecalho(xs,["ID","Ajuste","Regra","F1","Delta F1","Delta TP","Delta FP","Delta FN","T médio","Máscara %"],459)
    ids = ["r2c17","r2c19","r2c11","r2c21","r2c23","r2c18","r2c20","r2c12","r2c22","r2c24"]
    itens = {r["id"]: r for r in dados["plano"]["configuracoes"]}
    for i, ident in enumerate(ids):
        p = itens[ident]["parametros"]
        separar = p["watershed"]["politica_aglomerados"] == "separar"
        r, ref = resumos[ident], resumos["r2c11" if separar else "r2c12"]
        delta = ("s/c" if any(x["f1_individuos"] in (None, "") for x in (r, ref)) else
                 f"{float(r['f1_individuos'])-float(ref['f1_individuos']):+.3f}")
        vals = [ident, f"{p['deslocamento_otsu']:+d}", "S" if separar else "P", valor(r["f1_individuos"]), delta,
                *[f"{int(r[k])-int(ref[k]):+d}" for k in ("tp_individuos", "fp_individuos", "fn_individuos")],
                f"{statistics.mean(int(q['limiar_efetivo']) for q in por_config[ident]):.1f}",
                f"{100*statistics.mean(float(q['fracao_pixels_mascara']) for q in por_config[ident]):.2f}"]
        for x, v in zip(xs, vals):
            texto(x,436-i*21,v,9)
    texto(30,209,"T médio = média do limiar efetivo nos 178 quadros. Máscara = média das frações após a morfologia.",8)
    texto(30,187,"Como interpretar os contrastes",12,True)
    texto(30,167,"Ajuste negativo inclui pixels menos claros; positivo exige pixels mais claros. Limiares limitados a [0, 255].")
    texto(30,149,"Mais pixels na máscara não significam mais acertos: podem alterar caixas, unir objetos ou aumentar ruído.")
    texto(30,131,"Delta F1 positivo favorece o ajuste testado; perda de TP e redução de FP devem ser examinadas em conjunto.")
    texto(30,113,"A área mínima de 144 impede previsões da classe 2 (limite 120). Sua cobertura e erros 0/2 continuam registrados.")
    texto(30,95,"Área, sementes, fechamento e políticas: consulte os pares no plano. Não há teste de significância nesta rodada.")
    texto(30,77,"Grade dirigida sem sorteio; seed 42 é mantida para identificação. Não existe nova estimativa de desempenho final.")
    texto(30,59,"segmentacao.json e resumo_por_quadro.csv preservam os limiares e pixels; codigo.zip preserva a implementação.",8)
    texto(30,41,"O relatório confere os metadados de todas as 5.696 avaliações e as referências arquivadas do round1.",8)


def gerar_relatorio(pasta):
    return base.gerar_relatorio(pasta, carregador=carregar, codigo_relatorio=__file__)
