
import { AnimatePresence, motion } from 'framer-motion';
import type { ToastMessage } from '@/types';

interface ToastProps {
  toasts: ToastMessage[];
  removeToast: (id: string) => void;
}

const glowStyles = {
  success: 'shadow-[0_0_30px_-5px_rgba(16,185,129,0.4)] border-emerald-500/40 dark:shadow-[0_0_30px_-5px_rgba(16,185,129,0.3)] dark:border-emerald-500/40',
  error: 'shadow-[0_0_30px_-5px_rgba(244,63,94,0.4)] border-rose-500/40 dark:shadow-[0_0_30px_-5px_rgba(244,63,94,0.3)] dark:border-rose-500/40',
  info: 'shadow-[0_0_30px_-5px_rgba(59,130,246,0.4)] border-blue-500/40 dark:shadow-[0_0_30px_-5px_rgba(59,130,246,0.3)] dark:border-blue-500/40',
};

const Toast = ({ toasts, removeToast }: ToastProps) => {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none items-center">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className={`pointer-events-auto group relative flex w-full max-w-[356px] items-center gap-3 overflow-hidden rounded-[14px] border bg-background/95 p-4 backdrop-blur-xl dark:bg-zinc-950/90 ${glowStyles[toast.type]}`}
          >
            {/* Icon */}
            <div className={`relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-black/5 dark:border-white/10 ${toast.type === 'success' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
              toast.type === 'error' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' :
                'bg-blue-500/10 text-blue-600 dark:text-blue-400'
              }`}>
              {toast.type === 'success' && (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              )}
              {toast.type === 'error' && (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {toast.type === 'info' && (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0 py-0.5">
              {toast.title && <h3 className="font-semibold text-[13px] leading-tight text-foreground">{toast.title}</h3>}
              <p className="text-[13px] text-muted-foreground leading-snug">{toast.message}</p>
            </div>

            {/* Close Button */}
            <button
              onClick={() => removeToast(toast.id)}
              className="absolute top-2 right-2 p-1 text-muted-foreground/50 opacity-0 transition-opacity hover:text-foreground hover:bg-muted rounded-md group-hover:opacity-100"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};

export default Toast;
