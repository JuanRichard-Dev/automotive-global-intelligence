'use client';

import { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';

/** API ranking, series-temporais and estatisticas.segmentos share unidades. */
export interface ChartItem {
  unidades: number | string | null;
  modelo?: string;
  marca?: string;
  ano?: number | string;
  mes?: number | null;
  segmento?: string;
}
export interface ChartProps {
  kind: 'ranking' | 'timeline' | 'segments';
  items: readonly ChartItem[];
}
export interface WordCloudItem {
  texto: string;
  valor: number;
}
export interface WordCloudProps {
  items: readonly WordCloudItem[];
}
interface CloudWord extends WordCloudItem {
  text: string;
  size: number;
  x?: number;
  y?: number;
  rotate?: number;
}
interface CloudLayout {
  size: (value: [number, number]) => CloudLayout;
  words: (value: CloudWord[]) => CloudLayout;
  padding: (value: number) => CloudLayout;
  rotate: (value: number) => CloudLayout;
  font: (value: string) => CloudLayout;
  fontSize: (value: (word: CloudWord) => number) => CloudLayout;
  random: (value: () => number) => CloudLayout;
  on: (event: 'end', callback: (words: CloudWord[]) => void) => CloudLayout;
  start: () => CloudLayout;
  stop: () => CloudLayout;
}
const number = new Intl.NumberFormat('pt-BR');
const palette = ['#d1b98d', '#a18b68', '#7b8c8e', '#5e7375', '#7b6d62', '#96968a'];
function labelOf(item: ChartItem, kind: ChartProps['kind']) {
  if (kind === 'ranking') return [item.marca, item.modelo].filter(Boolean).join(' ');
  if (kind === 'segments') return item.segmento || 'Sem segmento informado';
  return item.mes ? `${String(item.mes).padStart(2, '0')}/${item.ano}` : String(item.ano ?? '');
}

/** Responsive SVG ECharts; source rows are also exposed as an accessible table. */
export function Chart({ kind, items }: ChartProps) {
  const host = useRef<HTMLDivElement>(null);
  const title =
    kind === 'ranking'
      ? 'Ranking por unidades'
      : kind === 'timeline'
        ? 'Evolução das unidades'
        : 'Unidades por segmento';
  const rows = items.filter(
    (item) => item.unidades !== null && Number.isFinite(Number(item.unidades)),
  );
  const signature = JSON.stringify(rows);

  useEffect(() => {
    if (!host.current || !rows.length) return;
    const data: ChartItem[] = JSON.parse(signature);
    const chart = echarts.init(host.current, undefined, { renderer: 'svg' });
    const values = data.map((item) => Number(item.unidades));
    const labels = data.map((item) => labelOf(item, kind));
    const animate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const options: echarts.EChartsOption = {
      color: palette,
      animation: animate,
      animationDuration: 650,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Arial, sans-serif', color: '#aaa89f' },
      aria: { enabled: true, decal: { show: false } },
      tooltip: {
        trigger: kind === 'segments' ? 'item' : 'axis',
        renderMode: 'richText',
        backgroundColor: '#141a1c',
        borderColor: '#544b3d',
        textStyle: { color: '#f0e8d9' },
        valueFormatter: (value) =>
          typeof value === 'number'
            ? `${number.format(value)} unidades`
            : String(value ?? 'Sem dado'),
      },
      grid: { left: 12, right: 34, top: 20, bottom: 22, containLabel: true },
    };
    if (kind === 'segments') {
      options.legend = { bottom: 0, textStyle: { color: '#aaa89f' }, type: 'scroll' };
      options.series = [
        {
          type: 'pie',
          radius: ['46%', '72%'],
          center: ['50%', '43%'],
          itemStyle: { borderColor: '#101516', borderWidth: 3, borderRadius: 5 },
          label: { show: false },
          emphasis: { label: { show: true, color: '#eee4d2', formatter: '{b}\n{d}%' } },
          data: labels.map((name, index) => ({ name, value: values[index] })),
        },
      ];
    } else if (kind === 'ranking') {
      options.xAxis = {
        type: 'value',
        splitLine: { lineStyle: { color: '#ffffff0a' } },
        axisLabel: { color: '#93958f', formatter: (value: number) => number.format(value) },
      };
      options.yAxis = {
        type: 'category',
        inverse: true,
        data: labels,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#cbc6ba', width: 140, overflow: 'truncate' },
      };
      options.series = [
        {
          type: 'bar',
          data: values,
          barMaxWidth: 19,
          itemStyle: { color: '#bca378', borderRadius: [0, 4, 4, 0] },
          emphasis: { itemStyle: { color: '#e2cda7' } },
        },
      ];
    } else {
      // Insert nulls between missing annual observations; do not interpolate them as zero.
      const annual = data.every((item) => !item.mes && Number.isFinite(Number(item.ano)));
      const sorted = [...data].sort(
        (a, b) => Number(a.ano) - Number(b.ano) || (a.mes ?? 0) - (b.mes ?? 0),
      );
      const timeline: { label: string; value: number | null }[] = [];
      sorted.forEach((item, index) => {
        if (annual && index > 0) {
          const previous = Number(sorted[index - 1].ano);
          for (let year = previous + 1; year < Number(item.ano); year++)
            timeline.push({ label: String(year), value: null });
        }
        timeline.push({ label: labelOf(item, kind), value: Number(item.unidades) });
      });
      options.xAxis = {
        type: 'category',
        boundaryGap: false,
        data: timeline.map((item) => item.label),
        axisLine: { lineStyle: { color: '#ffffff18' } },
        axisLabel: { color: '#93958f' },
      };
      options.yAxis = {
        type: 'value',
        splitLine: { lineStyle: { color: '#ffffff0a' } },
        axisLabel: { color: '#93958f', formatter: (value: number) => number.format(value) },
      };
      options.series = [
        {
          type: 'line',
          data: timeline.map((item) => item.value),
          connectNulls: false,
          smooth: false,
          symbolSize: 7,
          lineStyle: { width: 3 },
          itemStyle: { color: '#d1b98d' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#bca37830' },
              { offset: 1, color: '#bca37800' },
            ]),
          },
        },
      ];
    }
    chart.setOption(options);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
    // The serialized rows are the stable dependency; arrays from query renders may be recreated.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, signature]);

  if (!rows.length)
    return (
      <p
        role="status"
        className="flex min-h-48 items-center justify-center p-6 text-sm text-white/50"
      >
        Sem observações compatíveis para este gráfico.
      </p>
    );
  return (
    <figure aria-label={title} className="w-full">
      <div ref={host} className="h-[300px] w-full" aria-hidden="true" />
      <details className="px-2 text-xs text-white/55">
        <summary className="cursor-pointer text-[#bca378]">
          Ver dados de {title.toLocaleLowerCase('pt-BR')}
        </summary>
        <div className="max-h-56 overflow-auto">
          <table className="mt-3 w-full text-left">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr>
                <th scope="col" className="py-2">
                  Recorte
                </th>
                <th scope="col" className="text-right">
                  Unidades
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item, index) => (
                <tr key={index} className="border-t border-white/5">
                  <th scope="row" className="py-2 font-normal">
                    {labelOf(item, kind)}
                  </th>
                  <td className="text-right tabular-nums">
                    {number.format(Number(item.unidades))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

/** d3-cloud positions API words in an SVG; click or Enter reveals the exact count. */
export function WordCloud({ items }: WordCloudProps) {
  const [words, setWords] = useState<CloudWord[]>([]);
  const [selected, setSelected] = useState<WordCloudItem | null>(null);
  const [failed, setFailed] = useState(false);
  const signature = JSON.stringify(
    items.filter((item) => item.texto && Number.isFinite(item.valor) && item.valor > 0),
  );
  useEffect(() => {
    let disposed = false;
    let layout: CloudLayout | undefined;
    setWords([]);
    setSelected(null);
    setFailed(false);
    const data: WordCloudItem[] = JSON.parse(signature);
    if (!data.length) return;
    const maximum = Math.max(...data.map((item) => item.valor));
    // This dependency has no bundled TypeScript definitions. The bounded adapter above
    // documents exactly the d3-cloud methods and word fields used by this component.
    // @ts-expect-error d3-cloud 1.2.9 does not publish a declaration file.
    import('d3-cloud')
      .then((module: unknown) => {
        if (disposed) return;
        const create = (module as { default: () => CloudLayout }).default;
        let seed = 71;
        layout = create()
          .size([760, 290])
          .words(
            data.map((item) => ({
              ...item,
              text: item.texto,
              size: 13 + 41 * Math.sqrt(item.valor / maximum),
            })),
          )
          .padding(5)
          .rotate(0)
          .font('Arial')
          .fontSize((word) => word.size)
          .random(() => {
            seed = (seed * 16807) % 2147483647;
            return (seed - 1) / 2147483646;
          })
          .on('end', (positioned) => {
            if (!disposed) setWords(positioned);
          });
        layout.start();
      })
      .catch(() => {
        if (!disposed) setFailed(true);
      });
    return () => {
      disposed = true;
      layout?.stop();
    };
  }, [signature]);

  const accessible: WordCloudItem[] = JSON.parse(signature);
  if (!accessible.length)
    return (
      <p role="status" className="p-8 text-center text-sm text-white/50">
        Sem palavras para o recorte selecionado.
      </p>
    );
  return (
    <figure aria-label="Modelos ponderados pelas unidades no recorte" className="w-full">
      {!failed && (
        <svg
          viewBox="0 0 760 290"
          className="h-auto min-h-44 w-full"
          role="group"
          aria-label="Nuvem de modelos. Selecione uma palavra para consultar as unidades."
        >
          <g transform="translate(380,145)">
            {words.map((word, index) => (
              <text
                key={`${word.texto}-${index}`}
                transform={`translate(${word.x ?? 0},${word.y ?? 0}) rotate(${word.rotate ?? 0})`}
                textAnchor="middle"
                fontFamily="Arial, sans-serif"
                fontSize={word.size}
                fill={palette[index % palette.length]}
                tabIndex={0}
                role="button"
                aria-label={`${word.texto}: ${number.format(word.valor)} unidades`}
                aria-pressed={selected?.texto === word.texto}
                onClick={() => setSelected(word)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelected(word);
                  }
                }}
                className="cursor-pointer outline-none hover:fill-white focus:fill-white"
              >
                <title>
                  {word.texto} · {number.format(word.valor)} unidades
                </title>
                {word.texto}
              </text>
            ))}
          </g>
        </svg>
      )}
      <figcaption className="min-h-8 px-3 text-center text-xs text-white/60" aria-live="polite">
        {selected
          ? `${selected.texto} · ${number.format(selected.valor)} unidades`
          : failed
            ? 'Visualização indisponível. Consulte as palavras na lista abaixo.'
            : 'Tamanho proporcional à raiz quadrada das unidades · selecione um modelo'}
      </figcaption>
      <details className="px-3 text-xs text-white/55">
        <summary className="cursor-pointer text-[#bca378]">Ver todas as palavras e valores</summary>
        <ul className="mt-3 grid max-h-52 grid-cols-2 gap-2 overflow-auto">
          {accessible.map((item, index) => (
            <li key={`${item.texto}-${index}`}>
              <button
                type="button"
                onClick={() => setSelected(item)}
                className="rounded p-1 text-left hover:text-white focus-visible:outline-2 focus-visible:outline-[#bca378]"
              >
                {item.texto} · {number.format(item.valor)}
              </button>
            </li>
          ))}
        </ul>
      </details>
    </figure>
  );
}
