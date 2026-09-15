"""Update only the local academic method/conclusion after both independent QAs."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--dataset-manifest',type=Path,required=True)
parser.add_argument('--dataset-qa',type=Path,required=True)
args=parser.parse_args()
def read(path): return Path(path).read_text(encoding='utf-8')
def load(path): return json.loads(read(path))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fmt(v): return f'{v:.6f}'.replace('.',',')
summary=load(ROOT/'data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json')
run_path=ROOT/summary['source_manifest']; qa_path=ROOT/summary['verification']
assert digest(run_path)==summary['source_manifest_sha256'] and digest(qa_path)==summary['verification_sha256']
run,qa=load(run_path),load(qa_path)
assert run['status']=='complete' and run['git_dirty'] is False and qa['status']=='passed'
dm,dq=load(args.dataset_manifest),load(args.dataset_qa)
assert dm['status']=='complete' and dq['status']=='passed' and dq['manifest_sha256']==digest(args.dataset_manifest)
method=ROOT/'monografia/cap_metodo/metodo.tex'
conclusion=ROOT/'monografia/cap_conclusao/conclusao.tex'
text=read(method)
assert 'sec:refinamento-classicos-20260911' not in text
values='; '.join(r['label']+': '+fmt(r['f1']) for r in summary['best_per_family'])
section=r'''
\subsection{Refinamento local e preparação dos dados aprendidos}
\label{sec:refinamento-classicos-20260911}

Após a busca anterior, foram registrados o contrato e a implementação de um refinamento local, antes das novas inferências. As duas finalistas de cada uma das cinco famílias pesquisadas originaram 54 propostas que incluíam os próprios pais e alterações de um parâmetro por vez. Três propostas ficaram fora dos limites prospectivos; as 51 válidas resultaram em 45 configurações únicas após deduplicação, preservando todas as origens. A referência T218 foi autenticada e não reexecutada nesta etapa.

Um smoke de 540 avaliações precedeu o refinamento completo. Ambos foram concluídos e conferidos independentemente sob o commit \texttt{COMMIT}. O refinamento utilizou os mesmos 576 quadros físicos dos 12 treinos, totalizando 25.920 avaliações. A melhor configuração da grade de cada família apresentou os seguintes F1 macro a 10 pixels: VALUES. Essas médias descrevem seleção nos dados de treino, com esforço desigual entre famílias. Foram retidas duas finalistas por família, totalizando dez, sem promoção, abertura do teste ou escolha final da pipeline.

Os dez pais reproduziram suas detecções, anotações exportadas e métricas científicas nos mesmos quadros, exceto tempo e identificação da nova execução. A conferência independente reconstruiu vizinhança, associações, agregações e classificação. Esse controle verifica consistência e reprodutibilidade dos derivados; não repete a inferência nem certifica generalização. A duração da bateria foi TIME segundos e o máximo de RSS amostrado foi RESOURCE_VALUE MiB. Recursos e custos permanecem vinculados ao ambiente e ao commit da execução.

Foi também preparado um dataset derivado independente para o futuro treinamento YOLO: 17.466 pares de imagem e anotação no treino e 5.850 na validação, totalizando 23.316. As 174 lacunas do vídeo 23 foram excluídas, sem tratá-las como negativos. As três classes foram preservadas; os rótulos geométricos YOLO foram confrontados com as anotações FTID usadas na avaliação, ignorando somente o identificador. Fontes, cópias e referências foram autenticadas por hashes, e as cópias JPEG foram decodificadas e conferidas independentemente. Não houve leitura de imagens do teste ou treinamento de rede nesta preparação.

O dataset preparado permanece imutável. O futuro executor de treinamento deverá usar outra cópia independente para isolar os caches e eventuais reparos da biblioteca, mantendo rastreável qualquer mudança de entrada. Receita, pesos iniciais, sementes, seleção de checkpoints e parâmetros de inferência exigem contrato próprio. A sequência seguinte é validar as finalistas clássicas em vídeos completos e treinar e comparar YOLO sob a mesma regra de detecção; os métodos temporais requerem protocolo contínuo com aquecimento.

A paridade geométrica dos rótulos não certifica igualdade de pixels entre os JPEGs recebidos e os quadros decodificados dos vídeos. Os JPEGs constituem as entradas de treinamento preparadas; a comparação de detecção entre YOLO e os clássicos deverá processar os mesmos quadros do vídeo ou cache de avaliação, com pré-processamento explicitamente registrado.

'''.replace('COMMIT',run['git_sha']).replace('VALUES',values).replace('TIME',fmt(run['elapsed_seconds'])).replace('RESOURCE_VALUE',fmt(run['summary']['ram_rss_peak_mb']))
marker=r'\section{Estimação do movimento aparente}'
assert text.count(marker)==1
text=text.replace(marker,section+marker,1)
text=text.replace('As finalistas clássicas ainda exigem refinamento e validação próprios; YOLO precisa de treinamento e comparação no protocolo atual.','O refinamento clássico e a preparação autenticada do dataset YOLO foram concluídos, conforme a Seção~\\ref{sec:refinamento-classicos-20260911}. As finalistas clássicas ainda exigem validação completa; YOLO precisa de treinamento e comparação no protocolo atual.')
method.write_text(text,encoding='utf-8',newline='\n')
text=read(conclusion)
text=text.replace('A próxima sequência compreende refinamento e validação das alternativas clássicas, treinamento e comparação de YOLO,','Após o refinamento local e a preparação do dataset descritos a seguir, a próxima sequência compreende validação completa das alternativas clássicas, treinamento e comparação de YOLO,')
insert=r'''
\subsection{Avanço após o refinamento local}

O refinamento das cinco famílias clássicas foi concluído e conferido em 45 configurações únicas, com 25.920 avaliações nos mesmos quadros de treino. As dez finalistas retidas ainda não constituem uma escolha final. A paridade dos dez pais, os hashes e a reconstrução das métricas apoiam a consistência dos resultados, mas não substituem a validação em vídeos completos ou a avaliação de rastreamento e predição. O dataset YOLO de 23.316 pares de treino e validação também foi materializado e conferido; não houve treinamento nesta etapa. As regras, o alcance e as limitações desses avanços estão na Seção~\ref{sec:refinamento-classicos-20260911}.

'''
marker='Espera-se que os resultados permitam identificar'
assert text.count(marker)==1 and 'Avanço após o refinamento local' not in text
text=text.replace(marker,insert+marker,1)
conclusion.write_text(text,encoding='utf-8',newline='\n')
print(json.dumps({'status':'local_latex_sources_updated','pdf_compiled':False,'paths':[str(method),str(conclusion)]}))
