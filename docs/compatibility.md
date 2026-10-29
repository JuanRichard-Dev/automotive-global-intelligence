# Auditoria de versões e compatibilidade

Consulta em 27/10/2026. Metadados das versões estão em `versions.json`, obtidos exclusivamente de PyPI/npm; o script `query_versions.py` permite repetir a consulta. A instalação e os testes do projeto devem confirmar a compatibilidade de resolução e execução, sem substituir o lockfile por tags `latest`.

## Runtime e versões de infraestrutura verificadas

| Componente | Constatação | Fonte oficial |
|---|---|---|
| Spark | A página de downloads anuncia 4.2.1, lançado em 27/10/2026; a documentação `latest` ainda identifica 4.2.0 | https://spark.apache.org/downloads.html |
| Java/Spark | A família Spark 4.2 documenta Java 17, 21 e 25; Java 25 anterior a 25.0.3 está depreciado. Java 21 LTS é uma escolha compatível para ETL local/Docker | https://spark.apache.org/docs/latest/ |
| Python/Spark | Python >=3.10; a versão local 3.12.14 está na faixa suportada | https://spark.apache.org/docs/latest/api/python/getting_started/install.html |
| pandas/Spark | A documentação 4.2.0 ainda informa >=2.2,<3.0, mas os metadados PyPI do novo PySpark 4.2.1 removem esse teto. Último pandas estável: 3.1.0; último 2.x: 2.3.3. Usar 2.3.3 é escolha conservadora compatível com ambas as declarações; 3.1.0 exige teste de execução do caminho utilizado | https://spark.apache.org/docs/latest/api/python/getting_started/install.html e https://pypi.org/pypi/pyspark/json |
| PostgreSQL | A tabela de suporte indica 18.6 como último estável; 19 RC1 é pré-lançamento | https://www.postgresql.org/support/versioning/ |
| pgJDBC | A página oficial indica 42.7.14 para Java 8+ e servidores PostgreSQL modernos; é compatível com Java21/PostgreSQL18 | https://jdbc.postgresql.org/download/ |
| Next.js | Documentação/registro indicam 16.4.3; Node >=20.9 e TypeScript >=5.1. O Node24.22.1 local atende | https://nextjs.org/docs/app/getting-started/installation |

## Critérios para fixar o conjunto final

- Usar apenas releases estáveis identificados pelos registros, excluindo `rc`, `beta`, `canary` e `snapshot` dos pins de runtime.
- Declarar React e React DOM na mesma versão estável e respeitar os peers declarados pelo Next e pelos componentes Radix/Motion.
- Validar o peer de `echarts-wordcloud`: se restringir a ECharts 5, a versão atual de ECharts 6 não pode ser combinada automaticamente. Nesse caso, usar uma alternativa permitida, como `d3-cloud`, ou documentar um pin compatível.
- Separar dependências do ETL e API se houver conflito: o serviço Spark não precisa herdar as versões do notebook/API ou do projeto anterior.
- `psycopg[binary]` simplifica testes locais; `psycopg` usa a mesma versão do pacote principal. O driver JDBC é necessário para a carga Spark, independentemente do driver da API.
- Validar com `pip check`, instalação npm sem `--legacy-peer-deps`, TypeScript/ESLint e build de produção. Verificação documental não equivale a testes executados.

## Pins pesquisados para a implementação

Os números abaixo são releases estáveis retornados por PyPI/npm em 27/10/2026; a decisão de compatibilidade não equivale a instalação ou build já aprovados.

### Python

| Pacote | Último estável consultado | Escolha sugerida |
|---|---|---|
| pyspark | 4.2.1 | 4.2.1 |
| fastapi | 0.162.0 | 0.162.0 |
| pydantic | 2.14.1 | 2.14.1; satisfaz FastAPI >=2.9 |
| psycopg | 3.3.6 | psycopg[binary]==3.3.6 |
| pandas | 3.1.0 | 2.3.3 no ETL por compatibilidade documental conservadora; 3.1.0 permitido pelos metadados novos se testado |
| numpy | 2.5.4 | 2.5.4; Python >=3.12 atendido |
| matplotlib | 3.11.2 | 3.11.2 |
| seaborn | 0.13.2 | 0.13.2 |
| plotly | 7.1.0 | 7.1.0 |
| wordcloud | 1.9.6 | 1.9.6 |
| geopandas | 1.2.0 | 1.2.0; requer pandas >=2.2 e NumPy >=2 |
| sqlalchemy | 2.1.6 | 2.1.6; driver psycopg3.3.6 satisfaz faixa declarada |
| pytest | 9.2.0 | 9.2.0 |
| httpx | 0.28.1 | 0.28.1 |
| uvicorn | 0.54.0 | 0.54.0 |
| pyarrow | 26.0.0 | 26.0.0; satisfaz Spark >=18 |

### Front-end

| Pacote | Último estável | Compatibilidade documental |
|---|---|---|
| next | 16.4.3 | Node >=20.9 e React ^19 aceitam o runtime/pins abaixo |
| react / react-dom | 19.3.1 / 19.3.1 | Devem ser mantidos iguais |
| typescript | 7.0.2 | Next declara mínimo5.1; testar integração do compilador e eslint-typescript8 antes de aceitar7 |
| tailwindcss / @tailwindcss/postcss | 4.3.3 / 4.3.3 | Plugin e núcleo iguais |
| shadcn | 4.23.0 | CLI exige Node >=20.18.1; componentes gerados fazem parte do código, não de um renderer Python |
| @radix-ui/react-select | 2.4.1 | Peer React/DOM19 suportado |
| @radix-ui/react-dialog | 1.3.1 | Peer React/DOM19 suportado |
| motion | 14.7.1 | Peer React/DOM18 ou19 |
| gsap | 3.15.0 | Sem peer React restritivo |
| lenis | 1.3.27 | Peer React >=17 |
| echarts | 6.1.0 | Não combinar com echarts-wordcloud2.1.0 |
| echarts-wordcloud | 2.1.0 | Peer ^5.0.1 exclui ECharts6; consultado e descartado |
| d3-cloud | 1.2.9 | Alternativa escolhida; não impõe peer ECharts |
| maplibre-gl | 6.16.0 | Node >=16.14; atende Node24 |
| @tanstack/react-query | 5.105.0 | React18/19 suportados |
| zustand | 5.0.16 | React >=18 |
| lucide-react | 1.62.0 | React19 suportado |
| eslint / eslint-config-next | 10.13.0 / 16.4.3 | Config-next aceita >=9, mas seus plugins transitivos devem ser resolvidos sem ignorar peers |
| prettier | 3.9.10 | Node >=14 |
| @types/react / @types/react-dom | 19.3.0 / 19.3.0 | Alinhados à família React19.3 |
| @types/node | 26.6.5 | Último global mira Node26; preferir um pin24.x verificado para o runtimeNode24 |

`versions.json` preserva URLs específicas, horários e intervalos declarados de dependências/peers. O runtime Adoptium21 consultado oferece build Windows `21.0.12.1+1-LTS`, com URL oficial e SHA256 do arquivo no mesmo JSON.

## Disponibilidade do ambiente

O agente principal verificou que Docker, Java e PostgreSQL não estavam no PATH inicial. A arquitetura Docker pode ser preparada sem presumir que `docker compose up` foi executado. Java e PostgreSQL portáteis, quando usados nos testes, devem ser registrados como ambiente de validação distinto do Compose.

## Ajuste verificado no build
TypeScript 7.0.2 compila a interface, mas typescript-eslint 8.72.1 exige API TS6. Foram instalados os aliases oficiais typescript=npm:@typescript/typescript6@6.0.2 e @typescript/native=npm:typescript@7.0.2. Orientação Microsoft: https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/#running-side-by-side-with-typescript-6.0

ESLint10.13.0 é incompatível com peers eslint-plugin-import/react/jsx-a11y do eslint-config-next16.4.3. Fixado ESLint9.39.5 (último9 estável consultado no registry oficial) para lint; pnpm install --strict-peer-dependencies passa. Essa linha já está fora do suporte upstream: atualizar quando os plugins suportarem ESLint10, sem ignorar peers.
