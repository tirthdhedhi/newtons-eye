import { z } from "zod";
import { Body, Connection, Contact, Force, Frame, Query, Surface, UserEvent } from "./entities";
import { qty, vec3 } from "./primitives";

export const Scene = z.strictObject({
  version: z.literal(1),
  title: z.string().optional(),
  /** How long to simulate. */
  duration: qty("time").default(10),
  environment: z
    .strictObject({ gravity: vec3("acceleration").default([0, -9.81, 0]) })
    .default({ gravity: [0, -9.81, 0] }),
  frames: z.array(Frame).default([]),
  bodies: z.array(Body).min(1),
  surfaces: z.array(Surface).default([]),
  contacts: z.array(Contact).default([]),
  forces: z.array(Force).default([]),
  connections: z.array(Connection).default([]),
  events: z.array(UserEvent).default([]),
  queries: z.array(Query).default([]),
});

/** A scene after parsing: every quantity is SI, every default is filled in. */
export type Scene = z.output<typeof Scene>;
/** A scene as written in JSON. */
export type SceneInput = z.input<typeof Scene>;
