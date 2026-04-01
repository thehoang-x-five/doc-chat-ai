import React, { useState, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../lib/api';
import { useI18n } from '../../lib/i18n';
import { Search, Clock, FileText, ChevronDown, ChevronUp, ExternalLink, Calendar } from 'lucide-react';
import { format } from 'date-fns';

// Debounce utility
function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return debouncedValue;
}

interface SearchResult {
    id: string;
    document_id: string;
    document_title: string;
    snippet: string;
    score?: number;
    rerank_score?: number;
    page_start?: number;
    created_at: string;
}

interface TimelineItem {
    chunk_id: string;
    document_title: string;
    snippet: string;
    page_start?: number;
    created_at: string;
    is_anchor: boolean;
}

interface ChunkDetail {
    id: string;
    document_id: string;
    document_title: string;
    content: string;
    page_start?: number;
    page_end?: number;
    section_title?: string;
    created_at: string;
}

interface ProgressiveSearchUIProps {
    workspaceId: string;
    onClose?: () => void;
}

export const ProgressiveSearchUI: React.FC<ProgressiveSearchUIProps> = ({ workspaceId, onClose }) => {
    const { t } = useI18n();
    const [query, setQuery] = useState('');
    const [activeSearch, setActiveSearch] = useState('');
    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
    const [timelineAnchor, setTimelineAnchor] = useState<string | null>(null);
    const [viewingDetails, setViewingDetails] = useState<string | null>(null);

    // Debounce search query - only search after 300ms of no typing
    const debouncedQuery = useDebounce(query, 300);

    // Update activeSearch when debounced query changes
    useEffect(() => {
        if (debouncedQuery && debouncedQuery.trim().length > 1) {
            setActiveSearch(debouncedQuery.trim());
        } else {
            setActiveSearch('');
        }
    }, [debouncedQuery]);

    // Layer 1: Search Index
    const { data: searchResults, isLoading: isSearching, error: searchError } = useQuery({
        queryKey: ['search', 'index', activeSearch, workspaceId],
        queryFn: () => apiClient.searchIndex({ query: activeSearch, workspaceId }),
        enabled: !!activeSearch && activeSearch.length > 1,
        retry: 1, // Only retry once on failure
        staleTime: 60000, // Cache for 1 minute
    });

    // Layer 2: Timeline
    const { data: timelineData, isLoading: isLoadingTimeline } = useQuery({
        queryKey: ['search', 'timeline', timelineAnchor],
        queryFn: () => apiClient.getTimeline({ anchorId: timelineAnchor! }),
        enabled: !!timelineAnchor,
    });

    // Layer 3: Details
    const { data: detailData, isLoading: isLoadingDetails } = useQuery({
        queryKey: ['search', 'details', viewingDetails],
        queryFn: async () => {
            const details = await apiClient.getChunkDetails([viewingDetails!]);
            return details[0];
        },
        enabled: !!viewingDetails,
    });

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        // No need to manually trigger - debounce handles it
    };

    const toggleExpand = (id: string) => {
        const newExpanded = new Set(expandedIds);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedIds(newExpanded);
    };

    return (
        <div className="flex flex-col h-full bg-background border-r">
            {/* Header & Search */}
            <div className="p-3 border-b sticky top-0 bg-background/95 backdrop-blur z-10">
                <h2 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <Search className="w-4 h-4 text-primary" />
                    {t.search?.title || 'Progressive Search'}
                </h2>
                <form onSubmit={handleSearch} className="relative">
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder={t.search?.placeholder || 'Search documents...'}
                        className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border bg-muted/50 focus:bg-background focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                        minLength={2}
                        maxLength={200}
                    />
                    <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-muted-foreground" />
                    {isSearching && (
                        <div className="absolute right-2.5 top-2">
                            <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-primary"></div>
                        </div>
                    )}
                </form>
                {query.length > 0 && query.length < 2 && (
                    <p className="text-[10px] text-muted-foreground mt-1">
                        Type at least 2 characters to search
                    </p>
                )}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-2 pr-1.5 space-y-2 chat-scrollbar">
                {searchError ? (
                    <div className="text-center py-8 text-xs text-red-500">
                        <p>Search failed. Please try again.</p>
                    </div>
                ) : isSearching ? (
                    <div className="flex justify-center py-8">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                    </div>
                ) : searchResults?.length === 0 ? (
                    <div className="text-center py-8 text-xs text-muted-foreground">
                        {t.search?.noResults || 'No results found'}
                    </div>
                ) : (
                    <div className="space-y-2">
                        {searchResults?.map((result) => (
                            <div
                                key={result.id}
                                className="group border rounded-lg overflow-hidden bg-card hover:shadow-sm transition-all duration-200"
                            >
                                {/* Result Card Header (Layer 1) */}
                                <div className="p-2.5 cursor-pointer" onClick={() => toggleExpand(result.id)}>
                                    <div className="flex justify-between items-start mb-1">
                                        <h3 className="text-xs font-semibold text-primary group-hover:text-primary/80 transition-colors line-clamp-1" title={result.document_title}>
                                            {result.document_title}
                                        </h3>
                                        {result.score && (
                                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${(result.rerank_score || result.score) > 0.7
                                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                                : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                                                }`}>
                                                {Math.round((result.rerank_score || result.score) * 100)}% {t.search?.match || 'Match'}
                                            </span>
                                        )}
                                    </div>

                                    <p className="text-[11px] text-muted-foreground line-clamp-2 mb-2 leading-tight">
                                        {result.snippet}
                                    </p>

                                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                                        {result.page_start && (
                                            <span className="flex items-center gap-1">
                                                <FileText className="w-2.5 h-2.5" /> {t.search?.page || 'Pg'} {result.page_start}
                                            </span>
                                        )}
                                        <span className="flex items-center gap-1">
                                            <Calendar className="w-2.5 h-2.5" />
                                            {format(new Date(), 'MMM d')}
                                        </span>
                                    </div>
                                </div>

                                {/* Expanded Actions (Progressive Disclosure) */}
                                {expandedIds.has(result.id) && (
                                    <div className="px-2 pb-2 pt-1 bg-muted/30 border-t flex gap-1.5 animate-in slide-in-from-top-1 duration-200">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setViewingDetails(result.id);
                                            }}
                                            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-[10px] font-medium rounded bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
                                        >
                                            <FileText className="w-3 h-3" />
                                            {t.search?.read || 'Read'}
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setTimelineAnchor(timelineAnchor === result.id ? null : result.id);
                                            }}
                                            className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-[10px] font-medium rounded border transition-colors ${timelineAnchor === result.id
                                                ? 'bg-secondary text-secondary-foreground border-primary/50'
                                                : 'bg-background hover:bg-muted'
                                                }`}
                                        >
                                            <Clock className="w-3 h-3" />
                                            {t.search?.context || 'Context'}
                                        </button>
                                    </div>
                                )}

                                {/* Layer 2: Timeline Visualization */}
                                {timelineAnchor === result.id && (
                                    <div className="border-t bg-muted/10 p-2 animate-in fade-in duration-300">
                                        <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            {t.search?.timeline || 'Timeline'}
                                        </h4>
                                        {isLoadingTimeline ? (
                                            <div className="flex justify-center py-2">
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                                            </div>
                                        ) : (
                                            <div className="relative pl-3 space-y-4 before:absolute before:left-[14px] before:top-1.5 before:bottom-1.5 before:w-px before:bg-border">
                                                {timelineData?.map((item) => (
                                                    <div key={item.chunk_id} className={`relative pl-6 ${item.is_anchor ? 'opacity-100' : 'opacity-70 group-hover/timeline:opacity-100'}`}>
                                                        {/* Timeline Node */}
                                                        <div className={`absolute left-0 top-1 w-2 h-2 rounded-full border bg-background z-10 ${item.is_anchor ? 'border-primary bg-primary' : 'border-muted-foreground'
                                                            }`} />

                                                        <div className={`text-[11px] leading-tight ${item.is_anchor ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                                                            {item.snippet}
                                                        </div>
                                                        <div className="text-[9px] text-muted-foreground mt-0.5">
                                                            {t.search?.page || 'Pg'} {item.page_start}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Layer 3: Full Details Modal/Inline */}
                                {viewingDetails === result.id && (
                                    <div className="border-t bg-background p-3 animate-in zoom-in-95 duration-200">
                                        <div className="flex justify-between items-start mb-2">
                                            <h4 className="font-semibold text-xs line-clamp-1" title={result.document_title}>{result.document_title}</h4>
                                            <button
                                                onClick={() => setViewingDetails(null)}
                                                className="p-0.5 hover:bg-muted rounded-full"
                                            >
                                                <ChevronUp className="w-4 h-4" />
                                            </button>
                                        </div>

                                        {isLoadingDetails ? (
                                            <div className="space-y-1.5 animate-pulse">
                                                <div className="h-3 bg-muted rounded w-3/4"></div>
                                                <div className="h-3 bg-muted rounded w-full"></div>
                                                <div className="h-3 bg-muted rounded w-5/6"></div>
                                            </div>
                                        ) : (
                                            <div className="prose dark:prose-invert max-w-none">
                                                <div className="whitespace-pre-wrap font-serif text-[11px] leading-relaxed text-foreground/90 max-h-[300px] overflow-y-auto pr-1 chat-scrollbar">
                                                    {detailData?.content}
                                                </div>
                                                <div className="mt-3 pt-2 border-t flex justify-between text-[10px] text-muted-foreground">
                                                    <span>{t.search?.page || 'Pg'} {detailData?.page_start}-{detailData?.page_end}</span>
                                                    <span className="flex items-center gap-1 text-primary hover:underline cursor-pointer">
                                                        {t.search?.pdf || 'PDF'} <ExternalLink className="w-2.5 h-2.5" />
                                                    </span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
