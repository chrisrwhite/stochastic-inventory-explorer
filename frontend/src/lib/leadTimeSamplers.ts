import type { LeadTimeModel } from "../api/types";

export interface LeadTimeStats {
  samples: number[];
  mean: number;
  median: number;
  p95: number;
  min: number;
  max: number;
}

function seededRng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

function clampInt(v: number, min = 1): number {
  return Math.max(min, Math.round(v));
}

function sampleTriangular(rng: () => number, a: number, m: number, b: number): number {
  const u = rng();
  const f = (m - a) / (b - a);
  const raw =
    u < f ? a + Math.sqrt(u * (b - a) * (m - a)) : b - Math.sqrt((1 - u) * (b - a) * (b - m));
  return clampInt(raw, Math.max(1, Math.floor(a)));
}

function sampleLognormal(
  rng: () => number,
  meanTarget: number,
  stdTarget: number,
  min: number,
  max: number | null,
): number {
  const v = stdTarget * stdTarget;
  const sigma2 = Math.log(1 + v / (meanTarget * meanTarget));
  const sigma = Math.sqrt(sigma2);
  const mu = Math.log(meanTarget) - 0.5 * sigma2;
  const u1 = Math.max(rng(), 1e-9);
  const u2 = rng();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  let raw = Math.exp(mu + sigma * z);
  if (max !== null) raw = Math.min(raw, max);
  raw = Math.max(raw, min);
  return clampInt(raw);
}

function samplePoissonKnuth(rng: () => number, lambda: number): number {
  if (lambda <= 0) return 0;
  const L = Math.exp(-lambda);
  let k = 0;
  let p = 1;
  do {
    k += 1;
    p *= rng();
  } while (p > L);
  return k - 1;
}

export function sampleLeadTimes(model: LeadTimeModel, n = 5000, seed = 42): number[] {
  const rng = seededRng(seed);
  const samples = new Array<number>(n);
  switch (model.distribution) {
    case "fixed": {
      const d = clampInt(model.days ?? model.mean_days ?? 1);
      samples.fill(d);
      break;
    }
    case "triangular": {
      const a = model.min_days ?? 1;
      const m = model.mode_days ?? Math.max(a, (a + (model.max_days ?? a + 2)) / 2);
      const b = model.max_days ?? Math.max(m + 1, a + 2);
      for (let i = 0; i < n; i++) samples[i] = sampleTriangular(rng, a, m, b);
      break;
    }
    case "lognormal": {
      const meanTarget = model.mean_days ?? 5;
      const stdTarget = model.std_days ?? Math.max(meanTarget * 0.3, 0.5);
      const min = model.min_days ?? 1;
      const max = model.max_days ?? null;
      for (let i = 0; i < n; i++)
        samples[i] = sampleLognormal(rng, meanTarget, stdTarget, min, max);
      break;
    }
    case "poisson_shifted": {
      const lambda = Math.max((model.mean_days ?? 3) - 1, 0);
      for (let i = 0; i < n; i++) samples[i] = samplePoissonKnuth(rng, lambda) + 1;
      break;
    }
    case "empirical":
    case "empirical_discrete": {
      const src = model.samples ?? [model.mean_days ?? 3];
      for (let i = 0; i < n; i++) samples[i] = clampInt(src[Math.floor(rng() * src.length)]);
      break;
    }
  }
  return samples;
}

export function summarizeLeadTimeSamples(samples: number[]): LeadTimeStats {
  if (samples.length === 0) {
    return { samples, mean: 0, median: 0, p95: 0, min: 0, max: 0 };
  }
  const sorted = [...samples].sort((a, b) => a - b);
  const mean = sorted.reduce((s, v) => s + v, 0) / sorted.length;
  const median = sorted[Math.floor(sorted.length / 2)];
  const p95 = sorted[Math.min(sorted.length - 1, Math.floor(0.95 * sorted.length))];
  return {
    samples,
    mean,
    median,
    p95,
    min: sorted[0],
    max: sorted[sorted.length - 1],
  };
}

export function histogram(samples: number[]): { day: number; count: number }[] {
  if (samples.length === 0) return [];
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const bins: Record<number, number> = {};
  for (let d = min; d <= max; d++) bins[d] = 0;
  for (const s of samples) bins[s] = (bins[s] ?? 0) + 1;
  return Object.keys(bins)
    .map((k) => Number(k))
    .sort((a, b) => a - b)
    .map((day) => ({ day, count: bins[day] }));
}
