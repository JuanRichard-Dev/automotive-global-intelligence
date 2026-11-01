import { NextRequest, NextResponse } from 'next/server';
import { accessCookie, refreshCookie, cookieOptions, supabaseAuth } from '@/lib/atlas-auth';
export async function POST(request: NextRequest) {
  const token = request.cookies.get(accessCookie)?.value;
  if (token) {
    try {
      await supabaseAuth('/logout', { method: 'POST', headers: { Authorization: 'Bearer ' + token } });
    } catch { /* local sign-out must still complete */ }
  }
  const response = NextResponse.redirect(new URL('/login', request.url), 303);
  response.cookies.set(accessCookie, '', { ...cookieOptions, maxAge: 0 });
  response.cookies.set(refreshCookie, '', { ...cookieOptions, maxAge: 0 });
  return response;
}
