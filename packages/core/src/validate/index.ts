import { AUTHORING_VERSION, AuthoringScene } from "../authoring/schema";
import { resolveAuthoring } from "../authoring/resolve";
import { Scene } from "../schema";
import type { ZodError } from "zod";

export interface Issue {
  path: string;
  message: string;
}

export type ParseResult =
  { ok: true; scene: Scene; warnings: Issue[] } | { ok: false; errors: Issue[]; warnings: Issue[] };

/** Keys the solver computes. They must never appear in scene JSON. */
export const DERIVED_KEYS = [
  "normal",
  "normalForce",
  "tension",
  "friction_force",
  "frictionForce",
  "acceleration",
  "answer",
  "answers",
  "result",
  "net_force",
  "netForce",
  "time_to_stop",
] as const;

const derived: ReadonlySet<string> = new Set(DERIVED_KEYS);

function findDerivedKeys(value: unknown, path: string, out: Issue[]): void {
  if (Array.isArray(value)) {
    value.forEach((v, i) => findDerivedKeys(v, `${path}[${i}]`, out));
  } else if (value !== null && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) {
      const p = path ? `${path}.${k}` : k;
      if (derived.has(k)) {
        out.push({
          path: p,
          message: `"${k}" is computed by the solver and must not be given in the scene`,
        });
      }
      findDerivedKeys(v, p, out);
    }
  }
}

const RESERVED_EVENTS: ReadonlySet<string> = new Set([
  "stop",
  "edge",
  "land",
  "slack",
  "taut",
  "slide_start",
]);

function duplicates(ids: string[]): string[] {
  const seen = new Set<string>();
  const dup = new Set<string>();
  for (const id of ids) (seen.has(id) ? dup : seen).add(id);
  return [...dup];
}

/** Checks that need the whole scene: ids resolve, ranges, queries are answerable. */
export function validateScene(scene: Scene): { errors: Issue[]; warnings: Issue[] } {
  const errors: Issue[] = [];
  const warnings: Issue[] = [];
  const err = (path: string, message: string) => errors.push({ path, message });

  const collections = {
    bodies: scene.bodies,
    surfaces: scene.surfaces,
    forces: scene.forces,
    connections: scene.connections,
    frames: scene.frames,
    events: scene.events,
    queries: scene.queries,
  };
  for (const [name, items] of Object.entries(collections)) {
    for (const id of duplicates(items.map((i) => i.id))) err(name, `duplicate id "${id}"`);
  }

  const bodyIds = new Set(scene.bodies.map((b) => b.id));
  const surfaceIds = new Set(scene.surfaces.map((s) => s.id));
  const forceIds = new Set(scene.forces.map((f) => f.id));
  const connectionIds = new Set(scene.connections.map((c) => c.id));
  const frameIds = new Set(scene.frames.map((f) => f.id));
  const eventIds = new Set(scene.events.map((e) => e.id));

  const need = (set: Set<string>, id: string, kind: string, path: string) => {
    if (!set.has(id)) err(path, `unknown ${kind} "${id}"`);
  };

  scene.bodies.forEach((b, i) => {
    if (!b.fixed && !(b.mass > 0))
      err(`bodies[${i}].mass`, "mass must be > 0 unless the body is fixed");
    if (b.shape.kind === "sphere" && !(b.shape.radius > 0))
      err(`bodies[${i}].shape.radius`, "radius must be > 0");
    if (b.orientation && b.orientation.every((c) => c === 0))
      err(`bodies[${i}].orientation`, "quaternion must be nonzero");
  });

  scene.surfaces.forEach((s, i) => {
    if (s.axis.every((c) => c === 0)) err(`surfaces[${i}].axis`, "axis must be nonzero");
    if (s.friction.kinetic > s.friction.static) {
      warnings.push({
        path: `surfaces[${i}].friction`,
        message: "kinetic friction exceeds static friction",
      });
    }
    if (s.extent && !(s.extent.length > 0))
      err(`surfaces[${i}].extent.length`, "length must be > 0");
  });

  scene.contacts.forEach((c, i) => {
    need(bodyIds, c.body, "body", `contacts[${i}].body`);
    need(surfaceIds, c.surface, "surface", `contacts[${i}].surface`);
    if (c.friction && c.friction.kinetic > c.friction.static) {
      warnings.push({
        path: `contacts[${i}].friction`,
        message: "kinetic friction exceeds static friction",
      });
    }
  });

  const perBody = new Map<string, number>();
  for (const c of scene.contacts) perBody.set(c.body, (perBody.get(c.body) ?? 0) + 1);
  for (const [body, n] of perBody) {
    if (n > 1)
      err("contacts", `body "${body}" has ${n} contacts; v1 supports one surface contact per body`);
  }
  if (!(scene.duration > 0)) err("duration", "duration must be > 0");

  scene.forces.forEach((f, i) => {
    const p = `forces[${i}]`;
    need(bodyIds, f.body, "body", `${p}.body`);
    if (f.kind === "spring") {
      if ("body" in f.anchor) need(bodyIds, f.anchor.body, "body", `${p}.anchor.body`);
      if (!(f.k > 0)) err(`${p}.k`, "spring constant must be > 0");
      if (f.restLength < 0) err(`${p}.restLength`, "rest length must be >= 0");
    } else if ("relativeTo" in f) {
      need(surfaceIds, f.relativeTo, "surface", `${p}.relativeTo`);
    } else {
      if (f.frame === "surface") {
        if (!f.surface) err(`${p}.surface`, 'frame "surface" needs a surface id');
        else need(surfaceIds, f.surface, "surface", `${p}.surface`);
      }
    }
  });

  scene.connections.forEach((c, i) => {
    need(bodyIds, c.a, "body", `connections[${i}].a`);
    need(bodyIds, c.b, "body", `connections[${i}].b`);
    if (c.a === c.b) err(`connections[${i}]`, "a connection must join two different bodies");
    if (c.length !== undefined && !(c.length > 0))
      err(`connections[${i}].length`, "length must be > 0");
  });

  scene.frames.forEach((f, i) => {
    if (typeof f.origin === "string") need(bodyIds, f.origin, "body", `frames[${i}].origin`);
  });

  scene.events.forEach((e, i) => {
    const p = `events[${i}].target`;
    if (e.kind === "release") need(bodyIds, e.target, "body", p);
    else if (e.kind === "cut_string") need(connectionIds, e.target, "connection", p);
    else need(forceIds, e.target, "force", p);
    if (e.at < 0) err(`events[${i}].at`, "time must be >= 0");
  });

  const hasEdge = scene.surfaces.some((s) => s.extent);
  const hasFriction =
    scene.surfaces.some((s) => s.friction.static > 0) ||
    scene.contacts.some((c) => c.friction && c.friction.static > 0);

  scene.queries.forEach((q, i) => {
    const p = `queries[${i}]`;
    if ("body" in q && q.body) need(bodyIds, q.body, "body", `${p}.body`);
    if ("connection" in q && q.connection)
      need(connectionIds, q.connection, "connection", `${p}.connection`);
    if ("frame" in q && q.frame) need(frameIds, q.frame, "frame", `${p}.frame`);
    if ("at" in q && q.at !== undefined && typeof q.at === "object") {
      if (!RESERVED_EVENTS.has(q.at.event)) need(eventIds, q.at.event, "event", `${p}.at.event`);
    }
    if (q.ask === "time") {
      const ev = q.until.event;
      if (ev === "edge" && !hasEdge)
        err(`${p}.until`, 'no surface has an "extent", so no edge can be reached');
      if (ev === "land" && scene.contacts.length === 0)
        err(`${p}.until`, "no body has a surface contact, so nothing can land");
      if (ev === "slack" && scene.connections.length === 0)
        err(`${p}.until`, "no connection can go slack");
      if (ev === "slide_start" && !hasFriction)
        err(`${p}.until`, "no surface has static friction, so sliding cannot start");
    }
    if ((q.ask === "range" || q.ask === "max_height") && scene.contacts.length === 0)
      err(p, `a ${q.ask} query needs a surface contact (the ground) for the body`);
    if (q.ask === "force" && q.force === "tension" && !q.connection) {
      err(`${p}.connection`, "a tension query needs a connection id");
    }
  });

  return { errors, warnings };
}

const formatPath = (path: PropertyKey[]): string =>
  path
    .map((s) => (typeof s === "number" ? `[${s}]` : `.${String(s)}`))
    .join("")
    .replace(/^\./, "");

const zodIssues = (error: ZodError): Issue[] =>
  error.issues.map((i) => ({ path: formatPath(i.path), message: i.message }));

/** True when the JSON declares the authoring layer (`"version": 1.1`). */
const isAuthoring = (json: unknown): boolean =>
  typeof json === "object" &&
  json !== null &&
  (json as { version?: unknown }).version === AUTHORING_VERSION;

/**
 * JSON in, a typed SI scene out (or a list of readable issues).
 * Accepts the canonical form (`version: 1`) or the authoring form (`version: 1.1`), which is
 * resolved into the canonical form first. `warnings` lists every default and inference made.
 */
export function parseScene(json: unknown): ParseResult {
  const bad: Issue[] = [];
  findDerivedKeys(json, "", bad);
  if (bad.length > 0) return { ok: false, errors: bad, warnings: [] };

  let input: unknown = json;
  const assumed: Issue[] = [];
  if (isAuthoring(json)) {
    const authored = AuthoringScene.safeParse(json);
    if (!authored.success) return { ok: false, errors: zodIssues(authored.error), warnings: [] };
    const resolved = resolveAuthoring(authored.data);
    if (!resolved.ok) return { ok: false, errors: resolved.errors, warnings: resolved.warnings };
    input = resolved.scene;
    assumed.push(...resolved.warnings);
  }

  const parsed = Scene.safeParse(input);
  if (!parsed.success) return { ok: false, errors: zodIssues(parsed.error), warnings: assumed };

  const { errors, warnings } = validateScene(parsed.data);
  const all = [...assumed, ...warnings];
  return errors.length > 0
    ? { ok: false, errors, warnings: all }
    : { ok: true, scene: parsed.data, warnings: all };
}
