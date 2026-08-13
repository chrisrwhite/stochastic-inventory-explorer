# Portfolio entry

Paste this into `mle-portfolio/src/data/projects.ts` (adjust field names to
match the file's existing schema).

```ts
{
  id: "stochastic-inventory-reorder",
  title: "Stochastic Inventory Reorder / Safety Stock Explorer",
  summary:
    "Interactive stochastic-optimization demo that recommends inventory reorder policies under demand and lead-time uncertainty. Renders the full cost-vs-service frontier, safety-stock decomposition, and CVaR tail-risk metrics for each policy.",
  tags: [
    "stochastic optimization",
    "monte carlo",
    "safety stock",
    "supply chain",
    "fastapi",
    "react",
  ],
  href: "https://inventory.christopherrobertwhite.com",
  github: "https://github.com/<you>/stochastic-inventory-reorder",
  cover: "/covers/inventory.png", // add your own screenshot
  highlights: [
    "6 bundled real-POS scenarios (Walmart M5, Favorita, UCI Online Retail) - no synthetic demand.",
    "Vectorized NumPy Monte Carlo simulator (up to 10k trajectories per policy).",
    "Grid search over (r, Q) and (s, S) with feasibility filters for service level, stockout risk, or CVaR budget.",
    "Recharts policy frontier and inventory fan chart, with a plain-English 'why this policy' breakdown.",
    "Deployed as a single Cloud Run container behind a Cloudflare-proxied subdomain.",
  ],
},
```
