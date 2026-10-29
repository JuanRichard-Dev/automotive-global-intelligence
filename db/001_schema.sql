-- Modelo estrela. Medida, período, origem e abrangência fazem parte do contrato.
CREATE TABLE IF NOT EXISTS fonte_dados (
  id text PRIMARY KEY, organizacao text NOT NULL, titulo text NOT NULL,
  url text NOT NULL, ano_inicio smallint, ano_fim smallint, licenca text NOT NULL,
  licenca_url text, acesso_em date NOT NULL, tipo text NOT NULL,
  medida text, cobertura text NOT NULL, limitacoes text NOT NULL,
  sha256 text, status text NOT NULL DEFAULT 'carregada'
);
CREATE TABLE IF NOT EXISTS dim_pais (
  id smallint PRIMARY KEY, iso char(2) UNIQUE NOT NULL CHECK (iso ~ '^[A-Z]{2}$'),
  iso3 text, nome text NOT NULL, continente text, geometria jsonb
);
CREATE TABLE IF NOT EXISTS mapa_base (
  id text PRIMARY KEY, pais_id smallint REFERENCES dim_pais(id), nome text NOT NULL,
  geometria jsonb NOT NULL, fonte_id text NOT NULL REFERENCES fonte_dados(id)
);
CREATE TABLE IF NOT EXISTS dim_estado (
  id integer PRIMARY KEY, pais_id smallint NOT NULL REFERENCES dim_pais(id),
  codigo text UNIQUE NOT NULL, sigla text NOT NULL, nome text NOT NULL,
  codigo_ibge text, geometria jsonb, UNIQUE (id,pais_id)
);
CREATE TABLE IF NOT EXISTS dim_cidade (
  id integer PRIMARY KEY, pais_id smallint NOT NULL REFERENCES dim_pais(id),
  estado_id integer, codigo text UNIQUE NOT NULL, nome text NOT NULL,
  tipo text NOT NULL, FOREIGN KEY (estado_id,pais_id) REFERENCES dim_estado(id,pais_id),
  UNIQUE (id,pais_id,estado_id)
);
CREATE TABLE IF NOT EXISTS dim_marca (id integer PRIMARY KEY,nome text UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS dim_modelo (
  id integer PRIMARY KEY, marca_id integer NOT NULL REFERENCES dim_marca(id),
  nome text NOT NULL, chave text UNIQUE NOT NULL, UNIQUE(id,marca_id)
);
CREATE TABLE IF NOT EXISTS dim_segmento (id smallint PRIMARY KEY,codigo text UNIQUE NOT NULL,nome text NOT NULL);
CREATE TABLE IF NOT EXISTS dim_combustivel (id smallint PRIMARY KEY,codigo text UNIQUE NOT NULL,nome text NOT NULL);
CREATE TABLE IF NOT EXISTS dim_tempo (
  id integer PRIMARY KEY, data_iso date UNIQUE NOT NULL, ano smallint NOT NULL,
  mes smallint NOT NULL CHECK(mes BETWEEN 1 AND 12), trimestre smallint NOT NULL,
  mes_nome text NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_medida (codigo text PRIMARY KEY,nome text NOT NULL,definicao text NOT NULL);
CREATE TABLE IF NOT EXISTS midia (
  id text PRIMARY KEY,pais_id smallint REFERENCES dim_pais(id),estado_id integer REFERENCES dim_estado(id),
  modelo_id integer REFERENCES dim_modelo(id),tipo text NOT NULL,url text NOT NULL,
  titulo text NOT NULL,lugar text,credito text NOT NULL,licenca text NOT NULL,
  licenca_url text NOT NULL,origem_url text NOT NULL,largura integer,altura integer,
  blur_data_url text,observacao text NOT NULL
);
CREATE TABLE IF NOT EXISTS cambio (
  moeda char(3) NOT NULL,data_referencia date NOT NULL,usd_por_unidade numeric(20,10) NOT NULL CHECK(usd_por_unidade>0),
  fonte_id text NOT NULL REFERENCES fonte_dados(id),PRIMARY KEY(moeda,data_referencia)
);
CREATE TABLE IF NOT EXISTS fato_vendas (
  ano smallint NOT NULL,registro_id bigint NOT NULL,
  pais_id smallint NOT NULL REFERENCES dim_pais(id),estado_id integer,cidade_id integer REFERENCES dim_cidade(id),
  marca_id integer NOT NULL REFERENCES dim_marca(id),modelo_id integer NOT NULL,
  segmento_id smallint NOT NULL REFERENCES dim_segmento(id),combustivel_id smallint NOT NULL REFERENCES dim_combustivel(id),
  tempo_id integer NOT NULL REFERENCES dim_tempo(id),fonte_id text NOT NULL REFERENCES fonte_dados(id),
  origem text NOT NULL CHECK(origem='real'),medida text NOT NULL REFERENCES dim_medida(codigo),
  periodicidade text NOT NULL CHECK(periodicidade IN ('anual','mensal','trimestral')),
  mes smallint CHECK(mes BETWEEN 1 AND 12),unidades bigint NOT NULL CHECK(unidades>=0),
  preco_original numeric(16,2),moeda_original char(3),cambio_usd numeric(20,10),preco_usd numeric(16,2),
  data_cambio date,registro_origem text NOT NULL,hash_origem text NOT NULL,
  coletado_em date NOT NULL,PRIMARY KEY(ano,registro_id),
  FOREIGN KEY(estado_id,pais_id) REFERENCES dim_estado(id,pais_id),
  FOREIGN KEY(cidade_id,pais_id,estado_id) REFERENCES dim_cidade(id,pais_id,estado_id),
  FOREIGN KEY(modelo_id,marca_id) REFERENCES dim_modelo(id,marca_id),
  CHECK(preco_original IS NULL OR preco_original>=0),CHECK(preco_usd IS NULL OR preco_usd>=0),
  CHECK((periodicidade='anual' AND mes IS NULL) OR (periodicidade<>'anual' AND mes IS NOT NULL)),
  CHECK(fonte_id NOT LIKE 'SYN%')
) PARTITION BY RANGE (ano);
CREATE TABLE IF NOT EXISTS fato_mercado (
  id bigserial PRIMARY KEY,pais_id smallint NOT NULL REFERENCES dim_pais(id),
  estado_id integer REFERENCES dim_estado(id),ano smallint NOT NULL,mes smallint,
  periodicidade text NOT NULL,origem text NOT NULL CHECK(origem='real'),medida text NOT NULL REFERENCES dim_medida(codigo),
  combustivel_id smallint REFERENCES dim_combustivel(id),unidades bigint NOT NULL CHECK(unidades>=0),
  fonte_id text NOT NULL REFERENCES fonte_dados(id),observacao text NOT NULL
);
CREATE TABLE IF NOT EXISTS app_config (chave text PRIMARY KEY,valor jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS execucao_etl (
  id text PRIMARY KEY,iniciada_em timestamptz NOT NULL,terminada_em timestamptz,
  seed integer NOT NULL,linhas_sinteticas bigint NOT NULL,status text NOT NULL,qualidade jsonb
);
CREATE INDEX IF NOT EXISTS fato_filtros ON fato_vendas(pais_id,origem,medida,periodicidade,ano,estado_id);
CREATE INDEX IF NOT EXISTS fato_modelo ON fato_vendas(modelo_id,ano);
CREATE INDEX IF NOT EXISTS fato_segmento_combustivel ON fato_vendas(segmento_id,combustivel_id,ano);
CREATE INDEX IF NOT EXISTS mercado_escopo ON fato_mercado(pais_id,ano,origem,medida,periodicidade);
CREATE INDEX IF NOT EXISTS estado_pais ON dim_estado(pais_id);
CREATE INDEX IF NOT EXISTS midia_escopo ON midia(pais_id,estado_id,modelo_id);
CREATE OR REPLACE FUNCTION garantir_particao_vendas(p_ano integer) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF p_ano < 1900 OR p_ano > 2100 THEN RAISE EXCEPTION 'Ano fora do contrato'; END IF;
  EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF fato_vendas FOR VALUES FROM (%s) TO (%s)', 'fato_vendas_'||p_ano,p_ano,p_ano+1);
END $$;
