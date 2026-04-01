import { useEffect, useState } from 'react';
import Card from '@/components/common/Card';
import JobsTable from '@/components/batch/JobsTable';
import { getJobs } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import type { BatchJob } from '@/types';

const History = () => {
  const [jobs, setJobs] = useState<BatchJob[]>([]);
  const { t } = useI18n();

  useEffect(() => {
    getJobs().then(setJobs);
  }, []);

  const handleRetry = (job: BatchJob) => {
    setJobs((prev) =>
      prev.map((j) => (j.id === job.id ? { ...j, status: 'queued', progress: 0, updatedAt: new Date().toISOString() } : j))
    );
  };

  const handleDownload = (job: BatchJob) => {
    console.info('Download', job.fileName);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{t.history.title}</h1>
          <p className="text-muted-foreground text-sm">{t.history.subtitle}</p>
        </div>
      </div>

      <Card title={t.history.jobHistory} description={t.history.jobHistoryDesc}>
        <JobsTable jobs={jobs} onRetry={handleRetry} onDownload={handleDownload} />
      </Card>
    </div>
  );
};

export default History;
