import { useMemo, useState } from 'react';
import type { BatchJob } from '@/types';

interface Props {
  jobs: BatchJob[];
  onRetry: (job: BatchJob) => void;
  onDownload: (job: BatchJob) => void;
  onCancel?: (job: BatchJob) => void;
}

const statusColor: Record<BatchJob['status'], string> = {
  queued: 'text-slate-500 bg-slate-100',
  preprocessing: 'text-amber-600 bg-amber-50',
  running: 'text-blue-600 bg-blue-50',
  postprocessing: 'text-indigo-600 bg-indigo-50',
  done: 'text-emerald-700 bg-emerald-50',
  error: 'text-rose-700 bg-rose-50',
  canceled: 'text-slate-500 bg-slate-100',
};

const JobsTable = ({ jobs, onRetry, onDownload, onCancel }: Props) => {
  const [statusFilter, setStatusFilter] = useState<BatchJob['status'] | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<BatchJob['type'] | 'all'>('all');
  const [dateFilter, setDateFilter] = useState('');

  const filtered = useMemo(() => {
    return jobs.filter((job) => {
      const statusOk = statusFilter === 'all' || job.status === statusFilter;
      const typeOk = typeFilter === 'all' || job.type === typeFilter;
      const dateOk = dateFilter ? job.createdAt.startsWith(dateFilter) : true;
      return statusOk && typeOk && dateOk;
    });
  }, [jobs, statusFilter, typeFilter, dateFilter]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)} className="input-modern w-36 text-sm">
          <option value="all">All status</option>
          <option value="queued">Queued</option>
          <option value="preprocessing">Preprocess</option>
          <option value="running">Running</option>
          <option value="postprocessing">Post</option>
          <option value="done">Done</option>
          <option value="error">Error</option>
        </select>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as any)} className="input-modern w-32 text-sm">
          <option value="all">All types</option>
          <option value="ocr">OCR</option>
          <option value="convert">Convert</option>
        </select>
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          className="input-modern w-44 text-sm"
        />
      </div>
      <div className="overflow-hidden rounded-xl border border-border/70">
        <table className="min-w-full divide-y divide-border/70 text-sm">
          <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">File</th>
              <th className="px-3 py-2 text-left font-semibold">Type</th>
              <th className="px-3 py-2 text-left font-semibold">Status</th>
              <th className="px-3 py-2 text-left font-semibold">Progress</th>
              <th className="px-3 py-2 text-left font-semibold">Created</th>
              <th className="px-3 py-2 text-left font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/70 bg-card/60">
            {filtered.map((job) => (
              <tr key={job.id} className="hover:bg-muted/40">
                <td className="px-3 py-2 font-medium text-foreground">{job.fileName}</td>
                <td className="px-3 py-2 capitalize text-muted-foreground">{job.type}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusColor[job.status]}`}>
                    {job.status}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="progress-bar h-1.5">
                    <div className="progress-fill h-1.5" style={{ width: `${job.progress}%` }} />
                  </div>
                  <span className="text-xs text-muted-foreground">{job.progress}%</span>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {new Date(job.createdAt).toLocaleString()}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2 text-xs">
                    <button className="rounded-lg border border-border px-2 py-1" onClick={() => onRetry(job)}>
                      Retry
                    </button>
                    <button className="rounded-lg border border-border px-2 py-1" onClick={() => onDownload(job)}>
                      Download
                    </button>
                    <button
                      className="rounded-lg border border-border px-2 py-1 text-destructive"
                      onClick={() => onCancel?.(job)}
                    >
                      Cancel
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!filtered.length && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">
                  No jobs match the filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default JobsTable;
