export interface SemanticMemoryItem {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  category: "preference" | "fact" | "rule" | "status";
  confidence: number;
  version: number;
  updated_at: string;
  source_episodic_id: string | null;
}
