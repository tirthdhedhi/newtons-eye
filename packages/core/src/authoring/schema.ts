import { z } from "zod";
import {
  AppliedAngleForce,
  AppliedVectorForce,
  Body,
  PulleyStringConnection,
  Pulley,
  Shape,
  SpringForce,
  StringConnection,
  Surface,
} from "../schema/entities";
import { Id, qty, vec3 } from "../schema/primitives";
import { Scene } from "../schema/scene";

/** Version string of the authoring layer. Canonical scenes stay at `version: 1`. */
export const AUTHORING_VERSION = 1.1 as const;

const Length = qty("length");

/** Where a body starts. The resolver turns this into a position (and orientation). */
export const Placement = z.union([
  /** Rest flush on a plane. `at` is "top", "bottom" or a distance along the slope; `offset` is the same for horizontal planes. */
  z.strictObject({
    on: Id,
    at: z.union([z.enum(["top", "bottom"]), Length]).optional(),
    offset: Length.optional(),
  }),
  /** Hang under the pulley end of a connection, `gap` above a plane. */
  z.strictObject({ hangingFrom: Id, above: Id, gap: Length }),
]);

export const Velocity = z.union([
  vec3("speed"),
  /** `angle` is above horizontal, toward +x. */
  z.strictObject({ speed: qty("speed"), angle: qty("angle") }),
  z.strictObject({ speed: qty("speed"), along: Id, direction: z.enum(["up", "down"]) }),
]);

export const AuthoringBody = Body.extend({
  /** Optional: it only matters when a force other than gravity acts. Default 1 kg. */
  mass: qty("mass").optional(),
  /**
   * Constant acceleration along the direction of motion (toward +x if the body starts at rest);
   * negative brakes. The resolver adds the force that makes the body accelerate by exactly this
   * much under gravity, so kinematics problems ("a car accelerates at 3 m/s^2") need no force.
   */
  constantAcceleration: qty("acceleration").optional(),
  shape: Shape.optional(),
  position: vec3("length").optional(),
  placement: Placement.optional(),
  velocity: Velocity.optional(),
});

export const AuthoringSurface = Surface.extend({
  point: vec3("length").default([0, 0, 0]),
});

export const EdgeOf = z.strictObject({ at: z.literal("edge_of"), surface: Id });

export const AuthoringPulleyString = PulleyStringConnection.extend({
  pulley: Pulley.extend({ position: z.union([vec3("length"), EdgeOf]).optional() }).default({}),
});

/** A spring whose other end is fixed in space, with the body pulled out by `stretch`. */
export const FixedAnchor = z.strictObject({ fixed: z.literal(true), stretch: Length });

export const AuthoringSpring = SpringForce.extend({
  anchor: z.union([SpringForce.shape.anchor, FixedAnchor]),
});

export const AuthoringConnection = z.discriminatedUnion("kind", [
  StringConnection,
  AuthoringPulleyString,
]);

export const AuthoringForce = z.union([AppliedVectorForce, AppliedAngleForce, AuthoringSpring]);

export const AuthoringScene = Scene.extend({
  version: z.literal(AUTHORING_VERSION),
  duration: qty("time").optional(),
  bodies: z.array(AuthoringBody).min(1),
  surfaces: z.array(AuthoringSurface).default([]),
  forces: z.array(AuthoringForce).default([]),
  connections: z.array(AuthoringConnection).default([]),
});

/** An authoring scene after parsing: quantities are SI, sugar is still unresolved. */
export type AuthoringScene = z.output<typeof AuthoringScene>;
export type AuthoringBody = z.output<typeof AuthoringBody>;
export type AuthoringSceneInput = z.input<typeof AuthoringScene>;
