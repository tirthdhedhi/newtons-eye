import type { Emphasis, LabelPrimitive } from "../types";

export interface LabelProps {
  primitive: LabelPrimitive;
  emphasis: Emphasis;
}

/** TODO(renderer): draw a label primitive. Kept renderer-agnostic until we pick 2D vs 3D. */
export default function Label(_props: LabelProps) {
  return null;
}
