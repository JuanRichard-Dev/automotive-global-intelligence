import type { NextConfig } from 'next';
const api = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8100';
const config: NextConfig = {
  distDir:process.env.NEXT_DIST_DIR||'.next',
  output: 'standalone',
  poweredByHeader: false,
  images: { formats: ['image/avif', 'image/webp'], qualities: [75, 80] },
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${api}/:path*` },
      { source: '/openapi.json', destination: `${api}/openapi.json` },
      { source: '/media/:path*', destination: `${api}/media/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ];
  },
};
export default config;
