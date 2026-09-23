# Execução de watershed

Etapa atual: **vídeos de seleção preparados para execução**.
As 6.840 avaliações das 114 configurações estão íntegras. Veja a
[análise da seleção](../../analise/analise_selecao_watershed.md) e o
[plano executado](../../analise/plano_selecao_watershed.md).
Foram aprovadas s063, s064, s061, s062 e s098; a líder teve F1 0,342956
nas imagens. As cinco serão executadas nos vídeos completos 13, 29, 52 e 54.

## Próxima execução: vídeos de seleção

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --etapa selecao
```

São **29.250 avaliações e vinte vídeos comparativos**, mantendo parâmetros,
caixas e critérios da seleção. Saídas em
`resultados/videos/watershed/selecao/batch__<UTC>/`, com uma pasta por
configuração, quatro MP4s em `midia/`, tabelas e PDF automático de quatro
páginas em `relatorios/<UTC>/relatorio.pdf`.
Consulte o [plano completo](../../analise/plano_videos_watershed.md).

Conferir apenas arquivos, versões e metadados, sem executar a detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --etapa selecao --conferir
```

Se apenas o PDF falhar, gere outro a partir dos resultados salvos:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

Os arquivos reais passaram na conferência sem detecção. Passaram 90 testes
sintéticos e de regressão; as quatro páginas do PDF fictício foram revisadas.
O alinhamento temporal completo será conferido antes de iniciar os detectores.
Cada execução cria outra pasta; não existe retomada parcial automática.
Conserve `codigo.zip`, `origens/` e resultados anteriores.
Após a revisão desta execução, prepararemos os vídeos finais 14, 24, 38 e 82.

## Etapas anteriores

O mesmo executor aceita `--rodada round1` até `--rodada round5`.
Sem a opção, mantém round1 para preservar o comportamento anterior.
O [diagnóstico](../../analise/diagnostico_round0_watershed.md) apresenta os
resultados. O
[plano explicado](../../analise/plano_watershed.md) descreve as oito configurações
e as duas políticas de aglomerados. São 48 avaliações: oito configurações
nos mesmos seis quadros de desenvolvimento inspecionados em blobs.

## Reproduzir a seleção concluída

Não é necessário repetir a execução. Para reprodução, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py"
```

São **114 configurações × 60 quadros = 6.840 avaliações**, incluindo as
20 variantes manuais e 94 Otsu, sem novos ajustes. Quadros 0, 100, …, 1400
dos vídeos 13, 29, 52 e 54; nenhum quadro será extraído novamente dos vídeos.
O [plano congelado](selecao/plano.json) registra parâmetros, hashes e as
136 origens históricas das configurações. Não é necessário rodar o gerador.

Saídas em `resultados/frame-to-frame/watershed/selecao/batch__<UTC>/`, com
pastas por configuração/quadro, imagens comparativas, máscaras, medidas,
ranking, resumos e **PDF de oito páginas**. O relatório apresenta todas as
configurações, cobertura por classe, erros de classificação e F1 por vídeo.
O caminho do PDF aparece no terminal e em `relatorio.json` no batch.

O ranking usa F1 de localização de indivíduos 0+2; classificação e
aglomerados continuam separados. Empates exatos compartilham posição;
um empate na quinta vaga é sinalizado para revisão, sem escolha automática.

Conferir entradas sem detecção nem criação de resultados:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py" --conferir
```

Regenerar somente o PDF de uma execução com métricas concluídas:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py" --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

A preparação conferiu 274 entradas de integridade e 42 fontes a arquivar.
Passaram 93 testes sintéticos e de regressão; as oito páginas do PDF fictício
foram revisadas. Isso confere implementação, não desempenho na base.
Conserve os cinco rounds, `codigo.zip` e `origens/`. A seleção usa imagens
diferentes do desenvolvimento; não existem controles históricos de igualdade
das detecções nesses novos quadros. Cada execução cria outra pasta e preserva
as anteriores; não há retomada automática. A geração do PDF não repete o detector.

## Reproduzir o round5 concluído

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round5
```

São **14 configurações × 178 quadros = 2.492 avaliações**, com seis controles
do round4 e oito combinações novas. O [plano](../../analise/plano_round5_watershed.md)
explica a combinação de Otsu −3/−5, semente 0,50, fechamento 3/5 e área 120/144.
O [JSON congelado](rodadas/round5.json) organiza sete pares separar/preservar.

Saídas em `resultados/frame-to-frame/watershed/round5/batch__<UTC>/`, com
imagens, máscaras, mapas, tabelas e PDF de cinco páginas. A última mostra
14 comparações que mudam um parâmetro por vez, reutilizando os resultados.
O caminho do PDF aparece no terminal e em `relatorio.json`.

Os controles comparam **1.068 casos e 4.272 arquivos** com o round4.
Uma divergência interrompe a rodada, preservando os arquivos produzidos.
Conferir entradas sem executar detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round5 --conferir
```

Recuperar somente o PDF após a conclusão das métricas:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round5 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

A conferência de preparação validou 4.636 origens. Conserve o round4,
`codigo.zip` e as origens. Cada execução cria outra pasta; não há retomada
automática de uma interrupção. Não é necessário executar o gerador
`planejamento_round5.py` antes do batch. A seleção em outras imagens e
os testes em vídeo são posteriores.
O batch `batch__20260921T193215730860Z` foi concluído e conferido, com
maior F1 0,482362 para r5c10. Não é necessário repetir a execução.

## Reproduzir o round4 concluído

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round4
```

São **18 configurações × 178 quadros = 3.204 avaliações**, com seis controles
do round3 e 12 novas. O [plano explicado](../../analise/plano_round4_watershed.md)
justifica Otsu −3/−7, áreas 132/144, semente 0,50 e fechamento 3×3.
O [JSON congelado](rodadas/round4.json) organiza nove pares separar/preservar.

Saídas em `resultados/frame-to-frame/watershed/round4/batch__<UTC>/`, com
pastas por configuração/quadro, imagens, máscaras, mapas, tabelas e PDF de
cinco páginas. A última compara os 12 refinamentos com seus controles.
F1 e diferenças de F1 têm seis casas decimais; ranking usa frações exatas.
O PDF aparece no terminal e no arquivo `relatorio.json` do batch.

Os controles comparam **1.068 casos e 4.272 arquivos** com o round3.
Uma divergência interrompe o batch e preserva os resultados parciais.
Para conferir entradas sem executar o detector:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round4 --conferir
```

Para recuperar apenas o PDF após a conclusão das métricas:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round4 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

O gerador `planejamento_round4.py` reproduz exatamente o plano salvo, sem
sobrescrever conteúdo diferente; não é necessário executá-lo antes do batch.
Conserve o round3, `codigo.zip` e as origens. Uma nova execução cria outra
pasta, sem sobrescrever resultados ou retomar automaticamente uma interrupção.
O batch `batch__20260921T184319705365Z` foi concluído e conferido, com
maior F1 0,481308. Não é necessário repetir a execução.

## Reproduzir o round3 concluído

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round3
```

São **24 configurações × 178 quadros = 4.272 avaliações**, com seis controles
do round2 e 18 novas. O [plano explicado](../../analise/plano_round3_watershed.md)
lista os 12 pares e justifica área mínima 108/132, semente 0,60 e ajustes de
Otsu -5/+5. O [JSON congelado](rodadas/round3.json) já está preparado.

Saídas em `resultados/frame-to-frame/watershed/round3/batch__<UTC>/`, seguindo
a mesma estrutura de pastas, tabelas, máscaras e comparações do round2.
Os controles verificam **1.068 casos e 4.272 arquivos** contra o round2;
uma divergência interrompe a execução e preserva os resultados parciais.

O PDF automático mantém cinco páginas e acrescenta os contrastes dos novos
parâmetros contra os controles. O F1 será exibido com seis casas decimais;
o ranking preserva a regra de empate exato. O caminho do PDF aparece no
terminal e em `relatorio.json` do batch. O batch `batch__20260921T174126692210Z`
foi concluído e conferido; maior F1 0,478007. Não é necessário repeti-lo.

Conferir entradas sem detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round3 --conferir
```

Recuperar somente o PDF após as métricas concluírem:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round3 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

O gerador `planejamento_round3.py` pode conferir a reprodução exata do plano;
não é necessário executá-lo antes do batch. Conserve o round2, `codigo.zip`
e as origens. Cada execução cria uma pasta nova, sem sobrescrever resultados;
não há retomada automática de uma execução interrompida.

## Reproduzir o round2 concluído

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round2
```

São **32 configurações × 178 quadros = 5.696 avaliações**, com quatro
controles e 28 configurações novas, em 16 pares das políticas de aglomerados.
O [desenho aprovado](../../analise/proposta_round2_watershed.md) explica cada
contraste. O plano [round2.json](rodadas/round2.json) já está preparado.
A grade é determinística, sem sorteio; a seed 42 permanece registrada.

O round2 refina área mínima, sementes e fechamento e testa deslocamentos
de Otsu -20, -10, +10 e +20. Deslocamento zero usa o detector original.
Nos quatro controles, o script compara as caixas, detecções, avaliações e
diagnósticos com todos os 178 quadros do round1: **712 casos e 2.848 arquivos**.
Uma divergência interrompe o batch e preserva as saídas para investigação.

As saídas seguem a estrutura do round1 descrita abaixo, em
`resultados/frame-to-frame/watershed/round2/batch__<UTC>/`. Cada configuração
tem pasta com ID, ajuste de Otsu (`dm20` = -20; `dp10` = +10), semente,
política, área mínima, fechamento, hash e instante de execução.

Além das saídas anteriores, cada quadro recebe `segmentacao.json` com:

- `limiar_otsu_original`, `deslocamento_otsu` e `limiar_efetivo`;
- `pixels_mascara`, `pixels_imagem` e `fracao_pixels_mascara` após morfologia.

Esses dados também aparecem em `resumo_por_quadro.csv`, inclusive sem detecções.
O PDF automático tem **cinco páginas**: F1 geral, variação por vídeo e classes,
ranking das 32, políticas em pares e contrastes do ajuste de Otsu.
O caminho aparece no terminal e em `relatorio.json`. Este ranking não seleciona
finalistas. O batch `batch__20260921T161513364669Z` concluiu as 5.696 avaliações
e os 712 controles; seu maior F1 foi 0,466361. A análise orientará o round3.

Conferir entradas sem executar o detector nem criar resultados:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round2 --conferir
```

Recuperar somente o PDF se a rodada concluiu as métricas:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round2 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

Para verificar a reprodução exata do plano, sem detectar imagens:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\planejamento_round2.py"
```

Cada execução e regeneração de PDF cria uma pasta nova. Conserve resultados,
`codigo.zip` e `origens/`; não é necessário apagar o round1. Os controles
dependem dos arquivos históricos. Uma interrupção exige iniciar outra execução;
não há retomada parcial automática. O PDF confere tabelas, metadados e controles;
não relê todas as mídias da rodada.

## Reproduzir o round1

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round1
```

São **48 configurações nos mesmos 178 quadros**, totalizando 8.544 avaliações.
O [plano do round1](../../analise/plano_round1_watershed.md) explica a escolha
dos parâmetros e lista as 48 configurações: quatro controles do round0,
36 explorações claras e oito escuras. Todas formam pares das duas políticas
de aglomerados. Seed 42 reproduz o desenho dos parâmetros; nenhuma configuração
é sorteada novamente durante a execução.

Antes de começar, o script confere as entradas, as referências e as versões
das bibliotecas. Durante a execução, imprime o progresso a cada vinte quadros
e verifica se os controles reproduzem exatamente as saídas do round0.
O resultado fica em:

```text
resultados/frame-to-frame/watershed/round1/batch__<UTC>/
├── relatorios/<UTC>/relatorio.pdf
├── <ID>__<configuracao>__cfg-<hash>__<UTC>/
│   ├── configuracao.json
│   ├── avaliacao.json
│   └── quadros/<video>_frame_<quadro>/
│       ├── comparacao.png, mascara.png, regioes_sementes.png
│       ├── mapas.npz, diagnostico.json
│       └── tabelas, predicoes.txt, avaliacao.json
├── ranking.csv
├── resumo_configuracoes.csv, resumo_por_video.csv, resumo_por_quadro.csv
├── controles.json, plano.json, execucao.json, relatorio.json
├── origens/
└── codigo.zip
```

O PDF é automático e contém quatro páginas: visão geral do F1, variação
por vídeo e cobertura das classes, ranking completo e comparação das políticas
em pares. O caminho aparece no terminal e em `relatorio.json`.
O ranking desta rodada não seleciona as cinco finalistas.

Cada execução cria outra pasta. Não é necessário apagar resultados anteriores.
Conserve `codigo.zip` e `origens/`, que preservam a reprodução e os controles.
São salvas imagens e mapas de todos os quadros; reserve espaço para milhares
de arquivos. O volume depende da segmentação e não é limitado pelo script.
Interromper preserva o batch parcial, mas a próxima execução começa uma nova
rodada; não há retomada automática nesta versão.

Conferir entradas sem executar o detector:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round1 --conferir
```

Se somente o PDF falhar após as métricas concluírem:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round1 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

O relatório recusa batch incompleto ou fontes inconsistentes. Ele verifica
as tabelas e os controles, mas não relê todas as imagens e mapas. Não executa
detecções nem modifica os resultados anteriores.

Para conferir se o plano congelado é reproduzido pelo gerador:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\planejamento.py"
```

Esse comando não é necessário para executar o batch: `rodadas/round1.json`
já está preparado. Um plano diferente não é sobrescrito.

## Reproduzir o round0 concluído

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_inspecao.py"
```

O script gera comparação visual, máscaras, regiões, tabelas, avaliação e PDF
automaticamente. Cada execução cria uma pasta nova em
`resultados/frame-to-frame/watershed/round0/batch__<execucao>/`.
O caminho completo do PDF aparece no terminal e em `relatorio.json`.

Conserve `codigo.zip`: ele guarda os arquivos exatos usados na execução.
Junto do plano, dependências e hashes, permite reproduzir o experimento mesmo
depois de alterações no projeto. Não é um arquivo temporário. Removê-lo não
apaga métricas ou imagens, mas impede a conferência completa da execução.

Abra primeiro `relatorios/<execucao>/relatorio.pdf`. Depois examine
`<configuracao>__<execucao>/quadros/<video>_frame_<quadro>/comparacao.png`.
Use `mascara.png` e `regioes_sementes.png` para entender a segmentação.
As cores das regiões não são classes; as sementes estão brancas.

## Dependências e conferência sem detecção

As bibliotecas necessárias já estavam instaladas e foram conferidas.
Para reproduzir em outro ambiente:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\algoritmos\classicos\requirements-watershed.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
& "C:\Python313\python.exe" ".\scripts\watershed\executar_inspecao.py" --conferir
```

O segundo comando confere parâmetros, seis imagens/anotações e suas origens,
sem executar o detector ou criar resultados.

## Recuperar somente o PDF do round0

Se as métricas concluírem e o PDF falhar, não é necessário repetir a detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_inspecao.py" --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

Substitua o texto pelo caminho impresso na execução. Cada PDF regenerado fica
em uma pasta nova; o script recusa batch incompleto ou com saídas alteradas.

## Continuidade

Round0, cinco rodadas e seleção em imagens já foram concluídos e conferidos.
O próximo comando está no início deste guia: vídeos completos de seleção.
Após a análise conjunta, seguirá a avaliação final. Não é necessário repetir
blobs ou limiarização: seus resultados estão concluídos e preservados.
