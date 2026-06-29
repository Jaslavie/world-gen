// Studio state: a thin client over one WebSocket. The server holds the entire UI state
// and streams it continuously; this file just sends commands and renders the last payload

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { Check, Clause, MappedAsset, ToolCall, Vec, World } from "./types";

type Phase = "idle" | "generating" | "ready" | "running" | "solved" | "error";
interface Stage { id: number; name: string; summary: string; status: "idle" | "running" | "done" | "failed"; ms?: number | null }

// payload from the server
interface Snapshot {
  phase: Phase;
  error: string | null;
  stages: Stage[];
  world: World | null;
  checks: Check[];
  assets: MappedAsset[];
  positions: Record<string, Vec>;
  holding: string | null;
  clauses: Clause[];
  toolCalls: ToolCall[];
  success: boolean;
  goalPct: number;
  elapsedMs: number;
}

const EMPTY: Snapshot = {
  phase: "idle", error: null, stages: [], world: null, checks: [], assets: [],
  positions: {}, holding: null, clauses: [], toolCalls: [], success: false,
  goalPct: 0, elapsedMs: 0,
};

interface Studio {
  prompt: string;
  setPrompt: (p: string) => void;
  phase: Phase;
  error: string | null;
  stages: Stage[];
  activeStage: number | null;
  world: World | null;
  positions: Record<string, Vec>;
  holding: string | null;
  clauses: Clause[];
  success: boolean;
  toolCalls: ToolCall[];
  lastCall: ToolCall | null;
  checks: Check[];
  mappedAssets: MappedAsset[];
  goalPct: number;
  elapsedMs: number;
  busy: boolean;
  generate: () => void;
  runAgent: () => void;
}

// Context is a global store of the application state
const Ctx = createContext<Studio | null>(null);
export const useStudio = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useStudio outside provider");
  return c;
};

export function StudioProvider({ children }: { children: React.ReactNode }) {
  const [prompt, setPrompt] = useState("pull the lever to cross water over bridge terrain");
  const [snap, setSnap] = useState<Snapshot>(EMPTY);
  const ws = useRef<WebSocket | null>(null);

  // One persistent connection to the server
  useEffect(() => {
    const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
    const sock = new WebSocket(url);
    ws.current = sock;
    sock.onmessage = (e) => setSnap(JSON.parse(e.data));
    return () => sock.close();
  }, []);

  const send = (msg: Record<string, unknown>) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  };

  // Send generation and run commands to the server
  const generate = useCallback(() => send({ cmd: "generate", prompt }), [prompt]);
  const runAgent = useCallback(() => send({ cmd: "run" }), []);

  const active = snap.stages.findIndex((s) => s.status === "running");
  const value: Studio = {
    prompt, setPrompt,
    phase: snap.phase,
    error: snap.error,
    stages: snap.stages,
    activeStage: active >= 0 ? active : null,
    world: snap.world,
    positions: snap.positions,
    holding: snap.holding,
    clauses: snap.clauses,
    success: snap.success,
    toolCalls: snap.toolCalls,
    lastCall: snap.toolCalls.length ? snap.toolCalls[snap.toolCalls.length - 1] : null,
    checks: snap.checks,
    mappedAssets: snap.assets,
    goalPct: snap.goalPct,
    elapsedMs: snap.elapsedMs,
    busy: snap.phase === "generating" || snap.phase === "running",
    generate, runAgent,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
