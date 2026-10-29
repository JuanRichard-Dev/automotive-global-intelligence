'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { GeoJSONSource, Map as LibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

/** Same filter names as FastAPI Filters. Null values are omitted from requests. */
export interface AtlasMapProps {
  filters: Record<string, string | number | null>;
  onCountry: (iso: string) => void;
  onState: (code: string) => void;
}

type AtlasGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] };
interface Territory {
  type: 'Feature';
  id?: string | number;
  geometry: AtlasGeometry | null;
  properties: {
    iso: string | null;
    estado?: string;
    nome: string;
    unidades: number | null;
    tem_dados: boolean;
  };
}
/** GET /api/mapa?nivel=pais|estado returns geometry and measures from PostgreSQL. */
interface MapResponse {
  type: 'FeatureCollection';
  features: Territory[];
  fonte?: string;
  nota?: string;
}
const EMPTY: MapResponse = { type: 'FeatureCollection', features: [] };
const units = new Intl.NumberFormat('pt-BR');

function queryFor(filters: AtlasMapProps['filters']) {
  const query = new URLSearchParams();
  Object.entries(filters)
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([key, value]) => {
      if (value !== null && value !== '') query.set(key, String(value));
    });
  return query.toString();
}

async function fetchMap(query: string, level: 'pais' | 'estado', signal: AbortSignal) {
  const params = new URLSearchParams(query);
  params.set('nivel', level);
  const response = await fetch(`/api/mapa?${params}`, { signal });
  if (!response.ok) throw new Error('Não foi possível carregar os territórios deste recorte.');
  const data: MapResponse = await response.json();
  if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
    throw new Error('O serviço de mapas retornou um formato inesperado.');
  }
  return data;
}

function boundsOf(features: Territory[]): [number, number, number, number] | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const feature of features) {
    const geometry = feature.geometry;
    if (!geometry) continue;
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
    for (const polygon of polygons) {
      for (const ring of polygon) {
        for (const [lng, lat] of ring) {
          if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
          west = Math.min(west, lng);
          east = Math.max(east, lng);
          south = Math.min(south, lat);
          north = Math.max(north, lat);
        }
      }
    }
  }
  return Number.isFinite(west) ? [west, south, east, north] : null;
}

export function AtlasMap({ filters, onCountry, onState }: AtlasMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LibreMap | null>(null);
  const handlers = useRef({ onCountry, onState });
  const [ready, setReady] = useState(false);
  const [webglError, setWebglError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [world, setWorld] = useState<MapResponse>(EMPTY);
  const [states, setStates] = useState<MapResponse>(EMPTY);
  const [showStates, setShowStates] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const query = useMemo(() => queryFor(filters), [filters]);
  const country = typeof filters.pais === 'string' ? filters.pais : '';
  const state = typeof filters.estado === 'string' ? filters.estado : '';
  const stateView = showStates && states.features.length > 0;
  const visible = stateView ? states : world;

  useEffect(() => {
    handlers.current = { onCountry, onState };
  }, [onCountry, onState]);

  useEffect(() => {
    setShowStates(true);
  }, [country]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    // Clear old values immediately: a new recorte must never show stale market figures.
    setWorld(EMPTY);
    setStates(EMPTY);
    Promise.all([
      fetchMap(query, 'pais', controller.signal),
      country ? fetchMap(query, 'estado', controller.signal) : Promise.resolve(EMPTY),
    ])
      .then(([countries, subdivisions]) => {
        setWorld(countries);
        setStates(subdivisions);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : 'Mapa indisponível.');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, country]);

  useEffect(() => {
    if (!container.current) return;
    let map: LibreMap;
    try {
      // Turbopack relocates import.meta.url; serve the official ESM worker unchanged.
      maplibregl.setWorkerUrl(`/maplibre-worker.js?v=${maplibregl.getVersion()}`);
      map = new maplibregl.Map({
        container: container.current,
        // Self-contained vector canvas: no external tiles, token, glyphs or tracking.
        style: {
          version: 8,
          sources: {},
          layers: [{ id: 'ocean', type: 'background', paint: { 'background-color': '#0c1011' } }],
        },
        center: [0, 20],
        zoom: 0.8,
        minZoom: 0.3,
        maxZoom: 9,
        renderWorldCopies: false,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
    } catch {
      setWebglError(true);
      return;
    }
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map
      .getCanvas()
      .setAttribute(
        'aria-label',
        'Mapa de territórios. Use os botões abaixo para selecionar pelo teclado.',
      );
    map.on('load', () => {
      for (const id of ['countries', 'states']) {
        map.addSource(id, { type: 'geojson', data: EMPTY });
        map.addLayer({
          id: `${id}-fill`,
          type: 'fill',
          source: id,
          paint: {
            'fill-color': ['case', ['boolean', ['get', 'tem_dados'], false], '#9b8462', '#242b2d'],
            'fill-opacity': id === 'countries' ? 0.7 : 0.9,
          },
        });
        map.addLayer({
          id: `${id}-line`,
          type: 'line',
          source: id,
          paint: { 'line-color': '#bcaa88', 'line-width': 0.55, 'line-opacity': 0.55 },
        });
        map.on('click', `${id}-fill`, (event) => {
          // A state also overlaps its country: select it once, without resetting it.
          if (
            id === 'countries' &&
            map.queryRenderedFeatures(event.point, { layers: ['states-fill'] }).length > 0
          )
            return;
          const properties = event.features?.[0]?.properties;
          if (!properties) return;
          if (id === 'states' && typeof properties.estado === 'string') {
            handlers.current.onState(properties.estado);
          } else if (typeof properties.iso === 'string' && /^[A-Z]{2}$/.test(properties.iso)) {
            setShowStates(true);
            handlers.current.onCountry(properties.iso);
          }
        });
        map.on('mousemove', `${id}-fill`, (event) => {
          const properties = event.features?.[0]?.properties;
          if (!properties) return;
          map.getCanvas().style.cursor = 'pointer';
          const value = properties.unidades;
          setHover(
            `${String(properties.nome)} · ${value === null || value === undefined ? 'Sem registros' : `${units.format(Number(value))} unidades`}`,
          );
        });
        map.on('mouseleave', `${id}-fill`, () => {
          map.getCanvas().style.cursor = '';
          setHover(null);
        });
      }
      // A separate outline makes the selected territory visible without inventing a measure.
      map.addSource('selection', { type: 'geojson', data: EMPTY });
      map.addLayer({
        id: 'selection-line',
        type: 'line',
        source: 'selection',
        paint: { 'line-color': '#ecd9b2', 'line-width': 2 },
      });
      setReady(true);
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (
      !ready ||
      !map ||
      !map.getSource('countries') ||
      !map.getSource('states') ||
      !map.getSource('selection')
    )
      return;
    (map.getSource('countries') as GeoJSONSource).setData(world);
    (map.getSource('states') as GeoJSONSource).setData(stateView ? states : EMPTY);
    const maximum = Math.max(
      0,
      ...visible.features.map((feature) => feature.properties.unidades ?? 0),
    );
    const layer = stateView ? 'states-fill' : 'countries-fill';
    if (maximum > 0) {
      map.setPaintProperty(layer, 'fill-color', [
        'case',
        ['boolean', ['get', 'tem_dados'], false],
        [
          'interpolate',
          ['linear'],
          ['sqrt', ['max', 0, ['coalesce', ['get', 'unidades'], 0]]],
          0,
          '#645a49',
          Math.sqrt(maximum),
          '#d1b98d',
        ],
        '#242b2d',
      ]);
    } else {
      map.setPaintProperty(layer, 'fill-color', [
        'case',
        ['boolean', ['get', 'tem_dados'], false],
        '#645a49',
        '#242b2d',
      ]);
    }
    const selected =
      stateView && state
        ? states.features.filter((feature) => feature.properties.estado === state)
        : world.features.filter((feature) => feature.properties.iso === country);
    (map.getSource('selection') as GeoJSONSource).setData({
      type: 'FeatureCollection',
      features: selected,
    });
    const bounds = boundsOf(
      stateView
        ? state && selected.length
          ? selected
          : states.features
        : showStates && country
          ? selected
          : [],
    );
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1100;
    if (bounds) map.fitBounds(bounds, { padding: 45, maxZoom: 6.5, duration });
    else if (!loading) map.flyTo({ center: [0, 20], zoom: 0.8, duration });
  }, [ready, world, states, stateView, showStates, visible, country, state, loading]);

  return (
    <section
      aria-label="Atlas de mercados"
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0c1011]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-[#b6a280]">Atlas de mercados</p>
          <p className="mt-1 text-sm text-white/65">
            {stateView
              ? 'Explore os estados do país selecionado'
              : 'Selecione um país para explorar'}
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={() => setShowStates(false)}
            aria-pressed={!stateView}
            className="rounded-full border border-white/20 px-3 py-2 text-[#e5d4b4] focus-visible:outline-2 focus-visible:outline-[#e5d4b4]"
          >
            Mundo
          </button>
          {states.features.length > 0 && (
            <button
              type="button"
              onClick={() => setShowStates(true)}
              aria-pressed={stateView}
              className="rounded-full border border-white/20 px-3 py-2 text-[#e5d4b4] focus-visible:outline-2 focus-visible:outline-[#e5d4b4]"
            >
              Estados · {country}
            </button>
          )}
        </div>
      </div>
      <div
        ref={container}
        className="h-[360px] w-full sm:h-[440px]"
        aria-hidden={webglError || undefined}
      />
      <div
        className="pointer-events-none absolute left-4 top-28 max-w-[75%] rounded-lg bg-[#0c1011]/90 px-3 py-2 text-xs text-[#e5d4b4]"
        aria-live="polite"
      >
        {loading
          ? 'Carregando geometrias e medidas…'
          : error ||
            (webglError
              ? 'Mapa visual indisponível. Use a lista de territórios abaixo.'
              : hover || 'Registros por território')}
      </div>
      <div className="border-t border-white/10 px-4 py-3 text-xs text-white/50">
        <p>{visible.fonte || 'Natural Earth · domínio público · geometrias servidas pelo banco'}</p>
        <p className="mt-1">{visible.nota || ''}</p>
        <details className="mt-3">
          <summary className="cursor-pointer text-[#d1b98d]">
            Territórios (
            {
              visible.features.filter(
                (feature) => feature.properties.estado || feature.properties.iso,
              ).length
            }
            )
          </summary>
          <ul className="mt-3 grid max-h-56 gap-1 overflow-auto sm:grid-cols-2">
            {visible.features.map((feature, index) => {
              const { properties: p } = feature;
              const code = stateView ? p.estado : p.iso;
              if (!code || (!stateView && !/^[A-Z]{2}$/.test(code))) return null;
              return (
                <li key={code || index}>
                  <button
                    type="button"
                    onClick={() => {
                      if (stateView) onState(code);
                      else {
                        setShowStates(true);
                        onCountry(code);
                      }
                    }}
                    aria-pressed={code === (stateView ? state : country)}
                    className="w-full rounded px-2 py-2 text-left text-white/80 hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-[#d1b98d]"
                  >
                    {p.nome} · {p.unidades === null ? 'Sem registros' : units.format(p.unidades)}
                  </button>
                </li>
              );
            })}
          </ul>
        </details>
      </div>
    </section>
  );
}

export default AtlasMap;
