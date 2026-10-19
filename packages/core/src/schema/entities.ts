import { z } from "zod";
import { Friction, Id, Quat, qty, vec3 } from "./primitives";

const Length = qty("length");
const Time = qty("time");

export const Shape = z.discriminatedUnion("kind", [
  z.strictObject({ kind: z.literal("box"), size: vec3("length") }),
  z.strictObject({ kind: z.literal("sphere"), radius: Length }),
  z.strictObject({ kind: z.literal("point") }),
]);

export const Body = z.strictObject({
  id: Id,
  shape: Shape.default({ kind: "point" }),
  mass: qty("mass"),
  /** Ixx, Iyy, Izz, Ixy, Ixz, Iyz in the body frame. Unused by the v1 particle solver. */
  inertia: z
    .tuple([z.number(), z.number(), z.number(), z.number(), z.number(), z.number()])
    .optional(),
  position: vec3("length"),
  orientation: Quat.optional(),
  velocity: vec3("speed").optional(),
  angularVelocity: z.tuple([z.number(), z.number(), z.number()]).optional(),
  fixed: z.boolean().optional(),
});

export const Surface = z.strictObject({
  id: Id,
  kind: z.literal("plane"),
  point: vec3("length"),
  /** Angle from horizontal about `axis`. */
  angle: qty("angle").default(0),
  axis: z.tuple([z.number(), z.number(), z.number()]).default([0, 0, 1]),
  /** A finite extent means the body can reach the edge. */
  extent: z.strictObject({ length: Length, width: Length.optional() }).optional(),
  friction: Friction.default({ static: 0, kinetic: 0 }),
});

export const Contact = z.strictObject({
  body: Id,
  surface: Id,
  friction: Friction.optional(),
});

/** Where a force is applied. Default is the body's center of mass. */
export const ForcePoint = z.strictObject({
  frame: z.enum(["body", "world"]),
  offset: vec3("length").optional(),
});

export const AppliedVectorForce = z.strictObject({
  id: Id,
  kind: z.literal("applied"),
  body: Id,
  vector: vec3("force"),
  frame: z.enum(["world", "surface", "body"]).default("world"),
  surface: Id.optional(),
  at: ForcePoint.optional(),
  during: z.tuple([Time, Time.nullable()]).optional(),
});

export const AppliedAngleForce = z.strictObject({
  id: Id,
  kind: z.literal("applied"),
  body: Id,
  magnitude: qty("force"),
  /** Angle of the force above the surface, measured in the surface's plane. */
  directionAngle: qty("angle"),
  relativeTo: Id,
  at: ForcePoint.optional(),
  during: z.tuple([Time, Time.nullable()]).optional(),
});

export const SpringForce = z.strictObject({
  id: Id,
  kind: z.literal("spring"),
  body: Id,
  anchor: z.union([z.strictObject({ body: Id }), z.strictObject({ point: vec3("length") })]),
  k: qty("stiffness"),
  restLength: Length,
  at: ForcePoint.optional(),
  anchorAt: ForcePoint.optional(),
});

export const Force = z.union([AppliedVectorForce, AppliedAngleForce, SpringForce]);

export const StringConnection = z.strictObject({
  id: Id,
  kind: z.literal("string"),
  a: Id,
  b: Id,
  length: Length.optional(),
  massless: z.literal(true).optional(),
});

/** Ideal pulley (massless, frictionless). A massive pulley is a later version. */
export const Pulley = z.strictObject({
  position: vec3("length"),
  mass: z.literal(0).optional(),
  radius: Length.optional(),
  /** Points where each side of the string leaves the pulley. Default: the pulley position. */
  endA: vec3("length").optional(),
  endB: vec3("length").optional(),
});

export const PulleyStringConnection = z.strictObject({
  id: Id,
  kind: z.literal("pulley_string"),
  a: Id,
  b: Id,
  pulley: Pulley,
  length: Length.optional(),
});

export const Connection = z.discriminatedUnion("kind", [StringConnection, PulleyStringConnection]);

export const Frame = z.strictObject({
  id: Id,
  origin: z.union([Id, vec3("length")]),
  /** Constant velocity relative to the world. */
  velocity: vec3("speed").optional(),
});

export const UserEvent = z.discriminatedUnion("kind", [
  z.strictObject({
    id: Id,
    at: Time,
    kind: z.enum(["release", "cut_string"]),
    target: Id,
  }),
  z.strictObject({
    id: Id,
    at: Time,
    kind: z.literal("set_force"),
    target: Id,
    vector: vec3("force"),
  }),
]);

const EventRef = z.strictObject({ event: Id });

export const Query = z.union([
  z.strictObject({
    id: Id,
    ask: z.enum(["acceleration", "velocity", "position"]),
    body: Id,
    at: z.union([Time, EventRef]).optional(),
    frame: Id.optional(),
  }),
  z.strictObject({
    id: Id,
    ask: z.literal("force"),
    force: z.enum(["normal", "friction", "tension", "net"]),
    body: Id.optional(),
    connection: Id.optional(),
    at: z.union([Time, EventRef]).optional(),
  }),
  z.strictObject({
    id: Id,
    ask: z.literal("time"),
    until: z.strictObject({
      event: z.enum(["stop", "edge", "land", "meet", "slack", "slide_start"]),
    }),
    body: Id.optional(),
    /** For `meet`: the other body. */
    with: Id.optional(),
  }),
  z.strictObject({
    id: Id,
    ask: z.enum(["distance", "work", "min_mu_s"]),
    body: Id,
    from: Time.optional(),
    to: Time.optional(),
  }),
  z.strictObject({
    id: Id,
    /** Highest point reached before landing (or the end of the simulation). */
    ask: z.literal("max_height"),
    body: Id,
    /** `ground`: height above the body's contact surface. `start`: above the starting position. */
    above: z.enum(["ground", "start"]).optional(),
  }),
  z.strictObject({
    id: Id,
    /** Horizontal distance from the starting position to where the body lands. */
    ask: z.literal("range"),
    body: Id,
  }),
  z.strictObject({
    id: Id,
    ask: z.literal("relative_velocity"),
    body: Id,
    frame: Id,
    at: z.union([Time, EventRef]).optional(),
  }),
]);

export type Body = z.output<typeof Body>;
export type Surface = z.output<typeof Surface>;
export type Contact = z.output<typeof Contact>;
export type Force = z.output<typeof Force>;
export type Connection = z.output<typeof Connection>;
export type Frame = z.output<typeof Frame>;
export type UserEvent = z.output<typeof UserEvent>;
export type Query = z.output<typeof Query>;
