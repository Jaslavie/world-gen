// MIDDLE — the interactive world (rendered from backend tiles/entities) + the
import { motion } from "framer-motion";
import { useStudio } from "../state";
import { objUrl, tileUrl } from "../types";

const CELL = 46;

function Controls() {
  const { lastCall } = useStudio();
  const dir = lastCall?.tool === "move" ? lastCall.arg : undefined;
  const tool = lastCall?.tool;
  const cls = (on: boolean) =>
    `grid h-9 w-9 place-items-center rounded-lg border text-[12px] font-medium transition-all ${
      on
        ? "scale-110 border-accent bg-accent text-white shadow-pop"
        : "border-line bg-surface text-muted"
    }`;
  const wide = (on: boolean) =>
    `rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-all ${
      on
        ? "scale-105 border-accent bg-accent text-white"
        : "border-line bg-surface text-muted"
    }`;
  return (
    <div className="absolute bottom-4 right-4 select-none rounded-xl2 border border-line bg-surface/90 p-2.5 shadow-card backdrop-blur">
      <div className="mb-2 grid grid-cols-3 gap-1">
        <span />
        <button className={cls(dir === "up")} aria-label="move up">
          ↑
        </button>
        <span />
        <button className={cls(dir === "left")} aria-label="move left">
          ←
        </button>
        <button className={cls(dir === "down")} aria-label="move down">
          ↓
        </button>
        <button className={cls(dir === "right")} aria-label="move right">
          →
        </button>
      </div>
      <div className="flex gap-1">
        <button className={wide(tool === "pick")}>pick</button>
        <button className={wide(tool === "place")}>place</button>
        <button className={wide(tool === "toggle")}>toggle</button>
      </div>
    </div>
  );
}

export function WorldView() {
  const { world, positions, success, phase, runAgent, error } = useStudio();

  if (!world) {
    const failed = phase === "error";
    return (
      <div className="grid place-items-center rounded-xl2 bg-surface text-center shadow-card">
        <div className="max-w-sm px-6">
          <div
            className={`mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl2 ${failed ? "bg-bad/10 text-bad" : "bg-accent-soft text-accent"}`}
          >
            {failed ? "!" : "▦"}
          </div>
          <p className="text-[14px] font-medium text-ink">
            {phase === "generating"
              ? "Compiling your world…"
              : failed
                ? "Generation failed"
                : "Describe a world to begin"}
          </p>
          {failed && error ? (
            <p className="mt-2 rounded-lg bg-bad/5 px-3 py-2 text-left font-mono text-[12px] leading-snug text-bad">
              {error}
            </p>
          ) : (
            <p className="mt-1 text-[12px] leading-snug text-muted">
              Type a prompt above and hit Generate.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="relative grid min-h-0 place-items-center rounded-xl2 bg-surface shadow-card">
      <div
        className="relative overflow-hidden rounded-lg ring-1 ring-line"
        style={{ width: world.gridW * CELL, height: world.gridH * CELL }}
      >
        {world.tiles.flatMap((row, y) =>
          row.map((label, x) => {
            const src = tileUrl(label);
            const style = {
              left: x * CELL,
              top: y * CELL,
              width: CELL,
              height: CELL,
            };
            return src ? (
              <img
                key={`${x},${y}`}
                src={src}
                alt=""
                className="pixelated absolute"
                style={style}
              />
            ) : (
              <div
                key={`${x},${y}`}
                className="absolute bg-[#e8e4dc]"
                style={style}
              />
            );
          }),
        )}
        {world.entities.map((e) => {
          const [x, y] = positions[e.id] ?? e.pos;
          const src = objUrl(e.sprite);
          const style = {
            width: CELL,
            height: CELL,
            left: 0,
            top: 0,
            zIndex: e.type === "agent" ? 30 : 10,
          };
          return src ? (
            <motion.img
              key={e.id}
              src={src}
              alt={e.type}
              className="pixelated absolute drop-shadow"
              style={style}
              animate={{ x: x * CELL, y: y * CELL }}
              transition={{ type: "tween", ease: "easeInOut", duration: 0.35 }}
            />
          ) : (
            <motion.div
              key={e.id}
              className="absolute rounded-sm bg-accent/30 ring-1 ring-accent/40"
              style={style}
              animate={{ x: x * CELL, y: y * CELL }}
              transition={{ type: "tween", ease: "easeInOut", duration: 0.35 }}
            />
          );
        })}
      </div>
      {/* top-center run control / live status */}
      <div className="absolute left-1/2 top-4 -translate-x-1/2">
        {phase === "ready" && (
          <motion.button
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            onClick={runAgent}
            className="flex items-center gap-2 rounded-full bg-ink px-5 py-2 text-[13px] font-semibold text-white shadow-pop transition hover:opacity-90"
          >
            ▶ Run agent
          </motion.button>
        )}
        {phase === "running" && !success && (
          <div className="flex items-center gap-2 rounded-full bg-accent px-4 py-1.5 text-[13px] font-semibold text-white shadow-pop">
            <span className="h-2 w-2 rounded-full bg-white animate-shimmer" />{" "}
            agent running…
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 rounded-full bg-ok px-4 py-1.5 text-[13px] font-semibold text-white shadow-pop">
            ✓ solved
            <button
              onClick={runAgent}
              className="ml-1 rounded-full bg-white/20 px-2 py-0.5 text-[11px] font-medium hover:bg-white/30"
            >
              ↻ run again
            </button>
          </div>
        )}
      </div>
      <Controls />
    </div>
  );
}
