import type { Quat, Vec3 } from "../math/vec3";

export type Id = string;

/** Positions and velocities of every body, indexed like Model.ids. */
export interface State {
  x: Vec3[];
  v: Vec3[];
}

export type ContactMode = "inactive" | "static" | "sliding";
export type StringMode = "taut" | "slack" | "cut";

/** Which constraint regime each contact and connection is in for one segment. */
export interface Regimes {
  contacts: ContactMode[];
  /** Unit direction of kinetic friction on the body when sliding starts from rest. */
  slideDir: (Vec3 | null)[];
  strings: StringMode[];
}

export type ForceKind = "gravity" | "applied" | "spring" | "normal" | "friction" | "tension";

export interface ForceRecord {
  id: string;
  kind: ForceKind;
  body: Id;
  /** Force on the body, world frame, newtons. */
  vector: Vec3;
  /** World-space application point. */
  point: Vec3;
  detail?: "static" | "kinetic";
}

export interface BodyState {
  position: Vec3;
  velocity: Vec3;
  acceleration: Vec3;
  orientation: Quat;
  angularVelocity: Vec3;
}

export interface ContactSnapshot {
  body: Id;
  surface: Id;
  mode: ContactMode;
}

export interface StringSnapshot {
  id: Id;
  mode: StringMode;
}

export interface Snapshot {
  t: number;
  bodies: Record<Id, BodyState>;
  forces: ForceRecord[];
  contacts: ContactSnapshot[];
  strings: StringSnapshot[];
}

export type EventKind =
  | "stop"
  | "edge"
  | "land"
  | "lift"
  | "slack"
  | "taut"
  | "slide_start"
  | "release"
  | "cut_string"
  | "set_force"
  | "force_on"
  | "force_off";

export interface SolvedEvent {
  t: number;
  kind: EventKind;
  body?: Id;
  connection?: Id;
  /** Id of the user event or force this came from. */
  ref?: Id;
  description: string;
}

export interface Motion {
  kind: "analytic" | "rk4";
  stateAt(t: number): State;
}

export interface Segment {
  t0: number;
  t1: number;
  regimes: Regimes;
  motion: Motion;
}
