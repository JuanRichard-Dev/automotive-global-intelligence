'use client';

import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

export default function LazySection({ children, minHeight = 300, label = 'Carregando visualização...' }: {
  children: ReactNode;
  minHeight?: number;
  label?: string;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (mounted || !holder.current) return;
    if (!('IntersectionObserver' in window)) {
      setMounted(true);
      return;
    }
    const observer = new IntersectionObserver(
      entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          setMounted(true);
          observer.disconnect();
        }
      },
      { rootMargin: '550px 0px', threshold: 0.01 },
    );
    observer.observe(holder.current);
    return () => observer.disconnect();
  }, [mounted]);

  return (
    <div ref={holder} style={mounted ? undefined : { minHeight }}>
      {mounted ? children : (
        <div className="skeleton map-loading" role="status" aria-label={label}
          style={{ minHeight, display: 'grid', placeItems: 'center', color: '#a6a49e' }}>
          {label}
        </div>
      )}
    </div>
  );
}
