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

## 6. The real-user flow (after sign-up)

Sign-up now redirects to **`/profile/new`** (`forceRedirectUrl`). Fill the
form, tap **"Use my current location"** (browser geolocation → `POST
/user-locations`), then submit — the page creates your profile and sends
you to `/demo`, where you're ranked against the seed corpus and your
clicks (`viewed` / `profile_opened` / `friend_request_sent`) are logged
as outcomes.

Two things to know:

- **The seed corpus lives in Washington DC.** Codespaces runs in the
  cloud, so your browser's geolocation is wherever *you* are — likely not
  DC. If `/demo` shows "No candidates within 5000 m", widen the radius:
  visit `/demo?radius_m=50000`. (The pipeline is working; it's a geography
  mismatch, not a bug.)
- The old `/demo?source_user_id=...` seed path is **gone** —
  `/recommendations` is Clerk-JWT-only now. A signed-in user with no
  profile or no location gets an onboarding CTA back to `/profile/new`
  instead of an error.

To see the ML-loop measurement after clicking around, run the offline
eval in the Codespace terminal:

```bash
docker compose -f infra/compose/docker-compose.yml exec api \
  python -m scripts.evaluate --days 7   # writes docs/eval/<date>-eval.md
```
