import { useState, useEffect } from 'react';
import { Copy, Check, ThumbsUp, ThumbsDown, AlertTriangle, Loader2 } from 'lucide-react';
import type { Citation } from '@/lib/api';
import { useCitations } from '@/lib/hooks/useCitations';

interface CitationNoteProps {
  messageId?: string;
  citations?: Citation[];
  model?: string;
  latencyMs?: number;
  mode?: 'rag_only' | 'hybrid' | 'llm_only';
  isGrounded?: boolean;
  contentLength?: number;
}

export function CitationNote({ messageId, citations: initialCitations, model, latencyMs, mode, isGrounded, contentLength = 0 }: CitationNoteProps) {
  const [showAllSources, setShowAllSources] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Lazy load citations if messageId is provided and we want to expand
  const { citations: loadedCitations, isLoading } = useCitations(
    (isExpanded && messageId) ? messageId : null
  );

  // Use loaded citations if available, otherwise initial ones
  const citations = (loadedCitations && loadedCitations.length > 0) ? loadedCitations : initialCitations;

  // Separate internal (document) and external (internet/AI) sources
  const internalSources = citations?.filter(c => c.documentTitle && c.documentTitle !== 'Unknown') || [];

  const hasInternalSources = internalSources.length > 0;
  const hasAnyInfo = hasInternalSources || model || latencyMs !== undefined;

  // Logic to determine if we should show a "Load Sources" button
  // 1. Must not already have sources
  // 2. Must have a valid messageId (UUID format, not timestamp)
  // 3. Not in modes that don't use RAG
  // 4. Not currently loading
  // 5. Content must be long enough to likely have sources (e.g. > 50 chars)
  const isUUID = messageId ? /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(messageId) : false;
  const noSourceModes = ['llm_only', 'intent_direct', 'greeting', 'chitchat', 'direct'];
  const canLoadCitations = !hasInternalSources && messageId && isUUID && !noSourceModes.includes(mode || '') && !isLoading && contentLength > 50;

  // Don't render if no information to show and can't load any
  if (!hasAnyInfo && !canLoadCitations && !isLoading) {
    return null;
  }

  return (
    <div className="mt-3 pt-2 border-t border-border/50 space-y-1.5">
      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Đang tải nguồn...</span>
        </div>
      )}

      {/* Lazy Load Button */}
      {canLoadCitations && !isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="flex items-center gap-1.5 text-[11px] text-primary/80 hover:text-primary hover:underline transition-all"
        >
          <span className="opacity-70">📚</span>
          <span>Xem nguồn tham khảo</span>
        </button>
      )}

      {/* Internal Sources (Documents) */}
      {hasInternalSources && (
        <div className="flex items-start gap-1.5 text-[11px] text-foreground/70">
          <span className="opacity-70">📄</span>
          <div className="flex-1">
            <span className="opacity-70 font-medium">Nguồn:</span>
            {' '}
            <span className="opacity-90">{internalSources.slice(0, showAllSources ? undefined : 3).map((citation, idx) => (
              <span key={idx}>
                {idx > 0 && ', '}
                <span
                  className="hover:opacity-100 transition-opacity cursor-default"
                  title={citation.content || citation.quote || citation.documentTitle || ''}
                >
                  {citation.documentTitle}
                  {citation.page && ` (tr. ${citation.page})`}
                </span>
              </span>
            ))}
              {!showAllSources && internalSources.length > 3 && (
                <button
                  onClick={() => setShowAllSources(true)}
                  className="ml-1 opacity-70 hover:opacity-100 underline transition-opacity"
                >
                  +{internalSources.length - 3} khác
                </button>
              )}
              {showAllSources && internalSources.length > 3 && (
                <button
                  onClick={() => setShowAllSources(false)}
                  className="ml-1 opacity-60 hover:opacity-100 underline transition-opacity"
                >
                  thu gọn
                </button>
              )}
            </span>
          </div>
        </div>
      )}

      {/* Model & Performance Info */}
      {(model || latencyMs !== undefined || isGrounded !== undefined) && (
        <div className="flex items-center gap-2 text-[10px] text-foreground/60">
          {model && (
            <span className="flex items-center gap-1">
              <span className="opacity-70">🤖</span>
              <span>{model}</span>
            </span>
          )}
          {latencyMs !== undefined && (
            <span className="flex items-center gap-1">
              <span className="opacity-70">⏱️</span>
              <span>{latencyMs}ms</span>
            </span>
          )}
          {isGrounded !== undefined && (
            <span className={`flex items-center gap-1 ${isGrounded ? 'text-green-600/80' : 'text-yellow-600/80'}`}>
              <span>{isGrounded ? '✓' : '~'}</span>
              <span>{isGrounded ? 'Có căn cứ' : 'Một phần'}</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

interface MessageActionsProps {
  content: string;
  role: 'user' | 'assistant';
}

export function MessageActions({ content, role }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`absolute ${role === 'user' ? 'left-2' : 'right-2'} top-0 -translate-y-1/2 p-1.5 rounded-full bg-background/50 backdrop-blur-md border border-border/50 shadow-sm z-10 transition-all opacity-0 group-hover:opacity-100 hover:bg-background/80`}
      title="Sao chép"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-600" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

// =============================================================================
// FEEDBACK BUTTONS - Like/Dislike for assistant messages
// =============================================================================

// Icons imported at top of file

interface FeedbackButtonsProps {
  messageId: string;
  conversationId: string;
  content: string;  // For copy functionality
  onFeedback?: (type: 'like' | 'dislike' | 'report' | 'copy') => void;
}

export function FeedbackButtons({ messageId, conversationId, content, onFeedback }: FeedbackButtonsProps) {
  const [feedback, setFeedback] = useState<'like' | 'dislike' | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [copied, setCopied] = useState(false);

  // Report Modal State
  const [selectedIssue, setSelectedIssue] = useState('hallucination');
  const [showIssueDropdown, setShowIssueDropdown] = useState(false);

  const issueOptions = [
    { value: 'hallucination', label: 'Thông tin sai lệch (Hallucination)' },
    { value: 'irrelevant', label: 'Không liên quan' },
    { value: 'incomplete', label: 'Chưa đầy đủ' },
    { value: 'inappropriate', label: 'Nội dung không phù hợp' },
    { value: 'other', label: 'Khác' }
  ];

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // ... (handleFeedback and handleReport same as before) ...
  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (isLoading || feedback === type) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/feedback/${type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, conversation_id: conversationId }),
      });
      if (response.ok) {
        setFeedback(type);
        onFeedback?.(type);
      }
    } catch (err) { console.error('Feedback error:', err); } finally { setIsLoading(false); }
  };

  const handleReport = async (issueType: string, description: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/feedback/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: messageId, conversation_id: conversationId,
          issue_type: issueType, description: description,
        }),
      });
      if (response.ok) { setShowReportModal(false); onFeedback?.('report'); }
    } catch (err) { console.error('Report error:', err); } finally { setIsLoading(false); }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      onFeedback?.('copy');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) { console.error('Failed to copy:', err); }
  };

  return (
    <div className="flex items-center gap-1 mt-0">
      {/* ... Buttons ... */}
      <button onClick={() => handleFeedback('like')} disabled={isLoading} className={`p-1.5 rounded-lg transition-all ${feedback === 'like' ? 'bg-green-100 text-green-600 dark:bg-green-900/30' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`} title="Hữu ích"><ThumbsUp className="h-3.5 w-3.5" /></button>
      <button onClick={() => handleFeedback('dislike')} disabled={isLoading} className={`p-1.5 rounded-lg transition-all ${feedback === 'dislike' ? 'bg-red-100 text-red-600 dark:bg-red-900/30' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`} title="Không hữu ích"><ThumbsDown className="h-3.5 w-3.5" /></button>
      <button onClick={() => setShowReportModal(true)} disabled={isLoading} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-yellow-600 transition-all" title="Báo cáo vấn đề"><AlertTriangle className="h-3.5 w-3.5" /></button>
      <button onClick={handleCopy} className={`p-1.5 rounded-lg transition-all ${copied ? 'bg-green-100 text-green-600 dark:bg-green-900/30' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`} title="Sao chép">{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}</button>

      {/* Report Modal */}
      {showReportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-background rounded-xl p-4 max-w-sm w-full shadow-2xl border border-border animate-in fade-in zoom-in-95 duration-200">
            <h3 className="font-medium text-sm mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              Báo cáo vấn đề
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Loại vấn đề</label>
                <div className="relative">
                  <button
                    onClick={() => setShowIssueDropdown(!showIssueDropdown)}
                    className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-sm transition hover:bg-muted/50"
                  >
                    <span>{issueOptions.find(o => o.value === selectedIssue)?.label}</span>
                    <svg className={`h-4 w-4 text-muted-foreground transition-transform ${showIssueDropdown ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {showIssueDropdown && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setShowIssueDropdown(false)} />
                      <div className="absolute top-full left-0 right-0 z-20 mt-1 rounded-lg border border-border bg-background shadow-lg overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                        {issueOptions.map(option => (
                          <button
                            key={option.value}
                            onClick={() => { setSelectedIssue(option.value); setShowIssueDropdown(false); }}
                            className={`w-full px-3 py-2 text-sm text-left hover:bg-muted transition-colors ${selectedIssue === option.value ? 'bg-primary/10 text-primary font-medium' : ''}`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Mô tả chi tiết</label>
                <textarea
                  id="description"
                  placeholder="Vui lòng mô tả chi tiết vấn đề..."
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary h-24 resize-none transition-all placeholder:text-muted-foreground/50"
                />
              </div>

              <div className="flex gap-2 pt-1">
                <button onClick={() => setShowReportModal(false)} className="flex-1 py-1.5 rounded-lg border border-border text-sm hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">Hủy</button>
                <button
                  onClick={() => {
                    const description = (document.getElementById('description') as HTMLTextAreaElement)?.value;
                    if (description) handleReport(selectedIssue, description);
                  }}
                  className="flex-1 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors shadow-sm"
                >
                  Gửi báo cáo
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
