# Motor Atlas — Supabase Auth

Supabase project: `absaldhcdvsquvvfgtpi`.

## Configure

Set `SUPABASE_PUBLISHABLE_KEY` in the Next.js **server runtime** (the `web` deployment), using the publishable key in Supabase Dashboard → Project Settings → API Keys. **Never** put service role keys in frontend code.

Create users in Supabase Dashboard → Authentication → Users. The app intentionally has no public signup form.

Deploy the branch after review, and ensure `SUPABASE_PUBLISHABLE_KEY` is set in production. Without it, login fails closed.

## Routes

- `/login`: public login screen.
- `POST /auth/login`: validates e-mail/password against Supabase and creates HttpOnly cookies.
- `POST /auth/logout`: revokes Supabase session when possible and clears cookies.
- `/`: requires a valid Supabase session.
- `/api/*`: access through the Next.js rewrite requires a valid session.

**Important:** The separately deployed FastAPI backend itself is NOT authenticated by this Next.js proxy. Direct access to FastAPI bypasses frontend protection. Restrict external network exposure of FastAPI or implement JWT verification on all sensitive FastAPI endpoints before treating the API/data as private. Currently the Next.js proxy protects only requests arriving through the Next.js deployment.

No registration UI or automated initial admin creation was added. Configure allowed users separately.

Security tests to perform on a deployment: anonymous request to `/` redirects to login; anonymous request to `/api/bootstrap` returns 401; valid login grants access; expired access token with valid refresh token rotates; logout revokes session and restores protection. Rate-limit auth requests at your edge/load balancer as appropriate.
