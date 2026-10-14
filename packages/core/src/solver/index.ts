import type { Scene } from "../schema";
import { evaluateQuery } from "./queries";
import type { Answer } from "./queries";
import { simulate } from "./simulate";
import type { Timeline } from "./simulate";

export interface Solution {
  timeline: Timeline;
  answers: Answer[];
}

/** Solve a validated, SI scene: simulate it and answer its queries. */
export function solve(scene: Scene): Solution {
  const timeline = simulate(scene);
  return { timeline, answers: scene.queries.map((q) => evaluateQuery(timeline, q)) };
}

export type { Answer } from "./queries";
export type { Timeline } from "./simulate";
export type {
  BodyState,
  ContactSnapshot,
  EventKind,
  ForceKind,
  ForceRecord,
  Segment,
  Snapshot,
  SolvedEvent,
  StringSnapshot,
} from "./types";
