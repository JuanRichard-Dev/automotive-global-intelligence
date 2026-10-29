"""Integration tests: real PostgreSQL, no mocks, no writes, no fallback data.

Run from the project root: python -m pytest tests/test_api.py -q
DATABASE_URL defaults to the same loopback database as the API. An unavailable
database or unfinished ETL fails setup explicitly rather than reporting a pass.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.main import app
from api.db import clear_cache, query

BR = dict(pais='BR', ano=2025, origem='real', medida='new_registrations', periodicidade='anual')
GB = dict(pais='GB', ano=2025, origem='real', medida='first_registrations_including_imports', periodicidade='anual')


@pytest.fixture(scope='session')
def client():
    clear_cache()
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get('/health')
        assert response.status_code == 200, f'PostgreSQL/ETL necessário: {response.text}'
        assert query('SELECT count(*) n FROM fato_vendas', one=True)['n'] > 0
        yield c
    clear_cache()


def get(client, path, params=None):
    response = client.get(path, params=params)
    assert response.status_code == 200, f'{path}: {response.status_code} {response.text}'
    return response.json()


def expected_top(params, size=10, state=None):
    extra = ' AND e.codigo=%s' if state else ''
    values = [params['pais'], params['ano'], params['origem'], params['medida']]
    if state: values.append(state)
    return query('''SELECT a.modelo_id,b.nome marca,m.nome modelo,sum(a.unidades)::bigint unidades
        FROM mv_agregados a JOIN dim_pais p ON p.id=a.pais_id
        JOIN dim_modelo m ON m.id=a.modelo_id JOIN dim_marca b ON b.id=a.marca_id
        LEFT JOIN dim_estado e ON e.id=a.estado_id
        WHERE p.iso=%s AND a.ano=%s AND a.origem=%s AND a.medida=%s
        AND a.periodicidade='anual' ''' + extra + ''' GROUP BY a.modelo_id,b.nome,m.nome
        ORDER BY unidades DESC,b.nome,m.nome LIMIT %s''', values + [size])


def test_health_and_catalog(client):
    assert get(client, '/health')['database'] == 'postgresql'
    bootstrap = get(client, '/bootstrap')
    assert bootstrap['execucao']['qualidade']['modo']=='real'
    assert 'linhas_sinteticas' not in bootstrap['execucao']
    assert query("SELECT count(*) n FROM fato_vendas WHERE origem<>'real' OR fonte_id LIKE 'SYN%'",one=True)['n']==0
    assert query("SELECT count(*) n FROM dim_cidade WHERE tipo='sintetica' OR codigo LIKE '%SYN%'",one=True)['n']==0
    assert query("SELECT count(*) n FROM fonte_dados WHERE id LIKE 'SYN%'",one=True)['n']==0
    assert {'BR','US','GB'}.issubset({p['iso'] for p in bootstrap['paises']})
    assert {a['origem'] for a in bootstrap['disponibilidade']} == {'real'}
    assert bootstrap['painel']['filtros']['origem'] == 'real'


@pytest.mark.parametrize('params', [BR, GB])
def test_ranking_matches_postgresql(client, params):
    result = get(client, f'/paises/{params["pais"]}/top-carros', {**params, 'tamanho':10})
    expected = expected_top(params)
    assert expected, f'Sem dados no recorte de integração: {params}'
    assert [(x['modelo_id'],x['marca'],x['modelo'],x['unidades']) for x in result['items']] == [
        (x['modelo_id'],x['marca'],x['modelo'],x['unidades']) for x in expected]
    assert result['filtros']['origem'] == params['origem']
    assert result['filtros']['medida'] == params['medida']
    assert [x['posicao'] for x in result['items']] == list(range(1, len(expected)+1))
    if result['mercado_elegivel']:
        assert result['unidades_observadas'] <= result['mercado_elegivel']
        for row in result['items']:
            assert row['participacao_pct'] == pytest.approx(row['unidades']/result['mercado_elegivel']*100)


def test_pagination_is_stable(client):
    one = get(client, '/paises/BR/top-carros', {**BR, 'tamanho':5, 'pagina':1})
    two = get(client, '/paises/BR/top-carros', {**BR, 'tamanho':5, 'pagina':2})
    combined = one['items'] + two['items']
    assert [x['modelo_id'] for x in combined] == [x['modelo_id'] for x in expected_top(BR)]
    assert not ({r['modelo_id'] for r in one['items']} & {r['modelo_id'] for r in two['items']})


def test_real_state_has_no_invented_allocation(client):
    params = {**BR, 'origem':'real'}
    count = query("SELECT count(*) n FROM fato_vendas WHERE origem='real' AND estado_id IS NOT NULL", one=True)['n']
    assert count == 0, 'Reavalie este contrato se uma nova fonte real estadual for adicionada.'
    result = get(client, '/estados/BR-SP/top-carros', params)
    assert result['items'] == []
    assert result['unidades_observadas'] is None
    assert result['mercado_elegivel'] is None
    panel = get(client, '/painel', {**params, 'estado':'BR-SP'})
    assert panel['status'] == 'sem_dados'
    assert panel['nota_ausencia']


def test_uk_measures_remain_separate(client):
    first = get(client, '/paises/GB/top-carros', GB)
    new = get(client, '/paises/GB/top-carros', {**GB,'medida':'new_registrations'})
    assert 'UK_DFT_VEH0160' in first['fontes']
    assert 'UK_SMMT_2025' not in first['fontes']
    if new['items']:
        assert 'UK_DFT_VEH0160' not in new['fontes']
        assert new['mercado_elegivel'] != first['mercado_elegivel']


def test_uk_annual_denominator_reconciles_all_published_cells(client):
    result = get(client, '/paises/GB/top-carros', GB)
    # Exact official 2025 passenger-car total in the collected DfT edition.
    assert result['mercado_elegivel'] == 2_071_394
    assert result['unidades_observadas'] == 2_071_394
    assert result['cobertura_pct'] == pytest.approx(100)
    assert result['fontes'] == ['UK_DFT_VEH0160']


@pytest.mark.parametrize('fuel,total', [('gas',212),('hidrogenio',1),('outro',1549)])
def test_small_uk_fuels_never_become_all_fuels(client,fuel,total):
    result = get(client, '/paises/GB/top-carros', {**GB,'combustivel':fuel})
    assert result['mercado_elegivel'] == total
    assert result['unidades_observadas'] == total
    assert result['mercado_elegivel'] != 2_071_394
    assert result['cobertura_pct'] == pytest.approx(100)
    assert sum(r['unidades'] for r in result['items']) <= total


def test_market_denominators_have_unique_compatible_scope(client):
    duplicates = query('''SELECT pais_id,estado_id,ano,mes,periodicidade,origem,medida,combustivel_id,count(*) n
        FROM fato_mercado GROUP BY pais_id,estado_id,ano,mes,periodicidade,origem,medida,combustivel_id
        HAVING count(*)>1''')
    assert not duplicates, f'Denominador duplicado no mesmo universo: {duplicates}'


def test_filters_match_same_scope_sql(client):
    # Choose a published pair, rather than inventing a segment/fuel combination
    # that might not exist in the published observations.
    pair = query('''SELECT s.codigo segmento,c.codigo combustivel FROM mv_agregados a
        JOIN dim_pais p ON p.id=a.pais_id JOIN dim_segmento s ON s.id=a.segmento_id
        JOIN dim_combustivel c ON c.id=a.combustivel_id WHERE p.iso='BR'
        AND a.origem='real' AND a.medida='new_registrations' AND a.ano=2025
        AND a.periodicidade='anual' GROUP BY s.codigo,c.codigo ORDER BY sum(a.unidades) DESC LIMIT 1''', one=True)
    assert pair
    segment, fuel = pair['segmento'], pair['combustivel']
    result = get(client, '/paises/BR/top-carros', {**BR,'segmento':segment,'combustivel':fuel})
    expected = query('''SELECT sum(a.unidades)::bigint total FROM mv_agregados a
        JOIN dim_pais p ON p.id=a.pais_id JOIN dim_segmento s ON s.id=a.segmento_id
        JOIN dim_combustivel c ON c.id=a.combustivel_id WHERE p.iso='BR'
        AND origem='real' AND medida='new_registrations' AND ano=2025
        AND periodicidade='anual' AND s.codigo=%s AND c.codigo=%s''',(segment,fuel),True)['total']
    assert result['unidades_observadas'] == expected
    assert result['mercado_elegivel'] is None or result['mercado_elegivel'] >= expected


@pytest.mark.parametrize('grain', ['anual','mensal'])
def test_series_uses_only_requested_periodicity(client, grain):
    result = get(client, '/series-temporais', {**BR,'granularidade':grain})
    expected = query('''SELECT ano,mes,sum(unidades)::bigint unidades FROM mv_agregados a
        JOIN dim_pais p ON p.id=a.pais_id WHERE p.iso='BR' AND origem='real'
        AND medida='new_registrations' AND periodicidade=%s GROUP BY ano,mes ORDER BY ano,mes''',(grain,))
    assert result['items'] == expected
    assert result['periodicidade'] == grain


def test_statistics_and_missing_prices(client):
    for params in (BR,GB):
        real=get(client,'/estatisticas',params)
        assert real['descritiva']['modelos']>0
        assert real['boxplot']['n']==0
        assert real['correlacao_preco_unidades'] is None


def test_maps_and_catalog_do_not_offer_unobserved_states(client):
    assert get(client,'/paises/BR/estados')['items']==[]
    assert get(client,'/mapa',{**BR,'nivel':'estado'})['features']==[]
    world=get(client,'/mapa',GB)
    assert world['type']=='FeatureCollection'
    assert any(not f['properties']['tem_dados'] for f in world['features'])
    assert all(f['properties']['unidades'] is None for f in world['features'] if not f['properties']['tem_dados'])


def test_market_cards_resolve_each_published_measure(client):
    result=get(client,'/comparador',{'ano':2025})
    assert result['items']
    assert all(row['disponivel'] and row['nome_medida'] for row in result['items'])
    metrics={row['iso']:row['medida'] for row in result['items']}
    assert metrics['BR']=='new_registrations'
    assert metrics['GB']=='first_registrations_including_imports'


def test_comparator_keeps_same_metric(client):
    result = get(client, '/comparador', {**GB,'isos':'BR,US,GB'})
    assert all(row['medida'] == GB['medida'] for row in result['items'])
    unavailable = [r for r in result['items'] if r['iso'] in ('BR','US')]
    assert unavailable and all(not r['disponivel'] and r['lider'] is None for r in unavailable)


def test_wordcloud_model_and_sources(client):
    words = get(client, '/nuvem-palavras', BR)['items']
    assert words and all(x['valor'] > 0 for x in words)
    assert [x['valor'] for x in words] == sorted([x['valor'] for x in words], reverse=True)
    top = get(client, '/paises/BR/top-carros', BR)['items'][0]
    obj = get(client, f'/modelos/{top["modelo_id"]}')
    assert obj['marca'] == top['marca'] and obj['nome'] == top['modelo']
    assert obj['series']
    assert get(client, '/marcas')['items']
    sources = get(client, '/fontes')['items']
    assert sources and all(s['url'] and s['licenca'] and s['limitacoes'] and not s['id'].startswith('SYN') for s in sources)
    media = get(client, '/midia', {'pais':'BR'})['items']
    assert media and all(m['credito'] and m['licenca'] and m['origem_url'] for m in media)


@pytest.mark.parametrize('path,params', [
    ('/paises/BR/top-carros',{'ano':1900}),
    ('/paises/BR/top-carros',{'origem':'misturado'}),
    ('/paises/BR/top-carros',{'origem':'sintetico'}),
    ('/paises/BR/top-carros',{'tamanho':101}),
    ('/paises/BR/top-carros',{'pagina':0}),
    ('/painel',{'periodicidade':'mensal'}),
    ('/painel',{'periodicidade':'anual','mes':1}),
    ('/painel',{'periodicidade':'trimestral','mes':2}),
    ('/painel',{'pais':'BR','estado':'US-CA'}),
    ('/painel',{'segmento':"suv'; DROP TABLE fato_vendas;--"}),
    ('/comparador',{'isos':'BR,USA'}),
])
def test_invalid_requests_are_422(client,path,params):
    response = client.get(path, params=params)
    assert response.status_code == 422, f'{path} {params}: {response.status_code} {response.text}'


@pytest.mark.parametrize('path', ['/paises/ZZ/estados','/estados/ZZ-X/top-carros','/modelos/2147483647'])
def test_unknown_resource_is_404(client,path):
    assert client.get(path).status_code == 404
