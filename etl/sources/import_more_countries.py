"""Import 100 verified 2025 annual top-model facts: Italy and Austria.

Downloads only primary statistical PDFs, extracts their real tables, validates
50 models per country and published eligible totals, then appends canonical
files idempotently. Does not run ETL or touch PostgreSQL/API/UI.

Run with work/clean-venv/Scripts/python.exe (pdfplumber already installed), or
global-venv; the existing clean-venv dependency path is a local fallback.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import re
from pathlib import Path
import ssl
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/raw/adicionais/more_countries'
PDFS={
    'IT_UNRAE_TOP50_2025.pdf':'https://www.unrae.it/files/06%20Top%2050%20Dicembre%202025_6957f75508974.pdf',
    'IT_UNRAE_TOTAL_2025.pdf':'https://unrae.it/files/01%20Comunicato%20Stampa%20UNRAE%20mercato%20Italia%20Dicembre%202025%20e%20infografica_6957f54f33d3b.pdf',
    'AT_STATISTIK_2025.pdf':'https://www.statistik.at/fileadmin/pages/77/Pressemappe_2025.pdf',
}
SIDS={'IT':'IT_UNRAE_2025_TOP50','AT':'AT_STATISTIK_2025_TOP50'}
BRANDS=sorted(['FIAT','DACIA','JEEP','CITROEN','TOYOTA','PEUGEOT','RENAULT','MG','VOLKSWAGEN','VW','FORD','BMW','OPEL','KIA','NISSAN','AUDI','BYD','HYUNDAI','ALFA ROMEO','MERCEDES','SUZUKI','SKODA','LANCIA','CUPRA','DR','VOLVO','SEAT','TESLA','MAZDA','MINI'],key=len,reverse=True)


def pdf_library():
    try:import pdfplumber
    except ModuleNotFoundError:
        sys.path.append(str(ROOT.parents[1]/'work/clean-venv/Lib/site-packages'))
        import pdfplumber
    return pdfplumber


def download(name,url):
    path=OUT/name
    if not path.exists():
        try:
            import certifi
            context=ssl.create_default_context(cafile=certifi.where())
        except ImportError:context=ssl.create_default_context()
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; MotorAtlasResearch; public statistical releases)'})
        with urllib.request.urlopen(request,timeout=120,context=context) as response:body=response.read()
        if not body.startswith(b'%PDF'):raise ValueError(f'Not a published PDF: {url}')
        path.write_bytes(body)
    body=path.read_bytes()
    if not body.startswith(b'%PDF'):raise ValueError(f'Invalid cached PDF: {path}')
    return dict(path=str(path.relative_to(ROOT)),url=url,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))


def brand_model(text):
    text=re.sub(r'\s+',' ',text.strip()).upper()
    for brand in BRANDS:
        if text.startswith(brand+' '):return brand,text[len(brand)+1:]
    raise ValueError(f'Unrecognized published brand/model: {text!r}')


def extract_italy(pdfplumber):
    with pdfplumber.open(OUT/'IT_UNRAE_TOP50_2025.pdf') as pdf:
        page=pdf.pages[0]
        whole=page.extract_text() or ''
        text=page.crop((page.width/2,0,page.width,page.height)).extract_text() or ''
    rows=[]
    # Try the annual right-hand table; each row is rank, brand/model and count.
    for line in text.splitlines():
        match=re.match(r'^\s*(\d{1,2})\s+(.+?)\s+([\d.]+)\s*$',line)
        if match and 1<=int(match[1])<=50:
            brand,model=brand_model(match[2]);rows.append((int(match[1]),brand,model,int(match[3].replace('.',''))))
    if len(rows)!=50:
        rows=[]
        # PDF text extractors can preserve both tables on a single line.
        for line in whole.splitlines():
            match=re.match(r'^\s*(\d{1,2})\s+.+?\s+[\d.]+\s+\1\s+(.+?)\s+([\d.]+)\s*$',line)
            if match:
                brand,model=brand_model(match[2]);rows.append((int(match[1]),brand,model,int(match[3].replace('.',''))))
    with pdfplumber.open(OUT/'IT_UNRAE_TOTAL_2025.pdf') as pdf:
        total_text='\n'.join(page.extract_text() or '' for page in pdf.pages)
    if '1.525.722' not in total_text:raise ValueError('Italy eligible total not verified in same-period UNRAE release')
    return rows,1525722,dict(annual_table_text=whole,total_text=total_text)


def extract_austria(pdfplumber):
    with pdfplumber.open(OUT/'AT_STATISTIK_2025.pdf') as pdf:
        text=pdf.pages[12].extract_text() or ''
    if 'Top 50 Typen' not in text:raise ValueError('Wrong Austria table/page; refusing another population')
    rows=[]
    for line in text.splitlines():
        match=re.match(r'^(.+?)\s+(\d{1,3}(?:\s\d{3})*)\s+\d+,\d\s+',line)
        if not match or match[1].startswith(('Pkw insgesamt','Sonstige')):continue
        brand,model=brand_model(match[1]);rows.append((len(rows)+1,brand,model,int(re.sub(r'\s','',match[2]))))
    if not re.search(r'Pkw insgesamt\s+284\s+978\s+100,0',text):raise ValueError('Austria eligible total not verified in same table')
    return rows,284978,dict(annual_table_text=text)


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle);return reader.fieldnames,list(reader)


def write_csv(path,fields,rows):
    temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-append',action='store_true',help='Save reviewed separate files only')
    parser.add_argument('--reviewed-evidence',type=Path,nargs='?',const=Path(__file__).with_name('reviewed_2025_rankings.json'),help='Use actually reviewed web PDF text evidence if official HTTPS downloads fail; no original PDF hash is invented')
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    method='downloaded_pdf_text'
    if args.reviewed_evidence:
        payload=json.loads(args.reviewed_evidence.read_text(encoding='utf-8'))
        if payload['extraction_method']!='web_pdf_text':raise ValueError('Unknown evidence method')
        method='web_pdf_text'
        tables={}
        manifest=[]
        for country,item in payload['countries'].items():
            if country not in SIDS or item['year']!=2025 or item['source_id']!=SIDS[country]:raise ValueError('Evidence country/year/source mismatch')
            rows=[tuple(row) for row in item['rows']]
            if country=='AT' and sum(row[3] for row in rows)+item['published_other_models_total']!=item['eligible_total']:raise ValueError('Austria top50 plus published other does not reconcile')
            tables[country]=(rows,item['eligible_total'],item)
            entry=dict(url=item['ranking_url'],path=None,sha256=None,bytes=None,extraction_method=method,evidence_path=str(args.reviewed_evidence.relative_to(ROOT)),evidence_sha256=hashlib.sha256(args.reviewed_evidence.read_bytes()).hexdigest())
            if country=='AT' and (OUT/'AT_STATISTIK_2025.pdf').exists():
                actual,actual_total,_=extract_austria(pdf_library())
                if actual!=rows or actual_total!=item['eligible_total']:raise ValueError('Downloaded Austria PDF differs from reviewed web evidence')
                entry.update(download('AT_STATISTIK_2025.pdf',item['ranking_url']))
                entry['extraction_method']='downloaded_pdf_text_verified_against_web_pdf_text'
            manifest.append(entry)
        if set(tables)!=set(SIDS):raise ValueError('Both reviewed countries required')
    else:
        manifest=[download(name,url) for name,url in PDFS.items()]
        pdfplumber=pdf_library()
        tables={'IT':extract_italy(pdfplumber),'AT':extract_austria(pdfplumber)}
    for country,(rows,total,evidence) in tables.items():
        if len(rows)!=50 or sorted(r[0] for r in rows)!=list(range(1,51)):
            raise ValueError(f'{country}: expected exactly 50 ranked rows; got {len(rows)}')
        if len({(r[1],r[2]) for r in rows})!=50 or any(r[3]<=0 for r in rows):raise ValueError('Duplicate model or invalid count')
        if sum(r[3] for r in rows)>total:raise ValueError('Top-model sum exceeds eligible total')
        if country=='IT' and rows[0][1:]!=('FIAT','PANDA',102485):raise ValueError('Italy annual column mismatch')
        if country=='AT' and rows[0][1:]!=('SKODA','OCTAVIA',7892):raise ValueError('Austria annual column mismatch')
        (OUT/f'{country}_extraction_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    raw_path=ROOT/'data/raw/real_sales.csv'
    fields,existing=read_csv(raw_path)
    existing=[row for row in existing if row['source_id'] not in SIDS.values()]
    # IDs use the next unused negative range, independent of source's row counts.
    next_id=min([0]+[int(r['record_id']) for r in existing])-1
    today=datetime.now(timezone.utc).date().isoformat()
    facts=[];markets=[];sources=[]
    for country,(rows,total,_) in tables.items():
        sid=SIDS[country]
        url=PDFS['IT_UNRAE_TOP50_2025.pdf' if country=='IT' else 'AT_STATISTIK_2025.pdf']
        for rank,brand,model,units in rows:
            reference=f'{url}#annual-2025-rank-{rank}'
            row=dict.fromkeys(fields,'')
            row.update(record_id=next_id,country_iso=country,year=2025,period_kind='annual',brand=brand,model=model,units=units,metric='new_registrations',source_id=sid,origin='real',reference_period='2025',record_origin=reference,hash_origin=hashlib.sha256(f'{reference}|{brand}|{model}|{units}'.encode()).hexdigest(),collected_at=today)
            facts.append(row);next_id-=1
        markets.append(dict(country_iso=country,state_code='',year=2025,month='',period_kind='annual',metric='new_registrations',source_id=sid,fuel='',units=total,scope='Top 50 passenger-car models; denominator is the full national new-passenger-car market from the same 2025 publication edition'))
        sources.append(dict(id=sid,organizacao='UNRAE' if country=='IT' else 'STATISTIK AUSTRIA',titulo='Immatricolazioni Italia 2025 — Top 50 e totale nazionale' if country=='IT' else 'Fahrzeugzulassungen 2025 — Tabelle 7 Top 50 Pkw-Typen',url=url,ano_inicio=2025,ano_fim=2025,licenca='Copyright da publicação preservado; licença aberta específica não identificada. Extrato factual para pesquisa pessoal com atribuição; não redistribuir PDF como se fosse CC.',licenca_url='https://www.unrae.it/' if country=='IT' else 'https://www.statistik.at/',acesso_em=today,tipo='primaria' if country=='IT' else 'oficial',medida='new_registrations',cobertura='Top 50 nacional de automóveis novos, ano completo 2025; todos os combustíveis; sem desagregação estadual',limitacoes='Cobertura parcial top 50. Estado, cidade, combustível, segmento e preço não publicados neste ranking permanecem ausentes. Não somar com outra fonte do mesmo país/ano/medida. Áustria: tabela M1; não confundir com usados, elétricos isolados ou estoque. Itália: coluna gen./dic. 2025, não dezembro isolado.',sha256=next(x['sha256'] for x in manifest if x['url']==url),status='carregada'))
    write_csv(OUT/'canonical_2025.csv',fields,facts)
    market_path=ROOT/'data/raw/market_totals.csv'
    market_fields,previous_markets=read_csv(market_path)
    write_csv(OUT/'market_totals_2025.csv',market_fields,markets)
    (OUT/'sources_metadata.json').write_text(json.dumps(dict(sources=sources,downloads=manifest,extraction_method=method,totals={c:t[1] for c,t in tables.items()},rows=len(facts),source_scope='Published statistical facts; attribution required; no open license inferred for PDF publications'),ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.no_append:
        write_csv(raw_path,fields,existing+facts)
        write_csv(market_path,market_fields,[r for r in previous_markets if r['source_id'] not in SIDS.values()]+markets)
        source_path=ROOT/'data/seed/sources.json'
        previous_sources=json.loads(source_path.read_text(encoding='utf-8'))
        temporary=source_path.with_suffix('.json.pending')
        temporary.write_text(json.dumps([s for s in previous_sources if s['id'] not in SIDS.values()]+sources,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(source_path)
    print(json.dumps(dict(rows=len(facts),countries=list(tables),totals={c:t[1] for c,t in tables.items()},appended=not args.no_append),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
