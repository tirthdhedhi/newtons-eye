import type { ArchetypeTemplateProps } from "@/lib/archetypes/registry";
import type { InclineInput } from "./schema";

/**
 * Builds the incline scene from solver output and renders it with engine primitives.
 * TODO(renderer): map input + solution into a Scene and Timeline.
 */
export default function InclineTemplate({ activeStep }: ArchetypeTemplateProps<InclineInput>) {
  return (
    <div data-archetype="incline" data-active-step={activeStep}>
      Incline diagram not implemented
    </div>
  );
}
