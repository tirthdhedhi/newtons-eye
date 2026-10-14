import type { Answer } from "@newtons-eye/core";
import type { ExpectedFile } from "../lib/examples";
import { fmt } from "../lib/fbd";

const show = (v: number | number[] | undefined): string =>
  v === undefined ? "-" : Array.isArray(v) ? `(${v.map((c) => fmt(c)).join(", ")})` : fmt(v);

function matches(
  got: Answer["value"],
  want: number | number[] | undefined,
  tol: number,
): boolean | null {
  if (got === undefined || want === undefined) return null;
  if (Array.isArray(want)) {
    return Array.isArray(got) && want.every((c, i) => Math.abs((got[i] ?? NaN) - c) < tol);
  }
  return typeof got === "number" && Math.abs(got - want) < tol;
}

export function Answers({
  answers,
  expected,
}: {
  answers: Answer[];
  expected: ExpectedFile | undefined;
}) {
  if (answers.length === 0) return <p className="text-sm opacity-70">This scene has no queries.</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left opacity-70">
          <th className="py-1 pr-2 font-normal">Query</th>
          <th className="py-1 pr-2 font-normal">Solver</th>
          {expected && <th className="py-1 font-normal">Hand-computed</th>}
        </tr>
      </thead>
      <tbody>
        {answers.map((a) => {
          const want = expected?.answers[a.id];
          const ok = expected ? matches(a.value, want?.value, expected.tolerance) : null;
          return (
            <tr key={a.id} className="border-t border-white/10 align-top">
              <td className="py-1 pr-2">
                {a.id}
                <div className="text-xs opacity-60">{a.ask}</div>
              </td>
              <td className="py-1 pr-2 font-mono">
                {a.error ? (
                  <span className="text-red-400">{a.error}</span>
                ) : (
                  `${show(a.value)} ${a.unit}`
                )}
              </td>
              {expected && (
                <td className="py-1 font-mono">
                  {show(want?.value)} {want?.unit}
                  {ok !== null && (
                    <span className={ok ? "ml-2 text-green-400" : "ml-2 text-red-400"}>
                      {ok ? "match" : "differs"}
                    </span>
                  )}
                </td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
