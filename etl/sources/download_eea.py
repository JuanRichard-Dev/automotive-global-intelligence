"""Official EEA 2024 FINAL new-car registrations, all countries, CC BY 4.0.

python etl/sources/download_eea.py
Downloads server-side aggregates, checks each country against an independent
SUM(r), and writes canonical CSVs. No database or UI changes, no invented values.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/raw/adicionais/eea'
SOURCE='EEA_CO2_CARS_2024_F'
TABLE='[CO2Emission].[latest].[co2cars_2024Fv30]'
METADATA='https://sdi.eea.europa.eu/catalogue/srv/api/records/5018ec17-2348-4c92-8761-6f2377bbd1c0'
QUERY_MODELS=f'SELECT MS,Mk,Cn,Ft,Fm,SUM(CAST(r AS bigint)) AS units FROM {TABLE} GROUP BY MS,Mk,Cn,Ft,Fm ORDER BY MS,Mk,Cn,Ft,Fm'
QUERY_TOTALS=f'SELECT MS,SUM(CAST(r AS bigint)) AS units,COUNT(*) AS source_rows FROM {TABLE} GROUP BY MS ORDER BY MS'
FILES={
    'metadata.html':METADATA,
    'statistical_metadata.pdf':'https://sdi.eea.europa.eu/catalogue/api/records/5018ec17-2348-4c92-8761-6f2377bbd1c0/attachments/CO2%20from%20cars%20and%20vans_Stastical%20metadata_2024.pdf',
    'table_definition.xlsx':'https://sdi.eea.europa.eu/catalogue/api/records/5018ec17-2348-4c92-8761-6f2377bbd1c0/attachments/Table-definition-cars-2024-Final.xlsx',
    'api_help.html':'https://discodata.eea.europa.eu/Help.html',
}
FIELDS=['record_id','country_iso','state_code','city','year','month','period_kind','brand','model','segment','fuel','price','currency','units','metric','source_id','origin','reference_period','record_origin','hash_origin','collected_at']


def fetch(url,path,manifest):
    if path.exists():
        body=path.read_bytes()
    else:
        req=urllib.request.Request(url,headers={'User-Agent':'MotorAtlasResearch/1.0 (EEA public statistical data)'})
        with urllib.request.urlopen(req,timeout=180,context=__import__('ssl').create_default_context(cafile=__import__('certifi').where())) as response:
            body=response.read()
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(body)
    manifest.append(dict(url=url,path=str(path.relative_to(ROOT)),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    return body


def request_page(query,page,size,name,manifest):
    url='https://discodata.eea.europa.eu/sql?'+urllib.parse.urlencode(dict(query=query,p=page,nrOfHits=size))
    body=fetch(url,OUT/f'{name}_page_{page:04d}.json',manifest)
    payload=json.loads(body)
    if payload.get('errors') or 'results' not in payload:
        raise RuntimeError(f'EEA query failed: {payload}')
    return [{str(k).lower():v for k,v in row.items()} for row in payload['results']]


def integer(value):
    n=Decimal(str(value))
    if not n.is_finite() or n<0 or n!=n.to_integral_value():
        raise ValueError(f'Invalid real registration count: {value!r}')
    return int(n)


def clean(value):
    return re.sub(r'\s+',' ',str(value or '').strip()).upper()


def iso(value):
    code=clean(value)
    code={'EL':'GR','UK':'GB'}.get(code,code)
    if not re.fullmatch('[A-Z]{2}',code):
        raise ValueError(f'Unknown country code: {value!r}')
    return code


def fuel(ft,fm):
    value=clean(ft).lower()
    mode=clean(fm)
    if value in ('hydrogen','hydrogen/electric'):return 'hidrogenio'
    if value=='electric':return 'eletrico'
    if mode in ('H','P') or '/electric' in value:return 'hibrido'
    if value=='petrol':return 'gasolina'
    if value=='diesel':return 'diesel'
    if value in ('lpg','ng','natural gas','cng','lng'):return 'gas'
    if value in ('e85','ethanol'):return 'flex'
    return 'nao_informado' if not value else 'outro'


def canonicalize(raw,totals,manifest):
    eligible={iso(row['ms']):integer(row['units']) for row in totals}
    grouped=defaultdict(int)
    raw_fuels=defaultdict(int)
    unknown=defaultdict(int)
    seen=set()
    for row in raw:
        key=tuple(row.get(c) for c in ['ms','mk','cn','ft','fm'])
        if key in seen:raise ValueError(f'Repeated page/group: {key!r}')
        seen.add(key)
        country=iso(row['ms']);units=integer(row['units'])
        brand=clean(row.get('mk')) or 'NAO INFORMADO'
        model=clean(row.get('cn')) or 'NAO INFORMADO'
        normalized=fuel(row.get('ft'),row.get('fm'))
        grouped[(country,brand,model,normalized)]+=units
        raw_fuels[(country,str(row.get('ft')),str(row.get('fm')),normalized)]+=units
        if brand=='NAO INFORMADO' or model=='NAO INFORMADO':unknown[country]+=units
    actual=defaultdict(int)
    byfuel=defaultdict(int)
    for (country,brand,model,f),units in grouped.items():
        actual[country]+=units;byfuel[(country,f)]+=units
    if dict(actual)!=eligible:
        raise ValueError(f'Country reconciliation failed: grouped={dict(actual)}, independent_totals={eligible}')
    today=datetime.now(timezone.utc).date().isoformat()
    rows=[]
    for i,((country,brand,model,f),units) in enumerate(sorted(grouped.items()),1):
        if units==0:continue
        origin=json.dumps([2024,country,brand,model,f,units],ensure_ascii=False,separators=(',',':'))
        rows.append(dict(record_id=i,country_iso=country,state_code=None,city=None,year=2024,month=None,period_kind='annual',brand=brand,model=model,segment=None,fuel=f,price=None,currency=None,units=units,metric='new_registrations',source_id=SOURCE,origin='real',reference_period='2024',record_origin=f'{METADATA}#aggregate-{i}',hash_origin=hashlib.sha256(origin.encode()).hexdigest(),collected_at=today))
    path=OUT/'eea_2024_canonical.csv'
    with path.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    market=[]
    for country,units in sorted(eligible.items()):
        market.append(dict(country_iso=country,year=2024,month=None,period_kind='annual',metric='new_registrations',fuel=None,units=units,source_id=SOURCE,scope='All 2024 final passenger-car registrations reported to EEA; same table as model aggregates; national coverage only'))
    for (country,f),units in sorted(byfuel.items()):
        market.append(dict(country_iso=country,year=2024,month=None,period_kind='annual',metric='new_registrations',fuel=f,units=units,source_id=SOURCE,scope='Selected normalized fuel; all 2024 final passenger-car registrations reported to EEA'))
    with (OUT/'eea_2024_market_totals.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(market[0]));writer.writeheader();writer.writerows(market)
    quality=dict(source_id=SOURCE,year=2024,status='FINAL',table=TABLE,countries=len(eligible),canonical_rows=len(rows),units=sum(eligible.values()),country_totals=eligible,unknown_brand_or_model_units=dict(unknown),grouped_rows_before_normalization=len(raw),reconciles=True,raw_fuel_mapping=[dict(country=c,source_fuel=f,source_mode=m,normalized_fuel=n,units=u) for (c,f,m,n),u in sorted(raw_fuels.items())])
    (OUT/'quality_report.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    metadata=dict(id=SOURCE,organizacao='European Environment Agency / DG-CLIMA',titulo='Monitoring of CO2 emissions from passenger cars, 2024 — FINAL',url=METADATA,ano_inicio=2024,ano_fim=2024,licenca='CC BY 4.0',licenca_url='https://creativecommons.org/licenses/by/4.0/',acesso_em=today,tipo='official_regulatory_new_registration_aggregates',medida='new_registrations',cobertura='EU27, Iceland and Norway as present in the downloaded final table; annual national new passenger cars; grouped make/commercial name/fuel',limitacoes='Regulatory monitoring universe; not retail transactions. No state, city, monthly period, body segment or price published in this extraction. Commercial names can include variants and incomplete or unknown names; no invented model-family harmonization. Use SUM(r), not number of rows; never combine provisional and final. Do not add to overlapping same-country/source new-registration facts without an explicit source choice.',status='coletada_verificada',table=TABLE,sql_models=QUERY_MODELS,sql_independent_country_totals=QUERY_TOTALS,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),files=manifest,quality=quality)
    (OUT/'source_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:quality[k] for k in ['countries','canonical_rows','units','reconciles']},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',action='store_true',help='Only inspect actual published schema and three records')
    parser.add_argument('--page-size',type=int,default=10000)
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);manifest=[]
    for name,url in FILES.items():
        try:fetch(url,OUT/name,manifest)
        except Exception as error:print('Documentation fetch failed:',name,str(error),flush=True)
    if args.probe:
        rows=request_page(f'SELECT TOP 3 * FROM {TABLE}',1,3,'probe',manifest)
        print(json.dumps(rows,ensure_ascii=False,indent=2),flush=True)
        return
    totals=request_page(QUERY_TOTALS,1,100,'totals',manifest)
    if not totals:raise RuntimeError('No official country totals returned')
    raw=[]
    for page in range(1,1001):
        rows=request_page(QUERY_MODELS,page,args.page_size,'models',manifest)
        raw.extend(rows);print('Page',page,'rows',len(rows),'total',len(raw),flush=True)
        if len(rows)<args.page_size:break
    else:raise RuntimeError('Safety pagination limit reached; refusing incomplete output')
    (OUT/'download_metadata.json').write_text(json.dumps(dict(accessed_utc=datetime.now(timezone.utc).isoformat(),files=manifest),ensure_ascii=False,indent=2),encoding='utf-8')
    canonicalize(raw,totals,manifest)


if __name__=='__main__':main()

