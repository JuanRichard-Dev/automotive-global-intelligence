# Publicação completa do Motor Atlas

O frontend Next.js já está no projeto Vercel `motor-atlas` (root `web`). Para preservar os rankings e filtros reais, mantenha a API FastAPI e o PostgreSQL originais.

## 1. Banco Supabase Atlas
O esquema SQL `db/001_schema.sql` e as configurações `db/002_seed.sql` já foram instalados no projeto Supabase Atlas. Ainda falta executar a carga completa de dados.

Crie no GitHub → Settings → Secrets and variables → Actions o secret **ATLAS_DATABASE_URL** com a URI de conexão PostgreSQL do Supabase Atlas (usar SSL). Nunca coloque a URI no código. Execute manualmente o workflow **Carregar dados reais no Supabase Atlas**, que roda o ETL original PySpark e valida o volume carregado. O ETL consome os CSVs e as evidências originais do GitHub.

## 2. API independente
Na Vercel, importe o mesmo repositório como um **segundo projeto** chamado `motor-atlas-api`, com Root Directory na raiz do repositório (não em `web`). Configure o build de Python/FastAPI conforme a versão em uso; o entrypoint é `api/index.py`, que exporta `app`.

A API usa `DATABASE_URL` com a URI PostgreSQL privada, configurada apenas nas variáveis de ambiente da Vercel. Não exponha a credencial ao navegador.

**Importante:** a API usa `data/media` para servir arquivos de fotos e há uma dependência Python FastAPI. Verifique a inclusão das mídias no pacote e a compatibilidade dos arquivos de build da Vercel antes da publicação.

## 3. Frontend
No projeto Vercel `motor-atlas`, adicione `API_INTERNAL_URL` apontando para a URL HTTPS da API pública (sem barra final). Refaça o deployment. O Next.js busca `/bootstrap` no servidor e encaminha `/api/*`, `/media/*` via rewrites.

## 4. Testes
- GET URL-API/health deve retornar status ok após carga
- GET URL-API/bootstrap deve retornar config, paises e painel com rankings
- Abrir frontend e testar rankings, filtros, série temporal e fotos
- Conferir logs de API e frontend sem publicar credenciais

**Não use a branch `feat/atlas-supabase-auth`**: o site acadêmico é público.
