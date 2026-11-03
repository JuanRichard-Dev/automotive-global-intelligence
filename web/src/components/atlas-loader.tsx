'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useState } from 'react';
import type { ComponentProps } from 'react';
import type AtlasComponent from '@/components/atlas';

const Atlas = dynamic(() => import('@/components/atlas'), {
  ssr: false,
  loading: () => (
    <main className="offline" role="status">
      <span className="eyebrow">MOTOR ATLAS</span>
      <h1>Preparando o observatório...</h1>
      <p>Carregando mapas e gráficos.</p>
    </main>
  ),
});

type Bootstrap = ComponentProps<typeof AtlasComponent>['initial'];

export default function AtlasLoader() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    setData(null);
    setError(null);

    fetch('/api/bootstrap', { signal: controller.signal, cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('Não foi possível acessar o banco de dados.');
        return response.json() as Promise<Bootstrap>;
      })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError('O serviço de dados está demorando para responder.');
        } else if (!controller.signal.reason || controller.signal.reason !== 'unmount') {
          setError('Tempo de conexão excedido. Tente novamente.');
        }
      })
      .finally(() => clearTimeout(timer));

    return () => {
      clearTimeout(timer);
      controller.abort('unmount');
    };
  }, [attempt]);

  if (data) return <Atlas initial={data} />;

  return (
    <main className="offline" role="status" aria-live="polite">
      <span className="eyebrow">MOTOR ATLAS</span>
      <h1>{error ? 'Não foi possível carregar os dados.' : 'Preparando o observatório...'}</h1>
      <p>{error || 'Conectando ao banco de dados e preparando os rankings.'}</p>
      {error ? <button type="button" onClick={retry}>Tentar novamente</button> : null}
    </main>
  );
}
