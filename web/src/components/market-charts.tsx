'use client';

import { useEffect, useMemo, useRef, useId } from 'react';
import * as echarts from 'echarts';

export interface MarketChartsProps {
  ranking: { modelo_id: number; marca: string; modelo: string; unidades: number }[];
  fuels: { nome: string; unidades: number }[];
  segments?: { segmento: string; unidades: number }[];
  annual?: { ano: number; mes: number | null; unidades: number }[];
}
interface ValueRow {
  name: string;
  value: number;
}
const numbers = new Intl.NumberFormat('pt-BR');
const percent = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
const colors = ['#d8bf94', '#a4bbbd', '#b59c86', '#a8b59a', '#e4d8be', '#9898b4', '#8a7967'];
const tooltip: echarts.TooltipComponentOption = {
  trigger: 'item',
  renderMode: 'richText',
  backgroundColor: '#121619',
  borderColor: '#6e604c',
  textStyle: { color: '#f2eee7' },
  valueFormatter: (value) => `${numbers.format(Number(value))} unidades`,
};

/** The installed ECharts API supplies React lifecycle integration without another wrapper package. */
function ReactECharts({ option, label }: { option: echarts.EChartsOption; label: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const container = host.current;
    if (!container) return;
    const chart = echarts.init(container, undefined, { renderer: 'svg' });
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const render = () => chart.setOption({ ...option, animation: !motion.matches }, true);
    render();
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);
    motion.addEventListener('change', render);
    return () => {
      motion.removeEventListener('change', render);
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);
  return <div ref={host} role="img" aria-label={label} className="h-[330px] w-full min-w-0" />;
}

function csvValue(value: string | number) {
  let text = String(value);
  if (/^[=+@\-\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function DataTable({ rows, title, file }: { rows: ValueRow[]; title: string; file: string }) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  const csv = [
    ['Categoria', 'Unidades', 'Participação na cobertura (%)'],
    ...rows.map((row) => [row.name, row.value, total > 0 ? (row.value / total) * 100 : '']),
  ]
    .map((row) => row.map(csvValue).join(';'))
    .join('\r\n');
  return (
    <div className="mt-4 flex flex-wrap items-start justify-between gap-3 text-xs">
      <details className="min-w-0 flex-1">
        <summary className="cursor-pointer text-[#d8bf94]">
          Ver tabela de {title.toLocaleLowerCase('pt-BR')}
        </summary>
        <div className="mt-3 max-h-64 overflow-auto">
          <table className="w-full text-left text-[#e1ddd3]">
            <caption className="sr-only">
              {title}. Participação calculada na cobertura recebida da API.
            </caption>
            <thead>
              <tr className="border-b border-white/15">
                <th scope="col" className="py-2 pr-3">
                  Categoria
                </th>
                <th scope="col" className="py-2 text-right">
                  Unidades
                </th>
                <th scope="col" className="py-2 pl-3 text-right">
                  % da cobertura
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name} className="border-b border-white/10">
                  <th scope="row" className="py-2 pr-3 font-normal">
                    {row.name}
                  </th>
                  <td className="py-2 text-right tabular-nums">{numbers.format(row.value)}</td>
                  <td className="py-2 pl-3 text-right tabular-nums">
                    {percent.format((row.value / total) * 100)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <a
        className="shrink-0 text-[#d8bf94] underline underline-offset-4"
        download={file}
        href={`data:text/csv;charset=utf-8,${encodeURIComponent('\uFEFF' + csv)}`}
        aria-label={`Baixar CSV de ${title.toLocaleLowerCase('pt-BR')}`}
      >
        Baixar CSV
      </a>
    </div>
  );
}

function sumByName(rows: ValueRow[]) {
  const grouped = new Map<string, number>();
  for (const row of rows) grouped.set(row.name, (grouped.get(row.name) ?? 0) + row.value);
  return [...grouped]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name, 'pt-BR'));
}

export function MarketCharts({ ranking, fuels }: MarketChartsProps) {
  const headingId = useId();
  const models = useMemo(
    () =>
      sumByName(
        ranking
          .filter((row) => Number.isFinite(Number(row.unidades)) && Number(row.unidades) > 0)
          .map((row) => ({
            name: `${row.marca} ${row.modelo}`.trim(),
            value: Number(row.unidades),
          })),
      ),
    [ranking],
  );
  const brands = useMemo(() => {
    const all = sumByName(
      ranking
        .filter((row) => Number.isFinite(Number(row.unidades)) && Number(row.unidades) > 0)
        .map((row) => ({ name: row.marca || 'Marca não informada', value: Number(row.unidades) })),
    );
    return all.length > 6
      ? [
          ...all.slice(0, 6),
          { name: 'Outras marcas', value: all.slice(6).reduce((sum, row) => sum + row.value, 0) },
        ]
      : all;
  }, [ranking]);
  const knownFuels = useMemo(
    () =>
      sumByName(
        fuels
          .filter((row) => {
            const name = row.nome
              .normalize('NFD')
              .replace(/[\u0300-\u036f]/g, '')
              .toLowerCase()
              .replaceAll('_', ' ')
              .trim();
            return (
              Number.isFinite(Number(row.unidades)) &&
              Number(row.unidades) > 0 &&
              name !== '' &&
              ![
                'nao informado',
                'nao informada',
                'desconhecido',
                'desconhecida',
                'unknown',
              ].includes(name)
            );
          })
          .map((row) => ({ name: row.nome, value: Number(row.unidades) })),
      ),
    [fuels],
  );
  const options = useMemo(() => {
    const base: echarts.EChartsOption = {
      color: colors,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Arial, sans-serif', color: '#e1ddd3' },
      animationDuration: 500,
      aria: { enabled: true, decal: { show: true } },
      tooltip,
    };
    const donut: echarts.EChartsOption = {
      ...base,
      legend: {
        type: 'scroll',
        bottom: 0,
        textStyle: { color: '#d4cfc4' },
        pageTextStyle: { color: '#d4cfc4' },
      },
      series: [
        {
          type: 'pie',
          radius: ['43%', '69%'],
          center: ['50%', '43%'],
          label: { show: false },
          emphasis: { label: { show: true, color: '#f2eee7', formatter: '{b}\n{d}%' } },
          itemStyle: { borderColor: '#121619', borderWidth: 3, borderRadius: 4 },
          data: brands,
        },
      ],
    };
    const treemap: echarts.EChartsOption = {
      ...base,
      series: [
        {
          type: 'treemap',
          data: models,
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          left: 0,
          right: 0,
          top: 8,
          bottom: 8,
          label: {
            show: true,
            color: '#0c0e10',
            fontWeight: 'bold',
            overflow: 'truncate',
            formatter: '{b}',
          },
          itemStyle: { borderColor: '#121619', borderWidth: 2, gapWidth: 2 },
          emphasis: { itemStyle: { borderColor: '#f2eee7', borderWidth: 2 } },
        },
      ],
    };
    const fuel: echarts.EChartsOption = {
      ...base,
      legend: {
        type: 'scroll',
        bottom: 0,
        textStyle: { color: '#d4cfc4' },
        pageTextStyle: { color: '#d4cfc4' },
      },
      grid: { top: 30, left: 8, right: 14, bottom: 55, containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#bcbdb7', formatter: (value: number) => numbers.format(value) },
        splitLine: { lineStyle: { color: '#ffffff10' } },
      },
      yAxis: {
        type: 'category',
        data: ['Unidades publicadas'],
        axisLabel: { color: '#bcbdb7' },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: knownFuels.map((row) => ({
        name: row.name,
        type: 'bar' as const,
        stack: 'combustiveis',
        barMaxWidth: 64,
        data: [{ name: row.name, value: row.value }],
        emphasis: { focus: 'series' as const },
      })),
    };
    return { donut, treemap, fuel };
  }, [brands, models, knownFuels]);
  return (
    <section aria-labelledby={headingId} className="mt-8">
      <h3 id={headingId} className="mb-2 text-3xl">
        O perfil da cobertura
      </h3>
      <p className="mb-6 max-w-3xl text-sm text-[#b5b6b0]">
        Distribuições ponderadas pelas unidades publicadas no recorte. As parcelas descrevem a
        cobertura disponível; não substituem o total elegível de mercado.
      </p>
      <div className="grid min-w-0 gap-5 lg:grid-cols-2">
        <figure className="m-0 min-w-0 rounded-xl border border-white/10 bg-[#121619] p-5">
          <figcaption className="mb-2 text-xl text-[#f2eee7]">Participação por marca</figcaption>

          {brands.length ? (
            <ReactECharts
              option={options.donut}
              label="Donut: participação por marca nas unidades da cobertura. Valores na tabela abaixo."
            />
          ) : (
            <p role="status" className="py-14 text-[#b5b6b0]">
              Sem unidades publicadas neste recorte.
            </p>
          )}
          {brands.length > 0 && (
            <DataTable rows={brands} title="Participação por marca" file="motor-atlas-marcas.csv" />
          )}
        </figure>
        <figure className="m-0 min-w-0 rounded-xl border border-white/10 bg-[#121619] p-5">
          <figcaption className="mb-2 text-xl text-[#f2eee7]">Volume por modelo</figcaption>

          {models.length ? (
            <ReactECharts
              option={options.treemap}
              label="Treemap: área proporcional às unidades de cada modelo. Valores na tabela abaixo."
            />
          ) : (
            <p role="status" className="py-14 text-[#b5b6b0]">
              Sem modelos publicados neste recorte.
            </p>
          )}
          {models.length > 0 && (
            <DataTable rows={models} title="Unidades por modelo" file="motor-atlas-modelos.csv" />
          )}
        </figure>
        {knownFuels.length > 0 && (
          <figure className="m-0 min-w-0 rounded-xl border border-white/10 bg-[#121619] p-5 lg:col-span-2">
            <figcaption className="mb-2 text-xl text-[#f2eee7]">Combustíveis informados</figcaption>

            {knownFuels.length ? (
              <ReactECharts
                option={options.fuel}
                label="Barra empilhada: unidades por combustível conhecido. Valores na tabela abaixo."
              />
            ) : (
              <p role="status" className="py-12 text-sm text-[#b5b6b0]">
                A fonte deste recorte não informa combustível. A distribuição permanece
                indisponível.
              </p>
            )}
            {knownFuels.length > 0 && (
              <DataTable
                rows={knownFuels}
                title="Combustíveis informados"
                file="motor-atlas-combustiveis.csv"
              />
            )}
          </figure>
        )}
      </div>
    </section>
  );
}

export default MarketCharts;
