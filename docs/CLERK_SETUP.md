# Clerk setup — local dev (Codespaces)

This is the browser-only path (see `CLAUDE.md` §1). Everything below is
done in tabs you already have open: the Clerk dashboard, GitHub
Codespaces secrets, and the Codespace terminal.

---

## 1. Create a Clerk application

1. Sign in at <https://dashboard.clerk.com>.
2. Click **+ Create application**, name it `hangpost-dev`, select the
   sign-in methods you want (email + Google is a sensible minimum).
3. Click **Create**.

## 2. Grab the three values you need

From the new app's dashboard, **API Keys** in the sidebar:

| Value | Used by | Notes |
|---|---|---|
| Publishable key (`pk_test_...`) | Web — bundled into the browser | Safe to expose. Public by design. |
| Secret key (`sk_test_...`) | Web — server-side calls | Never expose. |
| JWKS URL (`https://<instance>.clerk.accounts.dev/.well-known/jwks.json`) | API — JWT signature verification | Public. Find it under **API Keys → Show JWT public key → Show JWKS URL** in the Clerk dashboard, or compute it as `<frontend-api>/.well-known/jwks.json`. |

## 3. Set them as Codespaces secrets

GitHub → **Settings → Codespaces → Repository secrets → New secret**
(scope: this repo). Add three:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` = the `pk_test_...` value
- `CLERK_SECRET_KEY` = the `sk_test_...` value
- `CLERK_JWKS_URL` = the JWKS URL

> Codespaces secrets are injected as env vars into the Codespace container
> at startup. They're picked up by `docker compose` via the `${VAR}`
> interpolation in `infra/compose/docker-compose.yml`.

## 4. Rebuild the web image and restart the stack

Inside the Codespace:

```bash
# Confirm the env vars made it into the Codespace.
printenv NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY | head -c 20 && echo "..."
printenv CLERK_JWKS_URL

# Rebuild web (NEXT_PUBLIC_* values are baked into the JS at build time)
# and restart api so it picks up CLERK_JWKS_URL.
docker compose -f infra/compose/docker-compose.yml up -d --build web api
```

If the Codespace was created **before** you added the secrets, restart
it once: GitHub → **Codespaces → ... → Restart**.

## 5. Verify

In the browser:

1. Open `http://localhost:3000` (Codespaces will forward the port).
2. Header should show **Sign in** / **Sign up** buttons.
3. Click **Sign up**, complete the flow.
4. The header now shows a Clerk **UserButton** avatar.

In the Codespace terminal — confirm the API accepts the JWT:

```bash
# Manually grab a session JWT from the browser dev console:
#   await window.Clerk.session.getToken()  →  copy the string
TOKEN="paste-the-jwt-here"
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/me | python3 -m json.tool
# Expected: { "id": "...", "email": "...", "auth_provider": "clerk", "auth_sub": "user_..." }
```

If `/me` returns 503 → the API didn't see `CLERK_JWKS_URL`. Restart
`api`. If it returns 401 → the JWKS URL is wrong; double-check it in
the Clerk dashboard.

## 6. What's not done yet (intentional)

- **No profile auto-creation on sign-up.** The first `/profiles` call
  after sign-up returns 404 — `POST /profiles` exists and works, but no
  UI calls it yet. That's the next slice of Phase 1.6.
- **`/recommendations` against a fresh Clerk user.** Returns 404
  ("Source profile not found.") until that user has a profile + a
  `user_locations` row. The seed-corpus demo path
  (`/demo?source_user_id=...`) stays the simplest way to see the engine
  end-to-end.
