import Atlas from '@/components/atlas';
import Link from 'next/link';
export const dynamic = 'force-dynamic';
export default async function Page() {
  let initial;
  try {
    const r = await fetch(`${process.env.API_INTERNAL_URL || 'http://127.0.0.1:8100'}/bootstrap`, {
      cache: 'no-store',
    });
    if (!r.ok) throw Error('API indisponível');
    initial = await r.json();
  } catch {
    initial = null;
  }
  if (!initial) {
    return (
      <main className="offline">
        <span className="eyebrow">MOTOR ATLAS</span>
        <h1>Preparando o observatório.</h1>
        <p>
          O banco e o ETL precisam estar disponíveis. Consulte o README e execute docker compose up
          --build.
        </p>
        <Link href="/">Tentar novamente</Link>
      </main>
    );
  }
  return <Atlas initial={initial} />;
}
