import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import Card from '@/components/common/Card';
import Dropzone from '@/components/ocr/Dropzone';
import JobsTable from '@/components/batch/JobsTable';
import { createBatchJobs, createBatchJobsWithBackend, getJobs } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import type { AppOutletContext } from '@/App';
import type { BatchJob, OcrSettings } from '@/types';

const batchDefaults: OcrSettings = {
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
    qualityScore: 90,
  },
  layout: {
    preserveLayout: true,
    keepLineBreaks: true,
    detectColumns: true,
    detectHeadersFooters: false,
    detectLists: true,
    detectForms: false,
  },
  region: { mode: 'full', regions: [], activePage: 1 },
  post: {
    spellCorrection: true,
    customVocabulary: '',
    regexCleanup: { phone: true, email: true, date: true, id: false },
    normalizeWhitespace: true,
    maskSensitive: false,
    highlightLowConfidence: true,
  },
  intelligence: { tableExtraction: true, keyValueExtraction: true, entityExtraction: true, template: 'invoice' },
  security: { retention: '30d', piiDetection: false, redaction: false },
  output: { exportFormats: ['txt', 'md', 'json'], mergePages: true, includeConfidence: true },
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

const BatchJobs = () => {
  const { pushToast } = useOutletContext<AppOutletContext>();
  const { t } = useI18n();
  const [files, setFiles] = useState<File[]>([]);
  const [jobs, setJobs] = useState<BatchJob[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const totalSizeMb = files.reduce((sum, f) => sum + f.size, 0) / 1_000_000;
  const typeCounts = files.reduce<Record<string, number>>((acc, file) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || 'unknown';
    acc[ext] = (acc[ext] || 0) + 1;
    return acc;
  }, {});
  const topTypes = Object.entries(typeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([ext, count]) => `${ext.toUpperCase()} ×${count}`)
    .join(', ');

  useEffect(() => {
    getJobs().then(setJobs);
  }, []);

  const createJobs = async () => {
    if (!files.length) {
      pushToast({ type: 'error', message: t.batch.selectFirst });
      return;
    }
    setIsCreating(true);
    
    try {
      const created = await createBatchJobsWithBackend(files, batchDefaults);
      setJobs((prev) => [...created, ...prev]);
      setFiles([]);
      pushToast({ type: 'success', message: `${created.length} ${t.batch.jobsQueuedBackend}` });
    } catch (error) {
      console.warn('Backend batch processing failed, falling back to demo:', error);
      const created = await createBatchJobs(files, batchDefaults);
      setJobs((prev) => [...created, ...prev]);
      setFiles([]);
      pushToast({ type: 'info', message: `${created.length} ${t.batch.jobsQueuedDemo}` });
    }
    
    setIsCreating(false);
  };

  const handleRetry = (job: BatchJob) => {
    pushToast({ type: 'info', message: `${t.batch.retrying} ${job.fileName}` });
  };

  const handleDownload = (job: BatchJob) => {
    pushToast({ type: 'success', message: `${t.batch.downloading} ${job.fileName}` });
  };

  const handleCancel = (job: BatchJob) => {
    pushToast({ type: 'error', message: `${t.batch.canceled} ${job.fileName}` });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="rounded-2xl border border-border/70 bg-card/90 px-4 py-2 text-sm shadow-sm">
          <span className="text-muted-foreground">{t.common.files}:</span>{' '}
          <span className="font-semibold text-foreground">{files.length || 0}</span>
        </div>
        <div className="rounded-2xl border border-border/70 bg-card/90 px-4 py-2 text-sm shadow-sm">
          <span className="text-muted-foreground">{t.common.totalSize}:</span>{' '}
          <span className="font-semibold text-foreground">
            {totalSizeMb ? `${totalSizeMb.toFixed(2)} MB` : '0 MB'}
          </span>
        </div>
        <div className="rounded-2xl border border-border/70 bg-card/90 px-4 py-2 text-sm shadow-sm">
          <span className="text-muted-foreground">{t.common.types}:</span>{' '}
          <span className="font-semibold text-foreground">
            {topTypes || '—'}
          </span>
        </div>
        <div className="rounded-2xl border border-border/70 bg-card/90 px-4 py-2 text-sm shadow-sm">
          <span className="text-muted-foreground">{t.common.queuedJobs}:</span>{' '}
          <span className="font-semibold text-foreground">{jobs.length}</span>
        </div>
        <button className="btn-gradient ml-auto" onClick={createJobs} disabled={!files.length || isCreating}>
          {isCreating ? t.batch.queuing : t.batch.createJobs}
        </button>
      </div>

      <Card title={t.batch.batchUpload} description={t.batch.batchUploadDesc}>
        <Dropzone files={files} onFiles={setFiles} multiple onError={(m) => pushToast({ type: 'error', message: m })} />
      </Card>

      <Card title={t.batch.jobQueue} description={t.batch.jobQueueDesc}>
        <JobsTable jobs={jobs} onRetry={handleRetry} onDownload={handleDownload} onCancel={handleCancel} />
      </Card>
    </div>
  );
};

export default BatchJobs;
