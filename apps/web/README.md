# BreakPoint Web

Next.js frontend for BreakPoint.

Run it from this directory:

```bash
npm install
npm run dev
```

The web app expects the API at `http://localhost:8000` unless
`NEXT_PUBLIC_API_URL` is set.

Useful checks:

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm audit --audit-level=high
```

The Playwright suite starts the local API and web app, tests desktop and mobile
flows, checks horizontal overflow, and runs axe-core WCAG scans.

See the repository root `README.md` for the full product walkthrough.
