"""Synchronize documentary status after verified results have been published.

Importing this module has no side effects. Call apply(root) only after the
independent search QA and publish_classical_edition.py have succeeded. The
function edits ignored HTML components and the local atlas, never scientific
artifacts, source code, tracked documentation, JavaScript or CSS.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def _once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Expected one documentary anchor, found {text.count(old)}: {old[:100]}")
    return text.replace(old, new, 1)


def _algorithms(text: str) -> str:
    changes = [
        ('correspondem ao marco 8a, sem novos experimentos nesta atualização documental.',
         'incluem a busca comparativa de detecção concluída e conferida em 11/09/2026. O marco 8a continua sendo a evidência mais recente da frente de fluxo. A geração deste relatório não executa algoritmos; os resultados vêm das runs identificadas em <a href="#comparacao-classicos-20260911">resultados da comparação</a>.'),
        ('<strong>Estado:</strong> implementações e testes sintéticos existentes, além de pilotos históricos; sem conclusão pelo ciclo v3 atualmente concluído para o limiar fixo.',
         '<strong>Estado em 11/09:</strong> Otsu e adaptativo participaram da busca comparativa conferida, com 4 e 18 configurações, respectivamente, nos mesmos 576 quadros dos 12 treinos. Foram selecionadas duas candidatas de cada família para a próxima etapa. Refinamento e validação completa dos novos métodos permanecem pendentes; não há promoção ou conclusão de generalização.'),
        ('<strong>Estado de ambos:</strong> código e verificações sintéticas, com exploração histórica; avaliação comparativa prospectiva ainda pendente.',
         '<strong>Estado de ambos em 11/09:</strong> seis configurações de Blob e seis de Watershed foram executadas e conferidas na busca comparativa dos mesmos 576 quadros de treino. Duas candidatas por família seguem para refinamento; validação completa e comparação da pipeline permanecem pendentes. Os pilotos históricos continuam sendo registros separados.'),
        ('<strong>Estado:</strong> implementação e testes existentes; ainda não há evidência que autorize afirmar vantagem sobre T218.',
         '<strong>Estado em 11/09:</strong> oito configurações do híbrido CLAHE foram comparadas e conferidas no treino junto ao T218 e às outras famílias. A tabela de resultados descreve essa grade limitada, com esforço de ajuste desigual. Duas candidatas seguem para refinamento; ainda não há validação comparativa ou superioridade geral demonstrada.'),
        ('<strong>Estado:</strong> integração verificada e piloto real histórico; treino e avaliação científicos no desenho atual ainda pendentes.',
         '<strong>Estado em 11/09:</strong> integração e piloto real histórico preservados. O ambiente CUDA executou sinteticamente a arquitetura YOLOv8n com pesos aleatórios, sem treinar ou medir qualidade no VISEM. Dataset derivado autenticado, receita de treino, pesos e avaliação no desenho atual continuam pendentes.'),
        ('<strong>Estado:</strong> adaptador existente; validação prática de ambiente/pesos e bateria VISEM pendentes.',
         '<strong>Estado em 11/09:</strong> o adaptador RAFT small executou um par sintético na GPU com <code>weights=None</code>, verificando forma, validade e finitude. O ambiente passou nessa operação, mas pesos externos autenticados e comparação real no VISEM permanecem pendentes. Vetores de uma rede com pesos aleatórios não demonstram qualidade de fluxo.'),
        ('variante RAFT dependente de ambiente/pesos. Nenhuma foi promovida',
         'variante RAFT ainda dependente de pesos e validação de sua composição completa, embora o RAFT small isolado já tenha passado no smoke CUDA sem pesos treinados. Nenhuma foi promovida'),
        ('Ainda precisamos resolver custo, registrar a extração ampliada e executar a ablação pareada para saber se essa hipótese ajuda.',
         'A primeira ablação exploratória pode usar as 10.848 janelas já disponíveis, após contrato e leitor/executor autenticado, sem exigir primeiro uma otimização de velocidade. A ampliação posterior continua dependente de plano próprio de extração, memória e completude. Ainda não há ADE/FDE real com fluxo.'),
        ('<strong>Estado:</strong> arquitetura/API presentes, sem treino real validado no desenho atual.',
         '<strong>Estado em 11/09:</strong> arquiteturas sem e com fluxo executadas sinteticamente na GPU, com forward e gradientes finitos. Não houve passo de otimização nem treino real validado no desenho atual; o smoke verifica execução, não qualidade de previsão.'),
        ('<tr><td>Demais detectores</td><td>Código, testes e pilotos/explorações identificados.</td><td>Comparação sob o mesmo desenho experimental atual.</td></tr>',
         '<tr><td>Otsu, adaptativo, híbrido CLAHE, Blob e Watershed</td><td>Busca comparativa conferida no treino, junto à referência T218: 43 configurações no total × 576 quadros.</td><td>Refinamento, validação completa e impacto nas identidades e na previsão.</td></tr><tr><td>MOG2, KNN e YOLO</td><td>Implementações e evidências históricas próprias; arquitetura YOLOv8n exercitada no smoke CUDA.</td><td>Bateria temporal de MOG2/KNN e treinamento/avaliação de YOLO no protocolo atual.</td></tr>'),
        ('<tr><td>Outros fluxos</td><td>Métodos clássicos/híbridos e adaptador RAFT.</td>',
         '<tr><td>Outros fluxos</td><td>Métodos clássicos/híbridos; RAFT small sem pesos treinados exercitado sinteticamente na GPU.</td>'),
        ('A prioridade atual é preparar uma comparação em que tudo seja igual entre os braços, exceto o uso do fluxo: mesmos históricos, janelas, vídeos, horizontes e regras de exclusão. Depois será necessário avaliar o impacto dos erros de detecção e rastreamento e ampliar a comparação às abordagens aprendidas previstas no tema.',
         'A continuidade atual inclui refinar e validar os demais detectores, preparar o treinamento YOLO e comparar rastreadores e preditores antes de escolher a pipeline. A hipótese central permanece uma comparação controlada sem/com fluxo: mesmos históricos, janelas, vídeos, horizontes e regras de exclusão, com controle da capacidade dos modelos aprendidos. A ablação nos derivados disponíveis continua prevista; o impacto dos erros de detecção e rastreamento precisa ser medido na cadeia automática.'),
    ]
    for old, new in changes:
        text = _once(text, old, new)
    return text


def _metrics(text: str) -> str:
    changes = [
        ('revisadas em 10/09/2026, com resultados concluídos até o marco 8a de 09/09.',
         'revisadas nesta edição de 11/09/2026, que incorpora a busca comparativa de detecção conferida no treino. Os resultados anteriores de fluxo e predição continuam identificados por seus próprios marcos.'),
        ('<tr><td>Detecção por centros, F1, contagem e custo</td><td>Medidos e conferidos nas etapas registradas do threshold v3.</td><td>Busca e refinamento no treino; validação dos finalistas; T218 congelado para desenvolvimento. Não é confirmação independente no teste.</td></tr>',
         '<tr><td>Detecção por centros, F1, contagem e custo</td><td>Medidos e conferidos nas etapas do threshold v3 e na busca de 43 configurações de seis famílias nos mesmos 576 quadros do treino.</td><td>T218 conserva seu congelamento de desenvolvimento. As novas famílias têm candidatas selecionadas no treino; refinamento e validação completa permanecem pendentes. Não é confirmação independente no teste.</td></tr>'),
        ('Busca, refinamento e validação do threshold usam F1 macro por vídeo no raio principal, com critérios de desempate registrados.',
         'Busca, refinamento e validação do threshold usam F1 macro por vídeo no raio principal, com critérios de desempate registrados. A nova busca comparativa de detectores mantém a mesma métrica principal, agrega contagens dentro de cada vídeo e dá peso igual aos 12 vídeos de treino.'),
        ('O próximo ensaio deverá medir essas parcelas sob plano próprio.',
         'Uma extração ampliada poderá instrumentar essas parcelas sob plano próprio. A revisão de continuidade de 11/09 permite a primeira ablação nos derivados existentes antes de otimizar velocidade; o teto histórico de tempo não permanece um impedimento às novas etapas.'),
        ('<strong>A validação do threshold e os baselines atuais são descritivos/de seleção conforme seus protocolos.</strong>',
         '<strong>A busca comparativa dos detectores, a validação anterior do threshold e os baselines atuais são descritivos/de seleção conforme seus protocolos.</strong>'),
    ]
    for old, new in changes:
        text = _once(text, old, new)
    return text


def _core(text: str) -> str:
    if 'id="comparacao-classicos-20260911"' not in text:
        raise ValueError("Publish the independently verified comparison fragment before correcting status")
    changes = [
        ('<tr><td>Outros detectores clássicos</td><td>Implementações, configurações e testes; alguns têm exploração histórica.</td><td>Baterias comparáveis e seleção/avaliação atual próprias.</td></tr>',
         '<tr><td>Outros detectores clássicos</td><td>Otsu, adaptativo, híbrido CLAHE, Blob e Watershed participaram da busca comparativa conferida no treino, junto à referência T218.</td><td>Refinamento e validação das novas famílias; MOG2/KNN ainda exigem bateria temporal própria.</td></tr>'),
        ('<tr><td>YOLO</td><td>Integração e piloto real histórico, em divisão diferente.</td><td>Treinamento e avaliação no desenho atual, com ambiente validado e pesos rastreáveis.</td></tr>',
         '<tr><td>YOLO</td><td>Integração e piloto real histórico, em divisão diferente; arquitetura YOLOv8n sem pesos treinados exercitada no smoke CUDA.</td><td>Dataset derivado autenticado, receita, treinamento e avaliação no desenho atual, com pesos rastreáveis.</td></tr>'),
        ('<tr><td>RAFT / híbrido com RAFT</td><td>Interfaces e configurações.</td><td>Inferência prática validada com pesos/ambiente; comparação científica própria.</td></tr>',
         '<tr><td>RAFT / híbrido com RAFT</td><td>Interfaces e configurações; RAFT small isolado executado sinteticamente na GPU com weights=None.</td><td>Pesos externos autenticados, composição híbrida e comparação real no VISEM. O smoke sem pesos treinados não mede qualidade.</td></tr>'),
        ('<tr><td>LSTM com e sem fluxo</td><td>Arquitetura e interfaces de treino/inferência.</td><td>Treinamento e ablação reais, sementes e seleção dentro dos dados permitidos.</td></tr>',
         '<tr><td>LSTM com e sem fluxo</td><td>Arquiteturas e interfaces; forward e gradientes finitos no smoke CUDA sintético, sem passo de otimização.</td><td>Treinamento e ablação reais, controles de capacidade, sementes e seleção dentro dos dados permitidos.</td></tr>'),
        ('F1 alto por quadro não garante', 'F1 alto de detecção não garante'),
    ]
    for old, new in changes:
        text = _once(text, old, new)
    return text


def _catalog_card(text: str, search_prefix: str, current: str, *, searched: bool = False) -> str:
    pattern = re.compile(r'<details class="algorithm-card"[^>]*data-search="'
                         + re.escape(search_prefix) + r'[^\"]*"[^>]*>.*?</details>', re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Expected one atlas card: {search_prefix}, found {len(matches)}")
    match = matches[0]
    card = match.group()
    card = _once(card, '<div class="details-body">',
                 '<div class="details-body"><p><strong>Estado em 11/09/2026:</strong> ' + current + '</p>')
    # The previous evidence and proposed actions retain their original numbers
    # and become clearly historical; they are not rewritten as current runs.
    if '<strong>Evidência:</strong>' in card:
        card = _once(card, '<strong>Evidência:</strong>', '<strong>Evidência do registro anterior:</strong>')
    if '<strong>Próximo:</strong>' in card:
        card = _once(card, '<strong>Próximo:</strong>', '<strong>Próximo previsto naquele registro:</strong>')
    if searched:
        card, changed = re.subn(r'data-status="(?:pilot|synthetic)"', 'data-status="descriptive"', card, count=1)
        if changed != 1:
            raise ValueError(f"Unexpected former atlas status: {search_prefix}")
        card, changed = re.subn(r'<span class="status (?:pilot|synthetic)">[^<]*</span>',
                               '<span class="status descriptive">busca no treino</span>', card, count=1)
        if changed != 1:
            raise ValueError(f"Unexpected former atlas badge: {search_prefix}")
    return text[:match.start()] + card + text[match.end():]


def _atlas(text: str) -> str:
    if 'id="comparacao-classicos-atual"' not in text:
        raise ValueError("Publish the verified atlas comparison before correcting historical catalog status")
    changes = [
        ('O último marco científico permanece o 8a, de 09/09: benchmark conferido, projeção de tempo acima do teto.',
         'Na frente de fluxo, o último marco concluído permanece o 8a, de 09/09: benchmark conferido, projeção de tempo acima do teto histórico. Em detecção, a busca comparativa de seis famílias foi concluída e conferida em 11/09.'),
        ('<span class="kicker">Agora · marco 8a concluído e conferido · 09/09/2026</span>',
         '<span class="kicker">Frente de fluxo · marco 8a concluído e conferido · 09/09/2026</span>'),
        ('A navegação foi revisada em 10/09/2026, sem alterar o estado científico de 09/09.',
         'A navegação desta edição incorpora a comparação clássica conferida em 11/09/2026. A edição didática anterior, de 10/09, não alterava o estado científico de 09/09.'),
        ('Há implementações, configurações, executores e testes sintéticos para detecção, tracking, fluxo e predição. Isso prova coerência do software, <strong>não desempenho no VISEM</strong>. As baterias reais ainda precisam ser executadas algoritmo por algoritmo.',
         'Além das implementações e testes, já existem resultados reais conferidos de threshold, baselines de predição com GT e fluxo causal. Em 11/09 foi concluída a busca comparativa de 43 configurações de seis famílias nos mesmos 576 quadros de treino. Refinamento e validação dos novos detectores, rastreamento avaliado e predição automática permanecem pendentes; cada resultado responde ao seu próprio contrato.'),
        ('<h3>Andamento registrado no snapshot de 31/08/2026</h3>',
         '<h3>Andamento registrado no snapshot de 31/08/2026</h3><p class="footnote">Tabela histórica preservada, com anotações posteriores identificadas nas próprias células. Não representa a lista atual de pendências: a preparação GT, baselines, fluxo causal e busca comparativa avançaram depois. O estado vigente está no <a href="#comparacao-classicos-atual">resumo de 11/09</a> e nas seções de cada marco.</p>'),
        ('<h2>Estado científico real em 31/08/2026</h2>',
         '<h2>Estado científico real em 31/08/2026</h2><p class="footnote">Esta seção preserva a régua e os resultados históricos. Para o estado atual, consulte a <a href="#comparacao-classicos-atual">comparação de detecção conferida em 11/09</a>, os marcos de fluxo e os baselines GT. As linhas abaixo não substituem essas evidências posteriores.</p>'),
        ('Cada ficha resume como o método funciona, sua força, sua fragilidade, o nível real de evidência e a próxima ação. Use os filtros para estudar apenas uma tarefa ou um estado.',
         'Cada ficha explica o mecanismo e conserva evidências antigas identificadas como históricas. Os atestados de 11/09 atualizam os métodos que avançaram: busca comparativa dos detectores estáticos e smoke CUDA de arquiteturas aprendidas. O filtro descritivo no treino abrange resultados de detecção e de predição com GT; nenhum deles implica promoção final.'),
        ('<option value="descriptive">Descritivo GT no treino</option>',
         '<option value="descriptive">Descritivo no treino</option>'),
        ('<strong>Próximo:</strong> instrumentar o custo do laço, registrar ajuste operacional e depois extração ampliada/ablação. Máscaras/anéis exigem plano próprio.',
         '<strong>Continuidade vigente:</strong> a primeira ablação pode usar os derivados existentes após contrato e leitor/executor autenticado. A instrumentação e a extração ampliada terão plano próprio; otimizar velocidade não é requisito anterior obrigatório. Máscaras/anéis continuam exigindo contrato próprio.'),
    ]
    for old, new in changes:
        text = _once(text, old, new)
    for prefix, count in (('otsu threshold', 4), ('threshold adaptativo', 18),
                          ('clahe correção', 8), ('blob simple', 6), ('watershed distância', 6)):
        text = _catalog_card(text, prefix,
            f'{count} configurações executadas e conferidas na busca comparativa dos mesmos 576 quadros dos 12 treinos. '
            'Duas candidatas da família seguem para refinamento; validação completa e promoção permanecem pendentes. '
            '<a href="RELATORIO_COMPLETO_TCC.html#comparacao-classicos-20260911">Resultados e limites da grade</a>.', searched=True)
    text = _catalog_card(text, 'yolo neural',
        'A arquitetura YOLOv8n com pesos aleatórios passou no smoke CUDA. O novo treinamento no VISEM ainda não ocorreu: '
        'é necessário materializar cópias derivadas autenticadas e fixar receita, pesos e critérios de seleção em protocolo próprio. '
        '<a href="../metodologia/AMBIENTE_APRENDIDO_V1.md">Ambiente e preparação necessária</a>.')
    text = _catalog_card(text, 'raft neural',
        'RAFT small isolado executou um par sintético na GPU com weights=None, sem medir qualidade de fluxo. '
        'Pesos externos autenticados e inferência/avaliação nos vídeos reais continuam pendentes. '
        '<a href="../metodologia/AMBIENTE_APRENDIDO_V1.md">Alcance do smoke CUDA</a>.')
    for prefix in ('lstm rede recorrente', 'lstm com fluxo'):
        text = _catalog_card(text, prefix,
            'A arquitetura foi exercitada sinteticamente na GPU, com forward e gradientes finitos, sem passo do otimizador. '
            'Treinamento real, controles causais e de capacidade e comparação pareada ainda são necessários. '
            '<a href="../metodologia/AMBIENTE_APRENDIDO_V1.md">Verificação CUDA sem treinamento</a>.')
    return text


def apply(root: str | Path) -> dict:
    """Apply once, backing up every affected file before the first edit.

    All transforms are checked in memory first. A distinct exclusive backup
    directory and manifest preserve the complete pre-correction state. Calling
    twice fails instead of replacing an earlier backup or rewriting history.
    """
    root = Path(root).resolve()
    transforms = {
        'tmp/tcc_report/algorithms_deep.html': _algorithms,
        'tmp/tcc_report/metrics.html': _metrics,
        'tmp/tcc_report/core.html': _core,
        'docs/projeto/mapa-tcc-didatico.html': _atlas,
    }
    before, after = {}, {}
    for relative, transform in transforms.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Documentary target escaped the project")
        original = path.read_bytes()
        replacement = transform(original.decode('utf-8')).encode('utf-8')
        if replacement == original:
            raise ValueError(f"No status correction prepared for {relative}")
        before[relative], after[relative] = original, replacement
    backup = root / 'data/derived/project_audits/general_20260911/classical_comparison_edition/before_status_corrections'
    backup.mkdir(parents=True, exist_ok=False)
    records = []
    for relative, content in before.items():
        if (root / relative).read_bytes() != content:
            raise ValueError(f"Document changed before backup: {relative}")
        copy_path = backup / relative
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        with copy_path.open('xb') as stream:
            stream.write(content)
        records.append({'path': relative, 'before_sha256': hashlib.sha256(content).hexdigest(),
                        'before_bytes': len(content), 'planned_after_sha256': hashlib.sha256(after[relative]).hexdigest(),
                        'planned_after_bytes': len(after[relative])})
    receipt = {'kind': 'documentary_status_corrections_before_edit',
               'created_at': datetime.now(timezone.utc).isoformat(),
               'scope': 'ignored_HTML_only_no_new_experiments', 'files': records}
    with (backup / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
    # Every prior byte stream and the manifest already exist before this loop.
    for relative, content in after.items():
        if (root / relative).read_bytes() != before[relative]:
            raise ValueError(f"Document changed after backup: {relative}")
        (root / relative).write_bytes(content)
    completion = {'status': 'applied', 'backup_manifest': str(backup / 'manifest.json'),
                  'files': [{'path': relative, 'sha256': hashlib.sha256((root / relative).read_bytes()).hexdigest()}
                            for relative in after]}
    with (backup / 'completion.json').open('x', encoding='utf-8') as stream:
        json.dump(completion, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return completion
