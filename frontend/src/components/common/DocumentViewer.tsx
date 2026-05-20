import { useState, useEffect, useRef } from 'react';

/* ─────────────────────────────────────────────────────────────
 * SUPPORTED EXTENSIONS — single source of truth (frontend)
 * Must match backend config.py ALLOWED_EXTENSIONS exactly.
 * ──────────────────────────────────────────────────────────── */
export const SUPPORTED_EXTENSIONS = [
  'pdf',
  'docx', 'pptx', 'xlsx',
  'jpg', 'jpeg', 'png', 'bmp', 'tif', 'tiff', 'webp', 'gif',
  'txt', 'md', 'csv', 'json', 'rtf', 'odt', 'html', 'xhtml',
] as const;

/** Build the `accept` attribute string for <input type="file"> */
export const FILE_INPUT_ACCEPT = SUPPORTED_EXTENSIONS.map(e => `.${e}`).join(',');

/* ─────────────────────────────────────────────────────────────
 * Helpers
 * ──────────────────────────────────────────────────────────── */
function extOf(name: string): string {
  return (name.split('.').pop() || '').toLowerCase();
}

type ViewerMode = 'original' | 'ocr';

interface DocumentViewerProps {
  /** Document ID for API calls */
  documentId: string;
  /** Display name shown in header */
  documentName: string;
  /** MIME type from backend (e.g. application/pdf, image/jpeg) */
  mimeType: string;
  /** URL to download/inline original file (with token) */
  downloadUrl: string;
  /** Attachment download URL (for Save-As) */
  attachmentUrl: string;
  /** Async function that returns the original document blob with auth refresh support */
  fetchOriginalBlob?: (signal?: AbortSignal) => Promise<{ blob: Blob; filename: string; mimeType: string }>;
  /** Async function that returns the OCR/markdown text */
  fetchOcrText: () => Promise<string>;
  /** Called when close button is clicked */
  onClose: () => void;
  /** i18n translations (optional) */
  t?: Record<string, any>;
}

/* ─────────────────────────────────────────────────────────────
 * Component
 * ──────────────────────────────────────────────────────────── */
export default function DocumentViewer({
  documentId,
  documentName,
  mimeType,
  downloadUrl,
  attachmentUrl,
  fetchOriginalBlob,
  fetchOcrText,
  onClose,
  t,
}: DocumentViewerProps) {
  const [activeTab, setActiveTab] = useState<ViewerMode>('original');
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [rawText, setRawText] = useState<string | null>(null);
  const [rawLoading, setRawLoading] = useState(false);
  const [originalObjectUrl, setOriginalObjectUrl] = useState<string | null>(null);
  const [originalLoading, setOriginalLoading] = useState(false);
  const [originalError, setOriginalError] = useState<string | null>(null);
  const docxContainerRef = useRef<HTMLDivElement>(null);
  const fetchOriginalBlobRef = useRef(fetchOriginalBlob);
  const fetchOcrTextRef = useRef(fetchOcrText);
  const ext = extOf(documentName);

  /* ── Determine renderer type for original file ── */
  const rendererType = getRendererType(ext, mimeType);
  const sourceUrl = originalObjectUrl || downloadUrl;
  const sourceReady = rendererType === 'placeholder' || rendererType === 'extracted' || !fetchOriginalBlob || !!originalObjectUrl;

  useEffect(() => {
    fetchOriginalBlobRef.current = fetchOriginalBlob;
  }, [fetchOriginalBlob]);

  useEffect(() => {
    fetchOcrTextRef.current = fetchOcrText;
  }, [fetchOcrText]);

  useEffect(() => {
    setOcrText(null);
    setRawText(null);
    setRawLoading(false);
    setOriginalError(null);
    setOriginalLoading(false);
    setOriginalObjectUrl(prev => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }, [documentId]);

  useEffect(() => {
    return () => {
      if (originalObjectUrl) URL.revokeObjectURL(originalObjectUrl);
    };
  }, [originalObjectUrl]);

  /* Load original file through authenticated fetch to avoid stale token URLs */
  useEffect(() => {
    if (
      activeTab !== 'original' ||
      rendererType === 'placeholder' ||
      rendererType === 'extracted' ||
      originalObjectUrl ||
      originalLoading
    ) return;
    const loader = fetchOriginalBlobRef.current;
    if (!loader) return;

    const controller = new AbortController();
    setOriginalLoading(true);
    setOriginalError(null);
    if (rendererType === 'text') setRawLoading(true);

    loader(controller.signal)
      .then(async ({ blob }) => {
        if (controller.signal.aborted) return;
        setOriginalObjectUrl(URL.createObjectURL(blob));
        if (rendererType === 'text') {
          setRawText(await blob.text());
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.error('Original document load failed:', err);
        setOriginalError('Failed to load file.');
      })
      .finally(() => {
        if (controller.signal.aborted) return;
        setOriginalLoading(false);
        if (rendererType === 'text') setRawLoading(false);
      });

    return () => controller.abort();
  }, [activeTab, rendererType, originalObjectUrl, documentId]);

  useEffect(() => {
    if (activeTab !== 'original' || rendererType !== 'extracted' || rawText !== null || rawLoading) return;

    let cancelled = false;
    setRawLoading(true);
    fetchOcrTextRef.current()
      .then(text => {
        if (cancelled) return;
        const content = text || '(No extracted content available)';
        setRawText(content);
        setOcrText(prev => prev ?? content);
      })
      .catch(() => {
        if (cancelled) return;
        setRawText('(Failed to load extracted content)');
      })
      .finally(() => {
        if (!cancelled) setRawLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, rendererType, rawText, documentId]);

  /* ── Lazy-load OCR text when switching to Tab 2 ── */
  useEffect(() => {
    if (activeTab === 'ocr' && ocrText === null && !ocrLoading) {
      setOcrLoading(true);
      fetchOcrText()
        .then(text => setOcrText(text || '(No OCR text available)'))
        .catch(() => setOcrText('(Failed to load OCR text)'))
        .finally(() => setOcrLoading(false));
    }
  }, [activeTab, ocrText, ocrLoading, fetchOcrText]);

  /* ── Lazy-load raw text for TXT/MD/CSV viewers ── */
  useEffect(() => {
    if (!fetchOriginalBlob && rendererType === 'text' && rawText === null && !rawLoading) {
      setRawLoading(true);
      fetch(downloadUrl)
        .then(r => r.text())
        .then(text => setRawText(text))
        .catch(() => setRawText('(Failed to load file)'))
        .finally(() => setRawLoading(false));
    }
  }, [rendererType, rawText, rawLoading, downloadUrl, fetchOriginalBlob]);

  /* ── Lazy-load DOCX rendering ── */
  useEffect(() => {
    if (rendererType === 'docx' && activeTab === 'original' && sourceReady && docxContainerRef.current) {
      renderDocx(sourceUrl, docxContainerRef.current);
    }
  }, [rendererType, activeTab, sourceUrl, sourceReady]);

  /* ── Keyboard: Escape to close ── */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  /* ── Render ── */
  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-card border border-border rounded-2xl w-[90vw] max-w-[1100px] h-[88vh] shadow-2xl flex flex-col animate-in zoom-in-95 duration-200">

        {/* ═══════════ Header ═══════════ */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30 rounded-t-2xl flex-shrink-0">
          {/* Left: doc icon + name */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
              {fileIcon(ext)}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold truncate">{documentName}</h3>
              <p className="text-xs text-muted-foreground">{mimeType || ext.toUpperCase()}</p>
            </div>
          </div>

          {/* Right: tabs + actions */}
          <div className="flex items-center gap-2">
            {/* Tab switcher */}
            <div className="flex rounded-lg border border-border overflow-hidden text-xs">
              <button
                onClick={() => setActiveTab('original')}
                className={`px-3 py-1.5 font-medium transition ${
                  activeTab === 'original'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background hover:bg-muted text-muted-foreground'
                }`}
              >
                {t?.kb?.originalFile || 'Original'}
              </button>
              <button
                onClick={() => setActiveTab('ocr')}
                className={`px-3 py-1.5 font-medium transition ${
                  activeTab === 'ocr'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background hover:bg-muted text-muted-foreground'
                }`}
              >
                {t?.kb?.ocrText || 'OCR Text'}
              </button>
            </div>

            {/* Download button */}
            <a
              href={attachmentUrl}
              download={documentName}
              className="p-2 rounded-lg hover:bg-muted transition text-muted-foreground hover:text-foreground"
              title={t?.kb?.download || 'Download'}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </a>

            {/* Close button */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-destructive/10 hover:text-destructive transition"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* ═══════════ Content Area ═══════════ */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'original' ? (
            <OriginalViewer
              rendererType={rendererType}
              downloadUrl={sourceUrl}
              attachmentUrl={attachmentUrl}
              documentName={documentName}
              mimeType={mimeType}
              rawText={rawText}
              rawLoading={rawLoading || (rendererType === 'text' && originalLoading)}
              sourceReady={sourceReady}
              originalLoading={originalLoading}
              originalError={originalError}
              docxContainerRef={docxContainerRef}
              t={t}
            />
          ) : (
            <OcrTextViewer
              text={ocrText}
              loading={ocrLoading}
              t={t}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
 * Sub-components
 * ═══════════════════════════════════════════════════════════════ */

type RendererType = 'pdf' | 'image' | 'docx' | 'text' | 'html' | 'extracted' | 'placeholder';

function getRendererType(ext: string, mimeType: string): RendererType {
  const normalizedMime = (mimeType || '').toLowerCase();
  if (ext === 'pdf' || mimeType === 'application/pdf') return 'pdf';
  if (['jpg', 'jpeg', 'png', 'bmp', 'tif', 'tiff', 'webp', 'gif'].includes(ext) || normalizedMime.startsWith('image/'))
    return 'image';
  if (ext === 'docx' || normalizedMime.includes('wordprocessingml.document')) return 'docx';
  if (
    ['pptx', 'xlsx'].includes(ext) ||
    normalizedMime.includes('spreadsheetml.sheet') ||
    normalizedMime.includes('presentationml.presentation')
  ) return 'extracted';
  if (['txt', 'md', 'csv', 'json', 'rtf', 'odt'].includes(ext)) return 'text';
  if (['html', 'xhtml'].includes(ext)) return 'html';
  return 'placeholder';
}

function fileIcon(ext: string) {
  // Color-coded icons per file type
  if (ext === 'pdf')
    return <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>;
  if (['jpg','jpeg','png','bmp','tif','tiff','webp','gif'].includes(ext))
    return <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>;
  if (ext === 'docx')
    return <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>;
  if (ext === 'xlsx')
    return <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18M8 4v16m8-16v16M5 4h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z" /></svg>;
  if (ext === 'pptx')
    return <svg className="w-4 h-4 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4h10a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V6a2 2 0 012-2zm3 5h4.5a2.5 2.5 0 010 5H10V9z" /></svg>;
  return <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>;
}

/** Original-view renderer — routes to the appropriate viewer */
function OriginalViewer({
  rendererType,
  downloadUrl,
  attachmentUrl,
  documentName,
  mimeType,
  rawText,
  rawLoading,
  sourceReady,
  originalLoading,
  originalError,
  docxContainerRef,
  t,
}: {
  rendererType: RendererType;
  downloadUrl: string;
  attachmentUrl: string;
  documentName: string;
  mimeType: string;
  rawText: string | null;
  rawLoading: boolean;
  sourceReady: boolean;
  originalLoading: boolean;
  originalError: string | null;
  docxContainerRef: React.RefObject<HTMLDivElement | null>;
  t?: Record<string, any>;
}) {
  if (!sourceReady && originalError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-destructive p-8">
        <p>{originalError}</p>
      </div>
    );
  }

  if (!sourceReady || originalLoading) {
    return <LoadingSpinner label={t?.kb?.loadingContent || 'Loading...'} />;
  }

  switch (rendererType) {
    case 'pdf':
      return <PdfViewer url={downloadUrl} documentName={documentName} />;

    case 'image':
      return (
        <div className="flex items-center justify-center h-full p-6 bg-muted/20 overflow-auto">
          <img
            src={downloadUrl}
            alt={documentName}
            className="max-w-full max-h-full object-contain rounded-lg shadow-lg"
          />
        </div>
      );

    case 'docx':
      return (
        <div className="h-full overflow-auto bg-white">
          <div
            ref={docxContainerRef}
            className="docx-preview-container p-4"
            style={{ minHeight: '100%' }}
          />
        </div>
      );

    case 'text':
      if (rawLoading) return <LoadingSpinner label={t?.kb?.loadingContent || 'Loading...'} />;
      // CSV gets a table renderer; TXT/MD stay as <pre>
      if (extOf(documentName) === 'csv' && rawText) {
        return <CsvTableViewer rawText={rawText} />;
      }
      return (
        <div className="h-full overflow-auto p-5">
          <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed text-foreground">
            {rawText || ''}
          </pre>
        </div>
      );

    case 'html':
      return (
        <iframe
          src={downloadUrl}
          className="w-full h-full border-0 bg-white"
          sandbox="allow-same-origin"
          title={documentName}
        />
      );

    case 'extracted':
      if (rawLoading) return <LoadingSpinner label={t?.kb?.loadingContent || 'Loading...'} />;
      return <ExtractedContentViewer rawText={rawText || ''} documentName={documentName} />;

    case 'placeholder':
      return (
        <div className="flex flex-col items-center justify-center h-full gap-4 text-center p-8">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center">
            <svg className="w-8 h-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {t?.kb?.previewNotAvailable || 'Preview not available for this file type'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t?.kb?.downloadToView || 'Download the file to view it in a native application'}
            </p>
          </div>
          <a
            href={attachmentUrl}
            download={documentName}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {t?.kb?.downloadFile || 'Download File'}
          </a>
        </div>
      );
  }
}

/** CSV table renderer — parses raw CSV text and renders as styled table */
type MarkdownBlock =
  | { type: 'text'; lines: string[] }
  | { type: 'table'; rows: string[][] };

function ExtractedContentViewer({ rawText }: { rawText: string; documentName: string }) {
  const blocks = parseMarkdownBlocks(rawText);

  if (!rawText.trim()) {
    return (
      <div className="flex items-center justify-center h-full p-8 text-sm text-muted-foreground">
        No extracted content available.
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto bg-background">
      <div className="p-5 space-y-5">
        {blocks.map((block, index) => {
          if (block.type === 'table') {
            return <MarkdownTable key={`table-${index}`} rows={block.rows} />;
          }

          return (
            <pre
              key={`text-${index}`}
              className="whitespace-pre-wrap text-sm font-mono leading-relaxed text-foreground"
            >
              {block.lines.join('\n')}
            </pre>
          );
        })}
      </div>
    </div>
  );
}

function MarkdownTable({ rows }: { rows: string[][] }) {
  if (rows.length === 0) return null;

  const header = rows[0];
  const body = rows.slice(1);
  const columnCount = Math.max(...rows.map(row => row.length));

  return (
    <div className="overflow-hidden border border-border rounded-lg">
      <table className="w-full table-fixed text-xs border-collapse">
        <thead className="sticky top-0 z-10">
          <tr>
            {Array.from({ length: columnCount }).map((_, index) => (
              <th
                key={index}
                className="px-2 py-2 text-left text-[11px] font-semibold bg-primary/10 text-primary border-b border-border whitespace-normal break-words align-top"
              >
                {header[index] || ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={`border-b border-border/50 hover:bg-muted/40 ${rowIndex % 2 === 1 ? 'bg-muted/20' : ''}`}
            >
              {Array.from({ length: columnCount }).map((_, cellIndex) => (
                <td key={cellIndex} className="px-2 py-2 align-top text-foreground whitespace-pre-wrap break-words">
                  {row[cellIndex] || ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseMarkdownBlocks(text: string): MarkdownBlock[] {
  const lines = text.split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    if (isMarkdownTableStart(lines, index)) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        tableLines.push(lines[index]);
        index++;
      }

      const rows = tableLines
        .filter(line => !isMarkdownSeparatorRow(line))
        .map(splitMarkdownRow)
        .filter(row => row.length > 1);

      if (rows.length > 0) {
        blocks.push({ type: 'table', rows });
      }
      continue;
    }

    const textLines: string[] = [];
    while (index < lines.length && !isMarkdownTableStart(lines, index)) {
      textLines.push(lines[index]);
      index++;
    }

    const trimmed = trimBlankEdges(textLines);
    if (trimmed.length > 0) {
      blocks.push({ type: 'text', lines: trimmed });
    }
  }

  return blocks;
}

function isMarkdownTableStart(lines: string[], index: number): boolean {
  return Boolean(
    lines[index]?.includes('|') &&
    lines[index + 1]?.includes('|') &&
    isMarkdownSeparatorRow(lines[index + 1])
  );
}

function isMarkdownSeparatorRow(line: string): boolean {
  const cells = splitMarkdownRow(line);
  return cells.length > 1 && cells.every(cell => /^:?-{3,}:?$/.test(cell.replace(/\s/g, '')));
}

function splitMarkdownRow(line: string): string[] {
  let value = line.trim();
  if (value.startsWith('|')) value = value.slice(1);
  if (value.endsWith('|')) value = value.slice(0, -1);
  return value.split('|').map(cell => cell.trim());
}

function trimBlankEdges(lines: string[]): string[] {
  let start = 0;
  let end = lines.length;
  while (start < end && !lines[start].trim()) start++;
  while (end > start && !lines[end - 1].trim()) end--;
  return lines.slice(start, end);
}

function CsvTableViewer({ rawText }: { rawText: string }) {
  const rows = parseCsv(rawText);
  if (rows.length === 0) return <pre className="p-5 text-sm text-muted-foreground">(Empty CSV)</pre>;

  const header = rows[0];
  const body = rows.slice(1);

  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead className="sticky top-0 z-10">
          <tr>
            {header.map((cell, i) => (
              <th
                key={i}
                className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider bg-primary/10 text-primary border-b border-border whitespace-nowrap"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr
              key={ri}
              className={`border-b border-border/50 hover:bg-muted/40 transition ${ri % 2 === 1 ? 'bg-muted/20' : ''}`}
            >
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-foreground whitespace-nowrap">
                  {cell}
                </td>
              ))}
              {/* Pad missing columns */}
              {row.length < header.length &&
                Array.from({ length: header.length - row.length }).map((_, ci) => (
                  <td key={`pad-${ci}`} className="px-3 py-2" />
                ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Simple CSV parser that handles quoted fields */
function parseCsv(text: string): string[][] {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  return lines.map(line => {
    const cells: string[] = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"' && line[i + 1] === '"') { current += '"'; i++; }
        else if (ch === '"') { inQuotes = false; }
        else { current += ch; }
      } else {
        if (ch === '"') { inQuotes = true; }
        else if (ch === ',') { cells.push(current.trim()); current = ''; }
        else { current += ch; }
      }
    }
    cells.push(current.trim());
    return cells;
  });
}
function OcrTextViewer({
  text,
  loading,
  t,
}: {
  text: string | null;
  loading: boolean;
  t?: Record<string, any>;
}) {
  if (loading) return <LoadingSpinner label={t?.kb?.loadingOcr || 'Loading OCR text...'} />;
  return (
    <div className="h-full overflow-auto p-5">
      <pre className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm font-mono leading-relaxed text-foreground">
        {text || (t?.kb?.noContent || 'No content available.')}
      </pre>
    </div>
  );
}

/** Shared loading spinner */
function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3">
      <svg className="h-10 w-10 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}

/** Native browser PDF viewer component */
function PdfViewer({ url, documentName }: { url: string; documentName: string }) {
  return (
    <div className="h-full bg-muted/20">
      <iframe
        key={url}
        src={`${url}#toolbar=1&navpanes=0`}
        title={documentName}
        className="w-full h-full border-0 bg-white"
      />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * DOCX rendering helper (async import to avoid bundle bloat)
 * ──────────────────────────────────────────────────────────── */
async function renderDocx(url: string, container: HTMLElement) {
  container.innerHTML = '<div style="text-align:center;padding:2rem;color:#888">Loading DOCX preview…</div>';
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const { renderAsync } = await import('docx-preview');
    container.innerHTML = '';
    await renderAsync(blob, container, container, {
      className: 'docx-rendered',
      inWrapper: true,
      ignoreWidth: false,
      ignoreHeight: true,
      ignoreFonts: false,
      breakPages: true,
      experimental: true,
    });
  } catch (err) {
    console.error('DOCX preview failed:', err);
    container.innerHTML = `
      <div style="text-align:center;padding:2rem;color:#ef4444">
        <p style="font-weight:600">Could not render DOCX preview</p>
        <p style="font-size:12px;margin-top:4px;color:#888">${String(err)}</p>
      </div>
    `;
  }
}
