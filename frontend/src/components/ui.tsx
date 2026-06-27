import type { ReactNode } from "react";

export function Panel({ title, tag, children, className = "" }: {
  title?: string; tag?: string; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl2 bg-surface shadow-card ${className}`}>
      {title && (
        <header className="flex items-center justify-between px-4 pt-3 pb-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-faint">{title}</h2>
          {tag && <span className="text-[11px] text-faint">{tag}</span>}
        </header>
      )}
      <div className="px-4 pb-4">{children}</div>
    </section>
  );
}

export function StatusDot({ status }: { status: "idle" | "running" | "done" | "failed" }) {
  const color =
    status === "running" ? "bg-accent" : status === "done" ? "bg-ok" : status === "failed" ? "bg-bad" : "bg-line";
  return (
    <span className={`inline-block h-2 w-2 rounded-full ${color} ${status === "running" ? "animate-shimmer" : ""}`} />
  );
}

export function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 py-1 text-[13px]">
      <span className={`mt-[2px] font-semibold ${ok ? "text-ok" : "text-bad"}`}>{ok ? "✓" : "✗"}</span>
      <span className="text-ink/80">{children}</span>
    </div>
  );
}

export function Bar({ pct, tone = "accent" }: { pct: number; tone?: "accent" | "ok" }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-line">
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${tone === "ok" ? "bg-ok" : "bg-accent"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
