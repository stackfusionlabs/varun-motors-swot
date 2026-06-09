# Varun Motors SWOT — Blindspot Dashboard

Single-page review intelligence + Vahan registration dashboard for Varun Motors
(Maruti Suzuki dealer group, AP & TG).

## Live

Deployed on Vercel — root URL serves `index.html`.

## Files

- `index.html` — the SPA (HTML + inline CSS + Leaflet + Chart.js via CDN)
- `dashboard_data.js` — precomputed bundle (`const DASHBOARD_DATA = {...}`)
- `ap_boundary.js` — AP state boundary overlay

## Updating data

Regenerate `dashboard_data.js` locally (the ETL scripts live outside this repo),
commit it, and push — Vercel redeploys on push to `main`.
