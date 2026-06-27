// LEFT column — the full thinking process.
import { useState } from "react";
import { motion } from "framer-motion";
import { useStudio } from "../state";
import { StatusDot } from "./ui";

export function Pipeline() {
  const { stages, activeStage } = useStudio();
  const [pinned, setPinned] = useState<number | null>(null);

  return (
    <aside className="flex min-h-0 flex-col rounded-xl2 bg-surface shadow-card">
      <header className="px-4 pt-4 pb-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-faint">Thinking process</h2>
        <p className="mt-1 text-[12px] leading-snug text-muted">prompt → world → agent, one stage at a time</p>
      </header>
      <ol className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 pb-3">
        {stages.map((s, i) => {
          const isActive = activeStage === i || pinned === i;
          const dim = activeStage !== null && activeStage !== i && pinned !== i;
          return (
            <motion.li
              key={s.id}
              onClick={() => setPinned((p) => (p === i ? null : i))}
              animate={{ opacity: dim ? 0.4 : 1 }}
              transition={{ duration: 0.25 }}
              className={`cursor-pointer rounded-lg border px-3 py-2.5 transition-colors ${
                isActive ? "border-accent/30 bg-accent-soft" : "border-transparent hover:bg-canvas"
              }`}
            >
              <div className="flex items-center gap-2">
                <StatusDot status={s.status} />
                <span className="text-[11px] tabular-nums text-faint">{s.id}</span>
                <span className="text-[13px] font-medium text-ink">{s.name}</span>
                {s.ms !== undefined && (
                  <span className={`ml-auto tabular-nums text-[11px] ${s.status === "running" ? "text-accent" : "text-faint"}`}>
                    {(s.ms / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
              <p className="mt-1 pl-6 text-[12px] leading-snug text-muted">{s.summary}</p>
            </motion.li>
          );
        })}
      </ol>
    </aside>
  );
}
