
import React from 'react';
import { cn } from '@/lib/utils';
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Info } from 'lucide-react';

interface TokenUsageDisplayProps {
    tokenUsage?: {
        prompt: number;
        completion: number;
    };
    contextStats?: {
        memory_tokens: number;
        chunk_tokens: number;
        total_tokens: number;
    };
    className?: string;
    maxContext?: number;
}

export const TokenUsageDisplay: React.FC<TokenUsageDisplayProps> = ({
    tokenUsage,
    contextStats,
    className,
    maxContext = 4096 // Default max context if not provided
}) => {
    if (!tokenUsage && !contextStats) return null;

    const promptTokens = tokenUsage?.prompt || 0;
    const completionTokens = tokenUsage?.completion || 0;
    const totalTokens = promptTokens + completionTokens;

    // Context breakdown
    const memoryTokens = contextStats?.memory_tokens || 0;
    const chunkTokens = contextStats?.chunk_tokens || 0;
    // History is prompt tokens minus memory and chunks (approximate)
    const historyTokens = Math.max(0, promptTokens - memoryTokens - chunkTokens);

    // Percentages for visualization
    const usedPercentage = Math.min(100, (totalTokens / maxContext) * 100);

    // Breakdown percentages within the used portion
    const memoryPct = totalTokens > 0 ? (memoryTokens / totalTokens) * 100 : 0;
    const chunkPct = totalTokens > 0 ? (chunkTokens / totalTokens) * 100 : 0;
    const historyPct = totalTokens > 0 ? (historyTokens / totalTokens) * 100 : 0;
    const outputPct = totalTokens > 0 ? (completionTokens / totalTokens) * 100 : 0;

    return (
        <div className={cn("text-xs w-full max-w-[200px] space-y-1.5", className)}>
            <div className="flex items-center justify-between text-muted-foreground">
                <span className="flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    <span>Used: {totalTokens.toLocaleString()} / {maxContext.toLocaleString()}</span>
                </span>
                <span className="font-mono">{usedPercentage.toFixed(1)}%</span>
            </div>

            {/* Context Budget Visualization (Segmented Bar) */}
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div className="h-2 w-full bg-secondary rounded-full overflow-hidden flex cursor-help">
                            {/* Memory (Purple) */}
                            {memoryTokens > 0 && (
                                <div
                                    className="bg-purple-500 h-full transition-all duration-500"
                                    style={{ width: `${(memoryTokens / maxContext) * 100}%` }}
                                />
                            )}
                            {/* Chunks (Blue) */}
                            {chunkTokens > 0 && (
                                <div
                                    className="bg-blue-500 h-full transition-all duration-500"
                                    style={{ width: `${(chunkTokens / maxContext) * 100}%` }}
                                />
                            )}
                            {/* History (Gray) */}
                            {historyTokens > 0 && (
                                <div
                                    className="bg-gray-400 h-full transition-all duration-500"
                                    style={{ width: `${(historyTokens / maxContext) * 100}%` }}
                                />
                            )}
                            {/* Output (Green) */}
                            {completionTokens > 0 && (
                                <div
                                    className="bg-green-500 h-full transition-all duration-500"
                                    style={{ width: `${(completionTokens / maxContext) * 100}%` }}
                                />
                            )}
                        </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="w-64 p-3 space-y-2">
                        <div className="font-semibold border-b pb-1 mb-1">Token Breakdown</div>
                        <div className="space-y-1 text-xs">
                            <div className="flex justify-between items-center text-purple-200">
                                <span className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded bg-purple-500" />
                                    Memory
                                </span>
                                <span>{memoryTokens} ({memoryPct.toFixed(1)}%)</span>
                            </div>
                            <div className="flex justify-between items-center text-blue-200">
                                <span className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded bg-blue-500" />
                                    Documents
                                </span>
                                <span>{chunkTokens} ({chunkPct.toFixed(1)}%)</span>
                            </div>
                            <div className="flex justify-between items-center text-gray-200">
                                <span className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded bg-gray-400" />
                                    History/Prompt
                                </span>
                                <span>{historyTokens} ({historyPct.toFixed(1)}%)</span>
                            </div>
                            <div className="flex justify-between items-center text-green-200">
                                <span className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded bg-green-500" />
                                    Output
                                </span>
                                <span>{completionTokens} ({outputPct.toFixed(1)}%)</span>
                            </div>
                            <div className="border-t pt-1 mt-1 flex justify-between font-semibold">
                                <span>Total</span>
                                <span>{totalTokens}</span>
                            </div>
                        </div>
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
        </div>
    );
};
