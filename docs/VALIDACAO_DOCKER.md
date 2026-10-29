# Execução e validação do Docker Compose

Status desta etapa: **não executada no ambiente de preparação, pois Docker não estava instalado/disponível**. Os Dockerfiles e o Compose foram escritos para o stack versionado; a execução nativa de componentes, mesmo quando aprovada, não comprova o build ou a integração dos contêineres.

## Contrato operacional

1. PostgreSQL18.6 inicializa um volume dedicado e responde a `pg_isready`.
2. O serviço `etl` aplica os SQL versionados, valida os registros reais publicados, grava Parquet/JDBC, materializa agregações e registra a execução como concluída. Sai com código0 apenas no sucesso.
3. A API só inicia após `etl` concluir com sucesso. `/health` verifica acesso ao banco e execução concluída, retornando503 enquanto não estiver pronta.
4. O Next é servido em build standalone e aguarda a API saudável. Rewrites e SSR usam `http://api:8000` na rede interna.

O banco, Parquet e quarentena usam volumes. O relatório de qualidade é gravado no `./docs` do host. API/web executam como usuários sem privilégio administrativo dentro de suas imagens. As portas são publicadas em127.0.0.1 para uso local.

## Comandos para confirmar na máquina com Docker

Na pasta do projeto:

```powershell
docker compose version
docker compose config --quiet
docker compose build --pull
docker compose up --build -d
docker compose logs -f etl
docker compose ps -a
Invoke-RestMethod 'http://localhost:8100/health'
Invoke-RestMethod 'http://localhost:8100/paises/BR/top-carros?ano=2025&origem=real&periodicidade=anual'
Invoke-RestMethod 'http://localhost:8100/estados/BR-SP/top-carros?pais=BR&ano=2025&origem=real&periodicidade=anual'
```

Critérios de aceite: ETL com código0; API e web saudáveis; `/health` com banco PostgreSQL e ETL concluído; ranking nacional real com fontes; recorte estadual real sem cobertura devolvido vazio, sem imputação. Conferir `docs/qualidade_etl.json`, o volume efetivamente carregado e o banco antes de registrar a validação como aprovada.

Para testes:

```powershell
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)"
docker compose --profile reports run --rm analysis
```

A análise salva PNG/CSV/JSON/Markdown em `notebooks/resultados`. Lighthouse deve ser executado contra o servidor final, em condições documentadas; sua pontuação não foi pressuposta pelo uso do framework.

## Imagens e compatibilidade

- API/ETL: `python:3.12.14-slim-bookworm`; Spark4.2.1 e bibliotecas fixadas em requirements.txt. O ETL instala o JRE17 oficial do Debian, uma versão suportada pela família Spark4.2.
- Banco: `postgres:18.6-bookworm`. O volume cobre `/var/lib/postgresql` e `PGDATA=/var/lib/postgresql/18/docker`, adequados à organização versionada da imagem PostgreSQL18.
- Web: `node:24.22.1-bookworm-slim`; pnpm11.25.0 e lockfile. O build usa a URL interna da API; a imagem final contém somente os arquivos standalone, assets e servidor.

As versões das bibliotecas foram pesquisadas em registros oficiais; tags de imagem e instalação completa ainda precisam ser obtidas pelo Docker da máquina que executar os comandos. Para produção, escolha uma política de atualização e registre também os digests das imagens após o pull aprovado.
