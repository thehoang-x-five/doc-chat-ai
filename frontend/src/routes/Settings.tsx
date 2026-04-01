import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import Card from '@/components/common/Card';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';
import type { AppOutletContext } from '@/App';
import type { OcrLanguage, OcrMode } from '@/types';

const Settings = () => {
  const { pushToast } = useOutletContext<AppOutletContext>();
  const { t, language: uiLanguage, setLanguage: setUiLanguage } = useI18n();
  const { user, logout } = useAuth();
  const [language, setLanguage] = useState<OcrLanguage>('auto');
  const [mode, setMode] = useState<OcrMode>('balanced');
  const [autosave, setAutosave] = useState(true);
  
  // Backend settings
  const [parser, setParser] = useState<'docling' | 'mineru'>('docling');
  const [parseMethod, setParseMethod] = useState<'auto' | 'ocr' | 'txt'>('auto');
  const [useLocalOllama, setUseLocalOllama] = useState(false);
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState('http://localhost:11434/api');
  const [ollamaLlmModel, setOllamaLlmModel] = useState('qwen2.5:7b');
  const [ollamaEmbedModel, setOllamaEmbedModel] = useState('nomic-embed-text');
  const [ollamaVisionModel, setOllamaVisionModel] = useState('llava:7b');
  
  // Backend status
  const [backendStatus, setBackendStatus] = useState<{
    connected: boolean;
    version?: string;
    parserDefault?: string;
    enableRag?: boolean;
    ollamaReachable?: boolean;
  }>({ connected: false });

  useEffect(() => {
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const health = await apiClient.checkHealth();
      setBackendStatus({
        connected: true,
        version: health.version,
        parserDefault: health.parserDefault,
        enableRag: health.enableRag,
        ollamaReachable: health.ollamaReachable
      });
      
      if (health.parserDefault) {
        setParser(health.parserDefault as 'docling' | 'mineru');
      }
      setUseLocalOllama(health.enableRag);
    } catch (error) {
      setBackendStatus({ connected: false });
      console.warn('Backend health check failed:', error);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t.settings.title}</h1>
        <p className="text-muted-foreground">{t.settings.subtitle}</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {/* User Profile */}
        {user && (
          <Card title={t.settings?.userProfile || 'User Profile'} description={t.settings?.userProfileDesc || 'Your account information'}>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-2xl font-bold text-primary">
                  {user.name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="font-semibold text-lg">{user.name}</div>
                  <div className="text-sm text-muted-foreground">{user.email}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'
                    }`}>
                      {user.role}
                    </span>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">{t.settings?.memberSince || 'Member since'}:</span>
                  <div className="font-medium">{new Date(user.createdAt).toLocaleDateString()}</div>
                </div>
                {user.lastLogin && (
                  <div>
                    <span className="text-muted-foreground">{t.settings?.lastLogin || 'Last login'}:</span>
                    <div className="font-medium">{new Date(user.lastLogin).toLocaleString()}</div>
                  </div>
                )}
              </div>
              <button
                onClick={async () => {
                  await logout();
                  pushToast({ type: 'info', message: t.settings?.loggedOut || 'Logged out successfully' });
                }}
                className="w-full rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100"
              >
                {t.settings?.logout || 'Sign out'}
              </button>
            </div>
          </Card>
        )}

        <Card title={t.settings.uiLanguage} description={t.settings.uiLanguageDesc}>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setUiLanguage('vi')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition ${
                uiLanguage === 'vi' 
                  ? 'border-primary bg-primary/10 text-primary' 
                  : 'border-border hover:bg-muted'
              }`}
            >
              <span className="text-lg">🇻🇳</span>
              <span className="font-medium">Tiếng Việt</span>
            </button>
            <button
              onClick={() => setUiLanguage('en')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition ${
                uiLanguage === 'en' 
                  ? 'border-primary bg-primary/10 text-primary' 
                  : 'border-border hover:bg-muted'
              }`}
            >
              <span className="text-lg">🇺🇸</span>
              <span className="font-medium">English</span>
            </button>
          </div>
        </Card>

        <Card title={t.settings.backendStatus} description={t.settings.connectionStatus}>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${backendStatus.connected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm">
                {backendStatus.connected ? t.settings.connected : t.settings.disconnected}
              </span>
              {backendStatus.version && (
                <span className="text-xs text-muted-foreground">v{backendStatus.version}</span>
              )}
            </div>
            
            {backendStatus.connected && (
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-muted-foreground">{t.settings.parser}:</span>{' '}
                  <span className="font-medium">{backendStatus.parserDefault}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">{t.settings.rag}:</span>{' '}
                  <span className="font-medium">{backendStatus.enableRag ? t.settings.enabled : t.settings.disabled}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">{t.settings.ollama}:</span>{' '}
                  <span className="font-medium">{backendStatus.ollamaReachable ? t.settings.connected : t.settings.disconnected}</span>
                </div>
              </div>
            )}
            
            <button 
              onClick={checkBackendHealth}
              className="btn-secondary text-xs"
            >
              {t.settings.refreshStatus}
            </button>
          </div>
        </Card>

        <Card title={t.settings.defaultOcrSettings}>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <label className="flex flex-col gap-1">
              {t.settings.parser}
              <select 
                value={parser} 
                onChange={(e) => setParser(e.target.value as 'docling' | 'mineru')} 
                className="input-modern text-sm"
                disabled={!backendStatus.connected}
              >
                <option value="docling">Docling (Default)</option>
                <option value="mineru">MinerU</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              {t.settings.parseMethod}
              <select 
                value={parseMethod} 
                onChange={(e) => setParseMethod(e.target.value as 'auto' | 'ocr' | 'txt')} 
                className="input-modern text-sm"
                disabled={!backendStatus.connected}
              >
                <option value="auto">{t.ocrSettings.auto}</option>
                <option value="ocr">OCR</option>
                <option value="txt">Text</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              {t.settings.language}
              <select value={language} onChange={(e) => setLanguage(e.target.value as OcrLanguage)} className="input-modern text-sm">
                <option value="auto">{t.ocrSettings.auto}</option>
                <option value="vi">{t.ocrSettings.vietnamese}</option>
                <option value="en">{t.ocrSettings.english}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              {t.settings.mode}
              <select value={mode} onChange={(e) => setMode(e.target.value as OcrMode)} className="input-modern text-sm">
                <option value="fast">{t.ocrSettings.fast}</option>
                <option value="balanced">{t.ocrSettings.balanced}</option>
                <option value="accurate">{t.ocrSettings.accurate}</option>
              </select>
            </label>
            <label className="flex items-center gap-2 col-span-2">
              <input type="checkbox" checked={autosave} onChange={(e) => setAutosave(e.target.checked)} />
              {t.settings.autosaveResults}
            </label>
          </div>
        </Card>

        <Card title={t.settings.localOllamaSettings} description={t.settings.localOllamaDesc}>
          <div className="space-y-3">
            <label className="flex items-center gap-2">
              <input 
                type="checkbox" 
                checked={useLocalOllama} 
                onChange={(e) => setUseLocalOllama(e.target.checked)} 
              />
              {t.settings.useLocalOllama}
            </label>
            
            {useLocalOllama && (
              <div className="space-y-3 pl-6 border-l-2 border-border/50">
                <label className="flex flex-col gap-1">
                  {t.settings.baseUrl}
                  <input 
                    type="text" 
                    value={ollamaBaseUrl} 
                    onChange={(e) => setOllamaBaseUrl(e.target.value)}
                    className="input-modern text-sm"
                    placeholder="http://localhost:11434/api"
                  />
                </label>
                
                <div className="grid grid-cols-1 gap-2">
                  <label className="flex flex-col gap-1">
                    {t.settings.llmModel}
                    <input 
                      type="text" 
                      value={ollamaLlmModel} 
                      onChange={(e) => setOllamaLlmModel(e.target.value)}
                      className="input-modern text-sm"
                      placeholder="qwen2.5:7b"
                    />
                  </label>
                  
                  <label className="flex flex-col gap-1">
                    {t.settings.embeddingModel}
                    <input 
                      type="text" 
                      value={ollamaEmbedModel} 
                      onChange={(e) => setOllamaEmbedModel(e.target.value)}
                      className="input-modern text-sm"
                      placeholder="nomic-embed-text"
                    />
                  </label>
                  
                  <label className="flex flex-col gap-1">
                    {t.settings.visionModel}
                    <input 
                      type="text" 
                      value={ollamaVisionModel} 
                      onChange={(e) => setOllamaVisionModel(e.target.value)}
                      className="input-modern text-sm"
                      placeholder="llava:7b"
                    />
                  </label>
                </div>
                
                <div className="text-xs text-muted-foreground">
                  <p>{t.settings.ollamaInstructions}</p>
                  <code className="block mt-1 p-2 bg-muted rounded text-xs">
                    ollama pull {ollamaLlmModel}<br/>
                    ollama pull {ollamaEmbedModel}<br/>
                    ollama pull {ollamaVisionModel}
                  </code>
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card title={t.settings.limitsCompliance} description={t.settings.limitsDesc}>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>{t.settings.maxFileSize}</li>
            <li>{t.settings.allowedTypes}</li>
            <li>{t.settings.retentionPolicy}</li>
            <li>{t.settings.piiDetection}</li>
            <li>{t.settings.localProcessing}</li>
          </ul>
        </Card>
      </div>
    </div>
  );
};

export default Settings;
