/**
 * Fact Management Panel - View, add, edit, and delete facts
 */
import { useState, useEffect } from 'react';
import { Plus, Trash2, Search, TrendingUp, Pin, Star } from 'lucide-react';
import { useMemori } from '@/hooks/useMemori';
import { useI18n } from '@/lib/i18n';
import { useOutletContext } from 'react-router-dom';
import type { AppOutletContext } from '@/App';

interface FactManagementPanelProps {
  workspaceId: string;
  entityId: string;
  onClose?: () => void;
}

export function FactManagementPanel({
  workspaceId,
  entityId,
}: FactManagementPanelProps) {
  const { t } = useI18n();
  const { pushToast } = useOutletContext<AppOutletContext>();
  const { facts, stats, loading, error, listFacts, recallFacts, addFacts, updateFactImportance, pinFact, deleteFact } = useMemori(workspaceId, entityId);
  const [searchQuery, setSearchQuery] = useState('');
  const [newFactContent, setNewFactContent] = useState('');
  const [newFactImportance, setNewFactImportance] = useState(1.0);
  const [isAdding, setIsAdding] = useState(false);
  const [hasLoadedInitial, setHasLoadedInitial] = useState(false);
  const [isSearchMode, setIsSearchMode] = useState(false);

  // Auto-load all facts on mount
  useEffect(() => {
    if (!hasLoadedInitial && !loading && stats && stats.totalFacts > 0) {
      // Load all facts (no search)
      listFacts(100).then(() => {
        setHasLoadedInitial(true);
      });
    }
  }, [hasLoadedInitial, loading, stats, listFacts]);

  const handleSearch = async () => {
    if (searchQuery.trim()) {
      setIsSearchMode(true);
      try {
        const results = await recallFacts(searchQuery, 50);
        pushToast({
          type: 'success',
          title: t.memory?.searchSuccess || "Search completed",
          message: `${t.memory?.found || 'Found'} ${results.length} ${t.memory?.facts || 'facts'}`,
        });
      } catch (err) {
        pushToast({
          type: 'error',
          title: t.memory?.searchError || "Search failed",
          message: err instanceof Error ? err.message : String(err),
        });
      }
    } else {
      // If search is cleared, reload all facts
      setIsSearchMode(false);
      await listFacts(100);
    }
  };

  const handleAddFact = async () => {
    if (!newFactContent.trim()) {
      pushToast({
        type: 'error',
        title: t.memory?.emptyFactError || "Empty fact",
        message: t.memory?.emptyFactDescription || "Please enter fact content",
      });
      return;
    }

    setIsAdding(true);
    try {
      const result = await addFacts([{
        content: newFactContent.trim(),
        importanceScore: newFactImportance,
      }]);

      // Check if fact was actually added (result should contain IDs)
      if (result && result.length > 0) {
        pushToast({
          type: 'success',
          title: t.memory?.factAdded || "Fact added successfully",
          message: `${t.memory?.importance || 'Importance'}: ${newFactImportance.toFixed(1)}`,
        });

        setNewFactContent('');
        setNewFactImportance(1.0);

        // Refresh the list
        if (isSearchMode && searchQuery) {
          await recallFacts(searchQuery, 50);
        } else {
          await listFacts(100);
        }
      } else {
        // No IDs returned - might be duplicate or error
        pushToast({
          type: 'error',
          title: t.memory?.duplicateFact || "Duplicate fact",
          message: t.memory?.duplicateFactDescription || "This fact may already exist or couldn't be added",
        });
      }
    } catch (err) {
      console.error('Failed to add fact:', err);
      pushToast({
        type: 'error',
        title: t.memory?.addFactError || "Failed to add fact",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsAdding(false);
    }
  };

  const getImportanceColor = (score: number) => {
    if (score >= 8) return 'text-red-600 dark:text-red-400';
    if (score >= 5) return 'text-orange-600 dark:text-orange-400';
    if (score >= 3) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-green-600 dark:text-green-400';
  };

  const handleDeleteFact = async (factId: number) => {
    try {
      const success = await deleteFact(factId);
      if (success) {
        pushToast({
          type: 'success',
          title: t.memory?.factDeleted || 'Fact deleted',
          message: t.memory?.factDeletedDescription || 'The fact was removed from memory',
        });
      } else {
        pushToast({
          type: 'error',
          title: t.memory?.deleteFactError || 'Failed to delete fact',
          message: error || t.memory?.deleteFactError || 'Failed to delete fact',
        });
      }
    } catch (err) {
      pushToast({
        type: 'error',
        title: t.memory?.deleteFactError || 'Failed to delete fact',
        message: err instanceof Error ? err.message : String(err),
      });
    }
  };

  return (
    <div className="flex flex-col h-full bg-card">
      {/* Stats */}
      {stats && (
        <div className="p-3 border-b border-border">
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-primary/10 rounded-lg p-2">
              <div className="text-lg font-bold text-primary">{stats.totalFacts}</div>
              <div className="text-xs text-muted-foreground">{t.memory?.totalFacts || 'Total Facts'}</div>
            </div>
            <div className="bg-blue-500/10 rounded-lg p-2">
              <div className="text-lg font-bold text-blue-600 dark:text-blue-400">{stats.totalTriples}</div>
              <div className="text-xs text-muted-foreground">{t.memory?.relations || 'Relations'}</div>
            </div>
            <div className="bg-green-500/10 rounded-lg p-2">
              <div className="text-lg font-bold text-green-600 dark:text-green-400">{stats.avgImportance.toFixed(1)}</div>
              <div className="text-xs text-muted-foreground">{t.memory?.avgImportance || 'Avg Importance'}</div>
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="p-3 border-b border-border">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={t.memory?.searchPlaceholder || 'Search facts by semantic similarity...'}
              className="w-full pl-9 pr-3 py-2 text-sm border border-border rounded-lg bg-background focus:border-primary focus:outline-none"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loading || !searchQuery.trim()}
            className="px-3 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {t.memory?.search || 'Search'}
          </button>
        </div>
      </div>

      {/* Add New Fact */}
      <div className="p-3 border-b border-border bg-muted/30">
        <h3 className="text-sm font-semibold mb-2">{t.memory?.addNewFact || 'Add New Fact'}</h3>
        <div className="space-y-2">
          <textarea
            value={newFactContent}
            onChange={(e) => setNewFactContent(e.target.value)}
            placeholder={t.memory?.factPlaceholder || 'Enter a new fact to remember...'}
            rows={3}
            className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background focus:border-primary focus:outline-none resize-none"
          />
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <label className="block text-xs text-muted-foreground mb-1">
                {t.memory?.importance || 'Importance'} (0-10)
              </label>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={newFactImportance}
                onChange={(e) => setNewFactImportance(parseFloat(e.target.value))}
                className="w-full"
              />
              <div className="text-xs text-muted-foreground mt-1">
                {newFactImportance.toFixed(1)}
              </div>
            </div>
            <button
              onClick={handleAddFact}
              disabled={isAdding || !newFactContent.trim()}
              className="px-3 py-2 text-sm bg-green-600 dark:bg-green-500 text-white rounded-lg hover:bg-green-700 dark:hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              {t.memory?.addFact || 'Add Fact'}
            </button>
          </div>
        </div>
      </div>

      {/* Facts List */}
      <div className="flex-1 overflow-y-auto">
        {loading && facts.length === 0 && (
          <div className="flex items-center justify-center h-32">
            <div className="text-sm text-muted-foreground">{t.memory?.loading || 'Loading...'}</div>
          </div>
        )}

        {error && (
          <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-lg m-3">
            {error}
          </div>
        )}

        {!loading && facts.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <TrendingUp className="w-8 h-8 mb-2" />
            <p className="text-sm">{t.memory?.noFacts || 'No facts found'}</p>
          </div>
        )}

        {!loading && facts.length > 0 && (
          <div className="p-3 space-y-2">
            {facts.map((fact) => {
              const isPinned = (fact.importanceScore || 1.0) >= 9.5;
              return (
                <div
                  key={fact.id}
                  className={`p-3 border rounded-lg transition-all ${isPinned
                    ? 'border-yellow-500 bg-yellow-500/5'
                    : 'border-border hover:bg-muted/30'
                    }`}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 space-y-2">
                      {/* Fact Content */}
                      <p className="text-sm">{fact.content}</p>

                      {/* Importance Score Display & Control */}
                      <div className="flex items-center gap-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <Star className="w-3 h-3 text-yellow-600" />
                            <span className="text-xs font-medium text-muted-foreground">
                              {t.memory?.importance || 'Importance'}: {(fact.importanceScore || 1.0).toFixed(1)}/10
                            </span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="10"
                            step="0.5"
                            value={fact.importanceScore || 1.0}
                            onChange={async (e) => {
                              const newScore = parseFloat(e.target.value);
                              const success = await updateFactImportance(fact.id, newScore);
                              if (success) {
                                pushToast({
                                  type: 'success',
                                  title: t.memory?.updated || 'Updated',
                                  message: `${t.memory?.importance || 'Importance'}: ${newScore.toFixed(1)}`,
                                });
                              }
                            }}
                            className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                            style={{
                              background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${((fact.importanceScore || 1.0) / 10) * 100}%, hsl(var(--muted)) ${((fact.importanceScore || 1.0) / 10) * 100}%, hsl(var(--muted)) 100%)`
                            }}
                          />
                        </div>

                        {/* Pin Button */}
                        <button
                          onClick={async () => {
                            const success = await pinFact(fact.id, !isPinned);
                            if (success) {
                              pushToast({
                                type: 'success',
                                title: isPinned ? (t.memory?.unpinned || 'Unpinned') : (t.memory?.pinned || 'Pinned'),
                                message: isPinned ? (t.memory?.factImportanceReset || 'Fact importance reset') : (t.memory?.factAlwaysIncluded || 'Fact always included'),
                              });
                            }
                          }}
                          className={`p-2 rounded transition-colors ${isPinned
                            ? 'bg-yellow-500 text-white hover:bg-yellow-600'
                            : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                            }`}
                          title={isPinned ? (t.memory?.unpinned || 'Unpin') : (t.memory?.pinned || 'Pin (always include)')}
                        >
                          <Pin className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Search Scores */}
                      {(fact.similarity > 0 || fact.lexicalScore > 0) && (
                        <div className="flex gap-2 text-xs text-muted-foreground">
                          {fact.similarity > 0 && (
                            <span>{t.memory?.similarity || 'Similarity'}: {(fact.similarity * 100).toFixed(0)}%</span>
                          )}
                          {fact.lexicalScore > 0 && (
                            <span>{t.memory?.lexical || 'Lexical'}: {(fact.lexicalScore * 100).toFixed(0)}%</span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Delete Button */}
                    <button
                      onClick={() => handleDeleteFact(fact.id)}
                      className="p-1 text-destructive hover:bg-destructive/10 rounded transition-colors"
                      title={t.memory?.deleteFact || 'Delete'}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
