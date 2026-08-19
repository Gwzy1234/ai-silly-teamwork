# Silly Teamwork Frontend

React + TypeScript + Vite frontend for Silly Teamwork.

## Development

```bash
npm install
npm run dev
```

The development server runs at `http://localhost:5173`. Requests beginning with
`/api` are proxied to the FastAPI backend at `http://localhost:8000`.

`VITE_API_BASE_URL` should be empty in local development. In production, set it
to the backend origin only, for example `https://api.example.com`; API paths
already include `/api/v1`.

## Checks

```bash
npm run lint
npm run typecheck
npm run build
```

## OpenAPI types

Start the FastAPI backend first, then run:

```bash
npm run api:generate
```

Generated types are written to `src/api/generated/schema.d.ts`.
