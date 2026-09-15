from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace(name, old, new):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise ValueError(f'Missing text: {name}: {old[:80]}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
        '| Próximo marco | Preparar protocolo e garantias de completude da validação dos dois finalistas nos quatro vídeos 14/19/36/52 |',
        '| Revisão geral de alinhamento | Aprovada com controles documentados; 3.248 arquivos e 17.753 conferências de integridade, 502 testes antes das alterações |\n'
        '| Preparação da validação v3 | Plano e executor estrito implementados para 2 × 5.850 = 11.700 avaliações; fontes ainda não abertas nesta etapa |\n'
        '| Próximo marco | Executar a validação registrada depois do commit e conferir as oito runs, sem congelamento automático |')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
        'Antes da validação, registrar agregação e desempates próprios para os quatro\nvídeos, orçamento e configurações identificadas por hash; garantir oito runs\ncompletas, leitura estrita do GT e interrupção diante de dados incompletos.\nOs utilitários da busca exigem 12 vídeos e não devem ser aplicados diretamente\ncomo agregador da futura validação.',
        'O [plano de validação](../metodologia/VALIDACAO_THRESHOLD_V3.md) registra\nagregação, desempates, orçamento e hashes dos finalistas. O coordenador próprio\nexige oito runs completas, GT estrito, leitura até o fim e reconciliação dos\nCSVs; a agregação específica dá peso igual aos quatro vídeos. A\n[revisão geral](REVISAO_GERAL_20260908.md) registra alinhamento e limites.')
replace('docs/algoritmos/deteccao/threshold_fixo.md',
        'O próximo marco é **preparar o protocolo de validação\ndos dois finalistas nos vídeos completos 14/19/36/52**. Antes de abrir essas\nfontes, registrar critérios de agregação e desempate, orçamento, identidades\ndas configurações e verificações que recusem vídeos truncados, GT inválido\nou comparações incompletas. O executor completo existe, mas esse contrato\nde oito runs e a agregação dos quatro vídeos ainda precisam ser preparados.',
        'O próximo marco é **executar a validação registrada das duas finalistas**.\nO [protocolo prospectivo](../../metodologia/VALIDACAO_THRESHOLD_V3.md) e o\nexecutor estrito fixam 11.700 avaliações em oito runs completas, critérios\nde seleção, orçamento e hashes. O vídeo 52 possui 1.440 quadros; os outros\ntrês, 1.470. Fontes de validação ainda não foram abertas nesta preparação.')
replace('docs/metodologia/PROTOCOLO.md',
        'Preparar agora uma avaliação de **duas configurações × quatro\nvídeos completos de validação: 14, 19, 36 e 52**. Antes de consultar essas\nfontes, o registro deve fixar os parâmetros e hashes dos dois finalistas,\na agregação e o desempate entre quatro vídeos, o orçamento e o tratamento\nde falhas. O desempate histórico por recall, latência e memória acima não\nsubstitui esse registro; tampouco se deve transportar silenciosamente o\ndesempate da triagem de treino para outra etapa.',
        'O registro separado [VALIDACAO_THRESHOLD_V3.md](VALIDACAO_THRESHOLD_V3.md)\nfixa **duas configurações × quatro vídeos completos: 14, 19, 36 e 52**,\ncom 11.700 avaliações. Ordena por F1 macro, recall macro, MAE de contagem\nmacro e identificador, sem timing ou sensibilidades na seleção. O YAML\nidentifica parâmetros, pais e inventário por hash e fixa orçamento e falhas.\nO executor exige Git limpo, GT estrito, leitura integral e hashes inalterados.\nEssa regra prospectiva substitui os desempates históricos para esta bateria.')

replace('docs/projeto/NAVEGACAO.md',
        '   finalistas de treino, sem promoção. O próximo marco é preparar protocolo\n   e executor de validação; não iniciar validação ou teste sem a preparação\n   e o protocolo correspondentes. Resultados registrados em `bd2d216`;\n   executor, protocolo e runs permanecem em `da057ef`.\n   Consulte a seção 12.',
        '   finalistas de treino, sem promoção. A revisão geral confirmou o alinhamento\n   e levou à preparação do executor estrito e do protocolo de validação.\n   Consulte a seção 13 para esta etapa; a seção 12 preserva o refinamento\n   registrado em `bd2d216`, com execução em `da057ef`.')
with (ROOT / 'docs/projeto/NAVEGACAO.md').open('a', encoding='utf-8') as f:
    f.write('''

## 13. Revisão geral e validação das duas finalistas — 08/09/2026

[Parecer de alinhamento](REVISAO_GERAL_20260908.md) e
[plano científico](../metodologia/VALIDACAO_THRESHOLD_V3.md).
A revisão basal conferiu 3.248 arquivos e 17.753 itens sem divergências;
502 testes passaram antes das novas implementações. Não exige reinício.

| Parte | Local |
|---|---|
| Plano imutável antes dos dados | [validation_v3.yaml](../../configs/detection/threshold/validation_v3.yaml) |
| Execução das oito runs | [validate.py](../../script/detection/test/threshold/validate.py) |
| GT explícito, inventário, hashes e identidade do vídeo | [strict_inputs.py](../../src/detection/strict_inputs.py) e [io.py](../../src/detection/io.py) |
| Decodificação integral e EOF adicional | [runner.py](../../src/detection/runner.py) com FullVideoInput obrigatório nesta bateria |
| Conferência por quadro dos CSVs | [validation_frame_checks.py](../../src/experiments/validation_frame_checks.py) |
| Pais, finalistas, agregação e seleção | [detection_validation.py](../../src/experiments/detection_validation.py) |
| Comandos oficiais | [script/README.md](../../script/README.md#validação-completa-dos-dois-finalistas-v3) |

Plano: T219/o0/c2 e T218/o0/c2; 14/19/36 com 1.470 quadros, 52 com
1.440. São 5.850 quadros por configuração e 11.700 avaliações. O dry-run
lê só metadados. A execução exige Git limpo e orçamento de 1.800 s, 2 GiB
de RSS/artefatos e 2.000 previsões por quadro, sem truncamento. Qualquer
falha invalida a seleção; preservar runs incompletas. Não usar a CLI de
split legada como atalho e não congelar automaticamente o resultado.

Os controles futuros da hipótese são janelas comuns, somente informação
até t, elegibilidade individual 0/2 e ADE de todos os passos 1..H. O teste
histórico já foi exposto; quatro vídeos limitam inferência. Folds exigem
seleção dentro dos treinos externos, sem alegar restauração de cegueira.
''')
replace('docs/projeto/mapa-tcc-didatico.html',
        '<main id="conteudo" class="content">',
        '''<main id="conteudo" class="content">
        <section id="validacao-threshold-v3" class="section">
          <span class="kicker">Agora · revisão geral e preparação da validação · 08/09/2026</span>
          <h2>O TCC está alinhado; vamos conferir as finalistas em vídeos completos</h2>
          <p class="section-intro">A revisão conferiu <strong>3.248 arquivos e 17.753 itens de integridade</strong>, sem divergências. A suíte anterior às mudanças passou em 502 testes. O trabalho pode continuar sem recomeçar; a contribuição do fluxo à predição ainda precisa ser testada.</p>
          <div class="grid two">
            <article class="card"><h3>Próxima avaliação registrada</h3><p>T219/o0/c2 e T218/o0/c2 nos quatro vídeos completos 14/19/36/52. São <strong>11.700 avaliações</strong>; o vídeo 52 possui 1.440 quadros, e os outros três têm 1.470.</p><p>Escolha por F1 com peso igual por vídeo. Sensibilidades de 15/20 px serão descritivas. Não há congelamento automático ou abertura do teste.</p><p><a href="../metodologia/VALIDACAO_THRESHOLD_V3.md">Protocolo registrado</a> · <a href="../../configs/detection/threshold/validation_v3.yaml">Plano executável</a></p></article>
            <article class="card"><h3>O que a revisão mudou</h3><p>O novo executor recusa vídeo incompleto, GT inválido, métricas inconsistentes e artefatos alterados. A bateria só será iniciada após testes e commit.</p><p>Na etapa principal, os preditores usarão as mesmas janelas e nenhuma informação futura. ADE/FDE terão definição explícita por horizonte; quatro vídeos não sustentam promessas de significância.</p><p><a href="REVISAO_GERAL_20260908.md">Parecer completo</a> · <a href="NAVEGACAO.md">Guia para retomar</a></p></article>
          </div>
        </section>''')
replace('docs/projeto/mapa-tcc-didatico.html',
        '<span class="kicker">Agora · refinamento concluído e conferido · 08/09/2026</span>',
        '<span class="kicker">Treino concluído e conferido · 08/09/2026</span>')
