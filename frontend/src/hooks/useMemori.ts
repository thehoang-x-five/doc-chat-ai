/**
 * Custom hook for Memori (Memory Management) operations
 */
import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import type { MemoriFact, MemoriTriple, MemoriStats } from '@/types/memori';

export function useMemori(workspaceId?: string, entityId?: string) {
  const [facts, setFacts] = useState<MemoriFact[]>([]);
  const [triples, setTriples] = useState<MemoriTriple[]>([]);
  const [stats, setStats] = useState<MemoriStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load memory statistics
  const loadStats = useCallback(async () => {
    if (!workspaceId || !entityId) {
      return;
    }

    try {
      const memoryStats = await apiClient.getMemoryStats({
        entityId,
        workspaceId,
      });

      setStats(memoryStats);
    } catch (err) {
      console.error('Failed to load memory stats:', err);
    }
  }, [workspaceId, entityId]);

  // List all facts (no search)
  const listFacts = useCallback(async (limit: number = 100, offset: number = 0) => {
    if (!workspaceId || !entityId) {
      setError('Workspace ID and Entity ID are required');
      return [];
    }

    setLoading(true);
    setError(null);

    try {
      const allFacts = await apiClient.listFacts({
        entityId,
        workspaceId,
        limit,
        offset,
      });

      setFacts(allFacts);
      return allFacts;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to list facts';
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [workspaceId, entityId]);

  // Recall facts for a query
  const recallFacts = useCallback(async (query: string, limit: number = 5) => {
    if (!workspaceId) {
      setError('Workspace ID is required');
      return [];
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.recallFacts({
        query,
        workspaceId,
        entityId,
        limit,
      });

      setFacts(response.facts);
      return response.facts;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to recall facts';
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [workspaceId, entityId]);

  // Add new facts
  const addFacts = useCallback(async (newFacts: Array<{ content: string; importanceScore?: number }>) => {
    if (!workspaceId || !entityId) {
      setError('Workspace ID and Entity ID are required');
      return [];
    }

    setLoading(true);
    setError(null);

    try {
      const factIds = await apiClient.addFacts({
        entityId,
        workspaceId,
        facts: newFacts,
      });

      // Refresh stats after adding facts
      await loadStats();

      return factIds;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add facts';
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [workspaceId, entityId, loadStats]);

  // Load knowledge graph
  const loadKnowledgeGraph = useCallback(async (limit: number = 100) => {
    if (!workspaceId || !entityId) {
      setError('Workspace ID and Entity ID are required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const graphTriples = await apiClient.getKnowledgeGraph({
        entityId,
        workspaceId,
        limit,
      });

      setTriples(graphTriples);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load knowledge graph';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, entityId]);

  // Update fact importance (NEW - Memory Intelligence)
  const updateFactImportance = useCallback(async (factId: number, importanceScore: number) => {
    if (!workspaceId) {
      setError('Workspace ID is required');
      return false;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.updateFactImportance(factId, importanceScore, workspaceId);

      // Update local state
      setFacts(prev => prev.map(f =>
        f.id === factId ? { ...f, importanceScore } : f
      ));

      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update importance';
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  // Delete fact
  const deleteFact = useCallback(async (factId: number) => {
    if (!workspaceId) {
      setError('Workspace ID is required');
      return false;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.deleteFact(factId, workspaceId);
      setFacts(prev => prev.filter(f => f.id !== factId));
      await loadStats();
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete fact';
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, [workspaceId, loadStats]);

  // Pin/unpin fact (NEW - Memory Intelligence)
  const pinFact = useCallback(async (factId: number, pinned: boolean) => {
    if (!workspaceId) {
      setError('Workspace ID is required');
      return false;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.pinFact(factId, pinned, workspaceId);

      // Update local state (pinned = importance 10, unpinned = 1)
      const newImportance = pinned ? 10.0 : 1.0;
      setFacts(prev => prev.map(f =>
        f.id === factId ? { ...f, importanceScore: newImportance } : f
      ));

      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to pin fact';
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  // Load stats on mount
  useEffect(() => {
    if (workspaceId && entityId) {
      loadStats();
    }
  }, [workspaceId, entityId, loadStats]);

  return {
    facts,
    triples,
    stats,
    loading,
    error,
    listFacts,
    recallFacts,
    addFacts,
    updateFactImportance,  // NEW
    pinFact,               // NEW
    deleteFact,
    loadKnowledgeGraph,
    loadStats,
  };
}
