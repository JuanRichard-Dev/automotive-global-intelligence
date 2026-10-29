"""Agregações Spark sem combinar origens, medidas ou snapshots de período."""
from pyspark.sql import functions as F, Window


def annual_models(clean, state=False):
    """Somente observações anuais reais publicadas, separadas por medida."""
    keys = ['country_iso', 'year', 'origin', 'metric', 'brand', 'model']
    if state:
        keys.insert(1, 'state_code')
        clean = clean.filter(F.col('state_code').isNotNull())
    real = clean.filter((F.col('origin') == 'real') & (F.col('period_kind') == 'anual'))
    return real.groupBy(*keys).agg(F.sum('units').alias('units'))


def annual_ranking(clean, state=False):
    annual = annual_models(clean, state=state)
    scope = ['country_iso', 'year', 'origin', 'metric']
    history = ['country_iso', 'origin', 'metric', 'brand', 'model']
    if state:
        scope.insert(1, 'state_code')
        history.insert(1, 'state_code')
    ranked = Window.partitionBy(*scope).orderBy(F.desc('units'), 'brand', 'model')
    previous = Window.partitionBy(*history).orderBy('year')
    total = Window.partitionBy(*scope)
    result = (annual.withColumn('posicao', F.row_number().over(ranked))
              .withColumn('ano_anterior_observado', F.lag('year').over(previous))
              .withColumn('unidades_anteriores_observadas', F.lag('units').over(previous))
              .withColumn('unidades_no_recorte', F.sum('units').over(total)))
    return (result.withColumn('crescimento_pct',
                F.when((F.col('year') == F.col('ano_anterior_observado') + 1)
                       & (F.col('unidades_anteriores_observadas') > 0),
                       (F.col('units') / F.col('unidades_anteriores_observadas') - 1) * 100))
            .withColumn('participacao_no_recorte_pct',
                F.when(F.col('unidades_no_recorte') > 0,
                       F.col('units') / F.col('unidades_no_recorte') * 100))
            .withColumn('periodicidade', F.lit('anual')))


def monthly_seasonality(clean, state=False):
    """Participação mensal observada; índice sazonal só com 12 meses publicados.

    Não interpola ausências e não usa snapshots trimestrais/anuais. A participação
    é no ano observado, nunca uma participação de mercado elegível publicada.
    """
    scope = ['country_iso', 'year', 'origin', 'metric']
    if state:
        scope.insert(1, 'state_code')
        clean = clean.filter(F.col('state_code').isNotNull())
    monthly = clean.filter((F.col('origin') == 'real') & (F.col('period_kind') == 'mensal')).groupBy(*scope, 'month').agg(F.sum('units').alias('units'))
    yearly = Window.partitionBy(*scope)
    result = (monthly.withColumn('unidades_no_ano_observado', F.sum('units').over(yearly))
              .withColumn('meses_publicados', F.count('*').over(yearly)))
    return (result.withColumn('participacao_no_ano_observado_pct',
                F.when(F.col('unidades_no_ano_observado') > 0,
                       F.col('units') / F.col('unidades_no_ano_observado') * 100))
            .withColumn('indice_sazonal',
                F.when((F.col('meses_publicados') == 12) & (F.col('unidades_no_ano_observado') > 0),
                       F.col('units') / (F.col('unidades_no_ano_observado') / 12)))
            .withColumn('periodicidade', F.lit('mensal')))
