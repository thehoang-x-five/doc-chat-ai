/**
 * Memory Sidebar - Displays recalled facts about the user
 */
import { useState, useEffect } from 'react';
import { Brain, Trash2, RefreshCw, TrendingUp, Network } from 'lucide-react';
import { useMemori } from '@/hooks/useMemori';
import { useI18n } from '@/lib/i18n';
import type { MemoriFact } from '@/types/memori';

interface MemorySidebarProps {
  workspaceId?: string;
  entityId?: string;
  conversationId?: string;
  currentQuery?: string;
  className?: string;
  onClose?: () => void;
}

export function MemorySidebar({
  workspaceId,
  entityId,
  conversationId,
  currentQuery,
  className = '',
  onClose,
}: MemorySidebarProps) {
  const { t } = useI18n();
  const { facts, stats, loading, error, recallFacts, loadStats } = useMemori(workspaceId, entityId);
  const [autoRecall, setAutoRecall] = useState(true);

  // Auto-recall when query changes
  useEffect(() => {
    if (autoRecall && currentQuery && currentQuery.trim().length > 3) {
      recallFacts(currentQuery, 5);
    }
  }, [currentQuery, autoRecall, recallFacts]);

  const handleRefresh = () => {
    if (currentQuery) {
      recallFacts(currentQuery, 5);
    }
    loadStats();
  };

  const getScoreBadge = (score: number) => {
    if (score >= 0.8) return 'bg-green-500/20 text-green-700 dark:bg-green-500/30 dark:text-green-400';
    if (score >= 0.6) return 'bg-yellow-500/20 text-yellow-700 dark:bg-yellow-500/30 dark:text-yellow-400';
    return 'bg-gray-500/20 text-gray-700 dark:bg-gray-500/30 dark:text-gray-400';
  };

  return (
    <div className={`w-1/4 min-w-[180px] max-w-[260px] flex flex-col rounded-xl border border-border bg-card/50 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-3 border-b border-border bg-muted/30">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold">{t.memory?.title || 'Memory'}</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="p-1.5 hover:bg-muted rounded-lg transition-colors disabled:opacity-50"
              title={t.memory?.refresh || 'Refresh'}
            >
              <RefreshCw className={`w-3.5 h-3.5 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="p-1.5 hover:bg-muted rounded-lg transition-colors"
                title={t.common?.close || 'Close'}
              >
                <svg className="w-3.5 h-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-primary/10 rounded-lg p-2">
              <div className="text-primary font-medium">{stats.totalFacts}</div>
              <div className="text-muted-foreground">{t.memory?.facts || 'Facts'}</div>
            </div>
            <div className="bg-accent/10 rounded-lg p-2">
              <div className="text-accent-foreground font-medium">{stats.totalTriples}</div>
              <div className="text-muted-foreground">{t.memory?.relations || 'Relations'}</div>
            </div>
          </div>
        )}

        {/* Auto-recall toggle */}
        <label className="flex items-center gap-2 mt-3 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={autoRecall}
            onChange={(e) => setAutoRecall(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary/20"
          />
          <span>{t.memory?.autoRecall || 'Auto-recall on query'}</span>
        </label>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2 pr-1.5 space-y-1 chat-scrollbar">
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-2 mb-2">
            <p className="text-xs text-destructive">{error}</p>
          </div>
        )}

        {loading && facts.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <svg className="h-5 w-5 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        )}

        {!loading && facts.length === 0 && !error && (
          <div className="text-center py-8">
            <Brain className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">
              {currentQuery ? (t.memory?.noMemories || 'No relevant memories found') : (t.memory?.askQuestion || 'Ask a question to recall memories')}
            </p>
          </div>
        )}

        {facts.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between px-2 py-1">
              <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                {t.memory?.recalledFacts || 'Recalled'} ({facts.length})
              </h4>
            </div>

            {facts.map((fact) => (
              <div
                key={fact.id}
                className="bg-primary/5 border border-primary/10 rounded-lg p-2.5 hover:bg-primary/10 transition-colors"
              >
                <p className="text-xs mb-2 leading-relaxed">{fact.content}</p>

                {/* Scores */}
                <div className="flex items-center gap-1.5 text-[10px]">
                  <span className={`px-1.5 py-0.5 rounded-full font-medium ${getScoreBadge(fact.similarity)}`}>
                    {(fact.similarity * 100).toFixed(0)}%
                  </span>
                  {fact.rankScore > 0 && (
                    <span className="text-muted-foreground">
                      {t.memory?.rank || 'Rank'}: {fact.rankScore.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-border bg-muted/30">
        <p className="text-[10px] text-muted-foreground text-center">
          {t.memory?.poweredBy || 'Powered by semantic memory'}
        </p>
      </div>
    </div>
  );
}
