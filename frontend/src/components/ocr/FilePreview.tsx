import { useEffect, useState } from 'react';
import type { OcrResult } from '@/types';
import { createObjectUrl, isImageFile, revokeObjectUrl } from '@/utils/file';

interface FilePreviewProps {
  file: File | null;
  result?: OcrResult | null;
}

const FilePreview = ({ file, result }: FilePreviewProps) => {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (file && isImageFile(file)) {
      const objectUrl = createObjectUrl(file);
      setUrl(objectUrl);
      return () => revokeObjectUrl(objectUrl);
    }
    setUrl(null);
    return () => undefined;
  }, [file]);

  if (!file) {
    return (
      <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-border/70 bg-muted/40 text-sm text-muted-foreground">
        <p>No file selected</p>
        <p>Drop a file to preview</p>
      </div>
    );
  }

  const isPdf = file.type === 'application/pdf';

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between rounded-lg border border-border/70 bg-card/60 px-3 py-2">
        <div className="flex flex-col">
          <span className="text-sm font-medium text-foreground">{file.name}</span>
          <span className="text-xs text-muted-foreground">{file.type || 'Unknown type'}</span>
        </div>
        <span className="text-xs rounded-full bg-primary/10 px-2 py-1 text-primary">
          {file.size ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : ''}
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-border/70 bg-card/70">
        {isImageFile(file) && url && (
          <img src={url} alt={file.name} className="h-80 w-full object-contain" loading="lazy" />
        )}
        {isPdf && (
          <div className="flex h-80 flex-col items-center justify-center gap-3 text-muted-foreground">
            <div className="flex h-14 w-12 items-center justify-center rounded bg-muted text-lg font-semibold text-foreground">
              PDF
            </div>
            <p className="text-sm">
              PDF document {result?.pages?.length ? `(${result.pages.length} pages)` : ''}
            </p>
          </div>
        )}
        {!isImageFile(file) && !isPdf && (
          <div className="flex h-80 flex-col items-center justify-center gap-3 text-muted-foreground">
            <div className="flex h-14 w-12 items-center justify-center rounded bg-muted text-lg font-semibold text-foreground">
              TXT
            </div>
            <p className="text-sm">Preview not available for this type.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FilePreview;
