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

export const objUrl = (label: string | null) => (label ? `/assets/objects/${label}.png` : "");
export const tileUrl = (label: string | null) => (label ? `/assets/terrain/${label}.png` : "");
