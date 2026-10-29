"""Spark tests using JVM SQL fixtures with explicit schema, never PythonRDD/UDF.

The session is the production etl.pipeline.session(), including its Windows
filesystem setup. These tests do not write PostgreSQL or run the full pipeline.
They exercise actual Spark actions and validate the collected real CSV contract.
"""
from pathlib import Path
import sys

import pytest
from pyspark.sql import functions as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl.pipeline import session, run, input_manifest
from etl.transforms import RAW_SCHEMA, normalize, validate
from etl.aggregations import annual_models, annual_ranking, monthly_seasonality

COUNTRIES = ['BR','US','GB','DE','JP','AU','IT','AT']
STATES = [('BR','BR-SP'),('BR','BR-RJ'),('US','US-CA')]
SOURCES = ['TEST_REAL']


@pytest.fixture(scope='session')
def spark():
    active = session()
    active.sparkContext.setLogLevel('ERROR')
    yield active
    active.stop()


def sql_literal(value):
    if value is None: return 'NULL'
    if isinstance(value, str):
        return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
    if isinstance(value, float) and value != value: return "'NaN'"
    if value == float('inf'): return "'Infinity'"
    if value == float('-inf'): return "'-Infinity'"
    return str(value)


def raw(spark, overrides):
    """Rows are SQL literals cast to RAW_SCHEMA: no Python worker required."""
    defaults = dict(record_id=1, country_iso='BR', state_code='BR-SP', city=None,
                    year=2025, month=None, period_kind='annual', brand='VW', model='POLO',
                    segment='hatch', fuel='flex', price=None, currency=None, units=10,
                    metric='new_registrations', source_id='TEST_REAL', origin='real',
                    reference_period='2025', record_origin='fixture://unit-test',
                    hash_origin='fixture-hash', collected_at='2026-10-28')
    queries = []
    for i, override in enumerate(overrides, 1):
        values = {**defaults, 'record_id':i, **override}
        cols = [f'CAST({sql_literal(values[field.name])} AS {field.dataType.simpleString()}) AS `{field.name}`' for field in RAW_SCHEMA]
        queries.append('SELECT ' + ','.join(cols))
    result = spark.sql(' UNION ALL '.join(queries))
    assert result.schema.simpleString() == RAW_SCHEMA.simpleString(), 'Fixtures must preserve explicit raw column types.'
    return result


def checked(df):
    return validate(normalize(df), COUNTRIES, STATES, SOURCES)


def test_normalization_aliases_whitespace_and_unknowns(spark):
    data = raw(spark, [
        dict(brand='  vw ', model='  GOLF    GTI  ', country_iso=' br ', state_code=' br-sp ', currency=' brl ', segment=' SUV ', fuel=' HIBRIDO '),
        dict(brand='GM', model='ONIX', segment=None, fuel=''),
        dict(brand='M.BENZ', model='C 200'),
        dict(brand='MERCEDES BENZ', model='C 200'),
        dict(brand='Outra Marca', model='Sem alias'),
        dict(fuel='outros'),
        dict(fuel='gas'),
        dict(fuel='hidrogenio'),
    ])
    result = normalize(data).orderBy('record_id').collect()
    assert result[0].brand == 'VOLKSWAGEN'
    assert (result[0].model,result[0].country_iso,result[0].state_code,result[0].currency) == ('GOLF GTI','BR','BR-SP','BRL')
    assert (result[0].segment,result[0].fuel,result[0].period_kind) == ('suv','hibrido','anual')
    assert (result[1].brand,result[1].segment,result[1].fuel) == ('CHEVROLET','nao_informado','nao_informado')
    assert result[2].brand == result[3].brand == 'MERCEDES-BENZ'
    assert result[2].model_key == result[3].model_key
    assert result[4].brand == 'OUTRA MARCA'
    assert [r.fuel for r in result[5:]] == ['outro','gas','hidrogenio']
    assert len(result[0].model_key) == 64


def test_optional_absence_is_preserved_not_imputed(spark):
    clean, rejected, extreme = checked(raw(spark, [dict(state_code=None,city=None,price=None,currency=None,segment=None,fuel=None,units=0)]))
    row = clean.collect()[0]
    assert (row.state_code,row.city,row.price,row.currency) == (None,None,None,None)
    assert row.units == 0
    assert row.segment == row.fuel == 'nao_informado'
    assert rejected.count() == extreme.count() == 0


def test_rejected_rows_explain_validation_and_contamination(spark):
    cases = [
        ({'record_id':None}, 'identificador_ausente'),
        ({'country_iso':'ZZ'}, 'pais_invalido'),
        ({'year':2020}, 'ano_invalido'),
        ({'units':-1}, 'unidades_invalidas'),
        ({'units':None}, 'unidades_invalidas'),
        ({'brand':' '}, 'modelo_ausente'),
        ({'model':None}, 'modelo_ausente'),
        ({'source_id':'UNKNOWN'}, 'fonte_invalida'),
        ({'origin':'misturado'}, 'origem_invalida'),
        ({'origin':'real','source_id':'SYN_42'}, 'fonte_nao_publicada'),
        ({'origin':'sintetico','source_id':'TEST_REAL'}, 'origem_invalida'),
        ({'period_kind':'unknown'}, 'periodo_invalido'),
        ({'period_kind':'monthly','month':None}, 'mes_invalido'),
        ({'period_kind':'monthly','month':13}, 'mes_invalido'),
        ({'period_kind':'quarterly','month':2}, 'trimestre_invalido'),
        ({'price':-1}, 'preco_negativo'),
        ({'price':float('nan')}, 'preco_nao_finito'),
        ({'price':float('inf')}, 'preco_nao_finito'),
        ({'collected_at':None}, 'data_invalida'),
        ({'metric':'sales_unknown'}, 'medida_invalida'),
        ({'metric':None}, 'medida_invalida'),
        ({'state_code':'US-CA','country_iso':'BR'}, 'estado_pais_incompativel'),
    ]
    # record_origin is a stable case identifier even for the null record_id case.
    inputs = [{**fields,'record_origin':f'case:{i}'} for i,(fields,_) in enumerate(cases)]
    clean, rejected, extreme = checked(raw(spark, inputs))
    actual = {r.record_origin:set(r.motivo_rejeicao.split(';')) for r in rejected.collect()}
    assert len(actual) == len(cases)
    for i,(_,reason) in enumerate(cases):
        assert reason in actual[f'case:{i}']
    assert clean.count() == extreme.count() == 0


def test_extremes_are_quarantined_without_clipping(spark):
    clean, rejected, extreme = checked(raw(spark, [
        dict(price=10_000_001.0,units=5),
        dict(price=None,units=1_000_000_001),
        dict(price=10_000_000.0,units=1_000_000_000),
    ]))
    assert rejected.count() == 0
    actual = {r.record_id:(r.price,r.units) for r in extreme.collect()}
    assert actual == {1:(10_000_001.0,5),2:(None,1_000_000_001)}
    assert clean.select('record_id').first().record_id == 3


def test_collected_real_csv_has_traceable_rows_and_explicit_schema(spark):
    import json
    incoming=spark.read.option('header',True).schema(RAW_SCHEMA).csv(str(ROOT/'data/raw/real_sales.csv'))
    sources=json.loads((ROOT/'data/seed/sources.json').read_text(encoding='utf8'))
    source_ids=[r['id'] for r in sources if not r['id'].startswith('SYN')]
    clean,rejected,outliers=validate(normalize(incoming),COUNTRIES,STATES,source_ids)
    assert incoming.count()>0
    assert {r.origin for r in incoming.select('origin').distinct().collect()}=={'real'}
    assert incoming.filter(F.col('source_id').startswith('SYN')).count()==0
    assert incoming.filter(F.col('record_origin').isNull()|F.col('hash_origin').isNull()).count()==0
    assert rejected.count()==outliers.count()==0
    assert clean.count()==incoming.count()
    fingerprint,manifest,count=input_manifest()
    assert len(fingerprint)==64 and count==incoming.count()
    assert 'data/raw/real_sales.csv' in manifest


@pytest.mark.parametrize('rows', [1,-1,3_000_000])
def test_real_only_volume_guard_runs_before_database_access(rows):
    with pytest.raises(ValueError,match='apenas dados reais'):
        run(rows=rows)


def test_annual_rankings_separate_origin_metric_and_snapshot_grain(spark):
    clean = normalize(raw(spark, [
        dict(year=2023,units=100),
        dict(year=2025,units=200),  # gap: 2023 cannot be treated as previous year
        dict(year=2026,units=300),
        dict(year=2025,model='GOLF',units=100),
        dict(year=2025,units=900,metric='first_registrations_including_imports'),
        dict(year=2025,units=9999,period_kind='monthly',month=1),
        dict(year=2025,units=9999,period_kind='quarterly',month=3),
        dict(year=2025,units=2,period_kind='monthly',month=1,origin='sintetico',source_id='SYN_42'),
        dict(year=2025,units=3,period_kind='monthly',month=2,origin='sintetico',source_id='SYN_42'),
        dict(year=2025,units=9999,period_kind='annual',origin='sintetico',source_id='SYN_42'),
        dict(year=2025,model='GOLF',units=5,period_kind='monthly',month=1,origin='sintetico',source_id='SYN_42'),
    ]))
    rows = annual_ranking(clean).collect()
    real = next(r for r in rows if r.year==2025 and r.origin=='real' and r.metric=='new_registrations' and r.model=='POLO')
    assert real.units == 200 and real.unidades_no_recorte == 300
    assert real.participacao_no_recorte_pct == pytest.approx(200/300*100)
    assert real.ano_anterior_observado == 2023 and real.crescimento_pct is None
    following = next(r for r in rows if r.year==2026)
    assert following.crescimento_pct == pytest.approx(50)
    assert {r.origin for r in rows}=={'real'}
    imported = next(r for r in rows if r.metric=='first_registrations_including_imports')
    assert imported.units == imported.unidades_no_recorte == 900


def test_state_ranking_never_assigns_national_rows_to_states(spark):
    clean = normalize(raw(spark, [
        dict(state_code=None,units=1000),
        dict(state_code='BR-SP',units=30),
        dict(state_code='BR-RJ',units=10),
        dict(state_code='BR-SP',model='GOLF',units=10),
    ]))
    states = annual_ranking(clean,state=True).collect()
    assert len(states) == 3 and sum(r.units for r in states) == 50
    sp = next(r for r in states if r.state_code=='BR-SP' and r.model=='POLO')
    assert sp.participacao_no_recorte_pct == 75
    assert all(r.state_code is not None for r in states)


def test_zero_previous_volume_does_not_create_infinite_growth(spark):
    rows = annual_ranking(normalize(raw(spark,[dict(year=2024,units=0),dict(year=2025,units=20)]))).orderBy('year').collect()
    assert rows[0].participacao_no_recorte_pct is None
    assert rows[1].crescimento_pct is None


def test_monthly_seasonality_requires_all_months_and_never_adds_snapshots(spark):
    inputs = [dict(year=2025,month=m,period_kind='monthly',units=m) for m in range(1,13)]
    inputs += [dict(year=2025,period_kind='annual',units=9999),dict(year=2025,month=3,period_kind='quarterly',units=9999),
               dict(year=2025,month=1,period_kind='monthly',units=10,country_iso='GB',state_code=None),
               dict(year=2025,month=2,period_kind='monthly',units=20,country_iso='GB',state_code=None)]
    rows = monthly_seasonality(normalize(raw(spark,inputs))).collect()
    real = [r for r in rows if r.country_iso=='BR']
    partial = [r for r in rows if r.country_iso=='GB']
    assert len(real) == 12 and sum(r.units for r in real) == 78
    assert all(r.meses_publicados == 12 for r in real)
    assert sum(r.participacao_no_ano_observado_pct for r in real) == pytest.approx(100)
    assert sum(r.indice_sazonal for r in real)/12 == pytest.approx(1)
    assert len(partial) == 2 and all(r.indice_sazonal is None for r in partial)
    assert all(r.meses_publicados == 2 for r in partial)
    assert sum(r.participacao_no_ano_observado_pct for r in partial) == pytest.approx(100)
