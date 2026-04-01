import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api';

// Defined local interface to match API response
// Adjusted based on actual API response structure observation
interface CloudCodeAccount {
  id: string;
  email: string;
  name: string;
  quotas: {
    claude: number;
    gemini: number;
    geminiImage: number;
  };
  models?: Array<{
    name: string;
    percentage: number;
    resetTime?: string;
  }>;
  lastUsed?: string;
  totalRequests: number;
  totalFailures: number;
  isDefault: boolean;
  isOwn?: boolean;
  createdAt?: string;
  successRate?: number;
  avgLatencyMs?: number;
  lastError?: string;
}

interface AccountStats {
  totalAccounts: number;
  activeAccounts: number;
  totalRequests: number;
  avgSuccessRate: number;
}

type AddTab = 'oauth' | 'token';
type AddStatus = 'idle' | 'loading' | 'success' | 'error';

export default function Accounts() {
  const { t } = useI18n();
  const { user } = useAuth();

  // State
  const [accounts, setAccounts] = useState<CloudCodeAccount[]>([]);
  const [stats, setStats] = useState<AccountStats>({ totalAccounts: 0, activeAccounts: 0, totalRequests: 0, avgSuccessRate: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [addTab, setAddTab] = useState<AddTab>('oauth');
  const [addStatus, setAddStatus] = useState<AddStatus>('idle');
  const [addMessage, setAddMessage] = useState('');
  const [newToken, setNewToken] = useState('');
  const [oauthUrl, setOauthUrl] = useState('');
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<CloudCodeAccount | null>(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setIsLoading(true);
      const data = await apiClient.getCloudCodeAccounts();

      // Try to handle different response structures
      let accountList: any[] = [];
      if (Array.isArray(data)) accountList = data;
      else if (data && typeof data === 'object') {
        // @ts-ignore
        if (Array.isArray(data.accounts)) accountList = data.accounts;
        // @ts-ignore
        else if (Array.isArray(data.items)) accountList = data.items;
      }

      // Normalize data if needed
      const normalizedAccounts = accountList.map(acc => ({
        ...acc,
        // Ensure quotas object exists
        quotas: acc.quotas || { claude: 0, gemini: 0, geminiImage: 0 },
        // Ensure Stats exist
        totalRequests: acc.totalRequests || acc.total_requests || 0,
        totalFailures: acc.totalFailures || acc.total_failures || 0,
        isDefault: acc.isDefault || acc.is_default || false,
        isOwn: acc.isOwn || acc.is_own || false,
        name: acc.name || acc.full_name || acc.email?.split('@')[0] || 'Unknown',
      }));

      setAccounts(normalizedAccounts);

      // Calculate stats
      const totalReq = normalizedAccounts.reduce((sum, acc) => sum + (acc.totalRequests || 0), 0);
      const activeAccs = normalizedAccounts.filter(acc => (acc.quotas?.claude > 0 || acc.quotas?.gemini > 0)).length;

      setStats({
        totalAccounts: normalizedAccounts.length,
        activeAccounts: activeAccs,
        totalRequests: totalReq,
        avgSuccessRate: normalizedAccounts.length > 0 ?
          Math.round(normalizedAccounts.reduce((sum, acc) => sum + (acc.successRate || acc.success_rate || 99), 0) / normalizedAccounts.length) : 0
      });

    } catch (error) {
      console.error('Failed to load accounts:', error);
      setAccounts([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async (accountId: string) => {
    setRefreshingId(accountId);
    try {
      await apiClient.refreshCloudCodeAccount(accountId);
      await loadAccounts();
      // Update selected account details if open
      if (selectedAccount && selectedAccount.id === accountId) {
        const details = await apiClient.getCloudCodeAccountDetails(accountId);
        setSelectedAccount(prev => ({ ...prev!, ...details }));
      }
    } catch (error) {
      console.error('Failed to refresh account:', error);
    } finally {
      setRefreshingId(null);
    }
  };

  const handleStartOAuth = async () => {
    setAddStatus('loading');
    setAddMessage(t.accounts?.oauthStarting || 'Starting OAuth...');

    try {
      const response = await apiClient.startCloudCodeOAuth();
      setOauthUrl(response.authUrl);
      setAddMessage(t.accounts?.oauthOpenBrowser || 'Opening browser...');

      const authWindow = window.open(response.authUrl, '_blank', 'width=500,height=600');

      const messageHandler = (event: MessageEvent) => {
        if (event.origin !== window.location.origin && !event.origin.includes('localhost:8000')) return;

        if (event.data?.type === 'oauth-success' && event.data?.sessionId === response.sessionId) {
          cleanup();
          setAddStatus('success');
          setAddMessage(t.accounts?.oauthSuccess || 'Success!');
          loadAccounts();
          setTimeout(() => {
            setShowAddDialog(false);
            resetAddDialog();
          }, 1500);
          authWindow?.close();
        } else if (event.data?.type === 'oauth-error' && event.data?.sessionId === response.sessionId) {
          cleanup();
          setAddStatus('error');
          setAddMessage(event.data.error || 'OAuth failed');
          authWindow?.close();
        }
      };

      window.addEventListener('message', messageHandler);

      const pollInterval = setInterval(async () => {
        try {
          const status = await apiClient.checkCloudCodeOAuthStatus(response.sessionId);
          if (status.completed) {
            cleanup(pollInterval);
            if (status.success) {
              setAddStatus('success');
              setAddMessage(t.accounts?.oauthSuccess || 'Success!');
              loadAccounts();
              setTimeout(() => {
                setShowAddDialog(false);
                resetAddDialog();
              }, 1500);
            } else {
              setAddStatus('error');
              setAddMessage(status.error || 'OAuth failed');
            }
            authWindow?.close();
          }
        } catch { }
      }, 2000);

      const cleanup = (interval?: NodeJS.Timeout) => {
        window.removeEventListener('message', messageHandler);
        if (interval) clearInterval(interval);
      };

      setTimeout(() => {
        cleanup(pollInterval);
        if (addStatus === 'loading') {
          setAddStatus('error');
          setAddMessage(t.accounts?.oauthTimeout || 'Timeout');
        }
      }, 300000);

    } catch (error: any) {
      setAddStatus('error');
      setAddMessage(error.message || 'Failed to start');
    }
  };

  const handleAddByToken = async () => {
    if (!newToken.trim()) return;
    setAddStatus('loading');

    try {
      const tokens: string[] = [];
      const input = newToken.trim();

      if (input.startsWith('[')) {
        try {
          const parsed = JSON.parse(input);
          if (Array.isArray(parsed)) {
            parsed.forEach((item: any) => {
              if (item.refresh_token?.startsWith('1//')) tokens.push(item.refresh_token);
            });
          }
        } catch { }
      }

      if (tokens.length === 0 && input.includes('1//')) {
        const matches = input.match(/1\/\/[a-zA-Z0-9_\-]+/g);
        if (matches) tokens.push(...matches);
      }

      const uniqueTokens = [...new Set(tokens)];
      if (uniqueTokens.length === 0) throw new Error(t.accounts?.invalidToken || 'Invalid token');

      let successCount = 0;
      for (const token of uniqueTokens) {
        try {
          await apiClient.addCloudCodeAccount('', token);
          successCount++;
        } catch { }
      }

      if (successCount > 0) {
        setAddStatus('success');
        setAddMessage(`Added ${successCount}`);
        loadAccounts();
        setTimeout(() => { setShowAddDialog(false); resetAddDialog(); }, 1500);
      } else {
        throw new Error('Failed to add');
      }
    } catch (error: any) {
      setAddStatus('error');
      setAddMessage(error.message);
    }
  };

  const resetAddDialog = () => {
    setAddTab('oauth');
    setAddStatus('idle');
    setAddMessage('');
    setNewToken('');
    setOauthUrl('');
  };

  // UI Helpers
  const getQuotaColor = (quota: number) => {
    if (quota >= 70) return 'bg-emerald-500';
    if (quota >= 30) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  const QuotaBar = ({ label, value }: { label: string; value: number }) => (
    <div className="space-y-1.5">
      <div className="flex justify-between text-[10px] items-center">
        <span className="text-muted-foreground font-medium">{label}</span>
        <span className={`font-mono font-medium ${value < 20 ? 'text-rose-500' : 'text-foreground'}`}>{value}%</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-secondary">
        <div className={`h-full transition-all duration-500 ${getQuotaColor(value)}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );

  const StatCard = ({ title, value, icon, trend }: { title: string; value: string | number; icon: any; trend?: string }) => (
    <div className="rounded-xl border border-border/60 bg-card p-3 shadow-sm flex items-center justify-between">
      <div>
        <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">{title}</p>
        <p className="text-lg font-bold mt-0.5">{value}</p>
        {trend && <p className="text-[10px] text-emerald-500 font-medium">{trend}</p>}
      </div>
      <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
        {icon}
      </div>
    </div>
  );

  return (
    // Fixed height container - same as KnowledgeBase (h-[calc(100vh-88px)])
    <div className="flex h-[calc(100vh-88px)] flex-col gap-2.5 overflow-hidden">

      {/* Header & Stats Area */}
      <div className="flex-none space-y-1.5">
        <div className="flex items-center justify-between px-1">
          <div>
            <h1 className="text-xl font-bold">{t.accounts?.title || 'Cloud Code'}</h1>
            <p className="text-xs text-muted-foreground">{t.accounts?.subtitle || 'Manage API accounts'}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setRefreshingAll(true); apiClient.refreshAllCloudCodeAccounts().then(loadAccounts).finally(() => setRefreshingAll(false)); }}
              disabled={refreshingAll || isLoading}
              className="group flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-all disabled:opacity-50"
            >
              <svg className={`h-3.5 w-3.5 ${refreshingAll ? 'animate-spin' : 'text-muted-foreground group-hover:text-primary'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {refreshingAll ? (t.common?.processing || 'Refreshing') : (t.accounts?.refreshAll || 'Refresh All')}
            </button>
            <button
              onClick={() => setShowAddDialog(true)}
              className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 shadow-sm transition-all"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              {t.accounts?.addAccount || 'Add Account'}
            </button>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-1">
          <StatCard
            title={t.accounts?.totalAccounts || "Total Accounts"}
            value={stats.totalAccounts}
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>}
          />
          <StatCard
            title={t.accounts?.activeAccounts || "Active"}
            value={stats.activeAccounts}
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
          />
          <StatCard
            title={t.accounts?.totalRequests || "Requests"}
            value={stats.totalRequests.toLocaleString()}
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>}
          />
          <StatCard
            title={t.accounts?.successRate || "Success Rate"}
            value={`${stats.avgSuccessRate}%`}
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>}
          />
        </div>
      </div>

      {/* Main List - Scrollable */}
      <div className="flex-1 overflow-y-auto pr-1 pt-1 pb-1">
        {isLoading ? (
          <div className="flex h-40 items-center justify-center">
            <svg className="h-6 w-6 animate-spin text-primary/50" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : accounts.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/10 text-center">
            <div className="rounded-full bg-muted p-4 mb-3">
              <svg className="h-8 w-8 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <p className="text-sm font-medium text-foreground">{t.accounts?.noAccounts || 'No accounts found'}</p>
            <p className="max-w-xs text-xs text-muted-foreground mt-1">{t.accounts?.noAccountsDesc || 'Add a Cloud Code account to start using AI models.'}</p>
            <button onClick={() => setShowAddDialog(true)} className="mt-4 text-xs bg-primary/10 text-primary px-3 py-1.5 rounded-md hover:bg-primary/20 font-medium transition">
              {t.accounts?.addFirstAccount || 'Connect Account'}
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {accounts.map((acc) => (
              <div
                key={acc.id}
                onClick={() => {
                  setSelectedAccount(acc);
                  apiClient.getCloudCodeAccountDetails(acc.id).then(details => setSelectedAccount(prev => ({ ...prev!, ...details })));
                }}
                className="group relative flex flex-col justify-between rounded-xl border border-border bg-card p-4 transition-all hover:border-primary/50 hover:shadow-md cursor-pointer dark:bg-card/50"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold uppercase ${acc.isDefault ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                        {acc.email.substring(0, 2)}
                      </div>
                      <div>
                        <h3 className="truncate text-xs font-semibold text-foreground">{acc.name || acc.email}</h3>
                        <p className="truncate text-[10px] text-muted-foreground">{acc.email}</p>
                      </div>
                    </div>
                  </div>
                  {acc.isDefault && (
                    <span className="shrink-0 rounded-md bg-primary/10 px-1.5 py-0.5 text-[9px] font-bold text-primary uppercase tracking-wide border border-primary/20">
                      Default
                    </span>
                  )}
                </div>

                {/* Stats */}
                <div className="mt-4 space-y-3">
                  <QuotaBar label="Claude" value={acc.quotas?.claude || 0} />
                  <QuotaBar label="Gemini" value={acc.quotas?.gemini || 0} />
                </div>

                {/* Footer */}
                <div className="mt-4 flex items-center justify-between border-t border-border/40 pt-3">
                  <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    {acc.totalRequests}
                  </span>

                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => { e.stopPropagation(); setRefreshingId(acc.id); apiClient.refreshCloudCodeAccount(acc.id).then(loadAccounts).finally(() => setRefreshingId(null)); }}
                      className={`rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition ${refreshingId === acc.id ? 'animate-spin' : ''}`}
                      title="Refresh"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); if (confirm(t.accounts?.confirmRemove || 'Delete?')) apiClient.removeCloudCodeAccount(acc.id).then(loadAccounts); }}
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-rose-100 hover:text-rose-600 dark:hover:bg-rose-900/30 transition"
                      title="Remove"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Dialog */}
      {showAddDialog && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowAddDialog(false)}>
          <div className="w-full max-w-sm rounded-xl border border-border bg-background shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
            <div className="border-b border-border p-4 bg-muted/20 flex justify-between items-center">
              <h3 className="text-sm font-semibold">{t.accounts?.addAccount || 'Add Account'}</h3>
              <button onClick={() => setShowAddDialog(false)} className="text-muted-foreground hover:text-foreground">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div className="flex rounded-lg bg-muted p-1">
                <button onClick={() => setAddTab('oauth')} className={`flex-1 rounded-md py-1.5 text-xs font-medium transition ${addTab === 'oauth' ? 'bg-background shadow text-primary' : 'text-muted-foreground hover:text-foreground'}`}>{t.accounts?.oauthTab || 'Google OAuth'}</button>
                <button onClick={() => setAddTab('token')} className={`flex-1 rounded-md py-1.5 text-xs font-medium transition ${addTab === 'token' ? 'bg-background shadow text-primary' : 'text-muted-foreground hover:text-foreground'}`}>{t.accounts?.tokenTab || 'Refresh Token'}</button>
              </div>

              {addMessage && (
                <div className={`p-3 rounded-lg text-xs flex items-start gap-2 ${addStatus === 'error' ? 'bg-rose-50 text-rose-700 dark:bg-rose-900/20 dark:text-rose-300' : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300'}`}>
                  <span className="font-bold mt-0.5">{addStatus === 'error' ? '!' : '✓'}</span> <span className="leading-snug">{addMessage}</span>
                </div>
              )}

              {addTab === 'oauth' ? (
                <div className="text-center py-4">
                  <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-3">
                    <svg className="h-6 w-6 text-primary" viewBox="0 0 24 24" fill="currentColor"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" /><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" /><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" /></svg>
                  </div>
                  <button
                    onClick={handleStartOAuth}
                    disabled={addStatus === 'loading'}
                    className="w-full rounded-lg bg-primary py-2.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all shadow-sm"
                  >
                    {addStatus === 'loading' ? (t.accounts?.oauthWaiting || 'Waiting for authorization...') : (t.accounts?.oauthStart || 'Sign in with Google')}
                  </button>
                  <p className="text-[10px] text-muted-foreground mt-3 px-4">
                    {t.accounts?.oauthDesc || 'Securely connect your Google account to access Claude and Gemini models via Cloud Code.'}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="relative">
                    <textarea
                      value={newToken}
                      onChange={e => setNewToken(e.target.value)}
                      placeholder={t.accounts?.tokenPlaceholder || 'Paste refresh token starting with "1//..."'}
                      className="w-full h-32 rounded-lg border border-border bg-background p-3 text-xs font-mono focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none resize-none"
                    />
                    {newToken && (
                      <button onClick={() => setNewToken('')} className="absolute right-2 top-2 text-muted-foreground hover:text-foreground text-[10px] bg-muted px-1.5 py-0.5 rounded">{t.common?.clear || 'Clear'}</button>
                    )}
                  </div>
                  <button
                    onClick={handleAddByToken}
                    disabled={!newToken.trim() || addStatus === 'loading'}
                    className="w-full rounded-lg bg-primary py-2.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all shadow-sm"
                  >
                    {addStatus === 'loading' ? (t.accounts?.addingAccount || 'Adding...') : (t.accounts?.add || 'Add Token')}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Detail Dialog */}
      {selectedAccount && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setSelectedAccount(null)}>
          <div className="w-full max-w-2xl max-h-[80vh] flex flex-col rounded-xl border border-border bg-background shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-border p-4 bg-muted/20">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-xs font-bold text-primary uppercase">
                  {selectedAccount.email.substring(0, 2)}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{selectedAccount.email}</h3>
                  <p className="text-xs text-muted-foreground">Account Details</p>
                </div>
              </div>
              <button onClick={() => setSelectedAccount(null)} className="rounded p-1.5 hover:bg-muted text-muted-foreground">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 bg-muted/5">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Model Quotas</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {selectedAccount.models?.map(m => (
                  <div key={m.name} className="rounded-xl border border-border bg-card p-4 shadow-sm hover:border-primary/30 transition-all">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium">{m.name}</span>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${m.percentage >= 50 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : m.percentage >= 20 ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700'}`}>
                        {m.percentage}%
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
                      <div className={`h-full transition-all duration-700 ${getQuotaColor(m.percentage)}`} style={{ width: `${m.percentage}%` }} />
                    </div>
                    {m.resetTime && (
                      <p className="mt-2 text-[10px] text-muted-foreground flex items-center gap-1 font-mono">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        Reset: {new Date(m.resetTime).toLocaleString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="p-4 border-t border-border bg-background flex justify-end gap-2">
              <button onClick={() => setSelectedAccount(null)} className="px-4 py-2 border border-border rounded-lg text-xs font-medium hover:bg-muted transition">Close</button>
              <button
                onClick={() => { handleRefresh(selectedAccount.id); }}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 transition shadow-sm"
              >
                Refresh Data
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
