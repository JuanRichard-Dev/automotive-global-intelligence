'use client';
import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { create } from 'zustand';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ArrowUpRight, ArrowDown, Globe2, ChevronLeft, ChevronRight, Menu, X } from 'lucide-react';
import { FilterSelect } from './select';
const AtlasMap = dynamic(() => import('./atlas-map'), {
  ssr: false,
  loading: () => <div className="skeleton map-loading" />,
});
const Chart = dynamic(() => import('./charts').then((m) => m.Chart), { ssr: false });
const MarketCharts = dynamic(() => import('./market-charts').then((m) => m.MarketCharts), {
  ssr: false,
});
const WordCloud = dynamic(() => import('./charts').then((m) => m.WordCloud), { ssr: false });
type Filters = {
  pais: string;
  estado: string | null;
  cidade: string | null;
  ano: number;
  origem: string;
  medida: string | null;
  periodicidade: string;
  mes: number | null;
  segmento: string | null;
  combustivel: string | null;
};
type Media = {
  url: string;
  titulo: string;
  lugar: string;
  credito: string;
  licenca: string;
  licenca_url: string;
  origem_url: string;
  largura: number;
  altura: number;
  blur_data_url: string;
  observacao: string;
};
type Rank = {
  modelo_id: number;
  marca: string;
  modelo: string;
  unidades: number;
  posicao: number;
  participacao_pct: number | null;
};
type Source = {
  id: string;
  organizacao: string;
  titulo: string;
  url: string;
  licenca: string;
  limitacoes: string;
  status: string;
};
type Panel = {
  filtros: Filters;
  pais: { nome: string; iso: string };
  estado: { nome: string } | null;
  cidade: { nome: string } | null;
  status: string;
  medida: { nome: string; definicao: string };
  ranking: {
    items: Rank[];
    unidades_observadas: number | null;
    mercado_elegivel: number | null;
    observacoes: number;
    cobertura_pct: number | null;
    metodo_participacao: string;
  };
  serie: {
    items: { ano: number; mes: number | null; unidades: number }[];
    previsao: { ano: number; unidades: number; mae_backtest: number | null } | null;
    nota: string;
  };
  estatisticas: {
    segmentos: { segmento: string; unidades: number }[];
    descritiva: {
      modelos: number;
      media: number;
      mediana: number;
      desvio_padrao: number;
      hhi: number;
    };
    correlacao_preco_unidades: number | null;
    nota: string;
  } | null;
  nuvem: { texto: string; valor: number }[];
  midia_pais: Media | null;
  midia_carro: Media | null;
  fontes: Source[];
  nota_ausencia: string | null;
};
type Initial = {
  config: {
    identidade: { nome: string; subtitulo: string; descricao: string };
    padrao: Filters;
    metodologia: { titulo: string; regras: string[] };
    origens: Record<string, unknown>;
  };
  paises: { iso: string; nome: string; tem_real: boolean }[];
  disponibilidade: {
    iso: string;
    origem: string;
    medida: string;
    periodicidade: string;
    anos: number[];
    meses: number[];
  }[];
  segmentos: { codigo: string; nome: string }[];
  combustiveis: { codigo: string; nome: string }[];
  execucao: { linhas_sinteticas: number; qualidade: { carregados_postgresql: number } };
  painel: Panel;
};
const useFilters = create<{ filters: Filters | null; set: (v: Filters) => void }>((set) => ({
  filters: null,
  set: (filters) => set({ filters }),
}));
const nf = new Intl.NumberFormat('pt-BR');
const num = (n: number | null | undefined) => (n == null ? '—' : nf.format(Math.round(n)));
const pct = (n: number | null) =>
  n == null ? '—' : n.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%';
async function get<T>(path: string, filters?: Filters): Promise<T> {
  const q = new URLSearchParams();
  if (filters)
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== null) q.set(k, String(v));
    });
  const r = await fetch('/api/' + path + (path.includes('?') ? '&' : '?') + q);
  if (!r.ok) throw Error(`Consulta indisponível (${r.status})`);
  return r.json();
}
function Credit({ media }: { media: Media | null }) {
  return media ? (
    <span className="credit">
      {media.lugar} ·{' '}
      <a href={media.origem_url} target="_blank" rel="noreferrer">
        {media.credito}
      </a>{' '}
      ·{' '}
      <a href={media.licenca_url} target="_blank" rel="noreferrer">
        {media.licenca}
      </a>
    </span>
  ) : null;
}
function Count({ value }: { value: number | null }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!ref.current) return;
    if (value === null) {
      ref.current.textContent = '—';
      return;
    }
    if (reduce) {
      ref.current.textContent = num(value);
      return;
    }
    let frame = 0;
    const t = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t) / 650);
      if (ref.current) ref.current.textContent = num(value * (1 - (1 - p) ** 3));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, reduce]);
  return <span ref={ref}>{num(value)}</span>;
}
export default function Atlas({ initial }: { initial: Initial }) {
  const [client] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={client}>
      <Dashboard initial={initial} />
    </QueryClientProvider>
  );
}
function Dashboard({ initial }: { initial: Initial }) {
  const state = useFilters();
  const f = state.filters || initial.config.padrao;
  const reduced = useReducedMotion();
  const [menu, setMenu] = useState(false);
  const gallery = useRef<HTMLDivElement>(null);
  const [galleryStep, setGalleryStep] = useState(0);
  const slide = (direction: number) => {
    const el = gallery.current;
    if (el) {
      el.scrollBy({
        left: direction * el.clientWidth * 0.85,
        behavior: reduced ? 'instant' : 'smooth',
      });
    }
  };
  const update = (patch: Partial<Filters>) => state.set({ ...f, ...patch });
  useEffect(() => {
    gallery.current?.scrollTo({ left: 0 });
    setGalleryStep(0);
  }, [f.pais, f.ano]);
  const selectCountry = (iso: string) => {
    const opt = initial.disponibilidade.find(
      (d) => d.iso === iso && d.origem === f.origem && d.periodicidade === 'anual',
    );
    update({
      pais: iso,
      ano: opt?.anos.includes(f.ano) ? f.ano : Math.max(...(opt?.anos || [f.ano])),
      estado: null,
      medida: opt?.medida || null,
      periodicidade: 'anual',
      mes: null,
      segmento: null,
      combustivel: null,
    });
  };
  const panel = useQuery({
    queryKey: ['panel', f],
    queryFn: () => get<Panel>('painel', f),
    initialData:
      JSON.stringify(f) === JSON.stringify(initial.config.padrao) ? initial.painel : undefined,
    staleTime: 60000,
  });
  const states = useQuery({
    queryKey: ['states', f.pais],
    queryFn: () => get<{ items: { codigo: string; nome: string }[] }>(`paises/${f.pais}/estados`),
    staleTime: Infinity,
  });
  const cities = useQuery({
    queryKey: ['cities', f.estado],
    queryFn: () => get<{ items: { codigo: string; nome: string }[] }>(`estados/${f.estado}/cidades`),
    enabled: Boolean(f.estado),
    staleTime: Infinity,
  });
  const comparison = useQuery({
    queryKey: ['compare', f],
    queryFn: () =>
      get<{
        items: {
          iso: string;
          nome: string;
          disponivel: boolean;
          nome_medida: string;
          unidades_observadas: number | null;
          lider: Rank | null;
        }[];
        nota: string;
      }>('comparador', f),
    staleTime: 60000,
  });
  const photos = useQuery({
    queryKey: ['photos'],
    queryFn: () => get<{ items: (Media & { modelo_id: number | null })[] }>('midia'),
    staleTime: Infinity,
  });
  const chartData = useQuery({
    queryKey: ['charts', f],
    queryFn: () =>
      get<{
        ranking: Rank[];
        fuels: { nome: string; unidades: number }[];
        segments: { segmento: string; unidades: number }[];
        annual: { ano: number; mes: number | null; unidades: number }[];
      }>('graficos', f),
    staleTime: 60000,
  });
  const indicators = useQuery({
    queryKey: ['indicators'],
    queryFn: () =>
      get<{ items: { iso: string; pais: string; ano: number; medida: string; nome_medida: string; unidades: number; observacao: string }[] }>('indicadores'),
    staleTime: Infinity,
  });
  const p = panel.data;
  const leader = p?.ranking.items[0];
  const photo = p?.midia_pais;
  const rank = p?.ranking.items || [];
  const yr = initial.disponibilidade
    .filter((d) => d.iso === f.pais && d.origem === f.origem && d.periodicidade === f.periodicidade)
    .flatMap((d) => d.anos);
  const years = [...new Set(yr)].sort((a, b) => b - a);
  useEffect(() => {
    if (reduced) return;
    let dispose = () => {};
    let gone = false;
    Promise.all([import('lenis'), import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([l, g, s]) => {
        if (gone) return;
        const lenis = new l.default({ autoRaf: true, anchors: true });
        g.gsap.registerPlugin(s.ScrollTrigger);
        const ctx = g.gsap.context(() => {
          g.gsap.utils.toArray<HTMLElement>('.section-heading').forEach((el) =>
            g.gsap.from(el, {
              y: 24,
              opacity: 0.35,
              duration: 0.7,
              scrollTrigger: { trigger: el, start: 'top 92%', once: true },
            }),
          );
        });
        dispose = () => {
          lenis.destroy();
          ctx.revert();
        };
      },
    );
    return () => {
      gone = true;
      dispose();
    };
  }, [reduced]);
  return (
    <>
      <a href="#explorar" className="skip">
        Pular para os dados
      </a>
      <header className="nav">
        <a href="#" className="brand">
          <span className="brand-mark">
            M<span>∧</span>
          </span>
          <span>
            MOTOR ATLAS<small>AUTOMOTIVE INTELLIGENCE</small>
          </span>
        </a>
        <nav className={menu ? 'open' : ''} aria-label="Navegação">
          <a href="#explorar" onClick={() => setMenu(false)}>
            Explorar
          </a>
          <a href="#ranking" onClick={() => setMenu(false)}>
            Rankings
          </a>
          <a href="#analise" onClick={() => setMenu(false)}>
            Análise
          </a>
        </nav>
        <span className="nav-tag">
          <i /> MERCADOS AUTOMOTIVOS
        </span>
        <button
          className="mobile-menu"
          aria-label={menu ? 'Fechar menu' : 'Abrir menu'}
          onClick={() => setMenu(!menu)}
        >
          {menu ? <X /> : <Menu />}
        </button>
      </header>
      <main>
        <section className="hero">
          <AnimatePresence mode="sync">
            {photo && (
              <motion.div
                key={photo.url}
                className="hero-image"
                initial={{ opacity: 0, scale: 1.03 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 1.1 }}
              >
                <Image
                  src={photo.url}
                  alt={photo.titulo || photo.lugar}
                  fill
                  priority
                  sizes="100vw"
                  quality={80}
                  placeholder={photo.blur_data_url ? 'blur' : 'empty'}
                  blurDataURL={photo.blur_data_url}
                />
              </motion.div>
            )}
          </AnimatePresence>
          <div className="hero-shade" />
          <div className="hero-content">
            <div className="eyebrow">
              <span className="line" /> REGISTROS · MODELOS · MERCADOS
            </div>
            <h1>
              O mercado,
              <br />
              <em>modelo a modelo.</em>
            </h1>
            <p className="hero-desc">
              Emplacamentos e registros por país, ano e modelo.
              <br />
              Consulte os líderes e acompanhe sua evolução.
            </p>
            <a className="primary" href="#explorar">
              Ver rankings <ArrowUpRight size={18} />
            </a>
            <div className="hero-location">
              <Globe2 size={15} />
              <span>
                {p?.pais.nome || f.pais}
                {p?.estado ? ' / ' + p.estado.nome : ''}
              </span>
            </div>
          </div>
          <div className="hero-feature">
            <span className="eyebrow">MAIS REGISTRADO · {f.ano}</span>
            <h2>{leader ? `${leader.marca} ${leader.modelo}` : 'Sem registro neste período'}</h2>
            {p?.midia_carro && (
              <div className="car-photo">
                <Image
                  src={p.midia_carro.url}
                  alt={p.midia_carro.titulo}
                  fill
                  sizes="(max-width: 800px) 90vw, 360px"
                  quality={80}
                />
              </div>
            )}
            <div className="leader-figures">
              <div>
                <strong>
                  <Count value={leader?.unidades ?? null} />
                </strong>
                <span>{p?.medida.nome || 'Unidades observadas'}</span>
              </div>
              <div>
                <strong>{pct(leader?.participacao_pct ?? null)}</strong>
                <span>de participação</span>
              </div>
            </div>
            <Credit media={p?.midia_carro || null} />
          </div>
          <div className="hero-bottom">
            <span>
              <ArrowDown size={14} /> DESLIZE PARA DESCOBRIR
            </span>
            <Credit media={photo || null} />
          </div>
        </section>
        <section id="explorar" className="explore section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">01 / MERCADOS</span>
              <h2>
                Escolha
                <br />
                <em>seu mercado.</em>
              </h2>
            </div>
            <p>
              País, período e combustível.
              <br />
            </p>
          </div>
          <div className="filters">
            <FilterSelect
              label="País"
              value={f.pais}
              onChange={selectCountry}
              items={initial.paises
                .filter((x) => x.tem_real)
                .map((x) => ({ value: x.iso, label: x.nome }))}
            />
            {!!states.data?.items.length && (
              <FilterSelect
                label="Estado / UF"
                value={f.estado || 'todos'}
                onChange={(v) => update({ estado: v === 'todos' ? null : v, cidade: null })}
                items={[
                  { value: 'todos', label: 'Visão nacional' },
                  ...(states.data?.items || []).map((x) => ({ value: x.codigo, label: x.nome })),
                ]}
              />
            )}
            {!!cities.data?.items.length && (
              <FilterSelect
                label="Cidade"
                value={f.cidade || 'todas'}
                onChange={(v) => update({ cidade: v === 'todas' ? null : v })}
                items={[
                  { value: 'todas', label: 'Todas as cidades' },
                  ...cities.data.items.map((x) => ({ value: x.codigo, label: x.nome })),
                ]}
              />
            )}
            <FilterSelect
              label="Ano"
              value={String(f.ano)}
              onChange={(v) => update({ ano: Number(v) })}
              items={(years.length ? years : [f.ano]).map((y) => ({
                value: String(y),
                label: String(y),
              }))}
            />
            <FilterSelect
              label="Combustível"
              value={f.combustivel || 'todos'}
              onChange={(v) => update({ combustivel: v === 'todos' ? null : v })}
              items={[
                { value: 'todos', label: 'Todos' },
                ...initial.combustiveis.map((x) => ({ value: x.codigo, label: x.nome })),
              ]}
            />
          </div>
          <div aria-live="polite">
            {panel.isPending ? (
              <div className="loading-line" aria-label="Carregando" />
            ) : panel.isError ? (
              <div role="alert" className="inline-error">
                {panel.error.message}{' '}
                <button onClick={() => panel.refetch()}>Tentar novamente</button>
              </div>
            ) : null}
          </div>
          <div className="overview">
            <div className="map-panel">
              <div className="panel-label">
                <Globe2 size={16} /> GEOGRAFIA DO MERCADO{' '}
                <span>{f.estado ? 'ESCALA ESTADUAL' : 'ESCALA GLOBAL'}</span>
              </div>
              <AtlasMap
                filters={f}
                onCountry={selectCountry}
                onState={(v) => update({ estado: v })}
              />
            </div>
            <aside className="market-summary">
              <span className="eyebrow">MERCADO EM FOCO</span>
              <h3>{p?.cidade?.nome || p?.estado?.nome || p?.pais.nome || f.pais}</h3>
              <span className="subtle">
                {f.ano} · {p?.medida.nome}
              </span>
              <div className="big-stat">
                <Count value={p?.ranking.unidades_observadas ?? null} />
                <span>unidades registradas</span>
              </div>
              <dl>
                <div>
                  <dt>Modelos</dt>
                  <dd>
                    {num(
                      p?.ranking.items.length
                        ? p.ranking.items[0] && p.estatisticas?.descritiva.modelos
                        : undefined,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Total do mercado</dt>
                  <dd>{num(p?.ranking.mercado_elegivel)}</dd>
                </div>
                <div>
                  <dt>Cobertura da base</dt>
                  <dd>{pct(p?.ranking.cobertura_pct ?? null)}</dd>
                </div>
              </dl>
            </aside>
          </div>
        </section>
        <section id="ranking" className="section ranking-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">02 / RANKING</span>
              <h2>
                Os mais
                <br />
                <em>registrados.</em>
              </h2>
            </div>
            <p>
              Marca, modelo e volume no período.
              <br />
            </p>
          </div>
          <div className="gallery-toolbar">
            <span>MODELOS EM DESTAQUE</span>
            <div>
              <button
                aria-label="Modelos anteriores"
                onClick={() => slide(-1)}
                disabled={galleryStep === 0}
              >
                <ChevronLeft size={20} />
              </button>
              <button
                aria-label="Próximos modelos"
                onClick={() => slide(1)}
                disabled={galleryStep === 2}
              >
                <ChevronRight size={20} />
              </button>
            </div>
          </div>
          <div
            className="model-gallery"
            ref={gallery}
            onScroll={() => {
              const el = gallery.current;
              if (el)
                setGalleryStep(
                  el.scrollLeft < 10
                    ? 0
                    : el.scrollLeft + el.clientWidth >= el.scrollWidth - 10
                      ? 2
                      : 1,
                );
            }}
            tabIndex={0}
            aria-label="Galeria de modelos"
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight') {
                e.preventDefault();
                slide(1);
              }
              if (e.key === 'ArrowLeft') {
                e.preventDefault();
                slide(-1);
              }
            }}
          >
            {rank.map((r) => {
              const image = photos.data?.items.find((m) => m.modelo_id === r.modelo_id);
              return (
                <article key={r.modelo_id}>
                  <div className="model-visual">
                    {image ? (
                      <Image
                        src={image.url}
                        alt={image.titulo}
                        fill
                        sizes="(max-width:760px) 85vw, 23vw"
                      />
                    ) : (
                      <span className="model-monogram">{r.marca}</span>
                    )}
                    <span className="model-position">{String(r.posicao).padStart(2, '0')}</span>
                  </div>
                  <div className="model-caption">
                    <small>{r.marca}</small>
                    <h3>{r.modelo}</h3>
                    <strong>
                      {num(r.unidades)} <span>unidades</span>
                    </strong>
                    <Credit media={image || null} />
                  </div>
                </article>
              );
            })}
          </div>
          <div className="ranking-grid">
            <div className="ranking-table">
              <div className="panel-label">
                {f.cidade ? 'RANKING MUNICIPAL' : f.estado ? 'RANKING ESTADUAL' : 'RANKING NACIONAL'}
                <span>
                  {p?.pais.nome} / {f.ano}
                </span>
              </div>
              <table>
                <caption className="sr-only">Modelos líderes no recorte selecionado</caption>
                <thead>
                  <tr>
                    <th>Pos.</th>
                    <th>Marca / modelo</th>
                    <th>Unidades</th>
                    <th>Part.</th>
                  </tr>
                </thead>
                <tbody>
                  {rank.map((r) => (
                    <tr key={r.modelo_id}>
                      <td className={r.posicao === 1 ? 'gold' : ''}>
                        {String(r.posicao).padStart(2, '0')}
                      </td>
                      <td>
                        <strong>{r.modelo}</strong>
                        <small>{r.marca}</small>
                        <span
                          className="rank-bar"
                          style={{ width: `${(r.unidades / (rank[0]?.unidades || 1)) * 88}%` }}
                        />
                      </td>
                      <td>{num(r.unidades)}</td>
                      <td>{pct(r.participacao_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rank.length && <p className="empty">Sem registros neste período.</p>}
              <p className="source-line">
                Fonte:{' '}
                {p?.fontes
                  .map((s) => s.organizacao)
                  .filter((s, i, a) => a.indexOf(s) === i)
                  .join(' · ') || 'Sem fonte disponível'}
              </p>
            </div>
            <div className="chart-panel">
              <div className="panel-label">DISTRIBUIÇÃO DOS LÍDERES</div>
              <Chart kind="ranking" items={rank} />
            </div>
          </div>
        </section>
        <section id="analise" className="section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">03 / HISTÓRICO</span>
              <h2>
                Mercados em
                <br />
                <em>perspectiva.</em>
              </h2>
            </div>
            <p>
              Consulte os resultados de cada país
              <br />e a evolução anual dos registros.
            </p>
          </div>
          <div className="compare-grid">
            {comparison.data?.items.map((c) => (
              <article className="compare-card" key={c.iso}>
                <span className="eyebrow">
                  {c.iso} / {f.ano}
                </span>
                <h3>{c.nome}</h3>
                <small className="market-metric">{c.nome_medida}</small>
                <strong>{num(c.unidades_observadas)}</strong>
                <p>
                  {c.lider
                    ? `${c.lider.marca} ${c.lider.modelo}`
                    : 'Não publicado para este período'}
                </p>
                <button className="text-link" onClick={() => selectCountry(c.iso)}>
                  Explorar mercado <ArrowUpRight size={14} />
                </button>
              </article>
            ))}
          </div>

          <div className="history-panel">
            <article className="chart-panel">
              <div className="panel-label">
                REGISTROS POR ANO <span>ANUAL</span>
              </div>
              <Chart kind="timeline" items={p?.serie.items || []} />
            </article>
          </div>
          <div className="analysis-chart-grid">
            <article className="chart-panel">
              <div className="panel-label">
                VOLUME POR SEGMENTO <span>BARRAS</span>
              </div>
              <Chart kind="segments-bar" items={p?.estatisticas?.segmentos || []} />
            </article>
          </div>
          {chartData.data && (
            <MarketCharts
              ranking={chartData.data.ranking}
              fuels={chartData.data.fuels}
              segments={chartData.data.segments}
              annual={chartData.data.annual}
            />
          )}
          {!!indicators.data?.items.length && (
            <div className="stat-strip indicator-strip">
              {indicators.data.items.map((item) => (
                <div key={`${item.iso}-${item.medida}-${item.ano}`}>
                  <span>{item.pais} · {item.nome_medida} · {item.ano}</span>
                  <strong>{num(item.unidades)}</strong>
                  <small>{item.observacao}</small>
                </div>
              ))}
            </div>
          )}
          <div className="cloud-panel">
            <div>
              <span className="eyebrow">MARCAS E MODELOS</span>
              <h3>
                Presença
                <br />
                <em>no mercado.</em>
              </h3>
              <p>
                Tamanho proporcional ao volume. Selecione um modelo para consultar seu resultado.
              </p>
            </div>
            <WordCloud items={p?.nuvem || []} />
          </div>
          <div className="stat-strip">
            <div>
              <span>Mediana por modelo</span>
              <strong>{num(p?.estatisticas?.descritiva.mediana)}</strong>
            </div>
            <div>
              <span>Desvio padrão</span>
              <strong>{num(p?.estatisticas?.descritiva.desvio_padrao)}</strong>
            </div>
            <div>
              <span>Concentração (HHI)</span>
              <strong>{num(p?.estatisticas?.descritiva.hhi)}</strong>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
