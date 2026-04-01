import { useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import Card from '@/components/common/Card';
import Dropzone from '@/components/ocr/Dropzone';
import FilePreview from '@/components/ocr/FilePreview';
import OcrSettingsPanel from '@/components/ocr/OcrSettingsPanel';
import ProgressSteps from '@/components/ocr/ProgressSteps';
import TextResultEditor from '@/components/ocr/TextResultEditor';
import LayoutViewer from '@/components/ocr/LayoutViewer';
import { uploadAndExtractText } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import type { AppOutletContext } from '@/App';
import type { OcrResult, OcrSettings, ProcessStatus, ProgressState } from '@/types';
import { downloadBlob, findMatches } from '@/utils/file';

const defaultSettings: OcrSettings = {
  language: 'auto',
  mode: 'balanced',
  preprocess: {
    autoOrient: true,
    rotate: 0,
    deskew: true,
    denoise: true,
    deblur: false,
    binarize: false,
    contrastBoost: true,
    brightness: 0,
    shadowRemoval: false,
    removeLines: false,
    dpiNormalize: true,
    qualityScore: 92,
  },
  layout: {
    preserveLayout: true,
    keepLineBreaks: true,
    detectColumns: true,
    detectHeadersFooters: true,
    detectLists: true,
    detectForms: true,
  },
  region: {
    mode: 'full',
    regions: [],
    activePage: 1,
  },
  post: {
    spellCorrection: true,
    customVocabulary: '',
    regexCleanup: {
      phone: true,
      email: true,
      date: true,
      id: false,
    },
    normalizeWhitespace: true,
    maskSensitive: false,
    highlightLowConfidence: true,
  },
  intelligence: {
    tableExtraction: true,
    keyValueExtraction: true,
    entityExtraction: true,
    template: 'none',
  },
  security: {
    retention: '30d',
    piiDetection: true,
    redaction: false,
  },
  output: {
    exportFormats: ['txt', 'md', 'json', 'pdf'],
    mergePages: true,
    includeConfidence: true,
  },
  parser: 'docling',
  parseMethod: 'auto',
  preserveLayout: true,
  returnLayout: true,
  extract: {
    tables: true,
    equations: true,
    images: false,
  },
};

const Extract = () => {
  const { searchQuery, pushToast } = useOutletContext<AppOutletContext>();
  const { t } = useI18n();
  const [files, setFiles] = useState<File[]>([]);
  const [settings, setSettings] = useState<OcrSettings>(defaultSettings);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [status, setStatus] = useState<ProcessStatus>('idle');
  const [result, setResult] = useState<OcrResult | null>(null);
  const [editorText, setEditorText] = useState('');
  const [history, setHistory] = useState<OcrResult[]>([]);

  const uploadedFile = files[0] || null;
  const matches = useMemo(() => findMatches(editorText, searchQuery), [editorText, searchQuery]);

  const runOcr = async () => {
    if (!uploadedFile) {
      pushToast({ type: 'error', message: t.extract.uploadFirst });
      return;
    }
    setStatus('running');
    setResult(null);
    try {
      const data = await uploadAndExtractText(uploadedFile, settings, setProgress);
      setResult(data);
      setEditorText(data.fullText);
      setStatus('done');
      setHistory((prev) => [data, ...prev].slice(0, 5));
      pushToast({ type: 'success', title: t.extract.ocrDone, message: t.extract.textExtracted });
    } catch (err) {
      console.error(err);
      setStatus('error');
      pushToast({ type: 'error', message: t.extract.ocrFailed });
    }
  };

  const handleDownload = () => {
    if (!editorText) return;
    const blob = new Blob([editorText], { type: 'text/plain' });
    downloadBlob(blob, `${uploadedFile?.name || 'ocr-result'}.txt`);
    pushToast({ type: 'info', message: t.extract.downloadedText });
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(editorText);
    pushToast({ type: 'success', message: t.extract.copiedClipboard });
  };

  const handleClear = () => {
    setEditorText('');
    setResult(null);
    setStatus('idle');
    setProgress(null);
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-[1.2fr_1.8fr] items-start">
        <div className="space-y-4 min-w-0">
          <Card title={t.extract.uploadTitle} description={t.extract.uploadDesc}>
            <Dropzone files={files} onFiles={setFiles} onError={(m) => pushToast({ type: 'error', message: m })} />
          </Card>
          <Card title={t.extract.preview}>
            <FilePreview file={uploadedFile} result={result} />
          </Card>
          <Card title={t.extract.preprocessOutput}>
            <OcrSettingsPanel settings={settings} onChange={setSettings} disabled={status === 'running'} />
          </Card>
        </div>

        <div className="space-y-4 min-w-0">
          <Card title={t.extract.progress} description={t.extract.progressDesc}>
            <ProgressSteps progress={progress} status={status} />
            <div className="mt-3 rounded-lg border border-border/70 bg-muted/40 p-3 text-xs text-muted-foreground">
              {t.extract.queueInfo}
            </div>
          </Card>
          <Card title={t.extract.layoutResult} description={t.extract.layoutResultDesc}>
            <div className="space-y-4">
              <LayoutViewer layoutPages={result?.layoutPages} fullText={editorText || result?.fullText || ''} text={editorText} />
              <TextResultEditor
                value={editorText}
                onChange={setEditorText}
                onCopy={handleCopy}
                onClear={handleClear}
                onDownload={handleDownload}
                searchQuery={searchQuery}
                matches={matches}
                lowConfidenceRanges={result?.pages?.[0]?.lowConfidenceRanges}
                result={result}
                status={status}
              />
            </div>
          </Card>
          <button
            onClick={runOcr}
            disabled={!uploadedFile || status === 'running'}
            className="btn-gradient flex items-center justify-center gap-2 w-full"
          >
            {status === 'running' ? t.common.processing : t.extract.runOcr}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Extract;
