Placeholder build output so `go:embed web/dist/**` succeeds.

**Full UI:** from repo root:

```bash
cd frontend && npm ci && npm run build
```

This overwrites these files with the real Vite build (required only if `XUI_API_ONLY` is not set or you need the SPA).
