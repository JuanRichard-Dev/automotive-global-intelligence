import os,time,threading
import psycopg
from psycopg.rows import dict_row
from fastapi.encoders import jsonable_encoder

DSN=os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL') or 'postgresql://automotive:automotive_local@127.0.0.1:55432/automotive'
_cache={};_lock=threading.RLock()

def query(sql,params=(),one=False):
    with psycopg.connect(DSN,row_factory=dict_row,options='-c statement_timeout=20000',prepare_threshold=None) as conn:
        rows=conn.execute(sql,params or None).fetchall()
    return jsonable_encoder(rows[0] if one and rows else None if one else rows)

def cached(key,fn,ttl=60):
    now=time.monotonic()
    with _lock:
        value=_cache.get(key)
        if value and now-value[0]<ttl:return value[1]
    result=fn()
    with _lock:
        if len(_cache)>256:_cache.clear()
        _cache[key]=(now,result)
    return result

def clear_cache():
    with _lock:_cache.clear()
