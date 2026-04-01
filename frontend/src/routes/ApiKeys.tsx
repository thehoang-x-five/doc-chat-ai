import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useI18n } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api';
import type { AppOutletContext } from '@/App';

interface ApiKeyConfig {
  provider: string;
  name: string;
  description: string;
  keyName: string;
  placeholder: string;
  docsUrl?: string;
  models: string[];
  icon: string;
  category: 'text' | 'image';
}

const API_KEY_CONFIGS: ApiKeyConfig[] = [
  // === TEXT/CHAT MODELS ===
  {
    provider: 'groq',
    name: 'Groq',
    description: 'Fast inference for Llama, Mixtral models',
    keyName: 'GROQ_API_KEY',
    placeholder: 'gsk_...',
    docsUrl: 'https://console.groq.com/keys',
    models: ['llama-3.3-70b', 'mixtral-8x7b', 'gemma2-9b'],
    icon: '⚡',
    category: 'text',
  },
  {
    provider: 'deepseek',
    name: 'DeepSeek',
    description: 'DeepSeek Chat and Coder models',
    keyName: 'DEEPSEEK_API_KEY',
    placeholder: 'sk-...',
    docsUrl: 'https://platform.deepseek.com/api_keys',
    models: ['deepseek-chat', 'deepseek-coder'],
    icon: '🔮',
    category: 'text',
  },
  {
    provider: 'gemini',
    name: 'Google Gemini API',
    description: 'Gemini Pro and Flash models',
    keyName: 'GEMINI_API_KEY',
    placeholder: 'AIza...',
    docsUrl: 'https://aistudio.google.com/app/apikey',
    models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash'],
    icon: '✨',
    category: 'text',
  },
  {
    provider: 'ollama',
    name: 'Ollama (Local)',
    description: 'Local LLM server - no API key needed',
    keyName: 'OLLAMA_BASE_URL',
    placeholder: 'http://localhost:11434',
    docsUrl: 'https://ollama.ai',
    models: ['qwen2.5', 'llama3.2', 'mistral', 'phi3'],
    icon: '🦙',
    category: 'text',
  },
  // === IMAGE GENERATION MODELS ===
  {
    provider: 'together',
    name: 'Together.ai',
    description: '🥇 FLUX.1-schnell - Strongest FREE image model',
    keyName: 'TOGETHER_API_KEY',
    placeholder: 'sk-...',
    docsUrl: 'https://api.together.xyz/',
    models: ['FLUX.1-schnell', 'FLUX.1-pro'],
    icon: '🎨',
    category: 'image',
  },
  {
    provider: 'huggingface',
    name: 'Hugging Face',
    description: '🥉 Stable Diffusion XL - Good quality, free tier',
    keyName: 'HUGGINGFACE_API_KEY',
    placeholder: 'hf_...',
    docsUrl: 'https://huggingface.co/settings/tokens',
    models: ['SDXL', 'SD-2.1', 'Kandinsky'],
    icon: '🤗',
    category: 'image',
  },
  {
    provider: 'stability',
    name: 'Stability AI',
    description: 'Stable Diffusion - 25 free credits',
    keyName: 'STABILITY_API_KEY',
    placeholder: 'sk-...',
    docsUrl: 'https://platform.stability.ai/',
    models: ['SD-v1.6', 'SDXL', 'SD-3'],
    icon: '🖼️',
    category: 'image',
  },
];

interface SavedApiKey {
  provider: string;
  hasKey: boolean;
  lastUpdated?: string;
  isValid?: boolean;
}

export default function ApiKeys() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { pushToast } = useOutletContext<AppOutletContext>();
  const isAdmin = user?.role === 'admin';

  const [savedKeys, setSavedKeys] = useState<SavedApiKey[]>([]);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [keyValue, setKeyValue] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<'all' | 'text' | 'image'>('all');

  useEffect(() => {
    loadApiKeys();
  }, []);

  const loadApiKeys = async () => {
    try {
      setIsLoading(true);
      const keys = await apiClient.getApiKeys();
      setSavedKeys(keys);
    } catch (error) {
      console.error('Failed to load API keys:', error);
      // Initialize with empty state
      setSavedKeys(API_KEY_CONFIGS.map(c => ({ provider: c.provider, hasKey: false })));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveKey = async (provider: string) => {
    if (!keyValue.trim()) {
      pushToast({ type: 'error', message: t.apiKeys?.keyRequired || 'Please enter an API key' });
      return;
    }

    setIsSaving(true);
    try {
      await apiClient.saveApiKey(provider, keyValue);
      pushToast({ type: 'success', message: t.apiKeys?.keySaved || 'API key saved successfully' });
      setEditingProvider(null);
      setKeyValue('');
      await loadApiKeys();
    } catch (error: any) {
      pushToast({ type: 'error', message: error.message || 'Failed to save API key' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteKey = async (provider: string) => {
    if (!confirm(t.apiKeys?.confirmDelete || 'Delete this API key?')) return;

    try {
      await apiClient.deleteApiKey(provider);
      pushToast({ type: 'success', message: t.apiKeys?.keyDeleted || 'API key deleted' });
      await loadApiKeys();
    } catch (error: any) {
      pushToast({ type: 'error', message: error.message || 'Failed to delete API key' });
    }
  };

  const handleTestKey = async (provider: string) => {
    setTestingProvider(provider);
    try {
      const result = await apiClient.testApiKey(provider);
      if (result.valid) {
        pushToast({ type: 'success', message: t.apiKeys?.keyValid || 'API key is valid!' });
      } else {
        pushToast({ type: 'error', message: result.error || t.apiKeys?.keyInvalid || 'API key is invalid' });
      }
      await loadApiKeys();
    } catch (error: any) {
      pushToast({ type: 'error', message: error.message || 'Failed to test API key' });
    } finally {
      setTestingProvider(null);
    }
  };

  const getKeyStatus = (provider: string) => {
    const saved = savedKeys.find(k => k.provider === provider);
    if (!saved?.hasKey) return null;
    if (saved.isValid === true) return 'valid';
    if (saved.isValid === false) return 'invalid';
    return 'unknown';
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
    <div className="flex h-[calc(100vh-88px)] gap-2 overflow-hidden">
      {/* Left Sidebar - Stats & Quick Actions */}
      <div className="w-48 flex flex-col gap-2">
        {/* Quick Stats */}
        <div className="rounded-xl border border-border bg-card/50 p-3">
          <h2 className="text-sm font-semibold mb-3">{t.apiKeys?.quickStats || 'Quick Stats'}</h2>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t.apiKeys?.configured || 'Configured'}</span>
              <span className="font-semibold text-green-600">{savedKeys.filter(k => k.hasKey).length}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t.apiKeys?.available || 'Available'}</span>
              <span className="font-semibold">{API_KEY_CONFIGS.length}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t.apiKeys?.valid || 'Valid'}</span>
              <span className="font-semibold text-green-600">{savedKeys.filter(k => k.isValid === true).length}</span>
            </div>
          </div>
        </div>

        {/* Provider Categories */}
        <div className="flex-1 rounded-xl border border-border bg-card/50 p-2 overflow-hidden">
          <h2 className="text-sm font-semibold mb-2 px-1">{t.apiKeys?.categories || 'Categories'}</h2>
          <div className="space-y-1">
            <button
              onClick={() => setFilterCategory('all')}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm font-medium transition ${filterCategory === 'all'
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-muted text-muted-foreground'
                }`}
            >
              <span>🌐</span>
              <span>{t.models?.allModels || 'All Models'}</span>
              <span className={`ml-auto text-xs px-1.5 py-0.5 rounded ${filterCategory === 'all' ? 'bg-primary/20' : 'bg-muted'}`}>
                {API_KEY_CONFIGS.length}
              </span>
            </button>
            <button
              onClick={() => setFilterCategory('text')}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm font-medium transition ${filterCategory === 'text'
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-muted text-muted-foreground'
                }`}
            >
              <span>💬</span>
              <span>{t.apiKeys?.textModels || 'Text/Chat'}</span>
              <span className={`ml-auto text-xs px-1.5 py-0.5 rounded ${filterCategory === 'text' ? 'bg-primary/20' : 'bg-muted'}`}>
                {API_KEY_CONFIGS.filter(c => c.category === 'text').length}
              </span>
            </button>
            <button
              onClick={() => setFilterCategory('image')}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm font-medium transition ${filterCategory === 'image'
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-muted text-muted-foreground'
                }`}
            >
              <span>🎨</span>
              <span>{t.apiKeys?.imageModels || 'Image Gen'}</span>
              <span className={`ml-auto text-xs px-1.5 py-0.5 rounded ${filterCategory === 'image' ? 'bg-primary/20' : 'bg-muted'}`}>
                {API_KEY_CONFIGS.filter(c => c.category === 'image').length}
              </span>
            </button>
          </div>
        </div>

        {/* Tip */}
        <div className="rounded-xl border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20 p-3">
          <p className="text-xs text-green-700 dark:text-green-300">
            💡 {t.apiKeys?.tip || 'Add API keys to unlock free AI models without using Cloud Code quota.'}
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-2 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between flex-shrink-0">
          <div>
            <h1 className="text-xl font-bold">{t.apiKeys?.title || 'API Keys'}</h1>
            <p className="text-xs text-muted-foreground">
              {t.apiKeys?.subtitle || 'Configure API keys for free AI providers'}
            </p>
          </div>
          <button
            onClick={loadApiKeys}
            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-all"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {t.apiKeys?.refresh || 'Refresh'}
          </button>
        </div>

        {/* API Keys Grid */}
        <div className="flex-1 rounded-xl border border-border bg-card/50 p-3 overflow-auto">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {API_KEY_CONFIGS.filter(c => filterCategory === 'all' || c.category === filterCategory).map((config) => {
              const saved = savedKeys.find(k => k.provider === config.provider);
              const status = getKeyStatus(config.provider);
              const isEditing = editingProvider === config.provider;

              return (
                <div key={config.provider} className="rounded-xl border border-border bg-card p-3 transition hover:shadow-md hover:border-primary/30">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-lg flex-shrink-0">
                        {config.icon}
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold truncate">{config.name}</h3>
                        <p className="text-[10px] text-muted-foreground line-clamp-1">{config.description}</p>
                      </div>
                    </div>
                    {status && (
                      <span className={`rounded-full px-1.5 py-0.5 text-[10px] whitespace-nowrap font-medium ${status === 'valid' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        status === 'invalid' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                          'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                        }`}>
                        {status === 'valid' ? (t.apiKeys?.valid || 'Valid') :
                          status === 'invalid' ? (t.apiKeys?.invalid || 'Invalid') :
                            (t.apiKeys?.configured || 'Configured')}
                      </span>
                    )}
                  </div>

                  {/* Models */}
                  <div className="mt-3 flex flex-wrap gap-1">
                    {config.models.map((model) => (
                      <span key={model} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {model}
                      </span>
                    ))}
                  </div>

                  {/* Edit form */}
                  {isEditing ? (
                    <div className="mt-4 space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-muted-foreground">{config.keyName}</label>
                        <input
                          type="password"
                          value={keyValue}
                          onChange={(e) => setKeyValue(e.target.value)}
                          placeholder={config.placeholder}
                          className="mt-1 block w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:border-primary focus:outline-none"
                          autoFocus
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setEditingProvider(null); setKeyValue(''); }}
                          className="flex-1 rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-muted"
                        >
                          {t.common?.cancel || 'Cancel'}
                        </button>
                        <button
                          onClick={() => handleSaveKey(config.provider)}
                          disabled={isSaving || !keyValue.trim()}
                          className="flex-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
                        >
                          {isSaving ? (t.common?.loading || 'Saving...') : (t.common?.save || 'Save')}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 flex gap-2">
                      {saved?.hasKey ? (
                        <>
                          <button
                            onClick={() => handleTestKey(config.provider)}
                            disabled={testingProvider === config.provider}
                            className="flex-1 rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-muted disabled:opacity-50"
                          >
                            {testingProvider === config.provider ? (
                              <span className="flex items-center justify-center gap-1">
                                <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Testing...
                              </span>
                            ) : (t.apiKeys?.test || 'Test')}
                          </button>
                          <button
                            onClick={() => setEditingProvider(config.provider)}
                            className="flex-1 rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-muted"
                          >
                            {t.apiKeys?.update || 'Update'}
                          </button>
                          <button
                            onClick={() => handleDeleteKey(config.provider)}
                            className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/20"
                          >
                            {t.common?.delete || 'Delete'}
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => setEditingProvider(config.provider)}
                          className="flex-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90"
                        >
                          {t.apiKeys?.addKey || 'Add API Key'}
                        </button>
                      )}
                      {config.docsUrl && (
                        <a
                          href={config.docsUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-muted"
                          title={t.apiKeys?.getDocs || 'Get API Key'}
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      )}
                    </div>
                  )}

                  {saved?.lastUpdated && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      {t.apiKeys?.lastUpdated || 'Last updated'}: {new Date(saved.lastUpdated).toLocaleString()}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Admin section */}
          {isAdmin && (
            <div className="rounded-2xl border border-purple-200 bg-purple-50 p-5 dark:border-purple-800 dark:bg-purple-900/20">
              <h3 className="font-semibold text-purple-800 dark:text-purple-200">
                {t.apiKeys?.adminSection || 'Admin: System Default Keys'}
              </h3>
              <p className="mt-1 text-sm text-purple-700 dark:text-purple-300">
                {t.apiKeys?.adminDesc || 'These keys are used as fallback when users don\'t have their own keys configured.'}
              </p>
              <button
                onClick={() => {/* TODO: Open admin key management */ }}
                className="mt-3 rounded-lg border border-purple-300 bg-white px-4 py-2 text-sm font-medium text-purple-700 transition hover:bg-purple-100 dark:border-purple-700 dark:bg-purple-900/50 dark:text-purple-200 dark:hover:bg-purple-900"
              >
                {t.apiKeys?.manageSystemKeys || 'Manage System Keys'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
