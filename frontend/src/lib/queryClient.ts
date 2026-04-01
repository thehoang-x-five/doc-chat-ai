import { QueryClient } from '@tanstack/react-query';

// Query keys factory for type-safe cache key management
export const QUERY_KEYS = {
    conversations: (workspaceId: string) => ['conversations', workspaceId] as const,
    messages: (conversationId: string) => ['messages', conversationId] as const,
    conversation: (conversationId: string) => ['conversation', conversationId] as const,
};

// Create query client with optimized caching settings
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            // Data is considered fresh for 5 minutes - no refetch during this time
            staleTime: 5 * 60 * 1000,
            // Keep cached data for 30 minutes even if component unmounts
            gcTime: 30 * 60 * 1000,
            // Show cached data while revalidating in background
            refetchOnWindowFocus: false,
            // Don't retry failed queries aggressively
            retry: 1,
        },
    },
});
