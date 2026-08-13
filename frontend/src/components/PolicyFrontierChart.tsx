import { useMemo, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Label,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { ComparisonPolicy, FrontierPoint } from "../api/types";
import { cn, formatCurrency, formatPercent } from "../lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";

interface FrontierChartProps {
  frontier: FrontierPoint[];
  comparisons: ComparisonPolicy[];
  serviceLevelTarget: number | null;
}

type SeriesKind = "candidate" | "reference" | "recommended";

type SeriesKey = "candidates" | "references" | "recommended" | "frontier";

type ZoomMode = "all" | "focus" | "frontier";

interface FrontierRow {
  cost: number;
  service_level: number;
  average_on_hand: number;
  is_recommended: boolean;
  policy_label: string;
  series: SeriesKind;
  name?: string;
}

const REFERENCE_LABELS: Record<string, string> = {
  lean: "Lean",
  conservative: "Conservative",
  order_when_empty: "Order when empty",
  average_demand: "Average demand",
};

const REFERENCE_DESCRIPTIONS: Record<string, string> = {
  lean: "Textbook rule: reorder at the mean lead-time demand (no safety stock). Cheap when it works, brittle when demand spikes.",
  conservative:
    "Textbook rule: reorder at mean + 2·std of lead-time demand. Adds a large safety buffer.",
  order_when_empty:
    "Reactive rule: only order once inventory hits zero. Almost always causes stockouts.",
  average_demand:
    "Naive rule: order the daily average every day, ignoring stock. Runaway holding cost, no correction.",
};

const DEFAULT_VISIBLE: Record<SeriesKey, boolean> = {
  candidates: true,
  references: true,
  recommended: true,
  frontier: true,
};

const ZOOM_LABELS: Record<ZoomMode, string> = {
  all: "Full view",
  focus: "Focus",
  frontier: "Frontier only",
};

const ZOOM_TITLES: Record<ZoomMode, string> = {
  all: "Show every policy including extreme outliers",
  focus: "Clip the worst outliers so the tradeoff is easier to read",
  frontier: "Zoom tight around the efficient frontier and recommended policy",
};

function policyLabel(p: FrontierPoint["policy"]): string {
  return p.policy_family === "r_Q"
    ? `r=${p.reorder_point}, Q=${p.order_quantity}`
    : `r=${p.reorder_point}, S=${p.order_up_to}`;
}

function TriangleMarker({ className }: { className?: string }): JSX.Element {
  return (
    <svg viewBox="0 0 10 10" aria-hidden className={className} fill="hsl(30 90% 45%)">
      <polygon points="5,1 9,9 1,9" />
    </svg>
  );
}

/**
 * Fixed-size hit target wrapping a size-varying blue dot. The transparent
 * outer circle makes the point easy to hover even when the visible marker is
 * small or overlaps its neighbours.
 */
function CandidateShape(props: { cx?: number; cy?: number; size?: number }): JSX.Element | null {
  const { cx, cy, size } = props;
  if (cx == null || cy == null) return null;
  const r = size != null && size > 0 ? Math.max(3, Math.sqrt(size / Math.PI)) : 4;
  return (
    <g>
      <circle cx={cx} cy={cy} r={12} fill="transparent" style={{ pointerEvents: "all" }} />
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="hsl(215 80% 55%)"
        fillOpacity={0.45}
        stroke="hsl(215 80% 40%)"
        strokeWidth={0.5}
      />
    </g>
  );
}

/** Orange triangle marker with a generous transparent hitbox. */
function ReferenceShape(props: { cx?: number; cy?: number }): JSX.Element | null {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const r = 6.5;
  return (
    <g>
      <circle cx={cx} cy={cy} r={14} fill="transparent" style={{ pointerEvents: "all" }} />
      <polygon
        points={`${cx},${cy - r} ${cx + r},${cy + r * 0.85} ${cx - r},${cy + r * 0.85}`}
        fill="hsl(30 90% 45%)"
        stroke="hsl(30 90% 30%)"
        strokeWidth={1}
      />
    </g>
  );
}

/**
 * Custom marker for the recommended policy. Overrides the ZAxis-based size
 * with a fixed, generous radius so the dot is easy to hover regardless of
 * that scenario's average_on_hand value.
 */
function RecommendedShape(props: { cx?: number; cy?: number }): JSX.Element | null {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={16} fill="transparent" style={{ pointerEvents: "all" }} />
      <circle
        cx={cx}
        cy={cy}
        r={9}
        fill="hsl(160 84% 32%)"
        stroke="hsl(160 84% 22%)"
        strokeWidth={2}
      />
    </g>
  );
}

function paretoFront(rows: FrontierRow[]): FrontierRow[] {
  const sorted = [...rows].sort((a, b) => a.cost - b.cost);
  const front: FrontierRow[] = [];
  let bestSl = -1;
  for (const r of sorted) {
    if (r.service_level > bestSl) {
      front.push(r);
      bestSl = r.service_level;
    }
  }
  return front;
}

interface TooltipRow {
  cost: number;
  service_level: number;
  average_on_hand: number;
  policy_label: string;
  series: SeriesKind;
  name?: string;
}

const SERIES_PRIORITY: Record<SeriesKind, number> = {
  recommended: 0,
  reference: 1,
  candidate: 2,
};

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: TooltipRow }>;
}): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;
  // When multiple series report data at the hover position (e.g. the
  // recommended dot sits on the pareto line), prefer the most informative one:
  // recommended > reference > candidate.
  const rows = payload
    .map((p) => p.payload)
    .filter((p) => p && p.series)
    .sort((a, b) => SERIES_PRIORITY[a.series] - SERIES_PRIORITY[b.series]);
  if (rows.length === 0) return null;
  const row = rows[0];
  const header =
    row.series === "recommended"
      ? "Recommended policy"
      : row.series === "reference"
        ? `Reference · ${row.name ?? ""}`
        : "Candidate policy";
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium text-foreground">{header}</div>
      <div className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5 tabular-nums">
        <span className="text-muted-foreground">Rule</span>
        <span className="font-medium">{row.policy_label}</span>
        <span className="text-muted-foreground">Reliability</span>
        <span className="font-medium">{formatPercent(row.service_level, 0)}</span>
        <span className="text-muted-foreground">Cost</span>
        <span className="font-medium">{formatCurrency(row.cost)}</span>
        <span className="text-muted-foreground">Avg on-hand</span>
        <span className="font-medium">{row.average_on_hand.toFixed(0)} units</span>
      </div>
    </div>
  );
}

interface LegendChipProps {
  active: boolean;
  onClick: () => void;
  icon: JSX.Element;
  label: string;
  description: string;
}

function LegendChip({ active, onClick, icon, label, description }: LegendChipProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={active ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        active
          ? "border-border/60 bg-background text-foreground hover:bg-muted"
          : "border-dashed border-border/40 bg-muted/20 text-muted-foreground opacity-60 hover:opacity-100",
      )}
    >
      <span className={cn(active ? "" : "opacity-50")}>{icon}</span>
      <span className="font-medium">{label}</span>
      <span className="text-muted-foreground">- {description}</span>
    </button>
  );
}

interface ZoomButtonProps {
  mode: ZoomMode;
  current: ZoomMode;
  onClick: (mode: ZoomMode) => void;
}

function ZoomButton({ mode, current, onClick }: ZoomButtonProps): JSX.Element {
  const active = mode === current;
  return (
    <button
      type="button"
      onClick={() => onClick(mode)}
      aria-pressed={active}
      title={ZOOM_TITLES[mode]}
      className={cn(
        "h-7 px-2.5 text-[11px] font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        "first:rounded-l-md last:rounded-r-md border-y",
        "first:border-l last:border-r",
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-background text-foreground border-border hover:bg-muted",
      )}
    >
      {ZOOM_LABELS[mode]}
    </button>
  );
}

export function PolicyFrontierChart({
  frontier,
  comparisons,
  serviceLevelTarget,
}: FrontierChartProps): JSX.Element {
  const [visible, setVisible] = useState<Record<SeriesKey, boolean>>(DEFAULT_VISIBLE);
  const [zoomMode, setZoomMode] = useState<ZoomMode>("focus");

  const toggle = (key: SeriesKey) => (): void =>
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));

  const allRows: FrontierRow[] = useMemo(() => {
    const candidates: FrontierRow[] = frontier.map((p) => ({
      cost: p.expected_total_cost,
      service_level: p.cycle_service_level,
      average_on_hand: p.average_on_hand,
      is_recommended: p.is_recommended,
      policy_label: policyLabel(p.policy),
      series: p.is_recommended ? "recommended" : "candidate",
    }));
    const refs: FrontierRow[] = comparisons.map((c) => ({
      cost: c.metrics.expected_total_cost,
      service_level: c.metrics.cycle_service_level,
      average_on_hand: c.metrics.average_on_hand,
      is_recommended: false,
      policy_label: policyLabel(c.policy),
      series: "reference",
      name: REFERENCE_LABELS[c.label] ?? c.label,
    }));
    return [...candidates, ...refs];
  }, [frontier, comparisons]);

  const candidateRows = useMemo(() => allRows.filter((r) => r.series === "candidate"), [allRows]);
  const recommendedRows = useMemo(
    () => allRows.filter((r) => r.series === "recommended"),
    [allRows],
  );
  const referenceRows = useMemo(() => allRows.filter((r) => r.series === "reference"), [allRows]);
  const pareto = useMemo(() => paretoFront(allRows), [allRows]);

  // Compute axis domains based on zoom mode. Focus (default) clips extreme
  // outliers so the interesting cluster fills the plot area. Frontier zooms
  // even tighter around the efficient set + recommended.
  const { xDomain, yDomain } = useMemo<{ xDomain: [number, number]; yDomain: [number, number] }>(
    () => {
      const paretoMaxCost = Math.max(...pareto.map((p) => p.cost), 1);
      const recommendedCost = recommendedRows[0]?.cost ?? paretoMaxCost;

      if (zoomMode === "all") {
        const maxCost = Math.max(...allRows.map((r) => r.cost), 1);
        return { xDomain: [0, maxCost * 1.05], yDomain: [0, 1] };
      }

      if (zoomMode === "frontier") {
        const paretoMinSl = Math.min(...pareto.map((p) => p.service_level), 1);
        const target = serviceLevelTarget ?? 1;
        const yLo = Math.max(0, Math.min(paretoMinSl, target) - 0.05);
        const xHi = Math.max(paretoMaxCost * 1.15, recommendedCost * 1.15, 50);
        return { xDomain: [0, xHi], yDomain: [yLo, 1] };
      }

      // focus
      const xHi = Math.max(paretoMaxCost * 1.5, recommendedCost * 3, 100);
      // Auto-tighten Y based on the candidate + recommended cloud (skip
      // references so a single extreme outlier doesn't push Y all the way to 0).
      const focusRows = [...candidateRows, ...recommendedRows].filter((r) => r.cost <= xHi);
      const minSl = Math.min(...focusRows.map((r) => r.service_level), serviceLevelTarget ?? 1);
      const yLo = minSl > 0.5 ? Math.max(0, minSl - 0.05) : 0;
      return { xDomain: [0, xHi], yDomain: [yLo, 1] };
    },
    [pareto, candidateRows, recommendedRows, allRows, zoomMode, serviceLevelTarget],
  );

  // A row is "on chart" if it fits within both axis domains. Anything outside
  // is either clipped by Recharts (via allowDataOverflow) or listed in the
  // off-chart references section below.
  const isVisible = (r: FrontierRow): boolean =>
    r.cost >= xDomain[0] &&
    r.cost <= xDomain[1] &&
    r.service_level >= yDomain[0] &&
    r.service_level <= yDomain[1];

  const visibleCandidates = candidateRows.filter(isVisible);
  const visibleReferences = referenceRows.filter(isVisible);
  const visibleRecommended = recommendedRows.filter(isVisible);
  const offChartReferences = referenceRows.filter((r) => !isVisible(r));
  const offChartRefSet = new Set(offChartReferences);

  const targetPct = serviceLevelTarget != null ? formatPercent(serviceLevelTarget, 0) : null;

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>Cost vs reliability</CardTitle>
            <CardDescription className="max-w-2xl">
              Each dot is one reorder policy the optimizer evaluated by simulating demand for it.
              Cost is on the X-axis, reliability on the Y-axis. Trivially bad policies (very low
              reliability regardless of cost) are omitted so the tradeoff is easier to read.
            </CardDescription>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Zoom</span>
            <div className="inline-flex items-center" role="group" aria-label="Zoom level">
              <ZoomButton mode="all" current={zoomMode} onClick={setZoomMode} />
              <ZoomButton mode="focus" current={zoomMode} onClick={setZoomMode} />
              <ZoomButton mode="frontier" current={zoomMode} onClick={setZoomMode} />
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-2 gap-y-1.5">
          <LegendChip
            active={visible.candidates}
            onClick={toggle("candidates")}
            icon={
              <span className="inline-block h-2 w-2 rounded-full bg-[hsl(215_80%_55%)]" />
            }
            label="Candidates"
            description="policies the optimizer tried"
          />
          <LegendChip
            active={visible.references}
            onClick={toggle("references")}
            icon={<TriangleMarker className="h-2.5 w-2.5" />}
            label="References"
            description="4 textbook rules, for comparison"
          />
          <LegendChip
            active={visible.recommended}
            onClick={toggle("recommended")}
            icon={
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[hsl(160_84%_32%)] ring-2 ring-[hsl(160_84%_22%)]" />
            }
            label="Recommended"
            description={`cheapest policy hitting ${targetPct ?? "the target"}`}
          />
          <LegendChip
            active={visible.frontier}
            onClick={toggle("frontier")}
            icon={<span className="inline-block h-0.5 w-4 bg-[hsl(160_60%_40%)]" />}
            label="Efficient frontier"
            description="best cost at each reliability"
          />
          <span className="text-[11px] text-muted-foreground">
            Click any chip to show or hide.
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-96 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart margin={{ top: 24, right: 32, bottom: 24, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
              <XAxis
                type="number"
                dataKey="cost"
                name="Expected cost"
                domain={xDomain}
                allowDataOverflow
                tickFormatter={(v: number) => formatCurrency(v)}
              >
                <Label
                  value="Expected total cost →"
                  offset={-12}
                  position="insideBottom"
                  fontSize={11}
                />
              </XAxis>
              <YAxis
                type="number"
                dataKey="service_level"
                name="Reliability"
                domain={yDomain}
                allowDataOverflow
                tickFormatter={(v: number) => formatPercent(v, 0)}
              >
                <Label value="Reliability →" angle={-90} position="insideLeft" fontSize={11} />
              </YAxis>
              <ZAxis type="number" dataKey="average_on_hand" range={[40, 240]} />
              <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
              {serviceLevelTarget != null && serviceLevelTarget >= yDomain[0] && (
                <ReferenceLine
                  y={serviceLevelTarget}
                  stroke="hsl(215 30% 45%)"
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                  ifOverflow="extendDomain"
                  label={{
                    value: `Target ${targetPct}`,
                    position: "insideTopRight",
                    fill: "hsl(215 30% 45%)",
                    fontSize: 11,
                  }}
                />
              )}
              {visible.frontier && (
                <Line
                  data={pareto}
                  dataKey="service_level"
                  type="stepAfter"
                  stroke="hsl(160 60% 40%)"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  legendType="plainline"
                  name="Efficient frontier"
                  tooltipType="none"
                  style={{ pointerEvents: "none" }}
                />
              )}
              {visible.candidates && (
                <Scatter
                  name="Candidate policies"
                  data={visibleCandidates}
                  shape={<CandidateShape />}
                  isAnimationActive={false}
                />
              )}
              {visible.references && (
                <Scatter
                  name="Reference policies"
                  data={visibleReferences}
                  shape={<ReferenceShape />}
                  isAnimationActive={false}
                />
              )}
              {visible.recommended && (
                <Scatter
                  name="Recommended"
                  data={visibleRecommended}
                  shape={<RecommendedShape />}
                  isAnimationActive={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-3 text-xs text-muted-foreground">
          <div>
            <div className="font-medium text-foreground">← Cheaper, riskier</div>
            <div>Less inventory, more stockouts.</div>
          </div>
          <div className="text-right">
            <div className="font-medium text-foreground">Safer, more expensive →</div>
            <div>More inventory, rarer stockouts.</div>
          </div>
        </div>
        {referenceRows.length > 0 && (
          <div className="mt-4 grid gap-2 border-t pt-3 text-xs">
            <div className="font-medium text-foreground">Reference policies</div>
            <ul className="grid gap-1.5 sm:grid-cols-2">
              {referenceRows.map((r) => {
                const label = r.name ?? "";
                const description =
                  REFERENCE_DESCRIPTIONS[
                    Object.keys(REFERENCE_LABELS).find((k) => REFERENCE_LABELS[k] === label) ?? ""
                  ] ?? "";
                const off = offChartRefSet.has(r);
                return (
                  <li key={label} className="flex items-start gap-2">
                    <TriangleMarker className="mt-0.5 h-3 w-3 flex-shrink-0" />
                    <span>
                      <span className="font-medium text-foreground">{label}</span>{" "}
                      <span className="tabular-nums text-muted-foreground">
                        ({formatCurrency(r.cost)}, {formatPercent(r.service_level, 0)}
                        {off ? " · off-chart at this zoom" : ""})
                      </span>
                      {description && (
                        <>
                          {" · "}
                          <span className="text-muted-foreground">{description}</span>
                        </>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
