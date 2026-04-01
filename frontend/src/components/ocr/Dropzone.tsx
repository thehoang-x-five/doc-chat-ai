import { useCallback, useState } from 'react';
import { formatBytes, validateFile } from '@/utils/file';

interface DropzoneProps {
  files: File[];
  onFiles: (files: File[]) => void;
  onError?: (message: string) => void;
  multiple?: boolean;
  disabled?: boolean;
}

const Dropzone = ({ files, onFiles, onError, multiple = false, disabled }: DropzoneProps) => {
  const [active, setActive] = useState(false);

  const handleFiles = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return;
      const arr = Array.from(incoming);
      const valid: File[] = [];
      arr.forEach((file) => {
        const result = validateFile(file);
        if (!result.valid) {
          onError?.(result.error || 'Invalid file');
        } else {
          valid.push(file);
        }
      });
      if (valid.length) {
        onFiles(multiple ? [...files, ...valid] : [valid[0]]);
      }
    },
    [files, multiple, onError, onFiles]
  );

  return (
    <div
      className={`dropzone ${active ? 'active' : ''} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setActive(true);
      }}
      onDragLeave={() => setActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        if (disabled) return;
        setActive(false);
        handleFiles(e.dataTransfer.files);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          (e.currentTarget.querySelector('input[type=file]') as HTMLInputElement | null)?.click();
        }
      }}
    >
      <div className="flex flex-col items-center justify-center gap-3 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">⇪</div>
        <div>
          <p className="font-semibold text-foreground">Drag & drop files</p>
          <p className="text-sm text-muted-foreground">
            JPG/PNG/WebP/PDF/DOCX/TXT/MD up to 15MB. {multiple ? 'Upload multiple files.' : 'Single file.'}
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary hover:text-primary">
          <input
            type="file"
            className="hidden"
            disabled={disabled}
            multiple={multiple}
            onChange={(e) => handleFiles(e.target.files)}
            accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.txt,.md"
          />
          <span>Browse files</span>
        </label>
      </div>
      {files.length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {files.map((file) => (
            <div
              key={file.name}
              className="flex items-center justify-between rounded-lg border border-border/70 bg-card/70 px-3 py-2 text-sm"
            >
              <div className="flex flex-col text-left">
                <span className="font-medium text-foreground">{file.name}</span>
                <span className="text-xs text-muted-foreground">{formatBytes(file.size)}</span>
              </div>
              <button
                className="text-xs text-destructive hover:underline"
                onClick={() => onFiles(files.filter((f) => f.name !== file.name))}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dropzone;
