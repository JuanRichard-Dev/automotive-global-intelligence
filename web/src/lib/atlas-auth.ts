const endpoint = 'https://absaldhcdvsquvvfgtpi.supabase.co/auth/v1';
export const accessCookie = 'atlas_access_token';
export const refreshCookie = 'atlas_refresh_token';
export function authHeaders(): Record<string,string> {
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!key) throw new Error('SUPABASE_PUBLISHABLE_KEY não configurada');
  return { apikey: key, 'Content-Type': 'application/json' };
}
export async function supabaseAuth(path: string, init: RequestInit = {}) {
  return fetch(endpoint + path, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers as Record<string,string> || {}) },
    cache: 'no-store',
  });
}
export const cookieOptions = {
  httpOnly: true as const,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const,
  path: '/',
};
