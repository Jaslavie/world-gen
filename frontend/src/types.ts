export type Vec = [number, number];

export interface Entity {
  id: string;
  type: string;
  pos: Vec;
  components: string[];
  sprite: string | null; // catalog label
}

export interface Check {
  name: string;
  passed: boolean;
  message: string;
}

export interface MappedAsset {
  word: string;
  label: string;
  png: string;
  source: "catalog" | "generated" | "missing";
}

export interface Clause {
  clause: string;
  satisfied: boolean;
}

export interface ToolCall {
  n: number;
  tool: string;
  arg?: string | null;
}

export interface World {
  gridW: number;
  gridH: number;
  tiles: (string | null)[][]; // [y][x] terrain label
  entities: Entity[];
  objective: string;
  clauses: string[];
  prompt: string;
}

// labels: gen_entity_foo | objects/rock | terrain/dirt
export const spriteUrl = (label: string | null) => {
  if (!label) return "";
  if (label.startsWith("gen_")) return `/generated/${label}.png`;
  if (label.includes("/")) return `/assets/${label}.png`;
  return `/assets/terrain/${label}.png`;
};
export const objUrl = spriteUrl;
export const tileUrl = spriteUrl;
