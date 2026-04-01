/**
 * Memori (Memory Management) Types
 */

export interface MemoriFact {
  id: number;
  content: string;
  similarity: number;
  lexicalScore: number;
  rankScore: number;
  createdAt?: string;
  importanceScore?: number;
}

export interface MemoriTriple {
  subjectName: string;
  subjectType?: string;
  predicate: string;
  objectName: string;
  objectType?: string;
}

export interface MemoriStats {
  entityId: string;
  totalFacts: number;
  totalTriples: number;
  avgImportance: number;
}

export interface RecallRequest {
  query: string;
  workspaceId: string;
  entityId?: string;
  conversationId?: string;
  limit?: number;
}

export interface RecallResponse {
  facts: MemoriFact[];
  query: string;
  totalFound: number;
}
