# Metodologia — Motor Atlas

Versão2.0, 28/10/2026. A carga e a aplicação aceitam somente evidências reais publicadas, com fonte e granularidade preservadas.

## Objeto de medição e cobertura

O ranking responde quais modelos têm maior volume da medida publicada no território, período e universo selecionados. `new_registrations` representa registros de veículos novos conforme a fonte. `first_registrations_including_imports` representa primeiros registros no Reino Unido, incluindo veículos usados importados. Venda efetiva, atacado, registro administrativo e estoque de frota não são equivalentes.

Brasil: top50 nacional de automóveis Fenabrave, acumulados anuais de dezembro2021–2025 e meses efetivamente coletados. Comercial leve não é somado a automóveis deste universo. Reino Unido: VEH0160 DfT/DVLA, BodyType=Cars, fabricante, modelo genérico e combustível; anuais e trimestres publicados são guardados separadamente. Categorias desconhecidas/suprimidas não são redistribuídas por modelos conhecidos.

A coleta não sustenta rankings reais estaduais ou municipais. Estados/geometrias são referências geográficas; só se tornam opções disponíveis com fatos reais observados. Não existe distribuição nacional por população, preferência presumida ou sorteio. País sem medida compatível fica sem valor no mapa. Mapa estadual sem observações retorna coleção vazia.

## Entrada, tratamento e rastreabilidade

1. CSV canônico com RAW_SCHEMA explícito, identificador, país, medida, período, fonte, localizador de origem, hash e coleta.
2. Bronze guarda essas observações reais em Parquet `country_iso/year`. A evidência original permanece em raw.
3. Normalização de espaços/caixa e aliases explícitos de marcas. Não há fusão aproximada de modelos nem inferência de versão.
4. Validação de país, estado/país, ano2021–2027, fonte conhecida, origem real, medida, datas, periodicidade, mês/trimestre e valores não negativos. Fonte com prefixo reservado SYN e qualquer origem diferente de real são rejeitadas.
5. Registros inválidos vão à quarentena; preços acima de10milhões ou unidades acima de1bilhão vão à revisão, sem corte artificial dos valores. Duplicidades são removidas por origem/fonte/identificador. Ausências legítimas não viram zero.
6. Broadcast joins associam dimensões pequenas. Segmento/combustível desconhecidos permanecem no domínio não informado; estado/cidade/preço/moeda podem continuar nulos. A dimensão de cidades fica vazia enquanto não houver fonte municipal validada.
7. Silver guarda a fato tratada por país/ano. A carga JDBC usa restrições PostgreSQL de FK/PK, medida, origem e partição anual. A contagem carregada deve coincidir com a tratada.
8. Materialized views e Window Functions agregam somente fatos reais, sem combinar snapshots anuais, mensais e trimestrais.

O manifesto de entrada SHA256 contempla CSVs, fontes, mídia, câmbio, geometrias e código ETL/SQL. Reuso de carga exige hashes, contagem real e estado concluído compatíveis. `--force` reconstrói o banco dedicado; remove resíduos de fatos/fontes/localidades antigos e recria modelos/marcas a partir das observações. Campos legados seed/linhas_sinteticas do log recebem zero e não participam da API pública. O relatório de qualidade registra modo real, manifesto, contagens recebidas/tratadas/rejeitadas, extremos, duplicidades, ausências e reconciliação.

## Modelo estrela

`fato_vendas` contém observações agregadas reais, com dimensões país, estado, cidade, marca, modelo, segmento, combustível, tempo, fonte e medida. PK ano/registro_id e partições anuais preservam identificação. `fato_mercado` guarda denominadores publicados separadamente. `dim_medida` conserva as definições. `fonte_dados`, `midia`, `cambio` e `execucao_etl` mantêm proveniência, direitos e auditoria. O dicionário CSV é regenerado do DDL e RAW_SCHEMA por `docs/gerar_dicionario.py`.

Dimensão de tempo usa a data representativa do período; não se trata de dia individual de transação. Ano tem mês nulo; trimestre aponta ao mês final3/6/9/12. Códigos ISO de estado incluem país; UFs brasileiras conservam código IBGE. As geometrias são representações Natural Earth simplificadas.

## Denominadores, ordenação e mercados

Participação = unidades do modelo / total elegível compatível ×100. O denominador precisa ser único, positivo, pelo menos igual ao volume observado e compatível com país, geografia, ano, período, medida e combustível aplicável. Segmento informado sem denominador próprio não recebe uma participação nacional. Top50 não vira automaticamente o total nacional. Sem total compatível, participação e cobertura ficam nulas com explicação.

API ordena volume decrescente com desempate estável por marca/modelo. Cartões de mercados são descrições independentes: cada país resolve sua medida quando ela não foi solicitada e devolve código/nome. Medidas diferentes não formam ranking numérico entre mercados. Ao fixar uma medida, países sem observação desse universo ficam indisponíveis. O mapa global mantém a mesma medida em uma consulta.

Variação anual só é calculada com ano anterior consecutivo observado e base positiva. Ausência no topN não é zero. Revisões administrativas, alterações de cobertura e nomes agregados limitam séries e comparações. Volume absoluto não controla população, frota, renda ou exposição e não comprova causalidade.

## Preço e estatística

Preço ausente permanece nulo. As fontes atuais não publicam preços observados por modelo nesta coleta; portanto boxplot de preços e correlação não recebem valores substitutos. A estrutura de câmbio conserva moeda, data e fonte de referência BCE, aplicável apenas quando houver preço real publicado. Conversão de referência não equivale ao câmbio histórico de cada venda.

A descritiva usa volumes por modelo. Desvio padrão amostral requer mais de um modelo; HHI usa a cobertura carregada e não implica concentração de todo o mercado. Pearson requer pelo menos três pares preço/volume e variância positiva nas duas dimensões. Ausências nunca são preenchidas para viabilizar uma estatística.

Participação mensal divide cada mês pelo ano observado. Índice sazonal mensal só existe com12meses publicados; a série incompleta conserva a lacuna. Meses e trimestres não são somados ao anual. Não há interpolação de lacunas nem previsão automática na API. Qualquer análise exploratória temporal deve identificar universo, janela e limitações da fonte.

## Mídia, licenças e apresentação

Fotos são ilustrativas, com lugar, autor, licença e origem. Uma imagem nacional não é identificada como retrato de um estado específico. A foto não comprova versão, motorização ou equipamentos do modelo agregado. Nuvem pondera marca/modelo pelas unidades do recorte; sua silhueta é decorativa. Animações devem respeitar redução de movimento.

Dados DfT usam OGLv3; geometrias Natural Earth são de domínio público; fotografias têm licença individual. Fenabrave preserva direitos da publicação sem licença aberta inventada. Fonte consultada não significa coletada ou redistribuível; SMMT e referências de frota não são promovidas ao universo de vendas. Os direitos dos dados são independentes do código.

## Reprodutibilidade e verificação

Versões fixadas constam dos manifests e lockfile; consulta a registros oficiais em docs/versions.json. Testes Spark validam normalização, rejeição, agregação e entrada real. Testes API comparam resultados ao PostgreSQL e verificam ausência de fatos/fontes/localidades artificiais. A integração exige última execução concluída em modo real. O status503 protege reconstruções incompletas.

Docker permanece sem execução comprovada no ambiente de preparação; comandos e critérios estão em VALIDACAO_DOCKER.md. Logs históricos não substituem testes da carga atual. Inspeção visual, build web, testes nativos e execução Docker são evidências distintas, registradas apenas quando realizadas.
