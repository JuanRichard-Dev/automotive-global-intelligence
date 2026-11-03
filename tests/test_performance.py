"""Regression tests for the read-only API's performance safeguards.

These tests mock SQL to validate cache/pool behavior without depending on
production database credentials or creating synthetic production records.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

from fastapi.testclient import TestClient
from api import db
from api import main


def test_cache_singleflight_reuses_one_load():
    db.clear_cache()
    calls = []
    lock = Lock()

    def expensive():
        with lock:
            calls.append(True)
        time.sleep(0.04)
        return {'ok': True}

    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes = list(workers.map(lambda _: db.cached(('same',), expensive), range(8)))
    assert len(calls) == 1
    assert all(x == {'ok': True} for x in outcomes)


def test_query_reuses_connection_pool(monkeypatch):
    call_count = []
    class StubConnection:
        def execute(self, sql, params):
            call_count.append((sql, params))
            return self
        def fetchall(self):
            return [{'n': 12}]

    class StubContext:
        def __enter__(self):
            return StubConnection()
        def __exit__(self, *args):
            return False

    class StubPool:
        def connection(self):
            return StubContext()

    monkeypatch.setattr(db, '_pool', StubPool())
    assert db.query('SELECT n', (), one=True) == {'n': 12}
    assert db.query('SELECT n') == [{'n': 12}]
    assert len(call_count) == 2


def test_readiness_cache_and_public_http_cache(monkeypatch):
    db.clear_cache()
    checks = []
    def fake_query(sql, params=(), one=False):
        if 'execucao_etl' in sql:
            checks.append(sql)
            return {'status': 'concluida', 'qualidade': {'modo': 'real'}}
        return []
    monkeypatch.setattr(main, 'query', fake_query)

    with TestClient(main.app) as client:
        for _ in range(3):
            response = client.get('/health')
            assert response.status_code == 200, response.text
            assert response.json()['status'] == 'ok'
        assert len(checks) == 1

        media = client.get('/midia')
        assert media.status_code == 200, media.text
        assert media.json() == {'items': []}
        assert 's-maxage=600' in media.headers['cache-control']

    db.clear_cache()


def test_unready_etl_returns_service_unavailable(monkeypatch):
    db.clear_cache()
    def fake_query(sql, params=(), one=False):
        if 'execucao_etl' in sql:
            return {'status': 'executando', 'qualidade': {'modo': 'real'}}
        raise AssertionError('No other SQL should run')
    monkeypatch.setattr(main, 'query', fake_query)

    with TestClient(main.app) as client:
        response = client.get('/health')
        assert response.status_code == 503
        assert 'indisponível' in response.text

    db.clear_cache()
