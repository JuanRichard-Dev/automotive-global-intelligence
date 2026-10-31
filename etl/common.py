import json,os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DSN=os.getenv('DATABASE_URL','postgresql://automotive:automotive_local@127.0.0.1:55432/automotive')

def connect():
    return psycopg.connect(DSN,row_factory=dict_row,prepare_threshold=None)

def load_json(name):
    return json.loads((DATA/'seed'/name).read_text(encoding='utf-8'))

def upsert(conn,table,rows,pk='id'):
    if not rows:return
    from psycopg import sql
    cols=list(rows[0])
    query=sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}').format(
        sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols),sql.Identifier(pk),
        sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in cols if c!=pk))
    from psycopg.types.json import Jsonb
    with conn.cursor() as cur:
        cur.executemany(query,[[Jsonb(r[c]) if isinstance(r[c],(dict,list)) else r[c] for c in cols] for r in rows])

def init_schema(conn):
    for name in ['001_schema.sql','002_seed.sql']:
        conn.execute((ROOT/'db'/name).read_text(encoding='utf-8'))
    conn.commit()
