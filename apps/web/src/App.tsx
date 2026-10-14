import { SCENE_VERSION } from "@newtons-eye/core";

export function App() {
  return (
    <main className="p-6">
      <h1 className="text-xl font-semibold">Newton&apos;s Eye</h1>
      <p>Scene schema v{SCENE_VERSION}</p>
    </main>
  );
}
