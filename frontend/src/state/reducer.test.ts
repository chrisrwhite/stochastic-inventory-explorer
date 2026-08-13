import { describe, expect, it } from "vitest";
import { formatCurrency, formatPercent } from "../lib/utils";

describe("formatters", () => {
  it("formats currency in USD", () => {
    expect(formatCurrency(1234.567)).toBe("$1,234.57");
  });

  it("formats percent with default digits", () => {
    expect(formatPercent(0.9345)).toBe("93.5%");
    expect(formatPercent(0.9345, 2)).toBe("93.45%");
  });
});
