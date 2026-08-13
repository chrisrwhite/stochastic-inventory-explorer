import { useState } from "react";
import type { LeadTimeDistribution, LeadTimeModel } from "../api/types";
import { cn } from "../lib/utils";
import { useAppState } from "../state/AppState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/Card";
import { Input } from "./ui/Input";
import { Label } from "./ui/Label";
import { Select } from "./ui/Select";

const DISTRIBUTIONS: { value: LeadTimeDistribution; label: string }[] = [
  { value: "fixed", label: "Fixed" },
  { value: "triangular", label: "Triangular" },
  { value: "lognormal", label: "Lognormal" },
  { value: "poisson_shifted", label: "Poisson-shifted" },
];

interface Preset {
  id: string;
  label: string;
  description: string;
  model: LeadTimeModel;
}

const PRESETS: Preset[] = [
  {
    id: "reliable_domestic",
    label: "Reliable domestic",
    description: "Fixed 2 days",
    model: { distribution: "fixed", days: 2 },
  },
  {
    id: "standard_shipping",
    label: "Standard shipping",
    description: "1–5 days, most common ~3",
    model: {
      distribution: "triangular",
      min_days: 1,
      mode_days: 3,
      max_days: 5,
    },
  },
  {
    id: "international",
    label: "International",
    description: "~14 days, high variance",
    model: {
      distribution: "lognormal",
      mean_days: 14,
      std_days: 4,
      min_days: 1,
    },
  },
];

function fieldsMatch(current: LeadTimeModel, preset: LeadTimeModel): boolean {
  if (current.distribution !== preset.distribution) return false;
  const keys: (keyof LeadTimeModel)[] = [
    "days",
    "min_days",
    "mode_days",
    "max_days",
    "mean_days",
    "std_days",
  ];
  for (const k of keys) {
    const p = preset[k];
    if (p == null) continue;
    const c = current[k];
    if (c == null || Number(c) !== Number(p)) return false;
  }
  return true;
}

function LabeledNumber({
  label,
  value,
  onChange,
  min,
  step = 0.1,
}: {
  label: string;
  value: number | undefined;
  onChange: (n: number) => void;
  min?: number;
  step?: number;
}): JSX.Element {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Input
        type="number"
        min={min}
        step={step}
        value={value ?? ""}
        onChange={(e) => {
          const v = e.target.value === "" ? NaN : Number(e.target.value);
          if (!Number.isNaN(v)) onChange(v);
        }}
      />
    </div>
  );
}

function CustomFields({
  lt,
  onSet,
}: {
  lt: LeadTimeModel;
  onSet: (patch: Partial<LeadTimeModel>) => void;
}): JSX.Element {
  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label>Distribution</Label>
        <Select
          value={lt.distribution}
          onChange={(e) =>
            onSet({ distribution: e.target.value as LeadTimeDistribution })
          }
        >
          {DISTRIBUTIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {lt.distribution === "fixed" && (
          <LabeledNumber
            label="Days"
            value={lt.days ?? lt.mean_days}
            onChange={(n) => onSet({ days: n })}
            min={1}
            step={1}
          />
        )}
        {lt.distribution === "triangular" && (
          <>
            <LabeledNumber
              label="Min days"
              value={lt.min_days}
              onChange={(n) => onSet({ min_days: n })}
              min={1}
              step={1}
            />
            <LabeledNumber
              label="Mode days"
              value={lt.mode_days}
              onChange={(n) => onSet({ mode_days: n })}
              min={1}
              step={1}
            />
            <LabeledNumber
              label="Max days"
              value={lt.max_days}
              onChange={(n) => onSet({ max_days: n })}
              min={1}
              step={1}
            />
          </>
        )}
        {(lt.distribution === "lognormal" ||
          lt.distribution === "poisson_shifted") && (
          <>
            <LabeledNumber
              label="Mean days"
              value={lt.mean_days}
              onChange={(n) => onSet({ mean_days: n })}
              min={1}
            />
            {lt.distribution === "lognormal" && (
              <LabeledNumber
                label="Std days"
                value={lt.std_days}
                onChange={(n) => onSet({ std_days: n })}
                min={0.1}
              />
            )}
            <LabeledNumber
              label="Min days"
              value={lt.min_days ?? 1}
              onChange={(n) => onSet({ min_days: n })}
              min={1}
              step={1}
            />
            <LabeledNumber
              label="Max days"
              value={lt.max_days}
              onChange={(n) => onSet({ max_days: n })}
              min={1}
              step={1}
            />
          </>
        )}
      </div>
    </div>
  );
}

export function LeadTimeEditor(): JSX.Element {
  const { config, dispatch } = useAppState();
  const lt = config.leadTime;
  const [forceCustom, setForceCustom] = useState(false);

  const matchedPreset = PRESETS.find((p) => fieldsMatch(lt, p.model));
  const activePresetId =
    !forceCustom && matchedPreset ? matchedPreset.id : "custom";

  function applyPreset(preset: Preset): void {
    setForceCustom(false);
    dispatch({ type: "set_lead_time", leadTime: { ...preset.model } });
  }

  function setPatch(patch: Partial<LeadTimeModel>): void {
    dispatch({ type: "set_lead_time", leadTime: { ...lt, ...patch } });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lead time</CardTitle>
        <CardDescription>
          How long between placing an order and receiving it. The biggest driver of
          stockout risk.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid gap-2 sm:grid-cols-2">
          {PRESETS.map((p) => {
            const active = activePresetId === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => applyPreset(p)}
                className={cn(
                  "grid gap-0.5 rounded-md border bg-background p-3 text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active && "border-primary ring-2 ring-primary/40 bg-accent/30",
                )}
                aria-pressed={active}
              >
                <span className="text-sm font-medium">{p.label}</span>
                <span className="text-xs text-muted-foreground">{p.description}</span>
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => setForceCustom(true)}
            className={cn(
              "grid gap-0.5 rounded-md border bg-background p-3 text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activePresetId === "custom" &&
                "border-primary ring-2 ring-primary/40 bg-accent/30",
            )}
            aria-pressed={activePresetId === "custom"}
          >
            <span className="text-sm font-medium">Custom</span>
            <span className="text-xs text-muted-foreground">
              Full distribution + parameters
            </span>
          </button>
        </div>
        {activePresetId === "custom" && (
          <div className="border-t pt-3">
            <CustomFields lt={lt} onSet={setPatch} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
