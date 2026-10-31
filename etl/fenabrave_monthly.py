"""Import verified Brazilian monthly Fenabrave headline totals, 2020 to last published month.

Only verified A) Autos, B) Com. Leves, A+B from the official report are accepted.
Missing/unreadable archives are logged, never guessed or replaced with zero.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
from datetime import date
from pathlib import Path

import fitz  # pymupdf
import psycopg
import requests

BASE = "https://www.fenabrave.org.br/portal/files"
OUT = Path("fenabrave_monthly_report.json")
NUM = r"(\\d{1,3}(?:\\.\\d{3})+|\\d+)"
ROW = {
    "auto": re.compile(r"\\bA\\s*\\)\\s*Autos\\s+" + NUM + r"\\s+" + NUM + r"\\s+" + NUM, re.I),
    "leves": re.compile(r"\\bB\\s*\\)\\s*Com\\.?\\s*Leves\\s+" + NUM + r"\\s+" + NUM + r"\\s+" + NUM, re.I),
    "total": re.compile(r"\\bA\\s*\\+\\s*B\\s+" + NUM + r"\\s+" + NUM + r"\\s+" + NUM, re.I),
}

def parse_pdf(blob: bytes, year: int, month: int):
    if not blob.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    doc = fitz.open(stream=blob, filetype="pdf")
    if len(doc) < 2:
        raise ValueError("incomplete document")
    # Every report starts with a monthly summary (and often repeats it on page 2).
    for page in range(min(2, len(doc))):
        txt = doc[page].get_text("text", sort=True)
        # The year and month must both match a page's report heading.
        if str(year) not in txt:
            continue
        rows = {}
        for name, pattern in ROW.items():
            match = pattern.search(txt)
            if match:
                rows[name] = tuple(int(x.replace(".", "")) for x in match.groups())
        if len(rows) != 3:
            continue
        autos, leves, total = rows["auto"], rows["leves"], rows["total"]
        if autos[0] + leves[0] != total[0] or autos[2] + leves[2] != total[2]:
            continue
        if total[0] <= 0 or total[2] < total[0] or total[2] > 30_000_000:
            continue
        return {
            "autos": autos[0], "leves": leves[0], "total": total[0],
            "acumulado": total[2],
        }
    raise ValueError("monthly A+B table unavailable or failed checksum")

def collect(start: int, end: int):
    session = requests.Session()
    session.headers.update({"User-Agent": "MotorAtlasAcademicData/1.0 (official publicly available reports)"})
    today = date.today()
    accepted, unavailable = [], []
    for year in range(start, min(end, today.year) + 1):
        # For the present year, don't request an as-yet unpublished current-month report.
        last_month = (today.month - 1) if year == today.year else 12
        for month in range(1, last_month + 1):
            url = f"{BASE}/{year}_{month:02d}_02.pdf"
            try:
                resp = session.get(url, timeout=(6, 16))
                resp.raise_for_status()
                if len(resp.content) > 40_000_000:
                    raise ValueError("PDF larger than 40 MB")
                data = parse_pdf(resp.content, year, month)
                accepted.append({
                    "ano": year, "mes": month, **data, "url": url,
                    "sha256": hashlib.sha256(resp.content).hexdigest(),
                })
                print(f"OK {year}-{month:02d}: {data['total']:,} units", flush=True)
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                unavailable.append({"ano": year, "mes": month, "url": url,
                                    "motivo": str(exc)[:200]})
                print(f"SKIP {year}-{month:02d}: {type(exc).__name__}", flush=True)
            time.sleep(0.1)
    report = {"intervalo": [start, end], "registros_validados": len(accepted),
              "arquivos_indisponiveis_ou_nao_processados": unavailable,
              "registros": accepted,
              "nota": "Only validated monthly A+B totals, not model rankings."}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def upload(report):
    uri = os.getenv("ATLAS_DATABASE_URL")
    if not uri:
        raise RuntimeError("ATLAS_DATABASE_URL missing; not writing data")
    if not report["registros"]:
        print("No compatible reports found: no data written", flush=True)
        return
    with psycopg.connect(uri, prepare_threshold=None) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS public.atlas_fenabrave_mensal (
            ano smallint NOT NULL, mes smallint NOT NULL CHECK(mes BETWEEN 1 AND 12),
            autos bigint NOT NULL CHECK(autos>=0),
            comerciais_leves bigint NOT NULL CHECK(comerciais_leves>=0),
            total bigint NOT NULL CHECK(total=autos+comerciais_leves),
            acumulado bigint NOT NULL CHECK(acumulado>=total),
            fonte_url text NOT NULL, arquivo_sha256 char(64) NOT NULL,
            carregado_em timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (ano,mes))""")
        con.execute("ALTER TABLE public.atlas_fenabrave_mensal ENABLE ROW LEVEL SECURITY")
        con.execute("REVOKE ALL ON public.atlas_fenabrave_mensal FROM anon, authenticated")
        with con.cursor() as cur:
            cur.executemany("""INSERT INTO public.atlas_fenabrave_mensal
              (ano,mes,autos,comerciais_leves,total,acumulado,fonte_url,arquivo_sha256)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT(ano,mes) DO UPDATE SET
                autos=excluded.autos,comerciais_leves=excluded.comerciais_leves,
                total=excluded.total,acumulado=excluded.acumulado,
                fonte_url=excluded.fonte_url,arquivo_sha256=excluded.arquivo_sha256,
                carregado_em=now()""", [
                (x["ano"], x["mes"], x["autos"], x["leves"],
                 x["total"], x["acumulado"], x["url"], x["sha256"])
                for x in report["registros"]])
    print(f"Inserted/updated {len(report['registros'])} validated monthly totals", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio", type=int, default=2020)
    parser.add_argument("--fim", type=int, default=date.today().year)
    args = parser.parse_args()
    report = collect(args.inicio, args.fim)
    upload(report)
