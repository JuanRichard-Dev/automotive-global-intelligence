"""Download only official public DGT monthly registration files; no database changes.

Run with the project Python: python etl/sources/download_dgt.py --year 2025 --months 1
After inspection, --months all collects the complete year (not fleet snapshots).
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/raw/adicionais/dgt'
LINKS = {
    'record_layout.pdf':'https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/matraba/MATRICULACIONES_MATRABA.pdf',
    'dataset.html':'https://datos.gob.es/es/catalogo/e00003801-microdatos-de-matriculaciones-de-vehiculos-mensual',
    'dataset.json':'https://datos.gob.es/apidata/catalog/dataset/e00003801-microdatos-de-matriculaciones-de-vehiculos-mensual.json',
    'official_listing.html':'https://www.dgt.es/menusecundario/dgt-en-cifras/matraba-listados/matriculaciones-automoviles-mensual.html',
    'dgt_legal.html':'https://www.dgt.es/contenido/aviso-legal/index.html',
}


def fetch(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        body = target.read_bytes()
        return dict(url=url,path=str(target.relative_to(ROOT)),bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),cached=True)
    request = urllib.request.Request(url, headers={'User-Agent':'MotorAtlasResearch/1.0 (public statistics collection)'})
    with urllib.request.urlopen(request, timeout=120) as response:
        body=response.read()
        if target.suffix=='.zip' and not body.startswith(b'PK'):
            raise ValueError(f'Not a ZIP: {url}')
        target.write_bytes(body)
        return dict(url=url,path=str(target.relative_to(ROOT)),bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),http_status=response.status,content_type=response.headers.get('Content-Type'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year',type=int,default=2025)
    parser.add_argument('--months',default='1',help='Comma-separated actual months or all')
    args=parser.parse_args()
    months=range(1,13) if args.months=='all' else [int(m) for m in args.months.split(',')]
    if not 2015<=args.year<=2026 or any(m<1 or m>12 for m in months):
        raise ValueError('Invalid published year/month')
    manifest_path=OUT/'download_metadata.json'
    previous=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    entries={r['path']:r for r in previous.get('files',[])}
    errors=[]
    for name,url in LINKS.items():
        try:
            item=fetch(url,OUT/name);entries[item['path']]=item
            print(name,item['bytes'],flush=True)
        except Exception as error:
            errors.append(dict(url=url,error=str(error)))
            print('Metadata unavailable:',name,error,flush=True)
    for month in months:
        url=f'https://www.dgt.es/microdatos/salida/{args.year}/{month}/vehiculos/matriculaciones/export_mensual_mat_{args.year}{month:02d}.zip'
        try:
            item=fetch(url,OUT/f'export_mensual_mat_{args.year}{month:02d}.zip')
            item.update(year=args.year,month=month)
            entries[item['path']]=item
            print(args.year,month,item['bytes'],flush=True)
        except Exception as error:
            errors.append(dict(url=url,error=str(error)))
            print('Failed month:',args.year,month,error,flush=True)
        manifest_path.parent.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(dict(accessed_utc=datetime.now(timezone.utc).isoformat(),files=list(entries.values()),errors=errors),ensure_ascii=False,indent=2),encoding='utf-8')
    if not any(p.get('year')==args.year for p in entries.values()):
        raise RuntimeError('No monthly source downloaded; no facts created.')


if __name__=='__main__':main()
