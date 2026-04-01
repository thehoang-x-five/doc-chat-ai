import { motion } from 'framer-motion';
import type { ProcessStatus, ProgressState } from '@/types';

interface Props {
  progress: ProgressState | null;
  status: ProcessStatus;
}

const steps = ['Upload', 'Preprocess', 'Recognize', 'Post-process', 'Done'];

const ProgressSteps = ({ progress, status }: Props) => {
  const current = progress?.current ?? 0;
  const total = progress?.total ?? steps.length;
  const percent = Math.min(100, Math.round((current / total) * 100));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm font-medium">
        <span className="text-muted-foreground">{progress?.label || 'Waiting to start'}</span>
        <span className="text-foreground">{percent}%</span>
      </div>
      <div className="progress-bar">
        <motion.div
          className="progress-fill"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.25 }}
        />
      </div>
      <div className="grid grid-cols-5 gap-2 text-xs">
        {steps.map((label, idx) => {
          const stepIndex = idx + 1;
          const state =
            stepIndex < current ? 'done' : stepIndex === current && status === 'running' ? 'active' : 'pending';
          return (
            <div
              key={label}
              className={`rounded-lg border px-2 py-2 text-center ${
                state === 'done'
                  ? 'border-primary/60 bg-primary/10 text-primary'
                  : state === 'active'
                  ? 'border-primary bg-primary/20 text-primary'
                  : 'border-border bg-muted/60 text-muted-foreground'
              }`}
            >
              {label}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProgressSteps;
