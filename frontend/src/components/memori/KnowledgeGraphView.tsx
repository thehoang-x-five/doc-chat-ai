/**
 * Knowledge Graph Visualization - Display semantic triples as a graph
 */
import { useEffect, useState } from 'react';
import { Network, RefreshCw, ZoomIn, ZoomOut } from 'lucide-react';
import { useMemori } from '@/hooks/useMemori';
import { useI18n } from '@/lib/i18n';
import type { MemoriTriple } from '@/types/memori';

interface KnowledgeGraphViewProps {
  workspaceId: string;
  entityId: string;
  limit?: number;
}

export function KnowledgeGraphView({
  workspaceId,
  entityId,
  limit = 50,
}: KnowledgeGraphViewProps) {
  const { t } = useI18n();
  const { triples, loading, error, loadKnowledgeGraph } = useMemori(workspaceId, entityId);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    loadKnowledgeGraph(limit);
  }, [loadKnowledgeGraph, limit]);

  const handleRefresh = () => {
    loadKnowledgeGraph(limit);
  };

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.2, 2));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.2, 0.5));

  // Group triples by subject
  const groupedTriples = triples.reduce((acc, triple) => {
    if (!acc[triple.subjectName]) {
      acc[triple.subjectName] = [];
    }
    acc[triple.subjectName].push(triple);
    return acc;
  }, {} as Record<string, MemoriTriple[]>);

  const getNodeColor = (type?: string) => {
    switch (type) {
      case 'person': return 'bg-blue-500/10 border-blue-500/30 text-blue-700 dark:text-blue-400';
      case 'organization': return 'bg-purple-500/10 border-purple-500/30 text-purple-700 dark:text-purple-400';
      case 'concept': return 'bg-green-500/10 border-green-500/30 text-green-700 dark:text-green-400';
      case 'preference': return 'bg-pink-500/10 border-pink-500/30 text-pink-700 dark:text-pink-400';
      case 'programming_language': return 'bg-orange-500/10 border-orange-500/30 text-orange-700 dark:text-orange-400';
      case 'country': return 'bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-400';
      default: return 'bg-muted border-border text-foreground';
    }
  };

  return (
    <div className="flex flex-col h-full bg-card">
      {/* Header with controls */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Network className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-sm">
            {t.memory?.knowledgeGraph || 'Knowledge Graph'}
          </h3>
          <span className="text-xs text-muted-foreground">
            ({triples.length} {t.memory?.relationships || 'relationships'})
          </span>
        </div>
        
        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            className="p-1.5 hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t.memory?.zoomOut || 'Zoom out'}
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= 2}
            className="p-1.5 hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t.memory?.zoomIn || 'Zoom in'}
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-1.5 hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t.memory?.refresh || 'Refresh'}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-3">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {loading && triples.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        )}

        {!loading && triples.length === 0 && (
          <div className="text-center py-12">
            <Network className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">{t.memory?.noRelationships || 'No relationships found'}</p>
          </div>
        )}

        {triples.length > 0 && (
          <div
            className="space-y-6"
            style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
          >
            {Object.entries(groupedTriples).map(([subject, subjectTriples]) => (
              <div key={subject} className="relative">
                {/* Subject Node */}
                <div className="flex items-center gap-3 mb-3">
                  <div className={`px-3 py-2 rounded-lg border-2 text-sm font-semibold ${getNodeColor(subjectTriples[0]?.subjectType)}`}>
                    {subject}
                    {subjectTriples[0]?.subjectType && (
                      <span className="ml-2 text-xs opacity-75">
                        ({subjectTriples[0].subjectType})
                      </span>
                    )}
                  </div>
                </div>

                {/* Relationships */}
                <div className="ml-6 space-y-2">
                  {subjectTriples.map((triple, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      {/* Connector Line */}
                      <div className="w-6 h-0.5 bg-border"></div>

                      {/* Predicate */}
                      <div className="px-2 py-1 bg-muted text-foreground rounded-full text-xs font-medium">
                        {triple.predicate.replace(/_/g, ' ')}
                      </div>

                      {/* Arrow */}
                      <div className="w-3 h-0.5 bg-border relative">
                        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-0 h-0 border-l-4 border-l-border border-t-2 border-t-transparent border-b-2 border-b-transparent"></div>
                      </div>

                      {/* Object Node */}
                      <div className={`px-3 py-1.5 rounded-lg border-2 text-sm ${getNodeColor(triple.objectType)}`}>
                        {triple.objectName}
                        {triple.objectType && (
                          <span className="ml-2 text-xs opacity-75">
                            ({triple.objectType})
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="p-3 border-t border-border bg-muted/30">
        <div className="flex flex-wrap gap-2 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-blue-500/10 border border-blue-500/30"></div>
            <span className="text-muted-foreground">{t.memory?.person || 'Person'}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-purple-500/10 border border-purple-500/30"></div>
            <span className="text-muted-foreground">{t.memory?.organization || 'Organization'}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-green-500/10 border border-green-500/30"></div>
            <span className="text-muted-foreground">{t.memory?.concept || 'Concept'}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-pink-500/10 border border-pink-500/30"></div>
            <span className="text-muted-foreground">{t.memory?.preference || 'Preference'}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-orange-500/10 border border-orange-500/30"></div>
            <span className="text-muted-foreground">{t.memory?.programmingLanguage || 'Programming Language'}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-red-500/10 border border-red-500/30"></div>
            <span className="text-muted-foreground">{t.memory?.country || 'Country'}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-muted border border-border"></div>
            <span className="text-muted-foreground">{t.memory?.other || 'Other'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
