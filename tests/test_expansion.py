import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.mark.parametrize('iso,leader,volume,total', [('IT','PANDA',102485,1525722),('AT','OCTAVIA',7892,284978)])
def test_official_annual_rankings(iso,leader,volume,total):
    with TestClient(app) as client:
        r=client.get(f'/paises/{iso}/top-carros',params={'ano':2025}).json()
        assert r['items'][0]['modelo']==leader
        assert r['items'][0]['unidades']==volume
        assert r['mercado_elegivel']==total
        assert r['total']==50

@pytest.mark.parametrize('iso',['BR','GB','IT','AT'])
def test_gallery_photos_and_chart_totals(iso):
    with TestClient(app) as client:
        p={'pais':iso,'ano':2025}
        panel=client.get('/painel',params=p).json()
        photos=client.get('/midia').json()['items']
        photographed={r['modelo_id'] for r in photos if r['modelo_id'] is not None}
        assert all(r['modelo_id'] in photographed for r in panel['ranking']['items'])
        chart=client.get('/graficos',params=p).json()
        assert sum(r['unidades'] for r in chart['ranking'])==panel['ranking']['unidades_observadas']
        assert sum(r['unidades'] for r in chart['fuels'])==panel['ranking']['unidades_observadas']
