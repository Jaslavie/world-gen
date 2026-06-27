import { StudioProvider, useStudio } from "./state";
import { Pipeline } from "./components/Pipeline";
import { WorldView } from "./components/WorldView";
import { RightDock } from "./components/RightDock";

function TopBar() {
  const { prompt, setPrompt, phase, generate, busy, elapsedMs } = useStudio();
  const secs = (elapsedMs / 1000).toFixed(1);
  const label =
    phase === "generating" ? "compiling…" : phase === "ready" ? "ready, press Run agent" :
    phase === "running" ? "agent running" : phase === "solved" ? "solved" :
    phase === "error" ? "error" : "idle";
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-surface px-5">
      <div className="flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-md bg-accent text-[13px] font-bold text-white">W</span>
        <span className="text-[15px] font-semibold tracking-tight">World Studio</span>
      </div>
      <div className="mx-2 flex-1">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && generate()}
          placeholder="Describe a world…  e.g. a kitchen: put the apple on the counter"
          className="h-9 w-full max-w-2xl rounded-lg border border-line bg-canvas px-3 text-[13px] text-ink outline-none placeholder:text-faint focus:border-accent/40 focus:ring-2 focus:ring-accent/15"
        />
      </div>
      <span className="flex items-center gap-2 text-[12px] text-muted">
        <span className={`h-2 w-2 rounded-full ${phase === "solved" ? "bg-ok" : phase === "error" ? "bg-bad" : "bg-accent"} ${busy ? "animate-shimmer" : ""}`} />
        {label}
        {(busy || phase === "solved") && elapsedMs > 0 && <span className="tabular-nums text-faint">· {secs}s</span>}
      </span>
      <button onClick={generate} disabled={busy} className="rounded-lg bg-ink px-3.5 py-1.5 text-[13px] font-medium text-white transition hover:opacity-90 disabled:opacity-40">
        Generate
      </button>
    </header>
  );
}

function Studio() {
  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <main className="grid min-h-0 flex-1 grid-cols-[270px_minmax(0,1fr)_348px] gap-4 p-4">
        <Pipeline />
        <WorldView />
        <RightDock />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <StudioProvider>
      <Studio />
    </StudioProvider>
  );
}
