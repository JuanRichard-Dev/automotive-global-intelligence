import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'Motor Atlas — Automotive Intelligence',
  description:
    'Explore os líderes automotivos por território, com fontes e cobertura transparentes.',
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
