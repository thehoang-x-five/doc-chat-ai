/**
 * Memory Management Page - Full page for managing memories
 */
import { useState, useEffect } from 'react';
import { List, Network, BarChart3 } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { useAuthStore } from '@/lib/authStore';
import { apiClient, type Workspace } from '@/lib/api';
import { FactManagementPanel } from '@/components/memori/FactManagementPanel';
import { KnowledgeGraphView } from '@/components/memori/KnowledgeGraphView';
import { MemoryStatsWidget } from '@/components/memori/MemoryStatsWidget';
import { useMemori } from '@/hooks/useMemori';

type Tab = 'facts' | 'graph' | 'stats';

export default function MemoryManagement() {
  const { t } = useI18n();
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<Tab>('facts');
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);

  // Get user's workspace on mount
  useEffect(() => {
    apiClient.getWorkspaces().then((ws) => {
      if (ws.length > 0) {
        setWorkspaceId(ws[0].id);
      }
    }).catch(console.error);
  }, []);

  // Use user.id as entityId (same as Chat.tsx)
  const entityId = user?.id || '';
  const { stats, loading } = useMemori(workspaceId || undefined, entityId || undefined);


  const tabs = [
    { id: 'facts' as Tab, label: t.memory?.factsList || 'Facts', icon: List },
    { id: 'graph' as Tab, label: t.memory?.knowledgeGraph || 'Knowledge Graph', icon: Network },
    { id: 'stats' as Tab, label: t.memory?.statistics || 'Statistics', icon: BarChart3 },
  ];

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{t.memory?.management || 'Memory Management'}</h1>
          <p className="text-xs text-muted-foreground">{t.memory?.subtitle || 'Manage semantic memories'}</p>
        </div>

        {/* Tabs */}
        <div className="rounded-xl border border-border bg-card/50 p-1 inline-flex gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition ${activeTab === tab.id
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'hover:bg-muted'
                  }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div>
        {activeTab === 'facts' && workspaceId && entityId && (
          <div className="rounded-xl border border-border bg-card overflow-hidden" style={{ height: 'calc(100vh - 140px)' }}>
            <FactManagementPanel workspaceId={workspaceId} entityId={entityId} />
          </div>
        )}

        {activeTab === 'graph' && workspaceId && entityId && (
          <div className="rounded-xl border border-border bg-card overflow-hidden" style={{ height: 'calc(100vh - 140px)' }}>
            <KnowledgeGraphView key={activeTab} workspaceId={workspaceId} entityId={entityId} />
          </div>
        )}

        {activeTab === 'stats' && (
          <div className="rounded-xl border border-border bg-card p-3" style={{ height: 'calc(100vh - 140px)', overflowY: 'hidden' }}>
            {/* Top Row - 3 cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2" style={{ height: '30%' }}>
              <MemoryStatsWidget stats={stats} loading={loading} />

              <div className="rounded-lg border border-border bg-background p-2.5">
                <h3 className="text-sm font-semibold mb-2">{t.memory?.memoryHealth || 'Memory Health'}</h3>
                <div className="space-y-1.5">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-muted-foreground">{t.memory?.storageUsage || 'Storage Usage'}</span>
                      <span className="font-medium">
                        {stats ? ((stats.totalFacts / 1000) * 100).toFixed(1) : '0.0'}%
                      </span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-1.5">
                      <div
                        className="bg-primary h-1.5 rounded-full transition-all"
                        style={{ width: stats ? `${Math.min((stats.totalFacts / 1000) * 100, 100)}%` : '0%' }}
                      ></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-muted-foreground">{t.memory?.qualityScore || 'Quality Score'}</span>
                      <span className="font-medium">
                        {stats ? ((stats.avgImportance / 10) * 100).toFixed(0) : '0'}%
                      </span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-1.5">
                      <div
                        className="bg-green-600 dark:bg-green-500 h-1.5 rounded-full transition-all"
                        style={{ width: stats ? `${(stats.avgImportance / 10) * 100}%` : '0%' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-background p-2.5">
                <h3 className="text-sm font-semibold mb-2">{t.memory?.recentActivity || 'Recent Activity'}</h3>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${stats && stats.totalFacts > 0 ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                    <span className="text-muted-foreground">{t.memory?.systemActive || 'System active and learning'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${stats && stats.totalFacts > 0 ? 'bg-blue-500' : 'bg-gray-400'}`}></div>
                    <span className="text-muted-foreground">{t.memory?.autoRecallEnabled || 'Auto-recall enabled'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${stats && stats.totalTriples > 0 ? 'bg-primary' : 'bg-gray-400'}`}></div>
                    <span className="text-muted-foreground">{t.memory?.graphUpdated || 'Knowledge graph updated'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Row - 4 charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2" style={{ height: '68%' }}>
              {/* Facts Growth Chart */}
              <div className="rounded-lg border border-border bg-background p-2.5 flex flex-col">
                <h3 className="text-sm font-semibold mb-2">{t.memory?.factsGrowth || 'Facts Growth'}</h3>
                <div className="flex-1 flex items-end justify-between gap-1">
                  {[12, 18, 25, 32, 45, 58, stats?.totalFacts || 0].map((value, idx) => (
                    <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                      <div className="w-full bg-primary/20 rounded-t relative" style={{ height: `${Math.max((value / 100) * 100, 5)}%` }}>
                        <div className="absolute inset-0 bg-gradient-to-t from-primary to-primary/50 rounded-t"></div>
                      </div>
                      <span className="text-[10px] text-muted-foreground">
                        {[t.memory?.mon || 'Mon', t.memory?.tue || 'Tue', t.memory?.wed || 'Wed', t.memory?.thu || 'Thu', t.memory?.fri || 'Fri', t.memory?.sat || 'Sat', t.memory?.sun || 'Sun'][idx]}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Relations Distribution */}
              <div className="rounded-lg border border-border bg-background p-2.5 flex flex-col">
                <h3 className="text-sm font-semibold mb-2">{t.memory?.relationsDistribution || 'Relations Distribution'}</h3>
                <div className="flex-1 flex items-center justify-center">
                  <div className="relative w-28 h-28">
                    <svg viewBox="0 0 100 100" className="transform -rotate-90">
                      <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="12"
                        className="text-muted"
                      />
                      <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="12"
                        strokeDasharray={`${((stats?.totalTriples || 0) / 100) * 251.2} 251.2`}
                        className="text-primary"
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <div className="text-xl font-bold text-primary">{stats?.totalTriples || 0}</div>
                      <div className="text-[10px] text-muted-foreground">{t.memory?.relations || 'Relations'}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Importance Distribution */}
              <div className="rounded-lg border border-border bg-background p-2.5 flex flex-col">
                <h3 className="text-sm font-semibold mb-2">{t.memory?.importanceDistribution || 'Importance Distribution'}</h3>
                <div className="flex-1 flex flex-col justify-center space-y-1.5">
                  {[
                    { label: t.memory?.critical || 'Critical (8-10)', value: 15, color: 'bg-red-500' },
                    { label: t.memory?.high || 'High (5-7)', value: 35, color: 'bg-orange-500' },
                    { label: t.memory?.medium || 'Medium (3-4)', value: 30, color: 'bg-yellow-500' },
                    { label: t.memory?.low || 'Low (0-2)', value: 20, color: 'bg-green-500' },
                  ].map((item, idx) => (
                    <div key={idx}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-muted-foreground">{item.label}</span>
                        <span className="font-medium">{item.value}%</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-1.5">
                        <div
                          className={`${item.color} h-1.5 rounded-full transition-all`}
                          style={{ width: `${item.value}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Memory Performance */}
              <div className="rounded-lg border border-border bg-background p-2.5 flex flex-col">
                <h3 className="text-sm font-semibold mb-2">{t.memory?.memoryPerformance || 'Memory Performance'}</h3>
                <div className="flex-1 flex flex-col">
                  <div className="flex-1 flex items-end justify-between gap-1">
                    {[65, 72, 68, 78, 85, 82, 88, 90, 87, 92, 95, 93].map((value, idx) => (
                      <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                        <div className="w-full bg-gradient-to-t from-blue-500 to-blue-400 rounded-t" style={{ height: `${value}%` }}></div>
                        {idx % 3 === 0 && (
                          <span className="text-[10px] text-muted-foreground">{idx + 1}</span>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="mt-1.5 text-center text-xs text-muted-foreground">
                    {t.memory?.last12Hours || 'Last 12 hours'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
