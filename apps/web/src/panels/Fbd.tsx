import type { Snapshot } from "@newtons-eye/core";
import { fbdArrows, fmt } from "../lib/fbd";
import { FORCE_COLOR } from "../viewer/Viewer3D";

const SIZE = 260;
const C = SIZE / 2;
const MAX = 96;

export function Fbd({ snapshot, bodyId }: { snapshot: Snapshot; bodyId: string }) {
  const arrows = fbdArrows(snapshot.forces, bodyId, MAX);
  const net = snapshot.forces
    .filter((f) => f.body === bodyId)
    .reduce<[number, number, number]>(
      (a, f) => [a[0] + f.vector[0], a[1] + f.vector[1], a[2] + f.vector[2]],
      [0, 0, 0],
    );
  return (
    <div>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="w-full max-w-xs"
        role="img"
        aria-label={`Free body diagram of ${bodyId}`}
      >
        <defs>
          {Object.entries(FORCE_COLOR).map(([k, c]) => (
            <marker
              key={k}
              id={`head-${k}`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0 0 L10 5 L0 10 z" fill={c} />
            </marker>
          ))}
        </defs>
        <rect
          x={C - 12}
          y={C - 12}
          width="24"
          height="24"
          rx="3"
          fill="currentColor"
          opacity="0.18"
          stroke="currentColor"
        />
        {arrows.map((a) => (
          <line
            key={a.id}
            x1={C}
            y1={C}
            x2={C + a.dx}
            y2={C + a.dy}
            stroke={FORCE_COLOR[a.kind]}
            strokeWidth="2.5"
            markerEnd={`url(#head-${a.kind})`}
          />
        ))}
      </svg>
      <ul className="mt-2 space-y-1 text-sm">
        {arrows.map((a) => (
          <li key={a.id} className="flex items-center gap-2">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: FORCE_COLOR[a.kind] }}
            />
            {a.label}
          </li>
        ))}
        <li className="pt-1 font-medium">
          Net: ({fmt(net[0])}, {fmt(net[1])}, {fmt(net[2])}) N
        </li>
      </ul>
    </div>
  );
}
