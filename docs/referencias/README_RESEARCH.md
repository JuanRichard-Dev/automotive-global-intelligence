# Fontes reais pesquisadas — 27/10/2026

Arquivos canônicos:

- `UK_SMMT_canonical_annual.csv`: top 10 real de **veículos novos**, 2025 completo. Denominador do mesmo comunicado: 2.020.520 automóveis. Dados por combustível/segmento do modelo ficam nulos: o ranking de todos os combustíveis não permite inferi-los.
- `UK_DFT_canonical_annual.csv`: série administrativa oficial por fabricante, modelo genérico e combustível, anos completos 2021–2025. Métrica distinta: **primeiros registros no Reino Unido, incluindo importações de usados**. Não somar à SMMT nem apresentar como vendas exclusivamente de veículos novos.
- `UK_DFT_canonical_quarterly.csv`: trimestres efetivamente publicados, sem desagregação mensal. Não somar aos acumulados anuais dos mesmos registros.
- `UK_DFT_denominators.csv`: total do mesmo universo de automóveis, por ano e, adicionalmente, por combustível. Nunca usar denominador SMMT para numeradores DfT.
- `UK_quality_report.json`: contagens de origem, filtros, células suprimidas/ausentes e reconciliação dos totais.
- `research_catalog.json`: catálogo das fontes solicitadas, com ano, licença/limite conhecido, link e status real da pesquisa/coleta.
- `download_metadata.json`: arquivos baixados, bytes, hashes SHA-256 e dia de acesso.

## Regras indispensáveis

O `BodyType == Cars` do DfT inclui automóveis de passageiros, mas não identifica carroceria SUV/sedan/hatch de cada modelo; segmento permanece desconhecido. Preços não são publicados. UF/estado e cidade não constam da fonte de modelos e ficam nulos.

O DfT documenta os símbolos `[c]` (1–4 veículos confidenciais), `[x]` (não disponível) e `[z]` (não aplicável). O transformador trata qualquer célula não numérica como desconhecida, propagando a ausência ao agregado, sem imputar zero. Na edição efetivamente baixada, as células selecionadas de automóveis para 2021–2026 são inteiras e não negativas, sem esses símbolos; isso é verificado no relatório, não presumido.

Nomes de modelos genéricos faltantes permanecem como categoria ausente da fonte, sem distribuir seus volumes por modelos conhecidos. O denominador inclui todos os modelos elegíveis, inclusive categorias desconhecidas. A normalização remove o prefixo exato da fabricante do nome genérico, preservando `source_generic_model`.

SMMT e DfT possuem escopos diferentes, como explicitado nas próprias notas oficiais do DfT: SMMT compila dados de fabricantes e conta veículos novos; DfT inclui todas as primeiras matrículas no Reino Unido, inclusive importações. Ambas são fontes reais, mas respondem perguntas diferentes.

## Limites geográficos pesquisados

A Senatran disponibiliza inventário de frota por UF/município/marca/modelo, não fluxo de vendas. O dataset Washington Electric Vehicle Population Data contém BEVs/PHEVs atualmente registrados, não novas vendas nem todo o mercado; `Model Year` não é ano de compra. A tabela federal FHWA MV-1 apresenta totais estaduais por tipo, sem modelo. Nenhuma dessas bases foi promovida à fato de vendas ou usada para fabricar rankings estaduais.

As páginas OICA, ACEA e MarkLines foram pesquisadas; suas restrições e o nível de agregação são registrados no catálogo. Não foi contornado login/paywall. A página oficial KBA retornou 503. Não foi confirmada uma extração Kaggle com origem e licença adequadas; nenhuma foi usada como dado real.

## Links primários principais

- DfT/DVLA: https://www.gov.uk/government/statistical-data-sets/vehicle-licensing-statistics-data-files
- Definições DfT: https://www.gov.uk/government/publications/vehicles-statistics-information/vehicle-licensing-statistics-notes-and-definitions
- SMMT 2025: https://www.smmt.co.uk/uk-new-car-market-breaches-two-million-as-almost-one-in-four-buyers-go-electric/
- Licença OGL v3: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
- RENAVAM/Senatran: https://dados.transportes.gov.br/pt_PT/dataset/registro-nacional-de-veiculos-automotores-renavam
- Washington/DOL: https://catalog.data.gov/dataset/electric-vehicle-population-data

As publicações HTML completas foram baixadas para auditoria local. Os termos oficiais SMMT permitem uso pessoal não comercial dos materiais do site e exigem permissão expressa para outros usos: o arquivo SMMT deve ser identificado como fonte restrita, sem alegar licença aberta, e não promovido a uma distribuição pública/comercial sem autorização. O CSV DfT é distribuído sob OGL v3, com atribuição a DfT/DVLA, sendo a opção de base britânica aberta. Os HTML SMMT completos não devem ser redistribuídos como conteúdo do produto.
