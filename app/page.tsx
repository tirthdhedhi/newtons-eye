export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-4 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">Newton&apos;s Eye</h1>
        <p className="text-slate-600">
          Paste a physics problem. Get a verified answer and a step-by-step free-body diagram.
        </p>
      </header>
      <label htmlFor="problem" className="sr-only">
        Physics problem
      </label>
      <textarea
        id="problem"
        name="problem"
        rows={8}
        placeholder="A 5.0 kg block rests on a 30° incline with μs = 0.6 and μk = 0.4..."
        className="w-full rounded-lg border border-slate-300 p-3 font-mono text-sm focus:ring-2 focus:ring-slate-400 focus:outline-none"
      />
      <button
        type="button"
        disabled
        className="self-start rounded-lg bg-slate-900 px-5 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        Visualize
      </button>
    </main>
  );
}
