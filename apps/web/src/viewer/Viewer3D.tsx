import { Canvas } from "@react-three/fiber";
import { Grid, Html, Line, OrbitControls } from "@react-three/drei";
import { useMemo } from "react";
import * as THREE from "three";
import type { ForceKind, Solution } from "@newtons-eye/core";

const FORCE_COLOR: Record<ForceKind, string> = {
  gravity: "#e5484d",
  normal: "#3e63dd",
  friction: "#f76b15",
  tension: "#30a46c",
  applied: "#8e4ec6",
  spring: "#ab6400",
};
const BODY_COLORS = ["#6e9bd1", "#d19a6e", "#7fbf9a", "#c78fb8"];

const v3 = (a: readonly number[]) => new THREE.Vector3(a[0] ?? 0, a[1] ?? 0, a[2] ?? 0);

/** Largest force magnitude seen over the whole simulation, for a stable arrow scale. */
function maxForce(solution: Solution): number {
  let best = 1e-9;
  const n = 40;
  for (let i = 0; i <= n; i++) {
    for (const f of solution.timeline.at((solution.timeline.duration * i) / n).forces) {
      best = Math.max(best, Math.hypot(f.vector[0], f.vector[1], f.vector[2]));
    }
  }
  return best;
}

function sceneBounds(solution: Solution): { center: THREE.Vector3; radius: number } {
  const model = solution.timeline.model;
  const start = solution.timeline.at(0);
  const anchor = new THREE.Box3();
  for (const b of Object.values(start.bodies)) anchor.expandByPoint(v3(b.position));
  for (const p of model.planes) {
    anchor.expandByPoint(v3(p.P));
    if (p.extent) anchor.expandByPoint(v3(p.P).addScaledVector(v3(p.u), p.extent.length));
  }
  for (const st of model.strings) {
    anchor.expandByPoint(v3(st.PA));
    anchor.expandByPoint(v3(st.PB));
  }
  // Include where bodies go, but ignore runaway free fall far from the setup.
  const near = anchor.clone().expandByScalar(2.5);
  const box = anchor.clone();
  const n = 30;
  for (let i = 0; i <= n; i++) {
    const s = solution.timeline.at((solution.timeline.duration * i) / n);
    for (const b of Object.values(s.bodies)) {
      const p = v3(b.position);
      if (near.containsPoint(p)) box.expandByPoint(p);
    }
  }
  const size = box.getSize(new THREE.Vector3());
  return { center: box.getCenter(new THREE.Vector3()), radius: Math.max(size.length() / 2, 1.2) };
}

function PlaneMesh({ solution, index }: { solution: Solution; index: number }) {
  const p = solution.timeline.model.planes[index];
  if (!p) return null;
  const L = p.extent?.length ?? 16;
  const W = p.extent?.width ?? (p.extent ? 1 : 16);
  const basis = new THREE.Matrix4().makeBasis(v3(p.u), v3(p.n), v3(p.w));
  const quat = new THREE.Quaternion().setFromRotationMatrix(basis);
  const center = v3(p.P)
    .addScaledVector(v3(p.u), p.extent ? L / 2 : 0)
    .addScaledVector(v3(p.n), -0.01);
  return (
    <mesh position={center} quaternion={quat} receiveShadow>
      <boxGeometry args={[L, 0.02, W]} />
      <meshStandardMaterial color="#9aa5b1" transparent opacity={0.55} />
    </mesh>
  );
}

function Arrow({
  origin,
  vector,
  color,
  scale,
}: {
  origin: THREE.Vector3;
  vector: THREE.Vector3;
  color: string;
  scale: number;
}) {
  const length = vector.length() * scale;
  if (length < 1e-3) return null;
  const dir = vector.clone().normalize();
  return <arrowHelper args={[dir, origin, length, color, Math.min(0.25, length * 0.35), 0.12]} />;
}

export function Viewer3D({
  solution,
  t,
  showForces,
}: {
  solution: Solution;
  t: number;
  showForces: boolean;
}) {
  const model = solution.timeline.model;
  const snap = solution.timeline.at(t);
  const fmax = useMemo(() => maxForce(solution), [solution]);
  const { center, radius } = useMemo(() => sceneBounds(solution), [solution]);
  const arrowScale = 1.2 / fmax;
  const bodies = model.scene.bodies;

  return (
    <Canvas
      camera={{ position: [center.x, center.y + radius * 0.5, center.z + radius * 2.2], fov: 45 }}
      shadows
    >
      <color attach="background" args={["#10151c"]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[5, 10, 6]} intensity={1.4} castShadow />
      <OrbitControls target={center} makeDefault />
      <Grid
        args={[40, 40]}
        position={[0, -0.02, 0]}
        cellColor="#2b3541"
        sectionColor="#3a4757"
        fadeDistance={30}
        infiniteGrid
      />
      {model.planes.map((p, i) => (
        <PlaneMesh key={p.id} solution={solution} index={i} />
      ))}
      {bodies.map((b, i) => {
        const s = snap.bodies[b.id];
        if (!s) return null;
        const color = BODY_COLORS[i % BODY_COLORS.length] ?? "#6e9bd1";
        const quat = new THREE.Quaternion(...s.orientation);
        return (
          <group key={b.id} position={v3(s.position)} quaternion={quat}>
            <mesh castShadow>
              {b.shape.kind === "box" && <boxGeometry args={b.shape.size} />}
              {b.shape.kind === "sphere" && <sphereGeometry args={[b.shape.radius, 24, 16]} />}
              {b.shape.kind === "point" && <sphereGeometry args={[0.06, 16, 12]} />}
              <meshStandardMaterial color={color} />
            </mesh>
            <Html
              center
              distanceFactor={9}
              position={[0, 0.35, 0]}
              style={{ pointerEvents: "none" }}
            >
              <span className="rounded bg-black/60 px-1.5 py-0.5 text-xs whitespace-nowrap text-white">
                {b.id}
              </span>
            </Html>
          </group>
        );
      })}
      {model.strings.map((st) => {
        const mode = snap.strings.find((x) => x.id === st.id)?.mode;
        if (mode === "cut") return null;
        const a = snap.bodies[model.ids[st.a] ?? ""]?.position;
        const b = snap.bodies[model.ids[st.b] ?? ""]?.position;
        if (!a || !b) return null;
        const pts: THREE.Vector3[] =
          st.kind === "pulley" ? [v3(a), v3(st.PA), v3(st.PB), v3(b)] : [v3(a), v3(b)];
        return (
          <group key={st.id}>
            <Line
              points={pts}
              color={mode === "slack" ? "#6b7280" : "#e6e1d3"}
              lineWidth={mode === "slack" ? 1 : 2}
              dashed={mode === "slack"}
              dashSize={0.1}
              gapSize={0.08}
            />
            {st.kind === "pulley" && (
              <mesh position={v3(st.PA).add(v3(st.PB)).multiplyScalar(0.5)}>
                <sphereGeometry args={[0.07, 16, 12]} />
                <meshStandardMaterial color="#c9ced6" />
              </mesh>
            )}
          </group>
        );
      })}
      {showForces &&
        snap.forces.map((f) => (
          <Arrow
            key={f.id}
            origin={v3(f.point)}
            vector={v3(f.vector)}
            color={FORCE_COLOR[f.kind]}
            scale={arrowScale}
          />
        ))}
    </Canvas>
  );
}

export { FORCE_COLOR };
