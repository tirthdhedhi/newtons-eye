import { useEffect, useMemo, useState } from "react";
import { parseScene, solve } from "@newtons-eye/core";
import type { Issue, Solution } from "@newtons-eye/core";
import { EXAMPLES } from "./lib/examples";
import { fmt } from "./lib/fbd";
import { usePlayback } from "./lib/playback";
import { Answers } from "./panels/Answers";
import { Fbd } from "./panels/Fbd";
import { Viewer3D } from "./viewer/Viewer3D";

type Result = { ok: true; solution: Solution; warnings: Issue[] } | { ok: false; errors: Issue[] };

function run(text: string): Result {
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch (e) {
    return {
      ok: false,
      errors: [{ path: "JSON", message: e instanceof Error ? e.message : "invalid JSON" }],
    };
  }
  const parsed = parseScene(json);
  if (!parsed.ok) return { ok: false, errors: parsed.errors };
  try {
    return { ok: true, solution: solve(parsed.scene), warnings: parsed.warnings };
  } catch (e) {
    return {
      ok: false,
      errors: [{ path: "solver", message: e instanceof Error ? e.message : "solver failed" }],
    };
  }
}

const pretty = (json: unknown) => JSON.stringify(json, null, 2);

export function App() {
  const params = new URLSearchParams(window.location.search);
  const [exampleName, setExampleName] = useState(() => {
    const wanted = params.get("example");
    return EXAMPLES.find((e) => e.name === wanted)?.name ?? EXAMPLES[0]?.name ?? "";
  });
  const example = EXAMPLES.find((e) => e.name === exampleName);
  const [draft, setDraft] = useState(() => pretty(example?.json ?? {}));
  const [applied, setApplied] = useState(draft);
  const [showForces, setShowForces] = useState(true);
  const [body, setBody] = useState<string | null>(null);

  const result = useMemo(() => run(applied), [applied]);
  const duration = result.ok ? result.solution.timeline.duration : 0;
  const play = usePlayback(duration);

  const startAt = Number(params.get("t"));
  const { seek } = play;
  useEffect(() => {
    if (startAt > 0 && duration > 0) seek(startAt);
  }, [startAt, duration, seek]);

  const pick = (name: string) => {
    const ex = EXAMPLES.find((e) => e.name === name);
    if (!ex) return;
    const text = pretty(ex.json);
    setExampleName(name);
    setDraft(text);
    setApplied(text);
    setBody(null);
    play.reset();
  };
  const apply = () => {
    setApplied(draft);
    play.reset();
  };

  const snapshot = result.ok ? result.solution.timeline.at(play.t) : null;
  const bodyIds = result.ok ? result.solution.timeline.model.ids : [];
  const selected = body && bodyIds.includes(body) ? body : (bodyIds[0] ?? null);
  const events = result.ok ? result.solution.timeline.events : [];
  const isExample = example !== undefined && pretty(example.json) === applied;

  return (
    <div className="grid h-screen grid-cols-1 grid-rows-[auto_1fr] bg-[#0c1117] text-slate-200 lg:grid-cols-[22rem_1fr_21rem] lg:grid-rows-1">
      <aside className="flex min-h-0 flex-col gap-2 border-b border-white/10 p-4 lg:border-r lg:border-b-0">
        <h1 className="text-lg font-semibold">Newton&apos;s Eye</h1>
        <label className="text-xs opacity-70" htmlFor="example">
          Example scene
        </label>
        <select
          id="example"
          value={exampleName}
          onChange={(e) => pick(e.target.value)}
          className="rounded border border-white/15 bg-[#161d27] p-2 text-sm"
        >
          {EXAMPLES.map((e) => (
            <option key={e.name} value={e.name}>
              {e.name}
            </option>
          ))}
        </select>
        <p className="text-xs opacity-70">{example?.title}</p>
        <label className="text-xs opacity-70" htmlFor="json">
          Scene JSON (givens only)
        </label>
        <textarea
          id="json"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") apply();
          }}
          spellCheck={false}
          className="min-h-48 flex-1 resize-none rounded border border-white/15 bg-[#0f151d] p-2 font-mono text-xs"
        />
        <button
          onClick={apply}
          className="rounded bg-blue-600 px-3 py-2 text-sm font-medium hover:bg-blue-500"
        >
          Solve (Ctrl/Cmd+Enter)
        </button>
        {!result.ok && (
          <ul
            className="max-h-40 overflow-auto rounded border border-red-500/40 bg-red-950/40 p-2 text-xs"
            role="alert"
          >
            {result.errors.map((e, i) => (
              <li key={i}>
                <span className="font-mono">{e.path}</span>: {e.message}
              </li>
            ))}
          </ul>
        )}
        {result.ok && result.warnings.length > 0 && (
          <ul className="rounded border border-amber-500/40 bg-amber-950/30 p-2 text-xs">
            {result.warnings.map((w, i) => (
              <li key={i}>
                <span className="font-mono">{w.path}</span>: {w.message}
              </li>
            ))}
          </ul>
        )}
      </aside>

      <main className="relative flex min-h-[28rem] min-w-0 flex-col">
        <div className="relative min-h-0 flex-1">
          {result.ok ? (
            <div className="absolute inset-0">
              <Viewer3D solution={result.solution} t={play.t} showForces={showForces} />
            </div>
          ) : (
            <div className="grid h-full place-items-center text-sm opacity-60">
              Fix the scene JSON to see the simulation.
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-white/10 bg-[#0f151d] p-3 text-sm">
          <button
            onClick={play.toggle}
            disabled={!result.ok}
            className="w-20 rounded bg-slate-700 px-3 py-1.5 hover:bg-slate-600 disabled:opacity-40"
          >
            {play.playing ? "Pause" : "Play"}
          </button>
          <input
            type="range"
            aria-label="Time"
            min={0}
            max={duration || 1}
            step={0.001}
            value={play.t}
            onChange={(e) => play.seek(Number(e.target.value))}
            disabled={!result.ok}
            className="min-w-40 flex-1"
          />
          <span className="w-28 text-right font-mono">
            {fmt(play.t, 4)} / {fmt(duration, 4)} s
          </span>
          <select
            aria-label="Speed"
            value={play.speed}
            onChange={(e) => play.setSpeed(Number(e.target.value))}
            className="rounded border border-white/15 bg-[#161d27] p-1"
          >
            {[0.25, 0.5, 1, 2].map((s) => (
              <option key={s} value={s}>
                {s}x
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showForces}
              onChange={(e) => setShowForces(e.target.checked)}
            />
            Force arrows
          </label>
        </div>
        {events.length > 0 && (
          <ol className="flex max-h-20 flex-wrap gap-x-4 gap-y-1 overflow-auto border-t border-white/10 px-3 py-2 text-xs">
            {events.map((e, i) => (
              <li key={i}>
                <button className="underline decoration-dotted" onClick={() => play.seek(e.t)}>
                  {fmt(e.t, 4)} s
                </button>{" "}
                {e.description}
              </li>
            ))}
          </ol>
        )}
      </main>

      <aside className="min-h-0 overflow-auto border-t border-white/10 p-4 lg:border-t-0 lg:border-l">
        <h2 className="mb-2 font-semibold">Free body diagram</h2>
        {result.ok && snapshot && selected ? (
          <>
            <select
              aria-label="Body"
              value={selected}
              onChange={(e) => setBody(e.target.value)}
              className="mb-2 rounded border border-white/15 bg-[#161d27] p-1 text-sm"
            >
              {bodyIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
            <Fbd snapshot={snapshot} bodyId={selected} />
            <h3 className="mt-3 text-sm font-medium">Motion</h3>
            <p className="font-mono text-xs">
              v = ({snapshot.bodies[selected]?.velocity.map((c) => fmt(c)).join(", ")}) m/s
              <br />a = ({snapshot.bodies[selected]?.acceleration.map((c) => fmt(c)).join(", ")})
              m/s²
            </p>
          </>
        ) : (
          <p className="text-sm opacity-60">No solved scene.</p>
        )}
        <h2 className="mt-5 mb-2 font-semibold">Answers</h2>
        {result.ok && (
          <Answers
            answers={result.solution.answers}
            expected={isExample ? example?.expected : undefined}
          />
        )}
      </aside>
    </div>
  );
}
