import { describe, expect, it } from "vitest";
import { toSI } from "./index";

describe("toSI", () => {
  it("passes plain numbers through as SI", () => {
    expect(toSI(2.5, "mass")).toEqual({ ok: true, value: 2.5 });
  });

  it("converts degrees to radians: 30 deg = pi/6 = 0.5236", () => {
    const r = toSI("30 deg", "angle");
    expect(r.ok && r.value).toBeCloseTo(0.5236, 4);
  });

  it("converts grams to kilograms: 2 g = 0.002 kg", () => {
    const r = toSI("2 g", "mass");
    expect(r.ok && r.value).toBeCloseTo(0.002, 12);
  });

  it("converts km/h to m/s: 72 km/h = 20 m/s", () => {
    const r = toSI("72 km/h", "speed");
    expect(r.ok && r.value).toBeCloseTo(20, 12);
  });

  it("converts cm and ft: 150 cm = 1.5 m, 10 ft = 3.048 m", () => {
    const a = toSI("150 cm", "length");
    const b = toSI("10 ft", "length");
    expect(a.ok && a.value).toBeCloseTo(1.5, 12);
    expect(b.ok && b.value).toBeCloseTo(3.048, 12);
  });

  it("treats a string without a unit as SI", () => {
    expect(toSI("4", "force")).toEqual({ ok: true, value: 4 });
  });

  it("rejects a unit from the wrong dimension", () => {
    const r = toSI("5 kg", "length");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.message).toContain('"kg"');
  });

  it("rejects non-numeric text and non-finite numbers", () => {
    expect(toSI("heavy", "mass").ok).toBe(false);
    expect(toSI(Number.NaN, "mass").ok).toBe(false);
  });
});
