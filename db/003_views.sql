DROP MATERIALIZED VIEW IF EXISTS mv_ranking_estado;
DROP MATERIALIZED VIEW IF EXISTS mv_ranking_pais;
DROP MATERIALIZED VIEW IF EXISTS mv_totais_anuais;
DROP MATERIALIZED VIEW IF EXISTS mv_agregados;
CREATE MATERIALIZED VIEW mv_agregados AS
 SELECT pais_id,estado_id,ano,mes,origem,medida,periodicidade,modelo_id,marca_id,segmento_id,combustivel_id,
 sum(unidades)::bigint unidades,count(*)::bigint observacoes,
 sum(preco_usd*unidades) receita_usd,sum(CASE WHEN preco_usd IS NOT NULL THEN unidades ELSE 0 END) unidades_com_preco,
 array_agg(DISTINCT fonte_id) fontes
 FROM fato_vendas WHERE origem='real' AND fonte_id NOT LIKE 'SYN%' GROUP BY pais_id,estado_id,ano,mes,origem,medida,periodicidade,modelo_id,marca_id,segmento_id,combustivel_id;
CREATE INDEX mv_agregados_filtro ON mv_agregados(pais_id,ano,origem,medida,periodicidade,estado_id);
CREATE MATERIALIZED VIEW mv_ranking_pais AS
SELECT *,dense_rank() OVER(PARTITION BY pais_id,ano,mes,origem,medida,periodicidade ORDER BY unidades DESC) posicao
FROM (SELECT pais_id,ano,mes,origem,medida,periodicidade,modelo_id,sum(unidades)::bigint unidades
 FROM mv_agregados GROUP BY pais_id,ano,mes,origem,medida,periodicidade,modelo_id) q;
CREATE INDEX mv_rank_pais_idx ON mv_ranking_pais(pais_id,ano,origem,medida,periodicidade,posicao);
CREATE MATERIALIZED VIEW mv_ranking_estado AS
SELECT *,dense_rank() OVER(PARTITION BY estado_id,ano,mes,origem,medida,periodicidade ORDER BY unidades DESC) posicao
FROM (SELECT estado_id,pais_id,ano,mes,origem,medida,periodicidade,modelo_id,sum(unidades)::bigint unidades
 FROM mv_agregados WHERE estado_id IS NOT NULL GROUP BY estado_id,pais_id,ano,mes,origem,medida,periodicidade,modelo_id) q;
CREATE INDEX mv_rank_estado_idx ON mv_ranking_estado(estado_id,ano,origem,medida,periodicidade,posicao);
CREATE MATERIALIZED VIEW mv_totais_anuais AS
SELECT pais_id,estado_id,ano,origem,medida,sum(unidades)::bigint unidades_observadas,
 sum(observacoes)::bigint observacoes,count(DISTINCT modelo_id) modelos
FROM mv_agregados WHERE periodicidade='anual' GROUP BY pais_id,estado_id,ano,origem,medida;
