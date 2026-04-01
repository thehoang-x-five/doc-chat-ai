/**
 * Inline Fact Display - Show recalled facts within chat messages
 */
import { Brain, TrendingUp } from 'lucide-react';
import type { MemoriFact } from '@/types/memori';

interface InlineFactDisplayProps {
  facts: MemoriFact[];
  className?: string;
}

export function InlineFactDisplay({ facts, className = '' }: InlineFactDisplayProps) {
  if (facts.length === 0) return null;

  return (
    <div className={`mt-3 space-y-2 ${className}`}>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Brain className="w-3.5 h-3.5" />
        <span className="font-medium">Recalled from memory:</span>
      </div>

      <div className="space-y-1.5">
        {facts.map((fact) => (
          <div
            key={fact.id}
            className="bg-purple-50 border border-purple-100 rounded-lg p-2.5 text-sm"
          >
            <div className="flex items-start gap-2">
              <div className="flex-1">
                <p className="text-gray-700">{fact.content}</p>
              </div>
              <div className="flex items-center gap-1 text-xs text-purple-600">
                <TrendingUp className="w-3 h-3" />
                <span>{(fact.similarity * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
