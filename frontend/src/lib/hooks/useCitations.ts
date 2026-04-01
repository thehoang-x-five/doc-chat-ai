import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, type Citation } from '@/lib/api';

/**
 * Hook for lazy loading citations for a specific message.
 * Citations are only fetched when the user expands/clicks on a message.
 */
export function useCitations(messageId: string | null) {
    const queryClient = useQueryClient();

    const query = useQuery({
        queryKey: ['citations', messageId],
        queryFn: async (): Promise<Citation[]> => {
            if (!messageId) return [];
            return await apiClient.getMessageCitations(messageId);
        },
        enabled: !!messageId,
        // Cache citations for 30 minutes since they don't change
        staleTime: 30 * 60 * 1000,
        gcTime: 60 * 60 * 1000,
    });

    // Prefetch citations for a message (e.g., on hover)
    const prefetch = (msgId: string) => {
        queryClient.prefetchQuery({
            queryKey: ['citations', msgId],
            queryFn: () => apiClient.getMessageCitations(msgId),
            staleTime: 30 * 60 * 1000,
        });
    };

    return {
        citations: query.data || [],
        isLoading: query.isLoading,
        isFetching: query.isFetching,
        error: query.error,
        refetch: query.refetch,
        prefetch,
    };
}
