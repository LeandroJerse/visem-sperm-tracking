# Monografia

Fonte LaTeX oficial e versionável da monografia do TCC. Nenhum arquivo em
`tmp/`, `data/` ou na raiz substitui esta fonte.

- `template_tcc_bsi.tex`: documento principal.
- `cap_*`: capítulos da monografia.
- `bib/`: referências bibliográficas.
- `abrev/`: abreviações.
- `figs/`: figuras necessárias para compilar o texto.
- `entregas/pdf/`: versões acadêmicas entregues, mantidas como registro.
- `entregas/arquivos-fonte/`: pacotes-fonte enviados em entregas anteriores.

Um PDF de trabalho gerado durante a compilação é descartável; uma entrega já
submetida é evidência acadêmica e permanece em `entregas/`. Resultados
experimentais que alimentam tabelas e figuras pertencem a `data/results/`, não
a esta pasta.

## Versão de trabalho — 09/09/2026

O resumo, o abstract, a introdução, a fundamentação e o método foram alinhados
ao uso exclusivo de vídeos VISEM e das anotações VISEM-Tracking, provenientes
da mesma coleção. A caracterização da aquisição e seus limites estão na seção
"Conjuntos de dados" de `cap_fundamentacao/fundamentacao.tex`.

O método também incorpora a tolerância de detecção aprovada nesta data:
10 pixels como critério principal, na resolução original, com análises de
sensibilidade a 15 e 20 pixels. Essa decisão não recalcula resultados antigos.
O método incorpora também a avaliação principal dos indivíduos 0/2, proteção
contra duplicatas próximas e tratamento de agrupamentos como regiões ignoradas
para previsões residuais. A avaliação complementar mantém todos os objetos.
O desenho da busca grossa e do refinamento de threshold foi registrado antes
das respectivas execuções, concluídas e conferidas em 08/09. A validação
completa selecionou T218/o0/c2, depois fixado para desenvolvimento sem liberar
teste/folds. O método incorpora também a referência individual do treino e
a comparação de persistência e CV mediana5 nas mesmas 343.776 janelas, com
ADE/FDE densos e pesos explícitos por ID e vídeo. Os resultados são de
desenvolvimento; não demonstram ainda a contribuição do fluxo.
O método conserva a amostragem, as regras de seleção e a ressalva de que folds
não restauram a independência perdida na exposição histórica do teste.

Em 09/09, o método passou a registrar o smoke causal de Farnebäck em 11/12:
40 quadros,68 janelas,1.292 amostras e conferência independente aprovada.
Esse ensaio verifica a conexão causal e os diagnósticos; a ablação continua
pendente. O contrato e os resultados estão em `docs/metodologia/FLUXO_CAUSAL_V1.md`.

A fonte corrigida ainda não foi recompilada. Na revisão anterior não foi
encontrado compilador LaTeX; a atualização documental atual não reavaliou essa
disponibilidade. Os PDFs de entregas anteriores,
inclusive o documento assinado fornecido pelo pesquisador, são registros
históricos e não incorporam esta correção. A conferência desta revisão cobriu
referências bibliográficas, inclusões e estrutura dos ambientes LaTeX;
paginação e apresentação visual dependem da próxima compilação.
