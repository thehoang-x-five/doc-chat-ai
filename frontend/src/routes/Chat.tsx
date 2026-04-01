import { useState, useEffect, useRef } from 'react';
import { useI18n } from '@/lib/i18n';
import { useAuthStore } from '@/lib/authStore';
import { apiClient, type AIModel, type ChatQueryResponse, type Citation, type Workspace, type Conversation, type Category } from '@/lib/api';
import { useMessages } from '@/lib/hooks/useMessages';
import { useConversations } from '@/lib/hooks/useConversations';
import { queryClient, QUERY_KEYS } from '@/lib/queryClient';
import { TokenUsageDisplay } from '@/components/chat/TokenUsageDisplay';
import { MemorySidebar } from '@/components/memori/MemorySidebar';
import { ProgressiveSearchUI } from '@/components/search/ProgressiveSearchUI';
import { CitationNote, MessageActions, FeedbackButtons } from '@/components/chat/CitationNote';
import { Search } from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  model?: string;
  latencyMs?: number;
  isGrounded?: boolean;
  evidenceScore?: number;
  mode?: ChatMode;
  // Image generation support
  images?: string[];
  isImageResponse?: boolean;
  // Image input (user attached image)
  attachedImage?: string;
  tokenUsage?: { prompt: number; completion: number };
  contextStats?: { memory_tokens: number; chunk_tokens: number; total_tokens: number };
}

interface ImageAttachment {
  data: string; // base64
  mimeType: string;
  preview: string; // data URL for preview
}



// Chat modes
type ChatMode = 'rag_only' | 'hybrid' | 'llm_only';

// Chat mode icons - labels come from translations
const CHAT_MODE_ICONS: Record<ChatMode, string> = {
  rag_only: '📚',
  hybrid: '🔄',
  llm_only: '🤖',
};

export default function Chat() {
  const { t } = useI18n();
  const { user } = useAuthStore();
  // State declarations

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [models, setModels] = useState<AIModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('auto');
  const [availableCategories, setAvailableCategories] = useState<Category[]>([]);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [showCategorySelector, setShowCategorySelector] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [chatMode, setChatMode] = useState<ChatMode>('hybrid');
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [selectAllDocs, setSelectAllDocs] = useState(true);
  const [imageAttachment, setImageAttachment] = useState<ImageAttachment | null>(null);
  const [showMemorySidebar, setShowMemorySidebar] = useState(true);
  const [showSearchPanel, setShowSearchPanel] = useState(false); // New state for search panel
  const [lastSentQuery, setLastSentQuery] = useState<string>('');

  // Streaming state
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamProgress, setStreamProgress] = useState<{ step: string; progress: number; message?: string } | null>(null);
  const [elapsedTime, setElapsedTime] = useState<number>(0);

  const elapsedTimerRef = useRef<NodeJS.Timeout | null>(null);
  const currentStreamedContentRef = useRef<string>('');

  // Conversation management (using hook)
  const {
    conversations,
    isLoading: loadingConversations,
    createConversation,
    deleteConversation: deleteConversationMutation
  } = useConversations(selectedWorkspaceId);

  // Restore last conversation ID
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(() => {
    return localStorage.getItem('lastConversationId');
  });

  // Message management with caching
  const {
    messages: rawMessages,
    isLoading: isMessageLoading,
    setMessages: setCachedMessages,
    addOptimisticMessage,
    updateMessage: updateCachedMessage,
    clearMessages
  } = useMessages(currentConversationId);

  // Cast raw messages to ChatMessage[] (types are compatible)
  const messages = rawMessages as any as ChatMessage[];

  // Sync isMessageLoading with local isLoading state
  useEffect(() => {
    setIsLoading(isMessageLoading);
  }, [isMessageLoading]);

  // Restore last conversation from list
  useEffect(() => {
    if (conversations.length > 0 && !currentConversationId) {
      const lastConvId = localStorage.getItem('lastConversationId');
      if (lastConvId && conversations.some(c => c.id === lastConvId)) {
        setCurrentConversationId(lastConvId);
      }
    }
  }, [conversations, currentConversationId]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Close all dropdowns helper
  const closeAllDropdowns = () => {
    setShowModeSelector(false);
    setShowCategorySelector(false);
    setShowModelSelector(false);
  };

  // Toggle dropdown with mutual exclusion
  const toggleModeSelector = () => {
    const newState = !showModeSelector;
    closeAllDropdowns();
    setShowModeSelector(newState);
  };

  const toggleCategorySelector = () => {
    const newState = !showCategorySelector;
    closeAllDropdowns();
    setShowCategorySelector(newState);
  };

  const toggleModelSelector = () => {
    const newState = !showModelSelector;
    closeAllDropdowns();
    setShowModelSelector(newState);
  };

  // ... (rest of the file until rendering)

  // Build chat modes from translations
  const chatModes: { id: ChatMode; label: string; description: string; icon: string }[] = [
    {
      id: 'rag_only',
      label: t.chat?.modeRagOnly || 'Internal Docs Only',
      description: t.chat?.modeRagOnlyDesc || 'Only answer from uploaded documents',
      icon: CHAT_MODE_ICONS.rag_only
    },
    {
      id: 'hybrid',
      label: t.chat?.modeHybrid || 'Docs + AI',
      description: t.chat?.modeHybridDesc || 'Prioritize docs, supplement with AI if needed',
      icon: CHAT_MODE_ICONS.hybrid
    },
    {
      id: 'llm_only',
      label: t.chat?.modeLlmOnly || 'AI Only',
      description: t.chat?.modeLlmOnlyDesc || 'Don\'t use documents, only AI',
      icon: CHAT_MODE_ICONS.llm_only
    },
  ];

  const currentMode = chatModes.find(m => m.id === chatMode)!;

  // Load initial data
  useEffect(() => {
    // Load models
    apiClient.getModels().then(setModels).catch(console.error);

    // Load workspaces and select first one or create default
    apiClient.getWorkspaces().then(async (ws) => {
      if (ws.length > 0) {
        setWorkspaces(ws);
        setSelectedWorkspaceId(ws[0].id);
        // Load categories for this workspace
        apiClient.getCategories(ws[0].id).then(setAvailableCategories).catch(() => setAvailableCategories([]));
      } else {
        // Create default workspace
        try {
          const newWs = await apiClient.createWorkspace({ name: 'Default Workspace' });
          setWorkspaces([newWs]);
          setSelectedWorkspaceId(newWs.id);
        } catch (e) {
          console.error('Failed to create default workspace:', e);
        }
      }
    }).catch(console.error);
  }, []);

  // Load categories when workspace changes
  useEffect(() => {
    if (selectedWorkspaceId) {
      apiClient.getCategories(selectedWorkspaceId).then(setAvailableCategories).catch(() => setAvailableCategories([]));
    }
  }, [selectedWorkspaceId]);

  // Create new conversation
  const handleNewConversation = () => {
    if (!selectedWorkspaceId) return;
    createConversation(
      { title: 'New Chat' },
      {
        onSuccess: (newConv) => {
          handleSelectConversation(newConv.id);
        }
      }
    );
  };

  // Helper function to generate conversation title from first message
  const generateConversationTitle = (message: string): string => {
    // Remove extra whitespace and newlines
    const cleaned = message.trim().replace(/\s+/g, ' ');

    // Take first 50 characters
    if (cleaned.length <= 50) {
      return cleaned;
    }

    // Try to cut at word boundary
    const truncated = cleaned.slice(0, 50);
    const lastSpace = truncated.lastIndexOf(' ');

    if (lastSpace > 30) {
      return truncated.slice(0, lastSpace) + '...';
    }

    return truncated + '...';
  };

  // Select conversation
  const handleSelectConversation = async (convId: string) => {
    setCurrentConversationId(convId);
    // Messages will be loaded from cache instantly if available via useMessages hook
    localStorage.setItem('lastConversationId', convId);

    // Set lastSentQuery for memory recall if messages exist in cache
    // We use a small timeout to allow the hook to update its data if needed
    setTimeout(() => {
      const queryData = queryClient.getQueryData<any[]>(QUERY_KEYS.messages(convId));
      if (queryData && queryData.length > 0) {
        const lastUserMsg = [...queryData].reverse().find(m => m.role === 'user');
        setLastSentQuery(lastUserMsg?.content || '');
      } else {
        setLastSentQuery('');
      }
    }, 0);
  };



  // Delete conversation
  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(t.chat?.confirmDelete || 'Delete this conversation?')) return;
    deleteConversationMutation(convId, {
      onSuccess: () => {
        if (currentConversationId === convId) {
          handleSelectConversation(''); // Clear selection
          clearMessages();
        }
      }
    });
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading || !selectedWorkspaceId) return;

    const currentInput = input.trim();
    const isFirstMessage = messages.length === 0;

    // Auto-create conversation if none selected
    let convId = currentConversationId;
    if (!convId) {
      try {
        // Generate title from first message
        const title = generateConversationTitle(currentInput);
        const conv = await apiClient.createConversation(selectedWorkspaceId, title);
        // Optimistically add to cache
        queryClient.setQueryData(
          QUERY_KEYS.conversations(selectedWorkspaceId || ''),
          (old: Conversation[] | undefined) => [conv, ...(old || [])]
        );
        convId = conv.id;
        setCurrentConversationId(convId);
        localStorage.setItem('lastConversationId', convId);
      } catch (error) {
        console.error('Failed to create conversation:', error);
        return;
      }
    } else if (isFirstMessage) {
      // Update conversation title in local state if this is the first message
      // and current title is "New Chat"
      const currentConv = conversations.find(c => c.id === convId);
      if (currentConv && currentConv.title === 'New Chat') {
        const newTitle = generateConversationTitle(currentInput);
        // Optimistically update conversation title in cache
        queryClient.setQueryData(
          QUERY_KEYS.conversations(selectedWorkspaceId || ''),
          (old: Conversation[] | undefined) =>
            old?.map(c => c.id === convId ? { ...c, title: newTitle } : c) || []
        );
      }
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: currentInput,
      mode: chatMode,
      attachedImage: imageAttachment?.preview,
    };

    // Cancel any outgoing refetches to prevent overwriting our optimistic data
    await queryClient.cancelQueries({ queryKey: QUERY_KEYS.messages(convId || '') });

    // Optimistically add user message using direct queryClient access to avoid stale closures
    queryClient.setQueryData(
      QUERY_KEYS.messages(convId || ''),
      (old: any[] | undefined) => [...(old || []), userMessage]
    );
    const currentImage = imageAttachment;
    setInput('');
    setImageAttachment(null);
    setIsLoading(true);

    // Track last sent query for memory sidebar recall
    setLastSentQuery(currentInput);

    try {
      // LLM only mode - direct chat without RAG and without saving to DB
      if (chatMode === 'llm_only') {
        const response = await apiClient.chatDirect({
          question: currentInput,
          model: selectedModel === 'auto' ? undefined : selectedModel,
          imageData: currentImage?.data,
          imageMimeType: currentImage?.mimeType,
        });

        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
          model: response.model,
          latencyMs: response.latencyMs,
          isGrounded: response.isGrounded,
          evidenceScore: response.evidenceScore,
          mode: chatMode,
          images: response.images,
          isImageResponse: response.isImageResponse,
          tokenUsage: response.tokenUsage,
          contextStats: response.contextStats,
        };

        // Optimistic update for LLM direct response
        queryClient.setQueryData(
          QUERY_KEYS.messages(convId || ''),
          (old: any[] | undefined) => [...(old || []), assistantMessage]
        );
      } else {
        // RAG or Hybrid mode - use streaming for real-time response
        setIsStreaming(true);
        setStreamingContent('');
        currentStreamedContentRef.current = '';
        setStreamProgress({ step: 'starting', progress: 0, message: '🤔 Đang suy nghĩ...' });
        setElapsedTime(0);

        // Start elapsed timer
        const startTime = Date.now();
        elapsedTimerRef.current = setInterval(() => {
          setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
        }, 1000);

        // Add placeholder assistant message for streaming
        const streamingMsgId = (Date.now() + 1).toString();
        const placeholderMsg: ChatMessage = {
          id: streamingMsgId,
          role: 'assistant',
          content: '',
          mode: chatMode,
        };

        queryClient.setQueryData(
          QUERY_KEYS.messages(convId || ''),
          (old: any[] | undefined) => [...(old || []), placeholderMsg]
        );

        let finalModel = '';
        let finalCitations: any[] = [];

        try {
          await apiClient.sendMessageStream(
            convId!,
            currentInput,
            {
              workspaceId: selectedWorkspaceId!,
              model: selectedModel === 'auto' ? undefined : selectedModel,
              tags: selectAllDocs ? undefined : (selectedCategoryIds.length > 0 ? selectedCategoryIds : undefined),
              onProgress: (step, progress, message) => {
                // Only show progress if we haven't received any content yet
                if (!currentStreamedContentRef.current) {
                  setStreamProgress({ step, progress, message: message || `${step}... ${progress}%` });
                }
              },
              onToken: (token) => {
                setStreamProgress(null); // Hide progress once tokens arrive
                setStreamingContent(prev => prev + token);

                currentStreamedContentRef.current += token;

                // Debug log to verify token reception
                // console.log('Token:', token, 'Total:', currentStreamedContentRef.current);

                // Update the streaming message in real-time
                queryClient.setQueryData(
                  QUERY_KEYS.messages(convId || ''),
                  (old: any[] | undefined) =>
                    old?.map(m => m.id === streamingMsgId ? { ...m, content: currentStreamedContentRef.current } : m) || []
                );
              },
              onMetadata: (metadata) => {
                finalModel = metadata.model || '';
                finalCitations = metadata.citations || [];
                // Update message with metadata + quality scores
                queryClient.setQueryData(
                  QUERY_KEYS.messages(convId || ''),
                  (old: any[] | undefined) =>
                    old?.map(m => m.id === streamingMsgId ? {
                      ...m,
                      model: finalModel,
                      citations: finalCitations,
                      quality: metadata.quality,
                      qualityWarnings: metadata.quality_warnings,
                    } : m) || []
                );
              },
              onError: (message, code) => {
                queryClient.setQueryData(
                  QUERY_KEYS.messages(convId || ''),
                  (old: any[] | undefined) =>
                    old?.map(m => m.id === streamingMsgId ? { ...m, content: `❌ Error: ${message}` } : m) || []
                );
              },
              onDone: (totalTimeMs) => {
                // Update message with final latency
                queryClient.setQueryData(
                  QUERY_KEYS.messages(convId || ''),
                  (old: any[] | undefined) =>
                    old?.map(m => m.id === streamingMsgId ? { ...m, latencyMs: totalTimeMs } : m) || []
                );
                console.log(`⏱️ Stream completed in ${totalTimeMs}ms`);
              },
              onQualityWarning: (warning) => {
                console.warn('⚠️ Quality warning:', warning);
                // Append warning indicator to the message
                queryClient.setQueryData(
                  QUERY_KEYS.messages(convId || ''),
                  (old: any[] | undefined) =>
                    old?.map(m => m.id === streamingMsgId ? {
                      ...m,
                      qualityWarnings: [...(m.qualityWarnings || []), warning],
                    } : m) || []
                );
              },
              onReplaceResponse: (newContent) => {
                console.log('🔄 Replacing response with validated content');
                currentStreamedContentRef.current = newContent;
                queryClient.setQueryData(
                  QUERY_KEYS.messages(convId || ''),
                  (old: any[] | undefined) =>
                    old?.map(m => m.id === streamingMsgId ? { ...m, content: newContent } : m) || []
                );
              },
            }
          );
        } finally {
          // Cleanup
          if (elapsedTimerRef.current) {
            clearInterval(elapsedTimerRef.current);
            elapsedTimerRef.current = null;
          }
          setIsStreaming(false);
          setStreamProgress(null);
          setStreamingContent('');
          currentStreamedContentRef.current = '';
        }

        // Update conversation message count in cache
        queryClient.setQueryData(
          QUERY_KEYS.conversations(selectedWorkspaceId || ''),
          (old: Conversation[] | undefined) =>
            old?.map(c => c.id === convId ? { ...c, messageCount: (c.messageCount || 0) + 2 } : c) || []
        );
      }
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };

      queryClient.setQueryData(
        QUERY_KEYS.messages(convId || ''),
        (old: any[] | undefined) => [...(old || []), errorMessage]
      );
    } finally {
      setIsLoading(false);
    }
  };

  const groupedModels = Array.isArray(models) ? models.reduce((acc, model) => {
    if (!acc[model.provider]) acc[model.provider] = [];
    acc[model.provider].push(model);
    return acc;
  }, {} as Record<string, AIModel[]>) : {};

  const toggleCategory = (categoryId: string) => {
    setSelectAllDocs(false);
    setSelectedCategoryIds(prev =>
      prev.includes(categoryId) ? prev.filter(id => id !== categoryId) : [...prev, categoryId]
    );
  };

  const clearCategories = () => {
    setSelectedCategoryIds([]);
    setSelectAllDocs(true);
  };

  const handleSelectAll = () => {
    setSelectAllDocs(true);
    setSelectedCategoryIds([]);
  };

  // Handle image file selection
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('Image size must be less than 10MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      // Extract base64 data (remove data:image/xxx;base64, prefix)
      const base64Data = dataUrl.split(',')[1];
      setImageAttachment({
        data: base64Data,
        mimeType: file.type,
        preview: dataUrl,
      });
    };
    reader.readAsDataURL(file);

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeImageAttachment = () => {
    setImageAttachment(null);
  };

  return (
    <div className="flex h-[calc(100vh-88px)] gap-2 overflow-hidden">
      {/* Conversation Sidebar - 1/4 width */}
      <div className="w-1/4 min-w-[180px] max-w-[260px] flex flex-col rounded-xl border border-border bg-card/50 overflow-hidden">
        {/* Sidebar Header */}
        <div className="p-2 border-b border-border bg-muted/30">
          <div className="flex gap-2">
            <button
              onClick={handleNewConversation}
              className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
              title={t.chat?.newChat || 'New Chat'}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span className="hidden sm:inline">New Chat</span>
            </button>

            {/* Search Toggle Button */}
            <button
              onClick={() => {
                if (!selectedWorkspaceId) return;
                setShowSearchPanel(!showSearchPanel);
                if (showMemorySidebar) setShowMemorySidebar(false);
              }}
              disabled={!selectedWorkspaceId}
              title={!selectedWorkspaceId ? "Select a conversation first" : "Search"}
              className={`w-10 flex items-center justify-center rounded-lg border transition ${showSearchPanel
                ? 'border-primary bg-primary/10 text-primary'
                : !selectedWorkspaceId
                  ? 'opacity-50 cursor-not-allowed bg-muted border-border'
                  : 'border-border bg-background hover:bg-muted'
                }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>

            {/* Memory Toggle Button */}
            <button
              onClick={() => {
                setShowMemorySidebar(!showMemorySidebar);
                if (showSearchPanel) setShowSearchPanel(false);
              }}
              className={`w-10 flex items-center justify-center rounded-lg border transition ${showMemorySidebar
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border bg-background hover:bg-muted'
                }`}
              title="Memory"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2a3 3 0 0 0-3 3v4a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z M12 15v7M8 22h8M15 9a5 5 0 0 1 5 5v1a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-1a5 5 0 0 1 5-5" />
              </svg>
            </button>
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 pr-1.5 space-y-1 conversation-scrollbar">
          {loadingConversations ? (
            <div className="flex items-center justify-center py-8">
              <svg className="h-5 w-5 animate-spin text-muted-foreground" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              <svg className="mx-auto h-8 w-8 opacity-50 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p>{t.chat?.noConversations || 'No conversations yet'}</p>
            </div>
          ) : (
            conversations.map(conv => (
              <div
                key={conv.id}
                onClick={() => handleSelectConversation(conv.id)}
                className={`group flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer transition ${currentConversationId === conv.id
                  ? 'bg-primary/10 text-primary'
                  : 'hover:bg-muted'
                  }`}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{conv.title || 'Untitled'}</p>
                  <p className="text-xs text-muted-foreground">
                    {conv.messageCount || 0} {t.chat?.messagesCount || 'messages'}
                  </p>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(conv.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/20 hover:text-destructive transition"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Chat Area - 3/4 width */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header with controls */}
        <div className="mb-2 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">{t.chat?.title || 'Chat'}</h1>
            <p className="text-xs text-muted-foreground">{t.chat?.subtitle || 'Ask questions about your documents'}</p>
          </div>

          <div className="flex items-center gap-2">
            {/* Chat Mode Selector */}
            <div className="relative">
              <button
                onClick={toggleModeSelector}
                className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs transition hover:bg-muted"
              >
                <span>{currentMode.icon}</span>
                <span className="hidden sm:inline">{currentMode.label}</span>
                <svg className={`h-3 w-3 transition ${showModeSelector ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showModeSelector && (
                <div className="absolute left-0 top-full z-20 mt-1 w-64 rounded-xl border border-border bg-background p-2 shadow-lg">
                  {chatModes.map(mode => (
                    <button
                      key={mode.id}
                      onClick={() => { setChatMode(mode.id); setShowModeSelector(false); }}
                      className={`flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left transition ${chatMode === mode.id ? 'bg-primary/10 text-primary' : 'hover:bg-muted'
                        }`}
                    >
                      <span className="text-base">{mode.icon}</span>
                      <div>
                        <p className="text-sm font-medium">{mode.label}</p>
                        <p className="text-xs text-muted-foreground">{mode.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Category Filter - Only show when not in LLM only mode */}
            {chatMode !== 'llm_only' && (
              <div className="relative">
                <button
                  onClick={toggleCategorySelector}
                  className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition ${!selectAllDocs && selectedCategoryIds.length > 0
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background hover:bg-muted'
                    }`}
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                  </svg>
                  {selectAllDocs ? (
                    <span className="hidden sm:inline">{t.chat?.allDocuments || 'All'}</span>
                  ) : selectedCategoryIds.length > 0 ? (
                    <span>{selectedCategoryIds.length}</span>
                  ) : (
                    <span className="hidden sm:inline">{t.chat?.selectCategories || 'Filter'}</span>
                  )}
                </button>

                {showCategorySelector && (
                  <div className="absolute right-0 top-full z-10 mt-1 w-72 rounded-xl border border-border bg-background p-3 shadow-lg">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">
                        {t.chat?.filterByCategory || 'Filter by category'}
                      </span>
                    </div>

                    {/* All Documents Option */}
                    <button
                      onClick={handleSelectAll}
                      className={`mb-2 flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition ${selectAllDocs ? 'bg-primary/10 text-primary' : 'hover:bg-muted'
                        }`}
                    >
                      <span>{t.chat?.allDocuments || 'All documents'}</span>
                      {selectAllDocs && (
                        <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>

                    {availableCategories.length > 0 && (
                      <>
                        <div className="my-2 border-t border-border" />
                        <div className="max-h-48 space-y-1 overflow-y-auto">
                          {availableCategories.map(category => (
                            <button
                              key={category.id}
                              onClick={() => toggleCategory(category.id)}
                              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition ${selectedCategoryIds.includes(category.id)
                                ? 'bg-primary/10 text-primary'
                                : 'hover:bg-muted'
                                }`}
                            >
                              <span className="flex items-center gap-2">
                                <span
                                  className="w-3 h-3 rounded-sm flex-shrink-0"
                                  style={{ backgroundColor: category.color || '#6366f1' }}
                                />
                                {category.name}
                              </span>
                              <span className="text-xs text-muted-foreground">{category.documentCount || 0}</span>
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}


            {/* Model Selector */}
            <div className="relative">
              <button
                onClick={toggleModelSelector}
                className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs transition hover:bg-muted"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                <span className="hidden sm:inline max-w-[100px] truncate">
                  {selectedModel === 'auto'
                    ? 'Auto'
                    : models.find(m => m.id === selectedModel)?.name || selectedModel
                  }
                </span>
              </button>

              {showModelSelector && (
                <div className="absolute right-0 top-full z-20 mt-1 w-64 rounded-xl border border-border bg-background p-2 shadow-lg">
                  {/* Auto option */}
                  <button
                    onClick={() => { setSelectedModel('auto'); setShowModelSelector(false); }}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition ${selectedModel === 'auto' ? 'bg-primary/10 text-primary' : 'hover:bg-muted'
                      }`}
                  >
                    <span>✨ Auto</span>
                    {selectedModel === 'auto' && (
                      <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>

                  <div className="my-2 border-t border-border" />

                  {/* Grouped models */}
                  <div className="max-h-64 overflow-y-auto">
                    {Object.entries(groupedModels).map(([provider, providerModels]) => (
                      <div key={provider} className="mb-2">
                        <div className="px-3 py-1 text-[10px] font-semibold text-muted-foreground uppercase">{provider}</div>
                        {providerModels.map(model => (
                          <button
                            key={model.id}
                            onClick={() => { if (model.available) { setSelectedModel(model.id); setShowModelSelector(false); } }}
                            disabled={!model.available}
                            className={`flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-xs transition ${selectedModel === model.id
                              ? 'bg-primary/10 text-primary'
                              : model.available
                                ? 'hover:bg-muted'
                                : 'opacity-50 cursor-not-allowed'
                              }`}
                          >
                            <span className="truncate">{model.name}</span>
                            {model.quota !== undefined && (
                              <span className="text-[10px] text-muted-foreground">{model.quota}%</span>
                            )}
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>

              )}
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden rounded-xl border border-border bg-card/50 p-3 pr-2 chat-scrollbar">
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="mt-2">{t.chat?.startConversation || 'Start a conversation'}</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex group ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} max-w-[85%]`}>
                    <div className={`relative w-full rounded-2xl px-4 py-3 break-words ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`} style={{ wordWrap: 'break-word', overflowWrap: 'break-word' }}>
                      {/* Copy button */}
                      <MessageActions content={msg.content} role={msg.role} />

                      {/* Display attached image for user messages */}
                      {msg.role === 'user' && msg.attachedImage && (
                        <div className="mb-2 overflow-hidden rounded-lg">
                          <img
                            src={msg.attachedImage}
                            alt="Attached"
                            className="max-w-full max-h-32 object-contain"
                          />
                        </div>
                      )}

                      {/* Thinking indicator for streaming - shown INSTEAD of content when empty */}
                      {msg.role === 'assistant' && msg.content === '' && isStreaming ? (
                        <div className="flex items-center gap-3 py-2">
                          <div className="flex space-x-1">
                            <span className="h-2 w-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                            <span className="h-2 w-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                            <span className="h-2 w-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                          </div>
                          <span className="text-sm text-muted-foreground">
                            {streamProgress?.message || '🤔 Đang suy nghĩ...'} ({elapsedTime}s)
                          </span>
                        </div>
                      ) : (
                        <div className="text-sm space-y-1 w-full" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'break-word', wordBreak: 'normal' }}>
                          {msg.content.split('\n').map((line, idx) => {
                            // Bold text: **text**
                            if (line.includes('**')) {
                              const parts = line.split(/(\*\*.*?\*\*)/g);
                              return (
                                <p key={idx} className="leading-normal">
                                  {parts.map((part, i) =>
                                    part.startsWith('**') && part.endsWith('**') ? (
                                      <strong key={i}>{part.slice(2, -2)}</strong>
                                    ) : (
                                      <span key={i}>{part}</span>
                                    )
                                  )}
                                </p>
                              );
                            }
                            // Bullet points: * text or - text
                            if (line.match(/^\s*[\*\-]\s+/)) {
                              return (
                                <p key={idx} className="pl-4 leading-normal">
                                  • {line.replace(/^\s*[\*\-]\s+/, '')}
                                </p>
                              );
                            }
                            // Numbered lists: 1. text
                            if (line.match(/^\s*\d+\.\s+/)) {
                              return <p key={idx} className="pl-4 leading-normal">{line}</p>;
                            }
                            // Headers: ## text
                            if (line.startsWith('##')) {
                              return <h3 key={idx} className="font-semibold mt-2 mb-1">{line.replace(/^#+\s*/, '')}</h3>;
                            }
                            // Regular text
                            return line ? <p key={idx} className="leading-normal">{line}</p> : <br key={idx} />;
                          })}
                        </div>
                      )}

                      {/* Display generated images */}
                      {msg.isImageResponse && msg.images && msg.images.length > 0 && (
                        <div className="mt-3 grid gap-2">
                          {msg.images.map((img, idx) => (
                            <div key={idx} className="overflow-hidden rounded-lg">
                              <img
                                src={`data:image/png;base64,${img}`}
                                alt={`Generated image ${idx + 1}`}
                                className="max-w-full max-h-48 object-contain"
                              />
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Token Usage Display - Hidden by default, can enable for debugging */}
                      {/* Citation Note - New unified component */}
                      {msg.role === 'assistant' && !msg.isImageResponse && (
                        <CitationNote
                          messageId={msg.id}
                          contentLength={msg.content?.length || 0}
                          citations={msg.citations}
                          model={msg.model}
                          latencyMs={msg.latencyMs}
                          mode={msg.mode}
                          isGrounded={msg.isGrounded}
                        />
                      )}
                    </div>

                    {/* Feedback Buttons - Below bubble */}
                    {msg.role === 'assistant' && !msg.isImageResponse && (
                      <div className="flex items-center gap-2 mt-1 px-1 opacity-100 transition-opacity">
                        <FeedbackButtons
                          messageId={msg.id}
                          conversationId={currentConversationId!}
                          content={msg.content}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="mt-3">
          {/* Image preview */}
          {imageAttachment && (
            <div className="mb-2 flex items-start gap-2">
              <div className="relative inline-block">
                <img
                  src={imageAttachment.preview}
                  alt="Attachment preview"
                  className="h-16 w-16 rounded-lg object-cover border border-border"
                />
                <button
                  onClick={removeImageAttachment}
                  className="absolute -right-1.5 -top-1.5 rounded-full bg-destructive p-0.5 text-destructive-foreground shadow-md hover:bg-destructive/90"
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          <div className="flex gap-2">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="hidden"
            />

            {/* Image upload button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="rounded-xl border border-border bg-background px-3 py-2.5 text-sm transition hover:bg-muted disabled:opacity-50"
              title={t.chat?.attachImage || 'Attach image'}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </button>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={imageAttachment ? (t.chat?.askAboutImage || 'Ask about this image...') : (t.chat?.placeholder || 'Ask a question...')}
              disabled={isLoading}
              className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Search Panel - Right side (mutually exclusive with Memory) */}
      {
        showSearchPanel && selectedWorkspaceId && (
          <div className="w-1/4 min-w-[180px] max-w-[260px] flex flex-col rounded-xl border border-border bg-card overflow-hidden h-full">
            <ProgressiveSearchUI
              workspaceId={selectedWorkspaceId}
              onClose={() => setShowSearchPanel(false)}
            />
          </div>
        )
      }

      {/* Memory Sidebar - Right side */}
      {
        showMemorySidebar && selectedWorkspaceId && user && (
          <MemorySidebar
            workspaceId={selectedWorkspaceId}
            entityId={user.id}
            currentQuery={lastSentQuery} // Pass the last sent query
            onClose={() => setShowMemorySidebar(false)}
            className="h-full"
          />
        )
      }
    </div >
  );
}
