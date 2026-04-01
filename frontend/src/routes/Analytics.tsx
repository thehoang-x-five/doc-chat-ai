import { useEffect, useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import Card from '@/components/common/Card';
import { apiClient, UsageStats } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

const COLORS = ['#38bdf8', '#10b981', '#6366f1', '#f97316', '#ec4899', '#8b5cf6'];

const Analytics = () => {
  const { t } = useI18n();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d'>('30d');

  useEffect(() => {
    loadStats();
  }, [dateRange]);

  const loadStats = async () => {
    try {
      setLoading(true);
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - (dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : 90) * 24 * 60 * 60 * 1000)
        .toISOString().split('T')[0];
      const data = await apiClient.getUsageStats({ startDate, endDate });
      setStats(data);
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const providerData = stats ? Object.entries(stats.byProvider).map(([name, data]) => ({
    name,
    requests: data.requests,
    tokens: data.tokens,
    cost: data.cost,
  })) : [];

  const modelData = stats ? Object.entries(stats.byModel).map(([name, data]) => ({
    name: name.length > 15 ? name.substring(0, 15) + '...' : name,
    fullName: name,
    requests: data.requests,
    tokens: data.tokens,
  })).sort((a, b) => b.requests - a.requests).slice(0, 10) : [];

  const pieData = providerData.map((p, i) => ({
    name: p.name,
    value: p.requests,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.analytics?.title || 'Analytics'}</h1>
          <p className="text-muted-foreground">{t.analytics?.subtitle || 'Usage statistics and insights'}</p>
        </div>
        <div className="flex gap-2">
          {(['7d', '30d', '90d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                dateRange === range
                  ? 'bg-primary text-white'
                  : 'bg-muted hover:bg-muted/80'
              }`}
            >
              {range === '7d' ? '7 days' : range === '30d' ? '30 days' : '90 days'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : stats ? (
        <>
          {/* Overview Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card title={t.analytics?.totalRequests || 'Total Requests'} description="">
              <p className="text-3xl font-bold text-primary">{stats.totalRequests.toLocaleString()}</p>
            </Card>
            <Card title={t.analytics?.totalTokens || 'Total Tokens'} description="">
              <p className="text-3xl font-bold text-emerald-500">{stats.totalTokens.toLocaleString()}</p>
            </Card>
            <Card title={t.analytics?.totalCost || 'Total Cost'} description="">
              <p className="text-3xl font-bold text-amber-500">${stats.totalCost.toFixed(2)}</p>
            </Card>
            <Card title={t.analytics?.providers || 'Providers'} description="">
              <p className="text-3xl font-bold text-purple-500">{Object.keys(stats.byProvider).length}</p>
            </Card>
          </div>

          {/* Charts */}
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Requests by Provider */}
            <Card title={t.analytics?.requestsByProvider || 'Requests by Provider'} description="">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={providerData}>
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="requests" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Provider Distribution */}
            <Card title={t.analytics?.providerDistribution || 'Provider Distribution'} description="">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-3">
                {pieData.map((entry) => (
                  <div key={entry.name} className="flex items-center gap-1.5 text-xs">
                    <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                    <span>{entry.name}</span>
                  </div>
                ))}
              </div>
            </Card>

            {/* Top Models */}
            <Card title={t.analytics?.topModels || 'Top Models by Usage'} description="" className="lg:col-span-2">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={modelData} layout="vertical">
                    <XAxis type="number" tick={{ fontSize: 12 }} />
                    <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={120} />
                    <Tooltip 
                      contentStyle={{ borderRadius: 8, fontSize: 12 }}
                      formatter={(value: number, name: string, props: any) => [
                        value.toLocaleString(),
                        props.payload.fullName
                      ]}
                    />
                    <Bar dataKey="requests" fill="#10b981" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Tokens by Provider */}
            <Card title={t.analytics?.tokensByProvider || 'Tokens by Provider'} description="">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={providerData}>
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="tokens" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Cost Breakdown */}
            <Card title={t.analytics?.costBreakdown || 'Cost Breakdown'} description="">
              <div className="space-y-3">
                {providerData.map((provider, idx) => (
                  <div key={provider.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="h-3 w-3 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                      <span className="text-sm font-medium">{provider.name}</span>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">${provider.cost.toFixed(2)}</div>
                      <div className="text-xs text-muted-foreground">
                        {stats.totalCost > 0 ? ((provider.cost / stats.totalCost) * 100).toFixed(1) : 0}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Detailed Table */}
          <Card title={t.analytics?.detailedStats || 'Detailed Statistics'} description="">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-4 py-2 text-left font-medium">{t.analytics?.provider || 'Provider'}</th>
                    <th className="px-4 py-2 text-right font-medium">{t.analytics?.requests || 'Requests'}</th>
                    <th className="px-4 py-2 text-right font-medium">{t.analytics?.tokens || 'Tokens'}</th>
                    <th className="px-4 py-2 text-right font-medium">{t.analytics?.cost || 'Cost'}</th>
                    <th className="px-4 py-2 text-right font-medium">{t.analytics?.avgTokens || 'Avg Tokens/Req'}</th>
                  </tr>
                </thead>
                <tbody>
                  {providerData.map((provider) => (
                    <tr key={provider.name} className="border-b border-border/50 hover:bg-muted/50">
                      <td className="px-4 py-2 font-medium">{provider.name}</td>
                      <td className="px-4 py-2 text-right">{provider.requests.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right">{provider.tokens.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right">${provider.cost.toFixed(2)}</td>
                      <td className="px-4 py-2 text-right">
                        {provider.requests > 0 ? Math.round(provider.tokens / provider.requests).toLocaleString() : 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          {t.analytics?.noData || 'No analytics data available'}
        </div>
      )}
    </div>
  );
};

export default Analytics;
