import { describe, expect, it } from "vitest";
import { archetypes } from "@/lib/archetypes/registry";
import { GoldenCaseSchema, ParseResultSchema, QuantitySchema } from "@/lib/schemas/common";

describe("QuantitySchema", () => {
  it("accepts an SI quantity that keeps the original value, unit, and source span", () => {
    const angle = {
      value: Math.PI / 6,
      unit: "rad",
      original: { value: 30, unit: "deg" },
      source: { start: 22, end: 25, text: "30°" },
      provenance: "given",
    };
    expect(QuantitySchema.parse(angle)).toEqual(angle);
  });

  it("rejects non-finite values", () => {
    const bad = {
      value: Number.POSITIVE_INFINITY,
      unit: "kg",
      original: null,
      source: null,
      provenance: "given",
    };
    expect(QuantitySchema.safeParse(bad).success).toBe(false);
  });
});

describe("ParseResultSchema", () => {
  it("rejects an unknown status", () => {
    expect(ParseResultSchema.safeParse({ status: "maybe" }).success).toBe(false);
  });
});

describe("golden data", () => {
  for (const [id, archetype] of Object.entries(archetypes)) {
    it(`${id}/golden.json matches GoldenCaseSchema and the archetype schema`, () => {
      for (const golden of archetype.golden) {
        const parsed = GoldenCaseSchema.parse(golden);
        expect(archetype.schema.safeParse(parsed.expectedInput).success).toBe(true);
      }
    });
  }
});
