"""Análise reproduzível somente de PostgreSQL; execute --help para os recortes.

Não lê CSV/JSON de vendas e não produz dados substitutos quando o banco falha.
"""
from __future__ import annotations

import argparse
import json
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row
import seaborn as sns
from PIL import Image, ImageDraw
from wordcloud import WordCloud

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DSN = 'postgresql://automotive:automotive_local@127.0.0.1:55432/automotive'
COLORS = ['#24b6aa', '#5b8ff9', '#f5b454', '#dc7091', '#9b88d4']
sns.set_theme(style='whitegrid', palette=COLORS)


def frame(conn, sql, params=()):
    return pd.DataFrame(conn.execute(sql, params).fetchall())


def car_mask():
    """Máscara vetorial decorativa; não contém observações analíticas."""
    im = Image.new('L', (1200, 560), 255)
    draw = ImageDraw.Draw(im)
    draw.polygon([(70, 330), (130, 255), (310, 230), (440, 105),
                  (760, 105), (925, 245), (1080, 280), (1145, 355),
                  (1110, 425), (95, 425)], fill=0)
    draw.ellipse((215, 340, 390, 515), fill=0)
    draw.ellipse((830, 340, 1005, 515), fill=0)
    return np.asarray(im)


def save_chart(out, name, title, subtitle, draw):
    fig, ax = plt.subplots(figsize=(12, 7))
    draw(ax)
    ax.set_title(title, loc='left', fontsize=17, fontweight='bold', pad=20)
    fig.text(.03, .018, textwrap.fill(subtitle, width=160), fontsize=8, color='#555555')
    fig.tight_layout(rect=(0, .09, 1, .97))
    fig.savefig(out / f'{name}.png', dpi=170, facecolor='white')
    plt.close(fig)


def missing(ax, reason):
    ax.text(.5, .5, reason, ha='center', va='center', transform=ax.transAxes,
            fontsize=13, wrap=True)
    ax.axis('off')


def forecast(annual):
    if len(annual) < 3:
        return {'disponivel': False, 'motivo': 'Menos de três anos observados.'}
    x = annual.ano.to_numpy(dtype=float)
    y = annual.unidades.to_numpy(dtype=float)
    if not np.all(np.diff(x) == 1):
        return {'disponivel': False, 'motivo': 'Lacunas anuais; sem interpolação.'}
    fit = np.polyfit(x - x[0], y, 1)
    errors = []
    for i in range(3, len(x)):
        trial = np.polyfit(x[:i] - x[0], y[:i], 1)
        errors.append(abs(float(np.polyval(trial, x[i] - x[0])) - y[i]))
    return {'disponivel': True, 'ano': int(x[-1] + 1),
            'unidades': round(max(0, float(np.polyval(fit, x[-1] + 1 - x[0])))),
            'anos_treino': len(x), 'mae_backtest': float(np.mean(errors)) if errors else None,
            'pontos_backtest': len(errors),
            'metodo': 'Tendência linear anual; previsão exploratória, sem intervalo probabilístico.'}


def run(pais='BR', origem='real', medida='new_registrations', ano=2025,
        dsn=None, output=None):
    out = Path(output) if output else ROOT / 'notebooks' / 'resultados' / f'{origem}_{pais}_{medida}_{ano}'
    # Conexão e validações acontecem antes de criar qualquer gráfico.
    with psycopg.connect(dsn or os.getenv('DATABASE_URL', DEFAULT_DSN),
                         row_factory=dict_row, connect_timeout=5,
                         options='-c statement_timeout=60000') as conn:
        if not conn.execute("SELECT 1 FROM execucao_etl WHERE status='concluida' LIMIT 1").fetchone():
            raise RuntimeError('ETL não concluído. Nenhum gráfico foi gerado.')
        scope = "a.pais_id=(SELECT id FROM dim_pais WHERE iso=%s) AND a.origem=%s AND a.medida=%s AND a.periodicidade='anual'"
        params = (pais, origem, medida)
        yearly = frame(conn, f'''SELECT a.ano,a.modelo_id,b.nome marca,m.nome modelo,
            sum(a.unidades)::bigint unidades,
            sum(a.receita_usd)/nullif(sum(a.unidades_com_preco),0) preco_usd
            FROM mv_agregados a JOIN dim_modelo m ON m.id=a.modelo_id
            JOIN dim_marca b ON b.id=a.marca_id WHERE {scope} AND a.ano<=%s
            GROUP BY a.ano,a.modelo_id,b.nome,m.nome ORDER BY a.ano,a.modelo_id''', (*params, ano))
        if yearly.empty or yearly[yearly.ano == ano].empty:
            raise RuntimeError(f'Sem dados anuais no recorte {params}, ano {ano}. Nenhum gráfico gerado.')
        current = yearly[yearly.ano == ano].copy().sort_values(['unidades', 'marca', 'modelo'], ascending=[False, True, True])
        current['rotulo'] = current.marca + ' ' + current.modelo
        annual = yearly.groupby('ano', as_index=False).unidades.sum().sort_values('ano')
        monthly = frame(conn, '''SELECT ano,mes,sum(unidades)::bigint unidades FROM mv_agregados a
            WHERE a.pais_id=(SELECT id FROM dim_pais WHERE iso=%s) AND origem=%s AND medida=%s
            AND periodicidade='mensal' AND ano<=%s GROUP BY ano,mes ORDER BY ano,mes''', (*params, ano))
        # Preços observacionais: fatos mensais sintéticos originam a visão anual.
        fact_period = 'mensal' if origem == 'sintetico' else 'anual'
        boxes = frame(conn, '''SELECT s.nome segmento,count(*) n,
            percentile_cont(ARRAY[.05,.25,.5,.75,.95]) WITHIN GROUP(ORDER BY a.preco_usd) quantis
            FROM fato_vendas a JOIN dim_segmento s ON s.id=a.segmento_id
            WHERE pais_id=(SELECT id FROM dim_pais WHERE iso=%s) AND origem=%s AND medida=%s
            AND ano=%s AND periodicidade=%s AND preco_usd IS NOT NULL
            GROUP BY s.nome ORDER BY s.nome''', (*params, ano, fact_period))
        geography = frame(conn, f'''SELECT e.codigo,e.nome,e.geometria,v.unidades FROM dim_estado e
            JOIN dim_pais p ON p.id=e.pais_id LEFT JOIN
            (SELECT estado_id,sum(unidades)::bigint unidades FROM mv_agregados a WHERE {scope}
             AND a.ano=%s GROUP BY estado_id) v ON v.estado_id=e.id
            WHERE p.iso=%s ORDER BY e.codigo''', (*params, ano, pais))
        map_level = 'estados'
        if geography.empty or not geography.unidades.notna().any():
            # Com a mesma medida/origem/ano, países sem cobertura ficam sem valor.
            geography = frame(conn, '''SELECT p.iso codigo,b.nome,b.geometria,v.unidades
                FROM mapa_base b LEFT JOIN dim_pais p ON p.id=b.pais_id LEFT JOIN
                (SELECT pais_id,sum(unidades)::bigint unidades FROM mv_agregados
                 WHERE origem=%s AND medida=%s AND periodicidade='anual' AND ano=%s GROUP BY pais_id) v
                ON v.pais_id=p.id ORDER BY b.id''', (origem, medida, ano))
            map_level = 'países; mesma medida, cobertura pode diferir'
        sources = frame(conn, f'''SELECT DISTINCT f.id,f.organizacao,f.titulo,f.url,f.licenca,f.cobertura,f.limitacoes
            FROM mv_agregados a CROSS JOIN LATERAL unnest(a.fontes) s(id)
            JOIN fonte_dados f ON f.id=s.id WHERE a.pais_id=(SELECT id FROM dim_pais WHERE iso=%s)
            AND a.origem=%s AND a.medida=%s AND a.periodicidade IN ('anual','mensal') AND a.ano<=%s''', (*params, ano))
        den = conn.execute('''SELECT count(*) n,sum(unidades)::bigint unidades FROM fato_mercado
            WHERE pais_id=(SELECT id FROM dim_pais WHERE iso=%s) AND origem=%s AND medida=%s
            AND ano=%s AND periodicidade='anual' AND mes IS NULL AND estado_id IS NULL
            AND combustivel_id IS NULL''', (*params, ano)).fetchone()
        etl = conn.execute("SELECT id,seed,linhas_sinteticas,terminada_em FROM execucao_etl WHERE status='concluida' ORDER BY terminada_em DESC LIMIT 1").fetchone()
    out.mkdir(parents=True, exist_ok=True)
    badge = 'SIMULAÇÃO · não representa vendas reais' if origem == 'sintetico' else 'DADOS REAIS · cobertura observada da fonte'
    subtitle = f'{badge} | {pais} · {ano} · {medida} | anos, meses e trimestres não são somados entre si'

    def ranking(ax):
        top = current.head(10).iloc[::-1]
        ax.barh(top.rotulo, top.unidades, color=COLORS[0]); ax.set_xlabel('Unidades observadas')
    save_chart(out, 'ranking', 'Modelos com maior volume no recorte', subtitle, ranking)

    def heatmap(ax):
        chosen = current.head(15).modelo_id
        h = yearly[yearly.modelo_id.isin(chosen)].copy()
        h['rotulo'] = h.marca + ' ' + h.modelo
        pivot = h.pivot(index='rotulo', columns='ano', values='unidades')
        sns.heatmap(pivot, ax=ax, cmap='YlGnBu', mask=pivot.isna(), cbar_kws={'label': 'Unidades'})
        ax.set_ylabel(''); ax.tick_params(axis='y', labelsize=8)
    save_chart(out, 'heatmap', 'Evolução dos 15 líderes do ano selecionado', subtitle + ' | célula vazia = ausência, nunca zero presumido', heatmap)

    prediction = {'disponivel': False}
    def temporal(ax):
        if not monthly.empty:
            t = monthly.copy(); t['data'] = pd.to_datetime(dict(year=t.ano, month=t.mes, day=1))
            # Reindex apenas para quebrar a linha nas lacunas, sem preencher valores.
            t = t.set_index('data').reindex(pd.date_range(t.data.min(), t.data.max(), freq='MS'))
            ax.plot(t.index, t.unidades, color=COLORS[0], marker='o', markersize=3); ax.set_xlabel('Mês publicado')
        else:
            t = annual.set_index('ano').reindex(range(int(annual.ano.min()), int(annual.ano.max()) + 1))
            ax.plot(t.index, t.unidades, marker='o', color=COLORS[0]); ax.set_xticks(t.index)
            ax.set_xlabel('Ano completo publicado')
        ax.set_ylabel('Unidades na cobertura observada')
    save_chart(out, 'temporal', f'Série temporal publicada até {ano}', subtitle + ' | mudança de cobertura pode afetar a tendência', temporal)

    def boxplot(ax):
        if boxes.empty:
            return missing(ax, 'Preço não publicado neste recorte.\nNão foi estimado a partir do modelo.')
        stats = []
        for row in boxes.itertuples():
            q = row.quantis
            stats.append(dict(label=f'{row.segmento}\nn={row.n:,}', whislo=q[0], q1=q[1], med=q[2], q3=q[3], whishi=q[4], fliers=[]))
        ax.bxp(stats, showfliers=False); ax.set_ylabel('Preço USD por observação da fato')
    save_chart(out, 'boxplot', 'Distribuição dos preços observados por segmento', subtitle + ' | caixa P25–P75; mediana; hastes P5–P95; não ponderada por unidades', boxplot)

    pairs = current[['preco_usd', 'unidades']].dropna().astype(float)
    corr = float(pairs.corr().iloc[0, 1]) if len(pairs) >= 3 and (pairs.std() > 0).all() else None
    def correlation(ax):
        if corr is None:
            return missing(ax, f'Correlação indisponível: {len(pairs)} pares com preço.\nSão necessários ≥3 e variância nas duas medidas.')
        ax.scatter(pairs.preco_usd, pairs.unidades, alpha=.7, color=COLORS[1])
        ax.set_xlabel('Preço médio USD do modelo, ponderado por unidades'); ax.set_ylabel('Unidades do modelo')
        ax.text(.98, .97, f'Pearson r = {corr:.3f}\nn = {len(pairs)} modelos', ha='right', va='top', transform=ax.transAxes)
    save_chart(out, 'correlacao', 'Associação entre preço e volume por modelo', subtitle + ' | associação descritiva; não implica causalidade', correlation)

    def choropleth(ax):
        if geography.empty or not geography.geometria.notna().any():
            return missing(ax, 'Geometria não carregada no PostgreSQL.')
        values = pd.to_numeric(geography.unidades, errors='coerce')
        valid = values.dropna()
        norm = plt.Normalize(vmin=0, vmax=max(float(valid.max()), 1) if len(valid) else 1)
        cmap = plt.get_cmap('YlGnBu')
        for row in geography.itertuples():
            g = row.geometria
            if not g: continue
            polygons = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates'] if g['type'] == 'MultiPolygon' else []
            color = cmap(norm(float(row.unidades))) if pd.notna(row.unidades) else '#e6e6e6'
            for poly in polygons:
                ax.add_patch(Polygon(poly[0], closed=True, facecolor=color, edgecolor='white', linewidth=.35))
        ax.autoscale_view(); ax.set_aspect('equal'); ax.axis('off')
        fig = ax.get_figure(); fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=.6, label='Unidades observadas')
    save_chart(out, 'coropletico', f'Volume por território — {map_level}', subtitle + ' | cinza = sem dado compatível; limites Natural Earth, representação não cadastral', choropleth)

    def cloud(ax):
        frequencies = dict(zip(current.rotulo, current.unidades.astype(float)))
        cloud = WordCloud(background_color='white', mask=car_mask(), random_state=42,
                          max_words=80, collocations=False, colormap='viridis',
                          contour_width=2, contour_color='#9ab9bb',
                          min_font_size=5, prefer_horizontal=.85).generate_from_frequencies(frequencies)
        ax.imshow(cloud, interpolation='bilinear'); ax.axis('off')
    save_chart(out, 'wordcloud', 'Preferência observada em uma silhueta de carro', subtitle + ' | tamanho ponderado por unidades; máscara decorativa autoral', cloud)

    total = int(current.unidades.sum())
    eligible = total if origem == 'sintetico' else int(den['unidades']) if den['n'] == 1 and den['unidades'] is not None and den['unidades'] >= total else None
    summary = {'gerado_em_utc': datetime.now(timezone.utc).isoformat(), 'pais': pais,
               'ano': ano, 'origem': origem, 'medida': medida, 'periodicidade': 'anual',
               'unidades_observadas': total, 'mercado_elegivel': eligible,
               'cobertura_pct': total / eligible * 100 if eligible else None,
               'modelos': len(current), 'lider': current.iloc[0][['marca','modelo','unidades']].to_dict(),
               'descritiva_unidades_modelo': current.unidades.describe().to_dict(),
               'correlacao_pearson_preco_unidades': corr, 'pares_correlacao': len(pairs),
               'previsao_exploratoria': prediction, 'execucao_etl': etl,
               'fontes': sources.to_dict(orient='records')}
    (out / 'resumo.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    current.to_csv(out / 'ranking_consultado.csv', index=False)
    annual.to_csv(out / 'serie_anual_consultada.csv', index=False)
    lines = [f'# Análise — {pais}, {ano}', '', f'**{badge}**', '',
             f'Medida: `{medida}`. Apenas registros anuais neste ranking.', '',
             f'Volume observado: **{total:,}** unidades; **{len(current)}** modelos.',
             f'Líder: **{current.iloc[0].rotulo}**, {int(current.iloc[0].unidades):,} unidades.',
             f'Denominador compatível: {eligible if eligible is not None else "indisponível"}.',
             f'Correlação preço/volume: {corr if corr is not None else "indisponível"}; {len(pairs)} pares.', '',
             '## Estatísticas dos volumes por modelo', '',
             f'Média: {current.unidades.mean():,.2f}; mediana: {current.unidades.median():,.2f}; '
             f'desvio padrão amostral: {current.unidades.std():,.2f}; '
             f'mínimo: {current.unidades.min():,}; máximo: {current.unidades.max():,}. '
             'Estas estatísticas descrevem os modelos presentes no recorte; não representam todos os modelos quando a fonte é top N.', '',
             '## Interpretação e limites', '',
             'A origem e a medida permanecem fixas em cada consulta. Totais anuais não são somados a meses ou trimestres. '
             'Ausência em ranking parcial não significa zero. A série acompanha a cobertura carregada, que pode mudar com a publicação. '
             'Primeiro registro DfT inclui importados usados; não é venda de novos. '
             'Correlação não estabelece causalidade. Mapas usam volume absoluto e não controlam população ou tamanho do mercado.', '',
             '## Projeção exploratória', '', json.dumps(prediction, ensure_ascii=False, indent=2), '',
             'A tendência linear serve apenas como demonstração; poucos anos, mudanças de cobertura e ausência de variáveis externas '
             'limitam qualquer uso preditivo. O backtest avança no tempo, sem treinar no futuro. Não há intervalo probabilístico.', '',
             '## Gráficos', '']
    for chart in ['ranking','heatmap','temporal','boxplot','correlacao','coropletico','wordcloud']:
        lines += [f'![{chart}]({chart}.png)', '']
    lines += ['## Proveniência', '', f'Consulta UTC: {summary["gerado_em_utc"]}. Execução ETL: `{etl["id"]}`.', '']
    for s in summary['fontes']:
        lines += [f'- [{s["organizacao"]}: {s["titulo"]}]({s["url"]}) · `{s["id"]}` · {s["licenca"]}. {s["cobertura"]}. {s["limitacoes"]}']
    report = '\n'.join(lines)
    (out / 'relatorio.md').write_text(report, encoding='utf-8')
    docs = ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    for chart in ['ranking','heatmap','temporal','boxplot','correlacao','coropletico','wordcloud']:
        relative = Path(os.path.relpath(out / f'{chart}.png', docs)).as_posix()
        report = report.replace(f']({chart}.png)', f']({relative})')
    (docs / f'relatorio_analise_{origem}_{pais}_{medida}_{ano}.md').write_text(report, encoding='utf-8')
    print(f'Análise concluída: {out}')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pais', default='BR')
    parser.add_argument('--origem', choices=['real'], default='real')
    parser.add_argument('--medida', choices=['new_registrations','first_registrations_including_imports'], default='new_registrations')
    parser.add_argument('--ano', type=int, default=2025)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    return run(**vars(args))


if __name__ == '__main__':
    main()
