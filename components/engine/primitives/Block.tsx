import type { Emphasis, BlockPrimitive } from "../types";

export interface BlockProps {
  primitive: BlockPrimitive;
  emphasis: Emphasis;
}

/** TODO(renderer): draw a block primitive. Kept renderer-agnostic until we pick 2D vs 3D. */
export default function Block(_props: BlockProps) {
  return null;
}
