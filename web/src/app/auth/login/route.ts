import { NextRequest, NextResponse } from 'next/server';
import { accessCookie, refreshCookie, cookieOptions, supabaseAuth } from '@/lib/atlas-auth';
export async function POST(request: NextRequest) {
  let body: { email?: string; password?: string };
  try { body = await request.json(); } catch { return NextResponse.json({ error: 'Dados inválidos' }, { status: 400 }); }
  if (!body.email || !body.password || body.email.length > 320 || body.password.length > 1024) {
    return NextResponse.json({ error: 'Informe e-mail e senha' }, { status: 400 });
  }
  try {
    const auth = await supabaseAuth('/token?grant_type=password', {
      method: 'POST', body: JSON.stringify({ email: body.email, password: body.password }),
    });
    if (!auth.ok) return NextResponse.json({ error: 'E-mail ou senha inválidos' }, { status: 401 });
    const data = await auth.json();
    const response = NextResponse.json({ ok: true });
    response.cookies.set(accessCookie, data.access_token, { ...cookieOptions, maxAge: data.expires_in });
    response.cookies.set(refreshCookie, data.refresh_token, { ...cookieOptions, maxAge: 60 * 60 * 24 * 30 });
    return response;
  } catch { return NextResponse.json({ error: 'Serviço de autenticação indisponível' }, { status: 503 }); }
}
