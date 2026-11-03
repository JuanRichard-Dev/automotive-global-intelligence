'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useState } from 'react';
import type { ComponentProps } from 'react';
import type AtlasComponent from '@/components/atlas';

const Atlas = dynamic(() => import('@/components/atlas'), { ssr: false });
type Bootstrap = ComponentProps<typeof AtlasComponent>['initial'];

const CACHE_KEY = 'motor-atlas:bootstrap:v2';
const CACHE_TTL_MS = 2 * 60 * 1000;

function readCachedBootstrap(): Bootstrap | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const cache: { savedAt: number; value: Bootstrap } = JSON.parse(raw);
    if (Date.now() - cache.savedAt > CACHE_TTL_MS) return null;
    if (!cache.value?.config?.padrao || !Array.isArray(cache.value.paises) || !cache.value.painel) return null;
    return cache.value;
  } catch {
    return null;
  }
}

function saveBootstrap(value: Bootstrap) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), value }));
  } catch {
    // Storage can be unavailable in private browsing; the network path still works.
  }
}

function LoadingShell({ error, onRetry, slow }: {
  error: string | null; onRetry: () => void; slow: boolean;
}) {
  return (
    <div className="atlas-loading" role="status" aria-live="polite">
      <header className="atlas-loading-nav">
        <div className="atlas-loading-logo">M<span>∧</span></div>
        <div className="atlas-loading-brand">MOTOR ATLAS<small>AUTOMOTIVE INTELLIGENCE</small></div>
        <span className="atlas-loading-caption">MERCADOS AUTOMOTIVOS</span>
      </header>
      <main className="atlas-loading-content">
        <div className="atlas-loading-hero">
          <span className="eyebrow">REGISTROS · MODELOS · MERCADOS</span>
          <h1>O mercado,<br /><em>modelo a modelo.</em></h1>
          <p>Explore os líderes automotivos por país, ano e modelo.</p>
          <div className="atlas-loading-status">
            {error ? 'Não foi possível carregar os dados.' : slow
              ? 'A conexão com os dados está demorando. O painel continua disponível quando a API responder.'
              : 'Preparando os rankings e os dados do mercado...'}
          </div>
          {error ? <button type="button" className="atlas-loading-retry" onClick={onRetry}>Tentar novamente</button> : null}
          {error ? <p className="atlas-loading-error">{error}</p> : null}
        </div>
        <aside className="atlas-loading-preview" aria-hidden="true">
          <span className="eyebrow">EXPLORAR · BRASIL</span>
          <div className="atlas-loading-placeholder atlas-loading-wide" />
          <div className="atlas-loading-placeholder atlas-loading-medium" />
          <div className="atlas-loading-bars">
            <div /><div /><div /><div />
          </div>
          <span className="atlas-loading-footnote">Dados oficiais · Fontes verificadas</span>
        </aside>
      </main>
    </div>
  );
}

export default function AtlasLoader() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setError(null);
    setSlow(false);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const cached = readCachedBootstrap();
    if (cached) setData(cached);
    else setData(null);
    setError(null);
    setSlow(false);
    const slowTimer = window.setTimeout(() => { if (active && !cached) setSlow(true); }, 2000);
    const timeoutTimer = window.setTimeout(() => controller.abort('timeout'), 22000);

    fetch('/api/bootstrap', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('API indisponível (' + response.status + ').');
        return response.json() as Promise<Bootstrap>;
      })
      .then((value) => {
        if (!active || controller.signal.aborted) return;
        if (!value?.config?.padrao || !value.painel) throw new Error('Resposta incompleta da API.');
        saveBootstrap(value);
        setData(value);
        setError(null);
      })
      .catch((reason) => {
        if (!active) return;
        if (!cached) {
          setError(controller.signal.aborted
            ? 'A consulta ultrapassou 22 segundos. Verifique sua conexão ou tente novamente.'
            : reason instanceof Error ? reason.message : 'Falha ao carregar dados.');
        }
      })
      .finally(() => {
        window.clearTimeout(slowTimer);
        window.clearTimeout(timeoutTimer);
      });

    return () => {
      active = false;
      window.clearTimeout(slowTimer);
      window.clearTimeout(timeoutTimer);
      controller.abort('unmount');
    };
  }, [attempt]);

  if (data) return <Atlas initial={data} />;
  return <LoadingShell error={error} slow={slow} onRetry={retry} />;
}
