# Motor Atlas — Automotive Global Intelligence

Plataforma de exploração geográfica de registros automotivos publicados: **fontes → PySpark → PostgreSQL → FastAPI → Next.js**. A aplicação consulta o banco para apresentar modelos, períodos, indicadores, fontes e mídia. Os registros mantêm sua medida original; emplacamentos de novos e primeiros registros que incluem importações têm universos diferentes.

## Cobertura desta entrega

A base contém evidências nacionais do Brasil, Reino Unido, Itália e Áustria. Itália: Top 50 anual 2025 da UNRAE. Áustria: Top 50 de automóveis 2025 da Statistik Austria (Tabela 7), ambos com totais elegíveis publicados e fonte rastreável. Brasil: top50 de automóveis dos informes Fenabrave, com totais elegíveis publicados à parte. Reino Unido: DfT/DVLA VEH0160, automóveis por fabricante, modelo genérico e combustível, incluindo novos e importados anteriormente usados. Anos completos, meses e trimestres são guardados separadamente.

Não há observações estaduais ou municipais validadas nesta coleta. O catálogo de estados e as geometrias são referências geográficas: não demonstram cobertura automotiva. A lista de estados disponíveis exige fatos reais; o mapa estadual fica vazio quando eles não existem. Preço, segmento, cidade e outros atributos não publicados permanecem desconhecidos. Nenhum total nacional é repartido artificialmente por estado ou cidade.

## Executar com Docker

Pré-requisitos: Docker Engine/Desktop com ComposeV2, internet no primeiro build e memória para PostgreSQL, Spark e Node. Na pasta do projeto:

```powershell
docker compose up --build
```

O Compose aguarda PostgreSQL saudável, executa a carga real e só inicia API/web após sua conclusão. Portas locais:

- Aplicação: http://localhost:3100
- API/Swagger: http://localhost:8100/docs
- Prontidão: http://localhost:8100/health
- PostgreSQL: 127.0.0.1:55432; banco/usuário automotive.

A senha de desenvolvimento está em `.env.example`; o Compose funciona com os padrões locais. Para alterar portas, credenciais ou memória do Spark, copie esse arquivo para `.env`. Credenciais usadas em DATABASE_URL precisam ser codificadas como URI quando contêm caracteres especiais.

Docker não estava disponível no ambiente de preparação. A sintaxe do Compose foi inspecionada; build e integração dos contêineres continuam pendentes. Consulte `docs/VALIDACAO_DOCKER.md`. Validação nativa e Docker são evidências distintas.

## Reconstrução e cache da carga

A carga normal aceita apenas dados reais dos CSVs canônicos. Não existe volume artificial configurável. Um manifesto SHA256 inclui `real_sales.csv`, `market_totals.csv`, fontes, mídia, câmbio, geometrias e regras ETL/SQL. A execução só é reutilizada quando a última carga está concluída em modo real, o manifesto e a contagem de entrada coincidem, a contagem de fatos reais confere e não há outra origem na fato.

Para reconstruir o banco dedicado:

```powershell
docker compose stop api web
docker compose run --rm etl python -m etl.pipeline --force
docker compose up -d api web
```

A reconstrução limpa os fatos, remove resíduos de fontes/localidades antigas, recria marcas/modelos observados e materializa as visões. As restrições passam a aceitar somente fatos reais. Os campos técnicos históricos `seed` e `linhas_sinteticas` continuam no registro de execução por compatibilidade de schema, com zero em novas cargas; não são expostos pelo bootstrap da API. O argumento legado `--rows` só aceita zero. O cache HTTP tem TTL de60 segundos; reinicie a API após a recarga.

```powershell
docker compose logs -f etl
docker compose ps -a
docker compose down
```

`down` mantém os volumes. `/health` responde503 enquanto a última execução não estiver concluída em modo real, evitando servir uma reconstrução parcial ou uma carga antiga incompatível.

## Arquitetura e diretórios

```mermaid
flowchart LR
    F[Publicações e snapshots rastreáveis] --> E[PySpark: schema, validação e Window]
    E --> P[Parquet bronze e silver por país/ano]
    E -->|JDBC| DB[(PostgreSQL estrela e views)]
    DB --> API[FastAPI]
    API --> W[Next.js / React / TypeScript]
    DB --> A[Análise Python e relatórios]
```

| Caminho | Conteúdo |
|---|---|
| api/ | API REST, consultas parametrizadas, filtros e cache |
| etl/ | Bootstrap, transformações, agregações e carga JDBC |
| db/ | Schema, domínios e materialized views versionados |
| web/ | Next.js App Router, React e TypeScript com lockfile |
| data/raw/ | CSVs canônicos reais e snapshots de referência |
| data/seed/ | Fontes, geometrias, mídia e dimensões de junção regeneráveis |
| data/media/ | Imagens licenciadas servidas pela API |
| data/bronze/real/ | Observações reais brutas em Parquet country_iso/year |
| data/silver/ | Fato tratada em Parquet country_iso/ano |
| data/analytics/ | Rankings e sazonalidade Spark em Parquet |
| data/quarantine/ | Rejeições e extremos separados para revisão |
| notebooks/ | Análise Python reproduzível e gráficos exportáveis |
| docs/ | Dicionário, metodologia, qualidade e validação |

O front-end não usa Streamlit/Dash. Dados analíticos, geometrias, configuração e créditos vêm do PostgreSQL pela API. O navegador não contém uma base numérica de fallback.

## Fontes e direitos

| Fonte | Uso e limites |
|---|---|
| [Fenabrave](https://www.fenabrave.org.br/portalv2/Conteudo/Emplacamentos) | Top50 nacional de automóveis novos e total elegível da edição; sem UF, preço, combustível ou segmento por modelo confirmados |
| [DfT/DVLA VEH0160](https://www.gov.uk/government/statistical-data-sets/vehicle-licensing-statistics-data-files) | Primeiros registros de Cars por fabricante/modelo/combustível; inclui importados usados; licença OGLv3 |
| [BCE](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml) | Referência cambial datada; só aplicável quando houver preço observado |
| [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) | Geometrias simplificadas de domínio público; referência de representação |
| Wikimedia Commons | Fotos ilustrativas com autoria, licença e página individual preservadas |

Fonte consultada não significa fonte carregada. Restrições de redistribuição da SMMT e demais fontes pesquisadas são registradas no catálogo. Estoque de frota, ano-modelo e totais sem modelo não foram convertidos em vendas por modelo. Os direitos dos dados são independentes do código; publicações Fenabrave conservam seus direitos, sem atribuição de licença aberta inventada. Fotografias não comprovam versão/equipamentos do agregado estatístico. Consulte `data/seed/sources.json`, `/fontes` e `docs/referencias/`.

## API e interpretação

Principais endpoints: `/bootstrap`, `/paises`, `/paises/{iso}/estados`, `/paises/{iso}/top-carros`, `/estados/{uf}/top-carros`, `/series-temporais`, `/estatisticas`, `/mapa`, `/comparador`, `/nuvem-palavras`, `/modelos/{id}`, `/fontes` e `/midia`.

Filtros: país, estado quando publicado, ano2021–2027, medida, periodicidade, mês final aplicável, segmento e combustível. A origem aceita é `real`; outra origem retorna422. Exemplos:

```text
/paises/BR/top-carros?ano=2025&origem=real&medida=new_registrations&periodicidade=anual
/paises/GB/top-carros?ano=2025&medida=first_registrations_including_imports
/mapa?pais=BR&ano=2025&nivel=estado
/comparador?ano=2025
```

Participação usa um denominador publicado, único e compatível; ausência permanece NULL. O top50 não vira automaticamente o mercado nacional completo. Os cartões de mercados resolvem a medida disponível de cada país e a exibem explicitamente; medidas diferentes não formam uma comparação numérica. Um parâmetro `medida` explícito é respeitado em todos os cartões. O mapa global mantém uma medida por consulta e deixa países sem observação compatível sem valor.

## Stack e execução nativa

Pins Python estão em `requirements.txt`; web em `web/package.json` e `web/pnpm-lock.yaml`; pesquisa de registros oficiais em `docs/versions.json` e `docs/compatibility.md`. Referência: Python3.12.14, Spark4.2.1, PostgreSQL18.6, JDBC42.7.14, Node24.22.1, Next16.4.3 e React19.3.1. Spark aceita Java17/21; Docker usa JRE17 e o ambiente Windows pode usar JDK21.

Com Python/Java/PostgreSQL configurados:

```powershell
python -m pip install -r requirements.txt
$env:DATABASE_URL='postgresql://automotive:automotive_local@127.0.0.1:55432/automotive'
python -m etl.pipeline --force
python -m uvicorn api.main:app --host 127.0.0.1 --port 8100
```

Em outro terminal, dentro de `web/`, use o pnpm fixado no projeto, instale com `pnpm install --frozen-lockfile`, depois `pnpm build` e `pnpm start --port 3100`. `API_INTERNAL_URL` deve apontar para `http://127.0.0.1:8100` durante build/execução nativa. O servidor web funciona atrás do rewrite da própria aplicação.

No Windows, o Spark compila a classe de filesystem portátil incluída em `etl/windows/` com o `javac` do JAVA_HOME. O JAR JDBC versionado acompanha `etl/jars/`. Não se exige um binário winutils externo.

## Verificações reproduzíveis

```powershell
python -m pytest tests/test_etl.py -q
python -m pytest tests/test_api.py -q
python docs/gerar_dicionario.py
python notebooks/analise.py --pais BR --origem real --ano 2025
```

Testes Spark usam ações reais do JVM e o CSV publicado, sem gravar PostgreSQL. Testes de API são integrações de leitura contra o banco carregado e falham se ele estiver indisponível. Relatórios de análise, contagens, logs e inspeções visuais devem corresponder à última carga real. `docs/qualidade_etl.json` registra hashes, contagens, rejeições, ausências e reconciliação JDBC. Não interprete um relatório histórico como validação automática da carga atual.
