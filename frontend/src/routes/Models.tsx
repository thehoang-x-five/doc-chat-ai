import { useState, useEffect } from 'react';
import { useI18n } from '@/lib/i18n';
import { apiClient, type AIModel, type ProviderHealth } from '@/lib/api';

interface CloudCodeStats {
  totalAccounts: number;
  avgClaudeQuota: number;
  avgGeminiQuota: number;
  avgGeminiImageQuota: number;
  lowQuotaAccounts: number;
}

export default function Models() {
  const { t } = useI18n();
  const [models, setModels] = useState<AIModel[]>([]);
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [cloudCodeStats, setCloudCodeStats] = useState<CloudCodeStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'text' | 'image' | 'thinking'>('all');

  useEffect(() => {
    Promise.all([
      apiClient.getModels(),
      apiClient.getProviderHealth(),
      apiClient.getCloudCodeStatistics(),
    ]).then(([modelsData, providersData, statsData]) => {
      setModels(modelsData);
      setProviders(providersData);
      setCloudCodeStats(statsData);
    }).catch(console.error).finally(() => setIsLoading(false));
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      // Refresh all Cloud Code accounts first
      await apiClient.refreshAllCloudCodeAccounts();
      // Then reload data
      const [modelsData, providersData, statsData] = await Promise.all([
        apiClient.getModels(),
        apiClient.getProviderHealth(),
        apiClient.getCloudCodeStatistics(),
      ]);
      setModels(modelsData);
      setProviders(providersData);
      setCloudCodeStats(statsData);
    } catch (error) {
      console.error('Refresh failed:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const filteredModels = models.filter(m => filter === 'all' || m.type === filter);

  const getQuotaColor = (quota: number) => {
    if (quota >= 70) return { text: 'text-green-600 dark:text-green-400', bg: 'bg-green-500' };
    if (quota >= 30) return { text: 'text-yellow-600 dark:text-yellow-400', bg: 'bg-yellow-500' };
    return { text: 'text-red-600 dark:text-red-400', bg: 'bg-red-500' };
  };

  const filterLabels: Record<string, string> = {
    all: t.models?.filterAll || 'All',
    text: t.models?.filterText || 'Text',
    image: t.models?.filterImage || 'Image',
    thinking: t.models?.filterThinking || 'Thinking',
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <svg className="h-8 w-8 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{t.models?.title || 'AI Models'}</h1>
          <p className="text-xs text-muted-foreground">{t.models?.subtitle || 'Monitor available AI models and providers'}</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-all disabled:opacity-50"
        >
          <svg className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {isRefreshing ? (t.common?.processing || 'Refreshing...') : (t.models?.refresh || 'Refresh Quota')}
        </button>
      </div>

      {/* Top Row: Provider Health + Cloud Code Stats */}
      <div className="grid gap-3 lg:grid-cols-2">
        {/* Provider Health */}
        <div className="rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">{t.models?.providerHealth || 'Provider Status'}</h2>
            <span className="text-xs text-muted-foreground">{providers.filter(p => p.available).length}/{providers.length} {t.models?.providers || 'providers'} {t.models?.online || 'online'}</span>
          </div>
          <div className="grid gap-2 p-3 sm:grid-cols-2">
            {providers.map((provider) => (
              <div key={provider.name} className="flex items-center gap-2.5 rounded-lg border border-border bg-background p-2.5">
                <div className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${provider.available ? 'bg-green-500' : 'bg-red-500'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{provider.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {provider.available ? `${provider.responseTimeMs}ms` : t.models?.unavailable || 'Unavailable'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cloud Code Statistics */}
        <div className="rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">{t.models?.cloudCodeStats || 'Cloud Code Statistics'}</h2>
            <span className="text-xs text-muted-foreground">
              {cloudCodeStats ? `${cloudCodeStats.totalAccounts} ${t.models?.totalAccounts?.toLowerCase() || 'accounts'}` : '—'}
            </span>
          </div>
          {cloudCodeStats ? (
            <div className="grid gap-2 p-3 sm:grid-cols-2">
              {/* Claude Quota */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-2.5">
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">{t.models?.avgClaude || 'Avg Claude Quota'}</p>
                  <p className={`text-lg font-bold ${getQuotaColor(cloudCodeStats.avgClaudeQuota).text}`}>
                    {cloudCodeStats.avgClaudeQuota.toFixed(0)}%
                  </p>
                </div>
                <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                  <div
                    className={`h-6 w-6 rounded-full border-2 ${getQuotaColor(cloudCodeStats.avgClaudeQuota).text.split(' ')[0].replace('text-', 'border-')}`}
                    style={{ background: `conic-gradient(currentColor ${cloudCodeStats.avgClaudeQuota}%, transparent 0)` }}
                  />
                </div>
              </div>

              {/* Gemini Quota */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-2.5">
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">{t.models?.avgGemini || 'Avg Gemini Quota'}</p>
                  <p className={`text-lg font-bold ${getQuotaColor(cloudCodeStats.avgGeminiQuota).text}`}>
                    {cloudCodeStats.avgGeminiQuota.toFixed(0)}%
                  </p>
                </div>
              </div>

              {/* Gemini Image Quota */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-2.5">
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">{t.models?.avgGeminiImage || 'Avg Gemini Image'}</p>
                  <p className={`text-lg font-bold ${getQuotaColor(cloudCodeStats.avgGeminiImageQuota).text}`}>
                    {cloudCodeStats.avgGeminiImageQuota.toFixed(0)}%
                  </p>
                </div>
              </div>

              {/* Low Quota */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-2.5">
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">{t.models?.lowQuota || 'Low Quota'} (&lt;20%)</p>
                  <p className={`text-lg font-bold ${cloudCodeStats.lowQuotaAccounts > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                    {cloudCodeStats.lowQuotaAccounts}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center text-muted-foreground">
              <p className="text-sm">{t.models?.noCloudCode || 'No Cloud Code accounts configured'}</p>
              <p className="text-xs mt-1">{t.models?.addCloudCode || 'Add accounts in Settings → Cloud Code'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Image Generation Providers */}
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🎨</span>
            <h2 className="text-sm font-semibold">{t.models?.imageGenProviders || 'Image Generation'}</h2>
          </div>
          <span className="text-xs text-purple-600 dark:text-purple-400">
            {t.models?.rankedByQuality || 'Ranked by quality'}
          </span>
        </div>
        <div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {[
            { name: 'Together.ai', model: 'FLUX.1', rank: '🥇', available: models.some(m => m.id === 'flux-schnell' && m.available), desc: '60 req/min' },
            { name: 'Pollinations', model: 'FLUX', rank: '🥈', available: true, desc: '100% FREE' },
            { name: 'Hugging Face', model: 'SDXL', rank: '🥉', available: models.some(m => m.id === 'sdxl' && m.available), desc: 'Free tier' },
            { name: 'Cloud Code', model: 'Imagen-3', rank: '4', available: models.some(m => m.id === 'imagen-3' && m.available), desc: 'Via accounts' },
            { name: 'Stability', model: 'SD v1.6', rank: '5', available: models.some(m => m.id === 'stable-diffusion' && m.available), desc: '25 credits' },
            { name: 'Gemini', model: 'Gemini 2.0', rank: '6', available: models.some(m => m.id === 'gemini-2.0-flash-img' && m.available), desc: '50 img/day' },
          ].map((p) => (
            <div key={p.name} className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
              <span className="text-base flex-shrink-0">{p.rank}</span>
              <div className={`h-2 w-2 rounded-full flex-shrink-0 ${p.available ? 'bg-green-500' : 'bg-red-500'}`} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{p.name}</p>
                <p className="text-[10px] text-muted-foreground truncate">{p.model} • {p.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* All Models Table */}
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">{t.models?.allModels || 'All Models'}</h2>
          <div className="flex gap-1">
            {(['all', 'text', 'image', 'thinking'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-md px-2.5 py-1 text-xs transition ${filter === f ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
              >
                {filterLabels[f]}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">{t.models?.model || 'Model'}</th>
                <th className="px-4 py-2.5 font-medium">{t.models?.provider || 'Provider'}</th>
                <th className="px-4 py-2.5 font-medium">{t.models?.type || 'Type'}</th>
                <th className="px-4 py-2.5 font-medium">{t.models?.status || 'Status'}</th>
                <th className="px-4 py-2.5 font-medium">{t.models?.quota || 'Quota'}</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {filteredModels.map((model) => (
                <tr key={model.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition">
                  <td className="px-4 py-2.5">
                    <p className="font-medium">{model.name}</p>
                    <p className="text-xs text-muted-foreground">{model.id}</p>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{model.provider}</td>
                  <td className="px-4 py-2.5">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${model.type === 'image' ? 'bg-purple-500/20 text-purple-700 dark:text-purple-400' :
                      model.type === 'thinking' ? 'bg-blue-500/20 text-blue-700 dark:text-blue-400' :
                        'bg-gray-500/20 text-gray-700 dark:text-gray-400'
                      }`}>
                      {filterLabels[model.type] || model.type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs ${model.available ? 'bg-green-500/20 text-green-700 dark:text-green-400' : 'bg-red-500/20 text-red-700 dark:text-red-400'}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${model.available ? 'bg-green-500' : 'bg-red-500'}`} />
                      {model.available ? t.models?.available || 'Available' : t.models?.unavailable || 'Unavailable'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {model.quota !== undefined && model.quota !== null ? (
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                          <div className={`h-full ${getQuotaColor(model.quota).bg}`} style={{ width: `${model.quota}%` }} />
                        </div>
                        <span className="text-xs">{model.quota}%</span>
                      </div>
                    ) : (
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs cursor-help ${model.available
                          ? 'bg-green-500/20 text-green-700 dark:text-green-400'
                          : 'bg-gray-500/20 text-gray-600 dark:text-gray-400'
                          }`}
                        title={
                          model.provider === 'cloudcode'
                            ? model.available
                              ? 'Free via Cloud Code accounts - quota varies by account'
                              : 'No Cloud Code accounts available'
                            : model.provider === 'ollama'
                              ? 'Runs locally on your machine - truly unlimited'
                              : model.provider === 'groq'
                                ? 'Free tier: ~30 req/min, ~14,400 req/day'
                                : model.provider === 'gemini'
                                  ? 'Free tier: 15 req/min, 1,500 req/day'
                                  : model.provider === 'deepseek'
                                    ? 'Pay-as-you-go: ~$0.14/1M tokens'
                                    : model.provider === 'together'
                                      ? 'Free tier: 60 req/min'
                                      : model.provider === 'pollinations'
                                        ? '100% FREE - No API key needed'
                                        : model.provider === 'huggingface'
                                          ? 'Free tier with rate limits'
                                          : model.provider === 'stability'
                                            ? '25 free credits'
                                            : 'Free tier with rate limits'
                        }
                      >
                        {model.available ? (
                          <>
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            {model.provider === 'pollinations' ? 'FREE' :
                              model.provider === 'cloudcode' ? 'Via Account' : 'Free Tier'}
                          </>
                        ) : (
                          <>
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            {model.provider === 'cloudcode' ? 'No Account' : 'Need Key'}
                          </>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
