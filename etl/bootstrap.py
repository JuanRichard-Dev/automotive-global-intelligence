"""Metadados e geometria entram no PostgreSQL; o navegador nunca lê sementes JSON."""
import csv,json,hashlib
from datetime import date
from .common import DATA,load_json,upsert

PT={'BR':'Brasil','US':'Estados Unidos','GB':'Reino Unido','DE':'Alemanha','FR':'França','IT':'Itália','AT':'Áustria','JP':'Japão'}
IBGE={'RO':'11','AC':'12','AM':'13','RR':'14','PA':'15','AP':'16','TO':'17','MA':'21','PI':'22','CE':'23','RN':'24','PB':'25','PE':'26','AL':'27','SE':'28','BA':'29','MG':'31','ES':'32','RJ':'33','SP':'35','PR':'41','SC':'42','RS':'43','MS':'50','MT':'51','GO':'52','DF':'53'}

def metadata(conn):
    sources=[r for r in load_json('sources.json') if not r['id'].startswith('SYN') and r.get('tipo')!='sintetica']
    upsert(conn,'fonte_dados',sources)
    world=load_json('world.geojson')['features']
    valid=sorted([f for f in world if len(f['properties']['iso'])==2],key=lambda f:f['properties']['iso'])
    countries=[];ids={}
    for i,f in enumerate(valid,1):
        p=f['properties'];iso=p['iso'];ids[iso]=i
        countries.append(dict(id=i,iso=iso,iso3=p.get('iso3'),nome=PT.get(iso,p['name']),continente=p.get('continent'),geometria=f['geometry']))
    upsert(conn,'dim_pais',countries)
    upsert(conn,'mapa_base',[dict(id=f['properties']['iso'],pais_id=ids.get(f['properties']['iso']),nome=PT.get(f['properties']['iso'],f['properties']['name']),geometria=f['geometry'],fonte_id='geo-world') for f in world])
    states=[]
    for i,f in enumerate(sorted(load_json('states-br-us.geojson')['features'],key=lambda f:f['properties']['state_code']),1):
        p=f['properties'];states.append(dict(id=i,pais_id=ids[p['iso']],codigo=p['state_code'],sigla=p['postal'],nome=p.get('name_local') or p['name'],codigo_ibge=IBGE.get(p['postal']) if p['iso']=='BR' else None,geometria=f['geometry']))
    upsert(conn,'dim_estado',states)
    # Nenhuma fonte atual publica cidades: dimensão de junção vazia, sem localidades inferidas.
    cities=[]
    times=[];months=['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
    for year in range(2021,2028):
        for month in range(1,13):times.append(dict(id=year*10000+month*100+1,data_iso=f'{year}-{month:02}-01',ano=year,mes=month,trimestre=(month-1)//3+1,mes_nome=months[month-1]))
    upsert(conn,'dim_tempo',times)
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO cambio(moeda,data_referencia,usd_por_unidade,fonte_id) VALUES (%s,%s,%s,%s) ON CONFLICT(moeda,data_referencia) DO UPDATE SET usd_por_unidade=EXCLUDED.usd_por_unidade',[(r['moeda'],r['data_referencia'],r['usd_por_unidade'],r['fonte_id']) for r in load_json('fx.json')])
    # CSVs pequenos: dimensão explícita para joins broadcast no Spark.
    def csv_file(name,rows,cols):
        with (DATA/'seed'/name).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows([{c:r.get(c) for c in cols} for r in rows])
    csv_file('countries.csv',countries,['id','iso','nome'])
    csv_file('states.csv',states,['id','pais_id','codigo'])
    csv_file('cities.csv',cities,['id','codigo','pais_id','estado_id'])
    conn.commit()

def media(conn):
    countries={r['iso']:r['id'] for r in conn.execute('SELECT id,iso FROM dim_pais')}
    states={r['codigo']:r['id'] for r in conn.execute('SELECT id,codigo FROM dim_estado')}
    models={r['chave']:r['id'] for r in conn.execute('SELECT id,chave FROM dim_modelo')}
    rows=[]
    for m in load_json('media.json'):
        key=hashlib.sha256((m.get('brand','').upper()+'|'+m.get('model','').upper()).encode()).hexdigest()
        rows.append(dict(id=m['id'],pais_id=countries.get(m.get('country_iso')),estado_id=states.get(m.get('state_code')),modelo_id=models.get(key),tipo=m['type'],url='/media/'+m['filename'],titulo=m['title'],lugar=m.get('place'),credito=m['credit'],licenca=m['license'],licenca_url=m['license_url'],origem_url=m['source_url'],largura=m['width'],altura=m['height'],blur_data_url=m['blur_data_url'],observacao=m.get('caption','Imagem de referência do país: '+m.get('place','')+'. Não representa necessariamente o estado selecionado.')))
    upsert(conn,'midia',rows);conn.commit()

