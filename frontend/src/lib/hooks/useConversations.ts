import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { QUERY_KEYS } from '../queryClient';
import { apiClient } from '@/lib/api';

export interface Conversation {
    id: string;
    workspaceId: string;
    title: string;
    createdAt: string;
    updatedAt: string;
    messageCount: number;
}

/**
 * Hook for fetching and caching conversations list.
 * Data is cached and shown instantly when switching workspaces.
 */
export function useConversations(workspaceId: string | null) {
    const queryClient = useQueryClient();

    const query = useQuery({
        queryKey: QUERY_KEYS.conversations(workspaceId || ''),
        queryFn: async () => {
            if (!workspaceId) return [];
            return await apiClient.getConversations(workspaceId);
        },
        enabled: !!workspaceId,
        // Keep previous data visible while fetching new workspace's conversations
        placeholderData: (prev) => prev,
    });

    const createMutation = useMutation({
        mutationFn: async ({ title }: { title?: string }) => {
            if (!workspaceId) throw new Error('No workspace selected');
            return await apiClient.createConversation(workspaceId, title || 'New Chat');
        },
        onSuccess: (newConv) => {
            // Add new conversation to cache optimistically
            queryClient.setQueryData(
                QUERY_KEYS.conversations(workspaceId || ''),
                (old: Conversation[] | undefined) => old ? [newConv, ...old] : [newConv]
            );
        },
    });

    const deleteMutation = useMutation({
        mutationFn: async (conversationId: string) => {
            await apiClient.deleteConversation(conversationId);
            return conversationId;
        },
        onSuccess: (deletedId) => {
            // Remove from cache immediately
            queryClient.setQueryData(
                QUERY_KEYS.conversations(workspaceId || ''),
                (old: Conversation[] | undefined) => old?.filter(c => c.id !== deletedId) || []
            );
        },
    });

    return {
        conversations: query.data || [],
        isLoading: query.isLoading,
        error: query.error,
        refetch: query.refetch,
        createConversation: createMutation.mutate,
        isCreating: createMutation.isPending,
        deleteConversation: deleteMutation.mutate,
        isDeleting: deleteMutation.isPending,
    };
}
