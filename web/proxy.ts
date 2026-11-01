import { NextRequest, NextResponse } from 'next/server';
import { accessCookie, refreshCookie, cookieOptions, supabaseAuth } from './src/lib/atlas-auth';

export async function proxy(request: NextRequest) {
  const token = request.cookies.get(accessCookie)?.value;
  const refresh = request.cookies.get(refreshCookie)?.value;
  let valid = false;
  if (token) {
    try {
      const response = await supabaseAuth('/user', { headers: { Authorization: 'Bearer ' + token } });
      valid = response.ok;
    } catch { /* fail closed */ }
  }
  if (valid) return NextResponse.next();
  if (refresh) {
    try {
      const response = await supabaseAuth('/token?grant_type=refresh_token', {
        method: 'POST', body: JSON.stringify({ refresh_token: refresh }),
      });
      if (response.ok) {
        const data = await response.json();
        const headers = new Headers(request.headers);
        const accessValue = data.access_token;
        // Ensure the downstream Server Component also receives the rotated token.
        const nextCookies = request.cookies;
        nextCookies.set(accessCookie, accessValue);
        nextCookies.set(refreshCookie, data.refresh_token);
        headers.set('cookie', nextCookies.toString());
        const next = NextResponse.next({ request: { headers } });
        next.cookies.set(accessCookie, accessValue, { ...cookieOptions, maxAge: data.expires_in });
        next.cookies.set(refreshCookie, data.refresh_token, { ...cookieOptions, maxAge: 60 * 60 * 24 * 30 });
        return next;
      }
    } catch { /* fail closed */ }
  }
  if (request.nextUrl.pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'Não autorizado' }, { status: 401 });
  }
  const response = NextResponse.redirect(new URL('/login', request.url));
  response.cookies.set(accessCookie, '', { ...cookieOptions, maxAge: 0 });
  response.cookies.set(refreshCookie, '', { ...cookieOptions, maxAge: 0 });
  return response;
}
export const config = { matcher: ['/', '/api/:path*'] };
