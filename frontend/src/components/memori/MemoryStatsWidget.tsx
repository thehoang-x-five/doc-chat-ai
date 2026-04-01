/**
 * Memory Stats Widget - Compact display of memory statistics
 */
import { Brain, Network, TrendingUp } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import type { MemoriStats } from '@/types/memori';

interface MemoryStatsWidgetProps {
  stats: MemoriStats | null;
  loading?: boolean;
  onClick?: () => void;
  className?: string;
}

export function MemoryStatsWidget({
  stats,
  loading,
  onClick,
  className = '',
}: MemoryStatsWidgetProps) {
  const { t } = useI18n();

  if (loading) {
    return (
      <div className={`bg-card rounded-lg border border-border p-3 ${className}`}>
        <div className="animate-pulse flex items-center gap-2">
          <div className="w-8 h-8 bg-muted rounded-lg"></div>
          <div className="flex-1 space-y-2">
            <div className="h-3 bg-muted rounded w-3/4"></div>
            <div className="h-2 bg-muted rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  // Always show widget, use default values if no stats
  const displayStats = stats || {
    totalFacts: 0,
    totalTriples: 0,
    totalPreferences: 0,
    totalAttributes: 0,
    avgImportance: 0,
  };

  return (
    <div
      className={`bg-gradient-to-br from-primary/10 to-blue-500/10 rounded-lg border border-primary/20 p-3 ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''} ${className}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
          <Brain className="w-4 h-4 text-primary-foreground" />
        </div>
        <div>
          <h3 className="text-sm font-semibold">{t.memory?.memorySystem || 'Memory System'}</h3>
          <p className="text-xs text-muted-foreground">{t.memory?.activeAndLearning || 'Active & Learning'}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-background rounded-lg p-2 text-center">
          <div className="text-base font-bold text-primary">{displayStats.totalFacts}</div>
          <div className="text-xs text-muted-foreground">{t.memory?.facts || 'Facts'}</div>
        </div>
        <div className="bg-background rounded-lg p-2 text-center">
          <div className="text-base font-bold text-blue-600 dark:text-blue-400">{displayStats.totalTriples}</div>
          <div className="text-xs text-muted-foreground">{t.memory?.relations || 'Relations'}</div>
        </div>
        <div className="bg-background rounded-lg p-2 text-center">
          <div className="text-base font-bold text-green-600 dark:text-green-400">{displayStats.avgImportance.toFixed(1)}</div>
          <div className="text-xs text-muted-foreground">{t.memory?.avgScore || 'Avg Score'}</div>
        </div>
      </div>

      {onClick && (
        <div className="mt-2 text-xs text-center text-primary font-medium">
          {t.memory?.clickToManage || 'Click to manage'} →
        </div>
      )}
    </div>
  );
}
