/**
 * Renderer-agnostic scene description.
 *
 * Nothing here assumes 2D or 3D, SVG, canvas, or WebGL. Coordinates are in SI
 * metres; `z` is optional so 2D renderers can ignore it. Archetype templates
 * build a Scene + Timeline; a renderer decides how to draw them.
 */

export interface Point {
  x: number;
  y: number;
  z?: number;
}

/** Rotation of `angle` radians about `axis` (defaults to +z for 2D). */
export interface Rotation {
  angle: number;
  axis?: Point;
}

export interface Transform {
  position: Point;
  rotation?: Rotation;
}

interface PrimitiveBase {
  /** Stable id; Step.highlight and StepState refer to primitives by id. */
  id: string;
  transform: Transform;
  /** Semantic color role, resolved to a real color by the renderer's theme. */
  role?: "body" | "surface" | "force" | "velocity" | "acceleration" | "component" | "annotation";
}

export interface BlockPrimitive extends PrimitiveBase {
  kind: "block";
  size: Point;
  mass?: number;
}

export interface InclinePrimitive extends PrimitiveBase {
  kind: "incline";
  /** Incline angle in radians. */
  angle: number;
  length: number;
}

export interface VectorPrimitive extends PrimitiveBase {
  kind: "vector";
  /** Direction and magnitude in scene units, from transform.position. */
  components: Point;
  /** Physical magnitude in SI, for labels (independent of drawn length). */
  magnitude?: number;
  unit?: string;
}

export interface LabelPrimitive extends PrimitiveBase {
  kind: "label";
  text: string;
  /** Render `text` as KaTeX. */
  latex?: boolean;
  /** Primitive id this label is attached to, if any. */
  attachTo?: string;
}

export type Primitive = BlockPrimitive | InclinePrimitive | VectorPrimitive | LabelPrimitive;
export type PrimitiveKind = Primitive["kind"];

export interface Scene {
  id: string;
  primitives: Primitive[];
}

export type Emphasis = "normal" | "highlight" | "dim" | "hidden";

/** Diagram state for one solution step. Primitives not listed use "normal". */
export interface StepState {
  stepId: string;
  emphasis: Record<string, Emphasis>;
}

export interface Timeline {
  steps: StepState[];
  /** Autoplay dwell time per step, in milliseconds. */
  stepDurationMs: number;
}
