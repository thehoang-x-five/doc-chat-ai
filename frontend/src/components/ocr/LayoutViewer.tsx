import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { OcrLayoutPage } from '@/types';
import { downloadBlob } from '@/utils/file';

type ExportType = 'txt' | 'txt-layout' | 'json-layout';

interface LayoutViewerProps {
  layoutPages?: OcrLayoutPage[];
  fullText: string;
  text: string;
}

const LayoutViewer = ({ layoutPages, fullText, text }: LayoutViewerProps) => {
  const [pageIndex, setPageIndex] = useState(0);
  const [zoom, setZoom] = useState(110);
  const [preserveLayout, setPreserveLayout] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [highlightLow, setHighlightLow] = useState(true);
  const [mergePages, setMergePages] = useState(false);

  const textLayout = useMemo<OcrLayoutPage[]>(() => {
    if (!text.trim()) return [];
    const lines = text.split('\n').filter(ln => ln.trim());
    if (!lines.length) return [];
    
    const lineHeight = 0.035;
    const lineGap = 0.012;
    const marginX = 0.05;
    const marginY = 0.05;
    const maxLinesPerPage = Math.floor((1.414 - marginY * 2) / (lineHeight + lineGap));
    
    // Split into pages if too many lines
    const pageChunks: string[][] = [];
    for (let i = 0; i < lines.length; i += maxLinesPerPage) {
      pageChunks.push(lines.slice(i, i + maxLinesPerPage));
    }
    
    const pages: OcrLayoutPage[] = pageChunks.map((pageLines, pageIdx) => {
      const blockLines = pageLines.map((ln, idx) => {
        const words = ln.trim().split(/\s+/).filter(Boolean);
        const y = marginY + idx * (lineHeight + lineGap);
        
        // Calculate word positions more accurately
        const totalChars = words.reduce((sum, w) => sum + w.length, 0);
        const availableWidth = 0.9;
        const charWidth = totalChars > 0 ? Math.min(availableWidth / totalChars, 0.025) : 0.02;
        const wordGap = 0.015;
        
        let xCursor = marginX;
        const wordBoxes = words.map((w) => {
          const wordWidth = Math.max(w.length * charWidth, 0.02);
          const bbox = { x: xCursor, y, w: wordWidth, h: lineHeight };
          xCursor += wordWidth + wordGap;
          return { text: w, bbox, confidence: 0.92 };
        });
        
        return {
          text: ln,
          confidence: 0.92,
          bbox: { x: marginX, y, w: Math.min(xCursor - marginX, availableWidth), h: lineHeight },
          words: wordBoxes,
        };
      });
      
      // Calculate block height based on content
      const lastLine = blockLines[blockLines.length - 1];
      const blockHeight = lastLine ? (lastLine.bbox.y + lastLine.bbox.h - marginY + 0.02) : 0.9;
      
      return {
        page: pageIdx + 1,
        width: 1,
        height: 1.414,
        blocks: [
          {
            id: `text-block-${pageIdx}`,
            bbox: { x: marginX, y: marginY, w: 0.9, h: Math.min(blockHeight, 0.9) },
            lines: blockLines,
          },
        ],
      };
    });
    
    return pages;
  }, [text]);

  const effectivePages = textLayout.length ? textLayout : layoutPages || [];
  const hasLayout = effectivePages.length > 0;
  const activePage = effectivePages[pageIndex];
  const pagesToRender = mergePages && effectivePages.length ? effectivePages : activePage ? [activePage] : [];

  const aspectRatio = useMemo(() => {
    if (!pagesToRender.length) return 1.3;
    const p = pagesToRender[0];
    return p.height / p.width;
  }, [pagesToRender]);

  const exportData = (type: ExportType) => {
    if (!effectivePages.length) return;
    if (type === 'json-layout') {
      downloadBlob(new Blob([JSON.stringify(effectivePages, null, 2)], { type: 'application/json' }), 'ocr-layout.json');
      return;
    }
    // txt-layout: concatenate words by lines respecting ordering
    const content = effectivePages
      .map((page) =>
        page.blocks
          .map((block) => block.lines.map((line) => line.words.map((w) => w.text).join(' ')).join('\n'))
          .join('\n\n')
      )
      .join('\n\n---\n\n');
    downloadBlob(new Blob([content], { type: 'text/plain' }), 'ocr-layout.txt');
  };

  const wordClasses = (conf: number) => {
    if (!highlightLow) return '';
    if (conf < 0.8) return 'bg-red-200/70 text-red-800';
    if (conf < 0.9) return 'bg-amber-200/70 text-amber-900';
    return 'bg-emerald-100/50 text-emerald-800';
  };

  const blockTypeColors: Record<string, string> = {
    heading: 'border-purple-400/60 bg-purple-50/30',
    table: 'border-green-400/60 bg-green-50/30',
    image: 'border-orange-400/60 bg-orange-50/30',
    list: 'border-cyan-400/60 bg-cyan-50/30',
    text: 'border-blue-400/40 bg-blue-50/20',
  };

  const renderPage = (page: OcrLayoutPage) => {
    if (!preserveLayout) {
      const text = page.blocks
        .map((b) => b.lines.map((l) => l.text).join('\n'))
        .filter(Boolean)
        .join('\n\n');
      return (
        <div className="rounded-lg border border-border/60 bg-muted/40 p-3 text-xs text-foreground/80 whitespace-pre-wrap">
          {text || 'No text in this page'}
        </div>
      );
    }

    const canvasStyle = {
      width: `${zoom}%`,
      minWidth: `${zoom}%`,
      paddingTop: `${aspectRatio * 100}%`,
    } as React.CSSProperties;

    return (
      <div className="relative w-full overflow-auto rounded-lg border border-border/70 bg-white shadow-inner max-h-[70vh]">
        {/* Background pattern */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(15,23,42,0.03),transparent_30%),radial-gradient(circle_at_80%_10%,rgba(15,23,42,0.04),transparent_28%)] pointer-events-none" />
        
        <div className="relative" style={canvasStyle}>
          <div className="absolute inset-0">
            {/* Render blocks with their bounding boxes */}
            {page.blocks.map((block, blockIdx) => {
              const blockType = (block as any).type || 'text';
              const blockLeft = `${block.bbox.x * 100}%`;
              const blockTop = `${block.bbox.y * 100}%`;
              const blockWidth = `${block.bbox.w * 100}%`;
              const blockHeight = `${block.bbox.h * 100}%`;
              
              return (
                <div
                  key={`block-${block.id || blockIdx}`}
                  className={`absolute rounded ${showBoxes ? `border-2 ${blockTypeColors[blockType] || blockTypeColors.text}` : ''}`}
                  style={{ left: blockLeft, top: blockTop, width: blockWidth, height: blockHeight }}
                >
                  {/* Render lines within block */}
                  {block.lines.map((line, lineIdx) => {
                    // Calculate line position relative to block
                    const lineLeft = `${((line.bbox.x - block.bbox.x) / block.bbox.w) * 100}%`;
                    const lineTop = `${((line.bbox.y - block.bbox.y) / block.bbox.h) * 100}%`;
                    const lineWidth = `${(line.bbox.w / block.bbox.w) * 100}%`;
                    const lineHeight = `${(line.bbox.h / block.bbox.h) * 100}%`;
                    
                    return (
                      <div
                        key={`line-${blockIdx}-${lineIdx}`}
                        className="absolute"
                        style={{ left: lineLeft, top: lineTop, width: lineWidth, height: lineHeight }}
                      >
                        {/* Render words within line */}
                        {line.words.map((word, wordIdx) => {
                          // Calculate word position relative to line
                          const wordLeft = line.bbox.w > 0 
                            ? `${((word.bbox.x - line.bbox.x) / line.bbox.w) * 100}%`
                            : '0%';
                          const wordTop = '0%';
                          const wordWidth = line.bbox.w > 0 
                            ? `${(word.bbox.w / line.bbox.w) * 100}%`
                            : 'auto';
                          const wordHeight = '100%';
                          
                          return (
                            <span
                              key={`word-${blockIdx}-${lineIdx}-${wordIdx}`}
                              className={`absolute flex items-center text-[9px] sm:text-[10px] leading-tight px-0.5 truncate ${wordClasses(
                                word.confidence
                              )} ${showBoxes ? 'border border-primary/30 rounded-sm' : ''}`}
                              style={{ 
                                left: wordLeft, 
                                top: wordTop, 
                                width: wordWidth, 
                                height: wordHeight,
                                maxWidth: '100%',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                fontSize: `clamp(6px, ${zoom * 0.08}px, 12px)`,
                              }}
                              title={`"${word.text}" - Conf: ${(word.confidence * 100).toFixed(1)}%`}
                            >
                              {word.text}
                            </span>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <label className="flex items-center gap-2 rounded-full border border-border/70 bg-muted/60 px-3 py-1">
          Preserve layout
          <input type="checkbox" checked={preserveLayout} onChange={(e) => setPreserveLayout(e.target.checked)} />
        </label>
        <label className="flex items-center gap-2 rounded-full border border-border/70 bg-muted/60 px-3 py-1">
          Show boxes
          <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
        </label>
        <label className="flex items-center gap-2 rounded-full border border-border/70 bg-muted/60 px-3 py-1">
          Highlight low-conf
          <input type="checkbox" checked={highlightLow} onChange={(e) => setHighlightLow(e.target.checked)} />
        </label>
        <label className="flex items-center gap-2 rounded-full border border-border/70 bg-muted/60 px-3 py-1">
          Merge pages
          <input type="checkbox" checked={mergePages} onChange={(e) => setMergePages(e.target.checked)} />
        </label>
        <div className="flex items-center gap-2 rounded-full border border-border/70 bg-muted/60 px-3 py-1">
          Zoom
          <input type="range" min={60} max={160} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
          <span className="font-semibold">{zoom}%</span>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border/70 bg-muted/60 px-3 py-1">
          Page
          <select
            className="input-modern text-xs"
            value={pageIndex}
            disabled={!layoutPages?.length || mergePages}
            onChange={(e) => setPageIndex(Number(e.target.value))}
          >
            {(layoutPages || []).map((p, idx) => (
              <option key={p.page} value={idx}>
                Page {p.page}
              </option>
            ))}
          </select>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:border-primary hover:text-primary"
            onClick={() => exportData('txt-layout')}
            disabled={!effectivePages.length}
          >
            Export (layout)
          </button>
          <button
            className="rounded-lg border border-border px-3 py-1.5 text-xs hover:border-primary hover:text-primary"
            onClick={() => exportData('json-layout')}
            disabled={!effectivePages.length}
          >
            Export JSON
          </button>
        </div>
      </div>

      {!hasLayout && (
        <div className="rounded-lg border border-dashed border-border/70 bg-muted/40 p-4 text-sm text-muted-foreground">
          No structured layout returned. Showing plain text fallback.
        </div>
      )}

      {hasLayout && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Layout viewer {mergePages ? '(merged)' : `(page ${activePage?.page || 1})`}</span>
            <span>Blocks: {pagesToRender.reduce((sum, p) => sum + p.blocks.length, 0)}</span>
          </div>
          <div className="overflow-hidden rounded-xl border border-border/70 bg-card/80 p-3">
            <div className="flex flex-col gap-4">
              {pagesToRender.map((p) => (
                <div key={p.page} className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Page {p.page}</span>
                    <span>Blocks: {p.blocks.length}</span>
                  </div>
                  {renderPage(p)}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LayoutViewer;
