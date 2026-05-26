# @hangpost/shared-types

Type-safe TypeScript client generated from the FastAPI OpenAPI schema.

Populated in **Phase 1** (Auth + Profile): the web app stops hand-writing
fetch wrappers (`apps/web/src/lib/api.ts`) and imports a generated client
so the API contract is enforced at compile time across the monorepo.

Generation (Phase 1):

```
# from a running API or its exported openapi.json
npx openapi-typescript http://localhost:8000/openapi.json -o src/index.ts
```
