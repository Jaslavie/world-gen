// RIGHT — live observability panels.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useStudio } from "../state";
import { Bar, Check, Panel } from "./ui";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="px-1 text-[10px] font-semibold uppercase tracking-widest text-faint">{title}</h2>
      {children}
    </div>
  );
}

function PromptBlock() {
  const { prompt, world } = useStudio();
  const text = world?.prompt ?? prompt;
  // highlight the object-words the harness actually extracted (entity types)
  const words = Array.from(new Set((world?.entities ?? []).map((e) => e.type).filter((t) => t !== "agent")));
  const parts = words.length ? text.split(new RegExp(`(${words.join("|")})`, "gi")) : [text];
  return (
    <Panel title="Prompt breakdown">
      <p className="text-[14px] leading-relaxed text-ink">
        {parts.map((p, i) =>
          words.some((w) => w.toLowerCase() === p.toLowerCase()) ? (
            <motion.mark
              key={i}
              animate={{ backgroundColor: "#EEF0FF" }}
              className="rounded px-1 font-medium text-accent"
            >
              {p}
            </motion.mark>
          ) : (
            <span key={i}>{p}</span>
          ),
        )}
      </p>
    </Panel>
  );
}

function MappedAssets() {
  const { mappedAssets } = useStudio();
  return (
    <Panel title="Objects" tag={mappedAssets.length ? `${mappedAssets.length} objects` : undefined}>
      {mappedAssets.length === 0 ? (
        <p className="text-[13px] text-faint">objects appear here once compiled</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <AnimatePresence>
            {mappedAssets.map((a, i) => (
              <motion.div
                key={a.label + i}
                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ delay: i * 0.1, duration: 0.3 }}
                className="rounded-lg border border-line bg-canvas p-2 text-center"
              >
                {a.png ? (
                  <img src={a.png} alt={a.label} className="pixelated mx-auto h-10 w-10 object-contain" />
                ) : (
                  <div className="mx-auto h-10 w-10 rounded bg-line" />
                )}
                <div className="mt-1 truncate text-[11px] font-medium text-ink">{a.word}</div>
                <div className="truncate text-[10px] text-faint">{a.label}</div>
                <div className={`mt-0.5 text-[9px] font-medium uppercase tracking-wide ${
                  a.source === "generated" ? "text-accent" : a.source === "catalog" ? "text-ok" : "text-faint"
                }`}>
                  {a.source === "generated" ? "generated" : a.source === "catalog" ? "catalog" : "missing"}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </Panel>
  );
}

function Validator() {
  const { checks } = useStudio();
  const [open, setOpen] = useState(false);
  const passed = checks.filter((c) => c.passed).length;
  return (
    <Panel title="Validator" tag="physics correctness">
      {checks.length === 0 ? (
        <p className="text-[13px] text-faint">awaiting grounding checks…</p>
      ) : (
        <>
          <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between">
            <span className="text-[13px] text-ink">
              <span className="font-semibold text-ok">{passed}</span>
              <span className="text-faint"> / {checks.length} validated</span>
            </span>
            <span className="text-[11px] text-faint">{open ? "hide" : "details"}</span>
          </button>
          <Bar pct={(passed / checks.length) * 100} tone="ok" />
          <AnimatePresence>
            {open && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="mt-2 overflow-hidden">
                {checks.map((c) => (
                  <Check key={c.name} ok={c.passed}>
                    <span className="font-medium">{c.name}</span> — <span className="text-muted">{c.message}</span>
                  </Check>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </Panel>
  );
}

function Goal() {
  const { goalPct, clauses, success } = useStudio();
  return (
    <Panel title="Goal status" tag="agent progress">
      <div className="mb-1 flex items-end justify-between">
        <span className={`text-2xl font-semibold tabular-nums ${success ? "text-ok" : "text-ink"}`}>{goalPct}%</span>
        {success && <span className="text-[12px] font-semibold text-ok">complete</span>}
      </div>
      <Bar pct={goalPct} tone={success ? "ok" : "accent"} />
      <div className="mt-2 space-y-0.5">
        {clauses.map((c) => (
          <Check key={c.clause} ok={c.satisfied}>
            <span className="font-mono text-[12px]">{c.clause}</span>
          </Check>
        ))}
      </div>
    </Panel>
  );
}

function ToolCalls() {
  const { toolCalls, phase, success } = useStudio();
  const [showAll, setShowAll] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [toolCalls.length]);
  const shown = showAll ? toolCalls : toolCalls.slice(-6);
  return (
    <Panel title="Tool calls" tag={toolCalls.length ? `${toolCalls.length} total` : undefined}>
      {toolCalls.length === 0 ? (
        <p className="text-[13px] text-faint">waiting for the agent…</p>
      ) : (
        <>
          <div className="max-h-44 space-y-1 overflow-y-auto pr-1">
            {shown.map((c) => (
              <div key={c.n} className="flex items-center gap-2 rounded-md bg-canvas px-2 py-1 text-[12px]">
                <span className="font-mono font-medium text-accent">{c.tool}</span>
                {c.arg && <span className="font-mono text-ink/70">{c.arg}</span>}
              </div>
            ))}
            {phase === "running" && !success && (
              <div className="flex items-center gap-2 px-2 py-1 text-[12px] text-muted">
                <span className="animate-shimmer">●</span>
                <span className="animate-shimmer">agent is thinking…</span>
              </div>
            )}
            <div ref={endRef} />
          </div>
          {toolCalls.length > 6 && (
            <button onClick={() => setShowAll((s) => !s)} className="mt-2 text-[11px] text-faint hover:text-muted">
              {showAll ? "collapse" : `view full audit log (${toolCalls.length})`}
            </button>
          )}
        </>
      )}
    </Panel>
  );
}

export function RightDock() {
  return (
    <aside className="flex min-h-0 flex-col gap-5 overflow-y-auto pr-1">
      <Section title="World generation">
        <PromptBlock />
        <MappedAssets />
        <Validator />
      </Section>
      <Section title="World interaction">
        <Goal />
        <ToolCalls />
      </Section>
    </aside>
  );
}
