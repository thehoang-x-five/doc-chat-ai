import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import Card from '@/components/common/Card';
import Dropzone from '@/components/ocr/Dropzone';
import { convertTextToFile, readTextFile } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import type { AppOutletContext } from '@/App';
import type { ConvertOptions, ProcessStatus, ProgressState } from '@/types';
import { downloadBlob } from '@/utils/file';

const defaultOptions: ConvertOptions = {
  format: 'txt',
  fileName: 'output',
  includeMetadata: true,
  includeHeader: true,
  pageSize: 'A4',
};

const Convert = () => {
  const { pushToast } = useOutletContext<AppOutletContext>();
  const { t } = useI18n();
  const [text, setText] = useState('');
  const [options, setOptions] = useState<ConvertOptions>(defaultOptions);
  const [status, setStatus] = useState<ProcessStatus>('idle');
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [textFiles, setTextFiles] = useState<File[]>([]);

  const handleConvert = async () => {
    if (!text.trim()) {
      pushToast({ type: 'error', message: t.convert.pasteFirst });
      return;
    }
    setStatus('running');
    try {
      const blob = await convertTextToFile(text, options, setProgress);
      const fileName = `${options.fileName || 'output'}.${options.format}`;
      downloadBlob(blob, fileName);
      setStatus('done');
      pushToast({ type: 'success', message: `${t.toast.downloaded} ${fileName}` });
    } catch (err) {
      console.error(err);
      setStatus('error');
      pushToast({ type: 'error', message: t.convert.conversionFailed });
    }
  };

  const handleTextUpload = async (incoming: File[]) => {
    setTextFiles(incoming);
    const file = incoming[0];
    if (!file) {
      setText('');
      return;
    }
    const content = await readTextFile(file);
    setText(content);
    setOptions((prev) => ({ ...prev, fileName: file.name.replace(/\.[^.]+$/, '') }));
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr] items-start xl:min-h-[calc(100vh-160px)]">
        <div className="space-y-4 min-w-0 h-full flex flex-col min-h-[calc(100vh-160px)]">
          <Card title={t.convert.inputText} description={t.convert.inputDesc}>
            <div className="rounded-2xl border border-border/70 bg-card/80 p-4 shadow-sm">
              <p className="mb-2 text-sm font-semibold text-foreground">{t.convert.rawInput}</p>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={14}
                className="text-editor w-full rounded-xl border border-border/70 bg-card/80 p-3"
                placeholder={t.convert.pastePlaceholder}
              />
            </div>
            <div className="mt-3">
              <Dropzone files={textFiles} onFiles={handleTextUpload} multiple={false} />
            </div>
          </Card>
        </div>

        <div className="space-y-4 min-w-0">
          <Card title={t.convert.options} description={t.convert.optionsDesc}>
            <div className="grid gap-3 sm:grid-cols-2 text-sm">
              <label className="flex flex-col gap-1">
                {t.convert.format}
                <select
                  value={options.format}
                  onChange={(e) => setOptions({ ...options, format: e.target.value as ConvertOptions['format'] })}
                  className="input-modern text-sm"
                >
                  <option value="txt">TXT</option>
                  <option value="md">Markdown</option>
                  <option value="json">JSON</option>
                  <option value="pdf">Searchable PDF</option>
                  <option value="docx">DOCX</option>
                </select>
              </label>
              <label className="flex flex-col gap-1">
                {t.convert.fileName}
                <input
                  value={options.fileName}
                  onChange={(e) => setOptions({ ...options, fileName: e.target.value })}
                  className="input-modern text-sm"
                />
              </label>
              <label className="flex flex-col gap-1">
                {t.convert.pageSize}
                <select
                  value={options.pageSize}
                  onChange={(e) => setOptions({ ...options, pageSize: e.target.value as ConvertOptions['pageSize'] })}
                  className="input-modern text-sm"
                >
                  <option value="A4">A4</option>
                  <option value="Letter">Letter</option>
                  <option value="auto">Auto</option>
                </select>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={options.includeMetadata}
                  onChange={(e) => setOptions({ ...options, includeMetadata: e.target.checked })}
                />
                {t.convert.includeMetadata}
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={options.includeHeader}
                  onChange={(e) => setOptions({ ...options, includeHeader: e.target.checked })}
                />
                {t.convert.includeHeader}
              </label>
            </div>
          </Card>

          <Card title={t.convert.progressTitle} description={t.convert.progressDesc}>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress ? Math.round((progress.current / progress.total) * 100) : 0}%` }} />
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{progress?.label || t.common.waiting}</p>
            {status === 'done' && <p className="text-sm text-emerald-600">{t.convert.conversionFinished}</p>}
          </Card>

          <button className="btn-gradient w-full" onClick={handleConvert} disabled={!text.trim() || status === 'running'}>
            {status === 'running' ? t.convert.converting : t.convert.convertDownload}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Convert;
