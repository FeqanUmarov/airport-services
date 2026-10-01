# Airport GIS Frontend

Independent React/TypeScript frontend for the Airport GIS API.

The frontend communicates with the backend only through HTTP APIs and can be
moved to its own repository later without changing application code.

## Source structure

- `src/app` - application bootstrap, router and providers
- `src/api` - HTTP client, generated API types and endpoint modules
- `src/auth` - authentication state, permissions and protected routes
- `src/components` - shared UI components
- `src/features` - business modules
- `src/map` - OpenLayers map, layers, interactions and styles
- `src/hooks` - shared React hooks
- `src/layouts` - page layouts
- `src/pages` - top-level route pages
- `src/types` - shared TypeScript types
- `src/utils` - framework-independent helpers
- `src/assets` - frontend-owned static assets
- `public` - files served without bundling

## Run with Docker (recommended)

From the repository root:

```bash
docker compose up -d --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1
- Swagger: http://localhost:8000/docs

Nginx serves the SPA and proxies `/api/*` to the `api` Docker service. The
browser therefore uses the same origin and production does not depend on a
development CORS exception.

## Run in development mode

Keep the backend running, then:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to
`http://localhost:8000`, so application code uses `/api/v1` in both modes.

## Development order

1. Authentication, refresh flow, permissions and protected routes.
2. Shared API types generated from `/openapi.json` and query hooks.
3. Airport selector and airport overview.
4. OpenLayers map shell, layer registry and Table of Contents.
5. Runway, direction, strip, area and declared-distance editors.
6. Standards and OLS parameter screens.
7. Automatic/manual OLS workflows and geometry editing.
8. DTM metadata, sampling and map-service layers.
9. Obstacle CRUD, manual check and Shapefile import.
10. Violations, reports, exports and administration.

Each folder under `src/features` owns its pages, components, forms, API query
hooks and feature-specific types. Reusable GIS code stays under `src/map`, and
raw HTTP endpoint functions stay under `src/api`.
