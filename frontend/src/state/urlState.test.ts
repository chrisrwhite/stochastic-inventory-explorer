import { describe, expect, it } from "vitest";
import type { AppConfig } from "./AppState";
import { initialConfig } from "./defaults";
import { readConfigFromSearch, writeConfigToSearch } from "./urlState";

/** Serialise a config and read it back, the way a shared link is used. */
function roundTrip(config: AppConfig): AppConfig {
  return readConfigFromSearch(`?${writeConfigToSearch(config, "")}`);
}

describe("urlState", () => {
  it("round-trips the default config", () => {
    expect(roundTrip(initialConfig)).toEqual(initialConfig);
  });

  it("round-trips a fully customised config", () => {
    // The backend is stateless, so anything not preserved here is silently
    // lost on reload and never travels with a shared link.
    const custom: AppConfig = {
      scenarioId: "retail_online_uk",
      policyFamily: "r_Q",
      demandModel: "negative_binomial",
      leadTime: { distribution: "lognormal", mean_days: 6.5, std_days: 1.25 },
      costs: {
        unit_cost: 12.5,
        holding_cost_per_unit_per_day: 0.075,
        stockout_cost_per_unit: 14,
        fixed_order_cost: 22,
        variable_order_cost_per_unit: 1.5,
        starting_inventory: 45,
        review_period_days: 7,
      },
      mode: "cvar_budget",
      targetServiceLevel: 0.95,
      maxStockoutRisk: 0.05,
      cvarStockoutBudget: 250,
      nSimulations: 3000,
      horizonDays: 240,
      randomSeed: 7,
    };
    expect(roundTrip(custom)).toEqual(custom);
  });

  it("keeps the everyday URL short by omitting defaults", () => {
    const params = new URLSearchParams(writeConfigToSearch(initialConfig, ""));
    expect([...params.keys()].sort()).toEqual(["m", "p", "s", "sl"]);
  });

  it("writes only the objective belonging to the active mode", () => {
    const stockoutMode: AppConfig = { ...initialConfig, mode: "stockout_risk" };
    const params = new URLSearchParams(writeConfigToSearch(stockoutMode, ""));
    expect(params.get("sr")).toBe("0.050");
    expect(params.has("sl")).toBe(false);
    expect(params.has("cvar")).toBe(false);
  });

  it("preserves query params it does not own", () => {
    const params = new URLSearchParams(writeConfigToSearch(initialConfig, "?tab=futures"));
    expect(params.get("tab")).toBe("futures");
  });

  it("falls back to defaults for out-of-range and malformed values", () => {
    const config = readConfigFromSearch(
      "?n=999999&h=0&sl=2&dm=not_a_model&lt=triangular:min_days=-1&c=1,2,3",
    );
    expect(config.nSimulations).toBe(initialConfig.nSimulations);
    expect(config.horizonDays).toBe(initialConfig.horizonDays);
    expect(config.targetServiceLevel).toBe(initialConfig.targetServiceLevel);
    expect(config.demandModel).toBe(initialConfig.demandModel);
    expect(config.leadTime).toEqual(initialConfig.leadTime);
    expect(config.costs).toEqual(initialConfig.costs);
  });

  it("ignores an unknown lead-time distribution rather than sending it upstream", () => {
    expect(readConfigFromSearch("?lt=gamma:mean_days=4").leadTime).toEqual(
      initialConfig.leadTime,
    );
  });
});
