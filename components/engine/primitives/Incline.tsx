import type { Emphasis, InclinePrimitive } from "../types";

export interface InclineProps {
  primitive: InclinePrimitive;
  emphasis: Emphasis;
}

/** TODO(renderer): draw a incline primitive. Kept renderer-agnostic until we pick 2D vs 3D. */
export default function Incline(_props: InclineProps) {
  return null;
}
