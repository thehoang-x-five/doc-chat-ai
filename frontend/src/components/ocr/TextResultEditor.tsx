import { useMemo, useState } from 'react';
import type { HighlightMatch, OcrResult, ProcessStatus } from '@/types';

interface Props {
  value: string;
  onChange: (text: string) => void;
  onCopy: () => void;
  onClear: () => void;
  onDownload: () => void;
  searchQuery: string;
  matches: HighlightMatch[];
  lowConfidenceRanges?: Array<[number, number]>;
  result: OcrResult | null;
  status: ProcessStatus;
}

const renderHighlighted = (text: string, matches: HighlightMatch[]) => {
  if (!matches.length) return <span>{text}</span>;
  const ordered = [...matches].sort((a, b) => a.start - b.start);
  const fragments: React.ReactNode[] = [];
  let cursor = 0;
  ordered.forEach((match, idx) => {
    if (cursor < match.start) fragments.push(<span key={`t-${idx}-${cursor}`}>{text.slice(cursor, match.start)}</span>);
    fragments.push(
      <mark key={`m-${idx}`} className="rounded bg-primary/20 px-0.5 text-primary">
        {text.slice(match.start, match.end)}
      </mark>
    );
    cursor = match.end;
  });
  if (cursor < text.length) fragments.push(<span key={`end-${cursor}`}>{text.slice(cursor)}</span>);
  return fragments;
};

const TextResultEditor = ({
  value,
  onChange,
  onCopy,
  onClear,
  onDownload,
  searchQuery,
  matches,
  lowConfidenceRanges,
  result,
  status,
}: Props) => {
  const [tab, setTab] = useState<'text' | 'structured' | 'export'>('text');
  const [showLowConfidence, setShowLowConfidence] = useState(true);

  const structured = useMemo(() => result?.structured, [result]);
  const combinedMatches = useMemo(() => {
    const base = matches || [];
    if (showLowConfidence && lowConfidenceRanges) {
      const lc: HighlightMatch[] = lowConfidenceRanges
        .filter(([start, end]) => start < value.length)
        .map(([start, end]) => ({ start, end: Math.min(end, value.length) }));
      return [...base, ...lc];
    }
    return base;
  }, [lowConfidenceRanges, matches, showLowConfidence, value.length]);

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-1.5 text-xs sm:text-sm md:flex-nowrap">
          {(['text', 'structured', 'export'] as const).map((key) => (
            <button
              key={key}
              className={`tab-button ${tab === key ? 'active' : ''} px-3 py-2`}
              onClick={() => setTab(key)}
            >
              {key === 'text' ? 'Text' : key === 'structured' ? 'Structured' : 'Export'}
            </button>
          ))}
          <button onClick={onCopy} className="ml-2 rounded-lg border border-border px-2 py-1 hover:border-primary hover:text-primary">
            Copy
          </button>
          <button onClick={onClear} className="rounded-lg border border-border px-2 py-1 hover:border-primary hover:text-primary">
            Clear
          </button>
          <button
            onClick={() => setShowLowConfidence((s) => !s)}
            className={`shrink-0 rounded-lg border px-2 py-1 ${showLowConfidence ? 'border-primary text-primary' : 'border-border'}`}
          >
            Highlight
          </button>
        </div>
        <div className="ml-auto">
          <button onClick={onDownload} className="btn-gradient px-3 py-1.5 whitespace-nowrap text-sm">
            Download
          </button>
        </div>
      </div>

      {tab === 'text' && (
        <div className="flex flex-col gap-3">
          <div className="rounded-xl border border-border/70 bg-muted/40 p-3 text-xs text-muted-foreground">
            {status === 'running'
              ? 'Processing...'
              : result
              ? `Language: ${result.language} • Avg confidence: ${(result.avgConfidence * 100).toFixed(1)}%`
              : 'Awaiting OCR run'}
          </div>

          <div className="rounded-2xl border border-border/70 bg-card/80 p-4 shadow-sm">
            <p className="mb-2 text-sm font-semibold text-foreground">Raw text (editable)</p>
            <textarea
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder="OCR results appear here. You can edit manually."
              className="text-editor custom-scrollbar h-64 w-full rounded-xl border border-border/70 bg-card/80 p-3"
            />
          </div>

          {(searchQuery || (showLowConfidence && lowConfidenceRanges?.length)) && (
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm">
              <p className="mb-1 font-semibold text-primary">Highlights</p>
              <p className="text-muted-foreground">
                {searchQuery
                  ? `Found ${combinedMatches.length} match${combinedMatches.length !== 1 ? 'es' : ''} for "${searchQuery}"`
                  : 'Low-confidence ranges highlighted'}
              </p>
              <div className="mt-2 rounded-lg border border-border/60 bg-card/70 p-3 text-sm leading-relaxed custom-scrollbar h-32 overflow-auto">
                {renderHighlighted(value, combinedMatches)}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'structured' && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border/70 bg-muted/30 p-3">
            <p className="mb-2 text-sm font-semibold">Tables</p>
            {structured?.tables?.map((table) => (
              <div key={table.id} className="mb-3 overflow-hidden rounded-lg border border-border/70">
                <div className="bg-muted px-2 py-1 text-xs font-semibold">{table.name}</div>
                <div className="divide-y divide-border/70 text-xs">
                  {table.rows.map((row, idx) => (
                    <div key={idx} className="grid grid-cols-3 gap-2 px-2 py-1">
                      {row.map((cell, cIdx) => (
                        <span key={cIdx}>{cell}</span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-border/70 bg-muted/30 p-3 space-y-3">
            <div>
              <p className="mb-1 text-sm font-semibold">Key-Value</p>
              <div className="space-y-2 text-sm">
                {structured?.keyValues?.map((kv) => (
                  <div key={kv.key} className="flex items-center justify-between rounded-lg border border-border/60 bg-card/70 px-2 py-1">
                    <span className="text-muted-foreground">{kv.key}</span>
                    <span className="font-semibold text-foreground">{kv.value}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1 text-sm font-semibold">Entities</p>
              <div className="flex flex-wrap gap-2">
                {structured?.entities?.map((entity, idx) => (
                  <span
                    key={`${entity.value}-${idx}`}
                    className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary"
                  >
                    {entity.type}: {entity.value}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'export' && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border/70 bg-muted/30 p-3 text-sm">
            <p className="mb-2 font-semibold">Version history</p>
            <div className="space-y-2">
              <div className="flex items-center justify-between rounded-lg border border-border/60 bg-card/70 px-2 py-1">
                <div>
                  <p className="font-medium">Edited v1</p>
                  <p className="text-xs text-muted-foreground">Manual fix from header spelling</p>
                </div>
                <button className="text-xs text-primary">Restore</button>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border/60 bg-card/70 px-2 py-1">
                <div>
                  <p className="font-medium">Edited v2</p>
                  <p className="text-xs text-muted-foreground">Approved</p>
                </div>
                <button className="text-xs text-primary">Use</button>
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <button className="btn-gradient px-4 py-2">Approve</button>
              <button className="rounded-lg border border-border px-4 py-2">Reject</button>
            </div>
          </div>
          <div className="rounded-xl border border-border/70 bg-muted/30 p-3 text-sm">
            <p className="mb-2 font-semibold">Export formats</p>
            <div className="flex flex-wrap gap-2">
              {(['txt', 'md', 'json', 'pdf'] as const).map((format) => (
                <span
                  key={format}
                  className="rounded-full border border-border/70 bg-card/70 px-3 py-1 text-xs font-semibold text-foreground"
                >
                  {format.toUpperCase()}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Download button uses current text value to generate a blob (mock).
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default TextResultEditor;
