import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { QUERY_KEYS } from '../queryClient';
import { apiClient } from '@/lib/api';

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: any[];
    model?: string;
    latencyMs?: number;
    tokenUsage?: { prompt: number; completion: number };
    contextStats?: any;
    isImageResponse?: boolean;
    images?: string[];
    mode?: string;
}

interface NormalizedMessage {
    id: string;
    conversationId: string;
    role: 'user' | 'assistant';
    content: string;
    createdAt: string;
    model?: string;
    latencyMs?: number;
    tokenUsage?: { prompt: number; completion: number };
    citations?: any[];
    contextStats?: any;
}

/**
 * Hook for fetching and caching messages for a conversation.
 * Messages are cached and shown instantly when switching conversations.
 */
export function useMessages(conversationId: string | null) {
    const queryClient = useQueryClient();

    // Get from localStorage for initial data
    const getStoredMessages = (convId: string): Message[] | undefined => {
        try {
            const stored = localStorage.getItem(`messages_${convId}`);
            return stored ? JSON.parse(stored) : undefined;
        } catch {
            return undefined;
        }
    };

    // Save to localStorage
    const saveToStorage = (convId: string, messages: Message[]) => {
        try {
            localStorage.setItem(`messages_${convId}`, JSON.stringify(messages));
        } catch (e) {
            console.warn('Failed to save messages to localStorage:', e);
        }
    };

    const query = useQuery({
        queryKey: QUERY_KEYS.messages(conversationId || ''),
        queryFn: async (): Promise<Message[]> => {
            if (!conversationId) return [];
            const msgs = await apiClient.getMessages(conversationId);
            const mapped = msgs.map((m: NormalizedMessage) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                citations: m.citations,
                model: m.model,
                latencyMs: m.latencyMs,
                tokenUsage: m.tokenUsage,
                contextStats: m.contextStats,
            }));
            // Save to localStorage for offline access
            saveToStorage(conversationId, mapped);
            return mapped;
        },
        enabled: !!conversationId,
        // Use localStorage data as initial placeholder for instant display
        placeholderData: () => conversationId ? getStoredMessages(conversationId) : undefined,
    });

    // Optimistic update: add message to cache before API response
    const addOptimisticMessage = (message: Message) => {
        queryClient.setQueryData(
            QUERY_KEYS.messages(conversationId || ''),
            (old: Message[] | undefined) => [...(old || []), message]
        );
    };

    // Update a message in cache (e.g., streaming content)
    const updateMessage = (messageId: string, updates: Partial<Message>) => {
        queryClient.setQueryData(
            QUERY_KEYS.messages(conversationId || ''),
            (old: Message[] | undefined) =>
                old?.map(m => m.id === messageId ? { ...m, ...updates } : m) || []
        );
    };

    // Replace all messages (after final API response)
    const setMessages = (messages: Message[]) => {
        queryClient.setQueryData(
            QUERY_KEYS.messages(conversationId || ''),
            messages
        );
    };

    // Clear messages from cache
    const clearMessages = () => {
        queryClient.setQueryData(
            QUERY_KEYS.messages(conversationId || ''),
            []
        );
    };

    // Invalidate cache to force refetch
    const invalidate = () => {
        queryClient.invalidateQueries({
            queryKey: QUERY_KEYS.messages(conversationId || ''),
        });
    };

    return {
        messages: query.data || [],
        isLoading: query.isLoading,
        isFetching: query.isFetching,
        error: query.error,
        refetch: query.refetch,
        // Optimistic update helpers
        addOptimisticMessage,
        updateMessage,
        setMessages,
        clearMessages,
        invalidate,
    };
}
