import type { z } from "zod";
import { add, scale, unit } from "../math/vec3";
import type { Quat, Vec3 } from "../math/vec3";
import { planeBasis } from "../solver/model";
import type { Shape } from "../schema/entities";
import type { SceneInput } from "../schema/scene";
import type { Issue } from "../validate";
import type { AuthoringBody, AuthoringScene } from "./schema";

/** Used when a body gives no `shape`. */
export const DEFAULT_SHAPE = { kind: "box", size: [0.4, 0.2, 0.4] } as const;
/** Shortest simulation an authoring scene gets when it gives no `duration`. */
export const MIN_DURATION = 2;
/**
 * Simulation length when a query depends on an event (a time until stop/edge/land, a range, a
 * maximum height, or a distance with no window): the event has to be able to happen.
 */
export const EVENT_DURATION = 60;
/** Extra simulated time after the last time any query refers to. */
export const DURATION_MARGIN = 1;

type ResolvedShape = z.output<typeof Shape>;
type OutBody = Omit<AuthoringBody, "placement" | "shape" | "position" | "velocity"> & {
  shape: ResolvedShape;
  position: Vec3;
  velocity?: Vec3;
};

export type ResolveResult =
  | { ok: true; scene: SceneInput; warnings: Issue[] }
  | { ok: false; errors: Issue[]; warnings: Issue[] };

const fmt = (n: number): string => String(Number(n.toPrecision(6)));
const fmtVec = (v: Vec3): string => `[${v.map(fmt).join(", ")}]`;

/** Half the body's extent along its own up axis (the distance from its center to a surface it rests on). */
function halfHeight(shape: ResolvedShape): number {
  if (shape.kind === "box") return shape.size[1] / 2;
  if (shape.kind === "sphere") return shape.radius;
  return 0;
}

function axisAngleQuat(axis: Vec3, angle: number): Quat {
  const w = unit(axis);
  const s = Math.sin(angle / 2);
  return [w[0] * s, w[1] * s, w[2] * s, Math.cos(angle / 2)];
}

/** Height (y) of a plane above the world point (x, z). */
function planeY(point: Vec3, n: Vec3, x: number, z: number): number {
  return point[1] - (n[0] * (x - point[0]) + n[2] * (z - point[2])) / n[1];
}

/**
 * Resolve the authoring sugar (schema v1.1) into a canonical scene input (v1, SI).
 * Every default or inference made on the author's behalf is reported in `warnings`.
 */
export function resolveAuthoring(a: AuthoringScene): ResolveResult {
  const errors: Issue[] = [];
  const warnings: Issue[] = [];
  const err = (path: string, message: string) => errors.push({ path, message });
  const note = (path: string, message: string) => warnings.push({ path, message });

  const surfaces = new Map(a.surfaces.map((s) => [s.id, { s, ...planeBasis(s.angle, s.axis) }]));
  const contactSurface = new Map<string, string>();
  for (const c of a.contacts)
    if (!contactSurface.has(c.body)) contactSurface.set(c.body, c.surface);

  const shapes = new Map<string, ResolvedShape>();
  a.bodies.forEach((b, i) => {
    if (b.shape) {
      shapes.set(b.id, b.shape);
    } else {
      shapes.set(b.id, { ...DEFAULT_SHAPE, size: [...DEFAULT_SHAPE.size] });
      note(
        `bodies[${i}].shape`,
        `"${b.id}" has no shape: using a box of ${fmtVec([...DEFAULT_SHAPE.size])} m`,
      );
    }
  });

  const surfaceOf = (id: string, path: string) => {
    const found = surfaces.get(id);
    if (!found) err(path, `unknown surface "${id}"`);
    return found;
  };

  // --- pulleys -------------------------------------------------------------------------------
  const pulleyEnds = new Map<string, { a: Vec3; b: Vec3 }>();

  const edgeOf = (surfaceId: string, bodies: string[], path: string): Vec3 | undefined => {
    const surf = surfaceOf(surfaceId, `${path}.surface`);
    if (!surf) return undefined;
    if (!surf.s.extent) {
      err(path, `surface "${surfaceId}" has no extent, so it has no edge to put a pulley on`);
      return undefined;
    }
    const rider = bodies.find((id) => contactSurface.get(id) === surfaceId);
    if (!rider) {
      err(path, `neither connected body rests on surface "${surfaceId}" (add a contact)`);
      return undefined;
    }
    const h = halfHeight(shapes.get(rider)!);
    const edge = add(surf.s.point, scale(surf.u, surf.s.extent.length));
    const pos = add(edge, scale(surf.n, h));
    note(path, `pulley placed at the edge of "${surfaceId}", level with the center of "${rider}"`);
    return pos;
  };

  const connections = a.connections.map((c, i) => {
    if (c.kind !== "pulley_string") return c;
    const path = `connections[${i}].pulley.position`;
    const p = c.pulley.position;
    let position: Vec3 | undefined;
    if (Array.isArray(p)) {
      position = p as Vec3;
    } else if (p) {
      position = edgeOf(p.surface, [c.a, c.b], path);
    } else {
      const surfaceId = [c.a, c.b].map((id) => contactSurface.get(id)).find((s) => s !== undefined);
      if (surfaceId === undefined) {
        err(
          path,
          'no pulley position: give coordinates, or { "at": "edge_of", "surface": <id> } ' +
            "(the position can only be inferred when a connected body rests on a surface)",
        );
      } else {
        note(path, `no pulley position given: assuming the edge of "${surfaceId}"`);
        position = edgeOf(surfaceId, [c.a, c.b], path);
      }
    }
    if (!position) return c;
    pulleyEnds.set(c.id, {
      a: (c.pulley.endA as Vec3 | undefined) ?? position,
      b: (c.pulley.endB as Vec3 | undefined) ?? position,
    });
    return { ...c, pulley: { ...c.pulley, position } };
  });

  // --- bodies --------------------------------------------------------------------------------
  const bodies: OutBody[] = a.bodies.map((b, i) => {
    const path = `bodies[${i}]`;
    const shape = shapes.get(b.id)!;
    const h = halfHeight(shape);
    const { placement, position: explicit, velocity, shape: _shape, ...rest } = b;
    let position: Vec3 = [0, 0, 0];
    let orientation = b.orientation;

    if (explicit && placement)
      err(`${path}.placement`, "give either position or placement, not both");
    if (placement && b.orientation)
      err(`${path}.orientation`, "placement computes the orientation: remove orientation");

    const restOn = (surfaceId: string, s: number, where: string) => {
      const surf = surfaceOf(surfaceId, `${path}.placement.on`);
      if (!surf) return;
      position = add(add(surf.s.point, scale(surf.u, s)), scale(surf.n, h));
      if (Math.abs(surf.s.angle) > 1e-12) orientation = axisAngleQuat(surf.s.axis, surf.s.angle);
      note(`${path}.placement`, `"${b.id}" placed ${where} of "${surfaceId}", resting flush on it`);
    };

    if (explicit) {
      position = explicit as Vec3;
    } else if (placement && "hangingFrom" in placement) {
      const ends = pulleyEnds.get(placement.hangingFrom);
      const conn = connections.find((c) => c.id === placement.hangingFrom);
      const above = surfaceOf(placement.above, `${path}.placement.above`);
      if (!conn)
        err(`${path}.placement.hangingFrom`, `unknown connection "${placement.hangingFrom}"`);
      else if (conn.kind !== "pulley_string")
        err(`${path}.placement.hangingFrom`, "hangingFrom needs a pulley_string connection");
      else if (b.id !== conn.a && b.id !== conn.b)
        err(`${path}.placement.hangingFrom`, `"${b.id}" is not attached to "${conn.id}"`);
      else if (ends && above) {
        const end = b.id === conn.a ? ends.a : ends.b;
        if (Math.abs(above.n[1]) < 1e-9) {
          err(
            `${path}.placement.above`,
            `surface "${above.s.id}" is vertical, so nothing hangs above it`,
          );
        } else {
          const floorY = planeY(above.s.point, above.n, end[0], end[2]);
          position = [end[0], floorY + placement.gap + h, end[2]];
          note(
            `${path}.placement`,
            `"${b.id}" hangs straight down from the pulley end of "${conn.id}", ${fmt(placement.gap)} m above "${above.s.id}"`,
          );
        }
      }
    } else if (placement) {
      const surf = surfaceOf(placement.on, `${path}.placement.on`);
      if (surf) {
        if (placement.at !== undefined && placement.offset !== undefined)
          err(`${path}.placement`, "give either at or offset, not both");
        let s = 0;
        let where = "at the start";
        if (placement.offset !== undefined) {
          if (Math.abs(surf.s.angle) > 1e-9)
            err(`${path}.placement.offset`, "offset is for horizontal planes: use at for a slope");
          s = placement.offset;
          where = `${fmt(s)} m along the surface`;
        } else if (placement.at === "top") {
          if (!surf.s.extent)
            err(
              `${path}.placement.at`,
              `surface "${placement.on}" has no extent, so it has no top`,
            );
          else s = surf.s.extent.length;
          where = "at the top";
        } else if (placement.at === "bottom") {
          where = "at the bottom";
        } else if (placement.at !== undefined) {
          s = placement.at;
          where = `${fmt(s)} m along the slope`;
        }
        restOn(placement.on, s, where);
      }
    } else {
      const surfaceId = contactSurface.get(b.id);
      if (surfaceId !== undefined) {
        note(
          `${path}.placement`,
          `no placement given: "${b.id}" rests on its contact "${surfaceId}"`,
        );
        restOn(surfaceId, 0, "at the start");
      } else {
        note(`${path}.position`, `no position given: "${b.id}" starts at the origin`);
      }
    }

    let vel: Vec3 | undefined;
    if (velocity) {
      if (Array.isArray(velocity)) {
        vel = velocity as Vec3;
      } else if ("angle" in velocity) {
        vel = [
          velocity.speed * Math.cos(velocity.angle),
          velocity.speed * Math.sin(velocity.angle),
          0,
        ];
        note(`${path}.velocity`, `"${b.id}" moves in the x-y plane, angled above the +x direction`);
      } else {
        const surf = surfaceOf(velocity.along, `${path}.velocity.along`);
        if (surf) {
          const sign = velocity.direction === "up" ? 1 : -1;
          vel = scale(surf.u, sign * velocity.speed);
          if (Math.abs(surf.s.angle) < 1e-9)
            note(
              `${path}.velocity`,
              `"up" on the horizontal surface "${velocity.along}" means toward +x`,
            );
        }
      }
    }

    return {
      ...rest,
      shape,
      position,
      ...(orientation ? { orientation } : {}),
      ...(vel ? { velocity: vel } : {}),
    };
  });

  // --- springs -------------------------------------------------------------------------------
  const displaced = new Set<string>();
  const forces = a.forces.map((f, i) => {
    if (f.kind !== "spring" || !("fixed" in f.anchor)) return f;
    const path = `forces[${i}]`;
    const body = bodies.find((b) => b.id === f.body);
    if (!body) {
      err(`${path}.body`, `unknown body "${f.body}"`);
      return f;
    }
    if (displaced.has(body.id)) {
      err(`${path}.anchor`, `"${body.id}" is already displaced by another spring's stretch`);
      return f;
    }
    displaced.add(body.id);
    const surfaceId = contactSurface.get(body.id);
    const surf = surfaceId === undefined ? undefined : surfaces.get(surfaceId);
    const dir: Vec3 = surf ? surf.u : [1, 0, 0];
    const natural = body.position;
    const anchorPoint = add(natural, scale(dir, -f.restLength));
    body.position = add(natural, scale(dir, f.anchor.stretch));
    note(
      `${path}.anchor`,
      `spring anchor fixed at ${fmtVec(anchorPoint)}; "${body.id}" starts ${fmt(f.anchor.stretch)} m from the natural-length point, along ${surf ? `"${surfaceId}"` : "+x"}`,
    );
    return { ...f, anchor: { point: anchorPoint } };
  });

  // --- duration ------------------------------------------------------------------------------
  let duration = a.duration;
  if (duration === undefined) {
    const eventAt = new Map(a.events.map((e) => [e.id, e.at]));
    let latest = 0;
    const see = (t: unknown) => {
      if (typeof t === "number") latest = Math.max(latest, t);
      else if (t && typeof t === "object" && "event" in t) {
        const at = eventAt.get(String((t as { event: unknown }).event));
        if (at !== undefined) latest = Math.max(latest, at);
      }
    };
    for (const q of a.queries) {
      if ("at" in q) see(q.at);
      if ("from" in q) see(q.from);
      if ("to" in q) see(q.to);
    }
    const eventDriven = a.queries.some(
      (q) =>
        q.ask === "time" ||
        q.ask === "range" ||
        q.ask === "max_height" ||
        (q.ask === "distance" && q.to === undefined) ||
        ("at" in q && q.at !== undefined && typeof q.at === "object" && !eventAt.has(q.at.event)),
    );
    duration = Math.max(MIN_DURATION, latest + DURATION_MARGIN);
    if (eventDriven && duration < EVENT_DURATION) {
      duration = EVENT_DURATION;
      note(
        "duration",
        `no duration given: simulating ${fmt(duration)} s because a query waits for an event (time until, range, max height, or an open-ended distance)`,
      );
    } else {
      note(
        "duration",
        `no duration given: simulating ${fmt(duration)} s (last query time ${fmt(latest)} s + ${DURATION_MARGIN} s, at least ${MIN_DURATION} s)`,
      );
    }
  }

  if (errors.length > 0) return { ok: false, errors, warnings };
  const scene = { ...a, version: 1 as const, duration, bodies, forces, connections } as SceneInput;
  return { ok: true, scene, warnings };
}
