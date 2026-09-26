import type { Emphasis, VectorPrimitive } from "../types";

export interface VectorProps {
  primitive: VectorPrimitive;
  emphasis: Emphasis;
}

/** TODO(renderer): draw a vector primitive. Kept renderer-agnostic until we pick 2D vs 3D. */
export default function Vector(_props: VectorProps) {
  return null;
}
