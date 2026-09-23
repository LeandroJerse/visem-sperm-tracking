# Blobs: conferência dos vídeos completos de seleção

Data: 21/09/2026. Execução: `batch__20260921T022547636341Z`.

## Integridade e escopo

A execução das cinco configurações aprovadas terminou corretamente nos
vídeos 13, 29, 52 e 54: **29.250 avaliações**, 5.850 frames por configuração
e **20 MP4 comparativos**. Os parâmetros, caixas e critérios foram mantidos.

A auditoria anterior à reorganização conferiu todos os **129 hashes de
saídas** (1.119.901.434 bytes) e **5.897 hashes de entradas/origens**, sem
divergências. O validador do relatório conferiu as 29.250 linhas por frame,
cinco totais, vinte agregados por vídeo, ranking e identidades das configurações.
As vinte referências de alinhamento correspondem aos índices previstos.
Os registros das mídias confirmam decodificação completa, FPS e dimensões;
os vídeos exportados possuem 1280 × 584 pixels. Esta auditoria verificou
esses registros e hashes, sem repetir detecção ou decodificar novamente os MP4s.

O PDF existente possui quatro páginas, 62 fontes verificadas e cópias do
plano e manifesto iguais às da execução original. Suas quatro páginas
foram renderizadas e revisadas. As métricas abaixo provêm dos CSVs salvos.

## Resultado agregado

| Configuração | F1 nas imagens | F1 nos vídeos | Precisão nos vídeos | Recall nos vídeos |
|---|---:|---:|---:|---:|
| s052 | 0,669617 | **0,668702** | 0,625229 | 0,718674 |
| s082 | 0,664032 | 0,660699 | 0,656502 | 0,664949 |
| s084 | 0,662461 | 0,660666 | 0,656486 | 0,664901 |
| s103 | 0,660178 | 0,654109 | **0,696710** | 0,616417 |
| s051 | 0,635693 | 0,636091 | 0,594737 | 0,683626 |

A ordem permaneceu igual à seleção em imagens. O F1 usa as contagens
somadas de indivíduos das classes 0 e 2; não é média dos F1 por frame.
s082 e s084 têm valores próximos, mas não empatados nas contagens exatas.
A estabilidade observada é descritiva, sem teste de significância.

| Configuração | Vídeo 13 | Vídeo 29 | Vídeo 52 | Vídeo 54 |
|---|---:|---:|---:|---:|
| s052 | **0,8407** | 0,2647 | 0,4333 | **0,6135** |
| s082 | 0,7868 | 0,5156 | **0,4878** | 0,5958 |
| s084 | 0,7868 | **0,5269** | 0,4852 | 0,5958 |
| s103 | 0,8388 | 0,0611 | 0,4097 | 0,5284 |
| s051 | 0,8034 | 0,4212 | 0,4575 | 0,5315 |

s052 lidera no agregado e nos vídeos 13 e 54; s082/s084 funcionam melhor
nos vídeos 29 e 52. O agregado não representa desempenho uniforme.

## Limitações que permanecem

- s052 localizou **88.009/117.286 normais (75,04%)**, mas somente
  **574/5.973 pequenos (9,61%)** e **30/4.403 aglomerados (0,68%)**.
  Para indivíduos: 88.583 TP, 53.098 FP e 34.676 FN.
- Todos os pequenos localizados pelos quatro SimpleBlob foram classificados
  como normal. A acurácia condicional próxima de 99% decorre da predominância
  dos normais nos pares; não demonstra boa separação das classes.
- s103 localizou e classificou corretamente 246 pequenos, mas classificou
  **55.861 normais como pequenos**. A acurácia condicional foi 26,48%, e
  nenhum aglomerado foi detectado.
- O tempo médio do pipeline foi 16,54 / 16,24 / 16,39 / 106,40 / 14,67 ms
  por frame, respectivamente para s052/s082/s084/s103/s051. Não inclui
  leitura, avaliação, desenho ou gravação. A ordem da execução e o ambiente
  limitam comparações rigorosas de diferenças pequenas de tempo.

Os mesmos vídeos já forneceram as imagens da seleção. Frames consecutivos
são dependentes, e as contagens representam ocorrências por frame, não
indivíduos únicos. Esta etapa não é a avaliação final independente, e o
histórico de exposição dos dados permanece relevante para o TCC.

## Continuidade

Não foi identificado impedimento técnico para preparar a avaliação final
nos vídeos **14, 24, 38 e 82**, preservando **s052, s082, s084, s103 e s051**,
seus parâmetros e critérios. As limitações devem acompanhar a comparação;
não serão corrigidas por ajustes nos dados finais. A execução final continua
a cargo do pesquisador. Após esta análise, foi autorizada a preparação e
o [plano final](plano_videos_final_blobs.md) passou a estar disponível no
mesmo executor, com `--etapa final`. Os resultados finais ainda dependem
da execução pelo pesquisador.

## Referências de integridade anteriores à reorganização

- Manifesto: `dc59d085720e1244821a52d741a46f9271ee375bdc7d70a8f07a7646a319a3dc`.
- Plano: `cc36923b5a846023e8ee538ea25a8e1ce09791a7ee5f798310165749b512b8ed`.
- PDF: `6d0f35ef2f91d4b3b1d928274b2dcf174698abc3969e08995b38a483bc04359b`.

Fontes: `resumo_configuracoes.csv`, `resumo_por_video.csv` e `ranking.csv`
do batch citado. O PDF está em `relatorios/20260921T025203121355Z/relatorio.pdf`.

## Reorganização das cópias de origem

As 22 cópias de procedência foram movidas da raiz do batch para `origens/`.
A raiz passou de 29 para **7 arquivos**, mantendo plano, manifesto, código,
ranking, resumos e indicação do PDF. As pastas de configurações, conferência
e relatórios permanecem no mesmo lugar.

O manifesto atual registra `pasta_origens: origens` e os novos caminhos
das cópias em `saidas_sha256`. `origens_sha256`, plano, parâmetros, métricas,
MP4s, código arquivado e PDFs não foram alterados. O manifesto anterior e
o mapeamento verificável ficam em `origens/historico_organizacao/`.
Os registros dos PDFs históricos preservam os caminhos antigos; sua
verificação usa esse mapeamento e o manifesto anterior arquivado.

Após a mudança, foram conferidos os **129 arquivos anteriores**, os **131
hashes atuais** (incluindo os dois registros do histórico) e as **62 fontes
do PDF histórico**. O validador do relatório aceitou a organização nova e
revalidou as 29.250 linhas e vinte mídias. Repetir a organização apenas
conferiu os arquivos, sem produzir novas alterações.

Novo SHA256 do manifesto:
`28c618a2cfdd012377006fcc5836e5070cce4a3bf02d333b3b228ee60399f565`.

Arquivos de código alterados/criados:

- `scripts/blobs/executar_videos.py`: novas execuções gravam cópias em `origens/`.
- `analise/relatorio_videos_blobs.py`: reconhece o layout atual e o histórico.
- `scripts/blobs/organizacao.py`: função interna de migração, preservação do
  histórico e reversão em caso de falha; não adiciona comando ao fluxo experimental.
- `scripts/testes/test_videos_blobs.py`, `test_relatorio_videos_blobs.py`
  e `test_organizacao_blobs.py`: exportação, compatibilidade e migração.

Passaram **46 testes**: 15 do executor, 15 do relatório e 16 da organização.
Foram atualizados também este registro, estado da pesquisa, plano dos vídeos
e guias principal, de scripts, de blobs e de análise. Não houve novo
experimento, ajuste de configurações ou preparação automática da avaliação final.
