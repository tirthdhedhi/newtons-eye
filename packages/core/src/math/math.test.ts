import { describe, expect, it } from "vitest";
import { linsolve } from "./linsolve";
import { rk4Step } from "./rk4";
import { quatToMat, rotateAbout, matVec } from "./vec3";

describe("linsolve", () => {
  it("solves 2x + y = 5, x - y = 1 -> x = 2, y = 1", () => {
    const x = linsolve(
      [
        [2, 1],
        [1, -1],
      ],
      [5, 1],
    );
    expect(x?.[0]).toBeCloseTo(2, 12);
    expect(x?.[1]).toBeCloseTo(1, 12);
  });

  it("pivots when the leading entry is zero", () => {
    const x = linsolve(
      [
        [0, 1],
        [1, 0],
      ],
      [3, 4],
    );
    expect(x).toEqual([4, 3]);
  });

  it("returns a particular solution (free variable = 0) for a consistent rank-deficient system", () => {
    // x + y = 2 stated twice: y is free.
    const x = linsolve(
      [
        [1, 1],
        [2, 2],
      ],
      [2, 4],
    );
    expect(x).toEqual([2, 0]);
  });

  it("returns null for an inconsistent system", () => {
    expect(
      linsolve(
        [
          [1, 2],
          [2, 4],
        ],
        [1, 3],
      ),
    ).toBeNull();
  });
});

describe("rk4Step", () => {
  it("integrates y' = y over 1 s to e within 1e-10 (h = 0.01)", () => {
    let y: Float64Array = new Float64Array([1]);
    for (let i = 0; i < 100; i++)
      y = rk4Step((_t, s) => new Float64Array([s[0] ?? 0]), i * 0.01, y, 0.01);
    expect(y[0]).toBeCloseTo(Math.E, 9);
  });
});

describe("rotations", () => {
  it("rotating (1,0,0) by 30 deg about z gives (cos30, sin30, 0)", () => {
    const v = rotateAbout([1, 0, 0], [0, 0, 1], Math.PI / 6);
    expect(v[0]).toBeCloseTo(0.8660254, 7);
    expect(v[1]).toBeCloseTo(0.5, 7);
  });

  it("quaternion for 90 deg about z maps x to y", () => {
    const s = Math.SQRT1_2;
    const v = matVec(quatToMat([0, 0, s, s]), [1, 0, 0]);
    expect(v[0]).toBeCloseTo(0, 12);
    expect(v[1]).toBeCloseTo(1, 12);
  });
});
