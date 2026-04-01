import { useState, useRef } from 'react';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  GitCompare, 
  Upload, 
  Link, 
  FileText, 
  Plus, 
  Minus, 
  Edit,
  Loader2,
  ChevronDown,
  ChevronUp,
  Download,
  X,
  Sparkles,
} from 'lucide-react';
import { api } from '@/lib/api';

interface DiffChange {
  type: 'added' | 'removed' | 'modified';
  category: 'text' | 'number' | 'date' | 'structural';
  content_a?: string;
  content_b?: string;
  confidence: number;
}

interface CompareResult {
  id: string;
  source_a: { title: string };
  source_b: { title: string };
  changes: DiffChange[];
  statistics: {
    added: number;
    removed: number;
    modified: number;
    total: number;
  };
  ai_summary?: string;
}

type SourceType = 'upload' | 'url';

export default function Compare() {
  const { t } = useI18n();
  const [sourceAType, setSourceAType] = useState<SourceType>('upload');
  const [sourceBType, setSourceBType] = useState<SourceType>('upload');
  const [sourceAFile, setSourceAFile] = useState<File | null>(null);
  const [sourceBFile, setSourceBFile] = useState<File | null>(null);
  const [sourceAUrl, setSourceAUrl] = useState('');
  const [sourceBUrl, setSourceBUrl] = useState('');
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showSummary, setShowSummary] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const fileInputARef = useRef<HTMLInputElement>(null);
  const fileInputBRef = useRef<HTMLInputElement>(null);

  const handleCompare = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const formData = new FormData();
      formData.append('workspace_id', 'default');
      formData.append('source_a_type', sourceAType);
      formData.append('source_b_type', sourceBType);
      formData.append('include_ai_summary', 'true');
      
      if (sourceAType === 'upload' && sourceAFile) {
        formData.append('source_a_file', sourceAFile);
      } else if (sourceAType === 'url' && sourceAUrl) {
        formData.append('source_a_url', sourceAUrl);
      }
      
      if (sourceBType === 'upload' && sourceBFile) {
        formData.append('source_b_file', sourceBFile);
      } else if (sourceBType === 'url' && sourceBUrl) {
        formData.append('source_b_url', sourceBUrl);
      }
      
      const response = await api.compareDocuments(formData);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.compare.error);
    } finally {
      setLoading(false);
    }
  };

  const canCompare = () => {
    const hasSourceA = (sourceAType === 'upload' && sourceAFile) || 
                       (sourceAType === 'url' && sourceAUrl.trim());
    const hasSourceB = (sourceBType === 'upload' && sourceBFile) || 
                       (sourceBType === 'url' && sourceBUrl.trim());
    return hasSourceA && hasSourceB && !loading;
  };

  const getChangeIcon = (type: string) => {
    switch (type) {
      case 'added': return <Plus className="h-4 w-4 text-green-500" />;
      case 'removed': return <Minus className="h-4 w-4 text-red-500" />;
      case 'modified': return <Edit className="h-4 w-4 text-yellow-500" />;
      default: return null;
    }
  };

  const getChangeColor = (type: string) => {
    switch (type) {
      case 'added': return 'bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800';
      case 'removed': return 'bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800';
      case 'modified': return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/30 dark:border-yellow-800';
      default: return '';
    }
  };

  const getCategoryBadge = (category: string) => {
    const colors: Record<string, string> = {
      text: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      number: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      date: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      structural: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    };
    return colors[category] || colors.text;
  };

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      text: t.compare.category.text,
      number: t.compare.category.number,
      date: t.compare.category.date,
      structural: t.compare.category.structural,
    };
    return labels[category] || category;
  };

  const clearSourceA = () => {
    setSourceAFile(null);
    setSourceAUrl('');
    if (fileInputARef.current) fileInputARef.current.value = '';
  };

  const clearSourceB = () => {
    setSourceBFile(null);
    setSourceBUrl('');
    if (fileInputBRef.current) fileInputBRef.current.value = '';
  };

  const exportToHtml = () => {
    if (!result) return;
    
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document Comparison Report</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
    h1 { color: #1a1a1a; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }
    .stat { text-align: center; padding: 16px; border-radius: 8px; }
    .stat-total { background: #f3f4f6; }
    .stat-added { background: #dcfce7; color: #16a34a; }
    .stat-removed { background: #fee2e2; color: #dc2626; }
    .stat-modified { background: #fef3c7; color: #ca8a04; }
    .stat-value { font-size: 2rem; font-weight: bold; }
    .summary { background: #f8fafc; padding: 16px; border-radius: 8px; margin: 20px 0; }
    .change { padding: 16px; border-radius: 8px; margin: 12px 0; border: 1px solid; }
    .change-added { background: #f0fdf4; border-color: #bbf7d0; }
    .change-removed { background: #fef2f2; border-color: #fecaca; }
    .change-modified { background: #fffbeb; border-color: #fde68a; }
    .change-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
    .badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    .diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .diff-content { background: white; padding: 12px; border-radius: 4px; border: 1px solid #e5e7eb; }
    pre { margin: 0; white-space: pre-wrap; font-family: monospace; font-size: 14px; }
    .empty { color: #9ca3af; font-style: italic; }
  </style>
</head>
<body>
  <h1>📊 Document Comparison Report</h1>
  <p><strong>Document A:</strong> ${result.source_a.title || 'Document A'}</p>
  <p><strong>Document B:</strong> ${result.source_b.title || 'Document B'}</p>
  <p><strong>Generated:</strong> ${new Date().toLocaleString()}</p>
  
  <div class="stats">
    <div class="stat stat-total">
      <div class="stat-value">${result.statistics.total}</div>
      <div>Total Changes</div>
    </div>
    <div class="stat stat-added">
      <div class="stat-value">${result.statistics.added}</div>
      <div>Added</div>
    </div>
    <div class="stat stat-removed">
      <div class="stat-value">${result.statistics.removed}</div>
      <div>Removed</div>
    </div>
    <div class="stat stat-modified">
      <div class="stat-value">${result.statistics.modified}</div>
      <div>Modified</div>
    </div>
  </div>
  
  ${result.ai_summary ? `
  <div class="summary">
    <h3>✨ AI Summary</h3>
    <p>${result.ai_summary}</p>
  </div>
  ` : ''}
  
  <h2>Changes</h2>
  ${result.changes.map((change, i) => `
  <div class="change change-${change.type}">
    <div class="change-header">
      <span>${change.type === 'added' ? '➕' : change.type === 'removed' ? '➖' : '✏️'}</span>
      <span class="badge">${change.category}</span>
      <span style="margin-left: auto; font-size: 12px; color: #6b7280;">
        Confidence: ${(change.confidence * 100).toFixed(0)}%
      </span>
    </div>
    <div class="diff-grid">
      <div class="diff-content">
        ${change.content_a ? `<pre>${change.content_a}</pre>` : '<span class="empty">(empty)</span>'}
      </div>
      <div class="diff-content">
        ${change.content_b ? `<pre>${change.content_b}</pre>` : '<span class="empty">(empty)</span>'}
      </div>
    </div>
  </div>
  `).join('')}
</body>
</html>`;
    
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `compare-report-${new Date().toISOString().slice(0, 10)}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };


  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <GitCompare className="h-8 w-8 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">{t.compare.title}</h1>
          <p className="text-muted-foreground">{t.compare.description}</p>
        </div>
      </div>

      {/* Source Selection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Source A */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t.compare.documentA}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={sourceAType} onValueChange={(v) => { setSourceAType(v as SourceType); clearSourceA(); }}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="upload" className="flex items-center gap-2">
                  <Upload className="h-4 w-4" />
                  {t.compare.upload}
                </TabsTrigger>
                <TabsTrigger value="url" className="flex items-center gap-2">
                  <Link className="h-4 w-4" />
                  {t.compare.url}
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="upload" className="mt-4">
                <div className="space-y-3">
                  <Label>{t.compare.selectFile}</Label>
                  <div className="flex gap-2">
                    <Input
                      ref={fileInputARef}
                      type="file"
                      accept=".txt,.md,.pdf,.docx,.doc"
                      onChange={(e) => setSourceAFile(e.target.files?.[0] || null)}
                      className="flex-1"
                    />
                    {sourceAFile && (
                      <Button variant="ghost" size="icon" onClick={clearSourceA}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                  {sourceAFile && (
                    <p className="text-sm text-muted-foreground">
                      {sourceAFile.name} ({(sourceAFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                </div>
              </TabsContent>
              
              <TabsContent value="url" className="mt-4">
                <div className="space-y-3">
                  <Label>{t.compare.enterUrl}</Label>
                  <div className="flex gap-2">
                    <Input
                      type="url"
                      placeholder="https://example.com/document.txt"
                      value={sourceAUrl}
                      onChange={(e) => setSourceAUrl(e.target.value)}
                      className="flex-1"
                    />
                    {sourceAUrl && (
                      <Button variant="ghost" size="icon" onClick={clearSourceA}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Source B */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t.compare.documentB}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={sourceBType} onValueChange={(v) => { setSourceBType(v as SourceType); clearSourceB(); }}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="upload" className="flex items-center gap-2">
                  <Upload className="h-4 w-4" />
                  {t.compare.upload}
                </TabsTrigger>
                <TabsTrigger value="url" className="flex items-center gap-2">
                  <Link className="h-4 w-4" />
                  {t.compare.url}
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="upload" className="mt-4">
                <div className="space-y-3">
                  <Label>{t.compare.selectFile}</Label>
                  <div className="flex gap-2">
                    <Input
                      ref={fileInputBRef}
                      type="file"
                      accept=".txt,.md,.pdf,.docx,.doc"
                      onChange={(e) => setSourceBFile(e.target.files?.[0] || null)}
                      className="flex-1"
                    />
                    {sourceBFile && (
                      <Button variant="ghost" size="icon" onClick={clearSourceB}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                  {sourceBFile && (
                    <p className="text-sm text-muted-foreground">
                      {sourceBFile.name} ({(sourceBFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                </div>
              </TabsContent>
              
              <TabsContent value="url" className="mt-4">
                <div className="space-y-3">
                  <Label>{t.compare.enterUrl}</Label>
                  <div className="flex gap-2">
                    <Input
                      type="url"
                      placeholder="https://example.com/document.txt"
                      value={sourceBUrl}
                      onChange={(e) => setSourceBUrl(e.target.value)}
                      className="flex-1"
                    />
                    {sourceBUrl && (
                      <Button variant="ghost" size="icon" onClick={clearSourceB}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {/* Compare Button */}
      <div className="flex justify-center">
        <Button 
          size="lg" 
          onClick={handleCompare} 
          disabled={!canCompare()}
          className="px-8"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              {t.compare.comparing}
            </>
          ) : (
            <>
              <GitCompare className="mr-2 h-5 w-5" />
              {t.compare.compareButton}
            </>
          )}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30">
          <CardContent className="pt-6">
            <p className="text-red-600 dark:text-red-400">{error}</p>
          </CardContent>
        </Card>
      )}


      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Statistics */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{t.compare.statistics}</span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={exportToHtml}>
                    <Download className="mr-2 h-4 w-4" />
                    {t.compare.exportHtml}
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 rounded-lg bg-muted">
                  <div className="text-3xl font-bold">{result.statistics.total}</div>
                  <div className="text-sm text-muted-foreground">{t.compare.totalChanges}</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-green-50 dark:bg-green-950/30">
                  <div className="text-3xl font-bold text-green-600">{result.statistics.added}</div>
                  <div className="text-sm text-green-600">{t.compare.added}</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-red-50 dark:bg-red-950/30">
                  <div className="text-3xl font-bold text-red-600">{result.statistics.removed}</div>
                  <div className="text-sm text-red-600">{t.compare.removed}</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-yellow-50 dark:bg-yellow-950/30">
                  <div className="text-3xl font-bold text-yellow-600">{result.statistics.modified}</div>
                  <div className="text-sm text-yellow-600">{t.compare.modified}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* AI Summary */}
          {result.ai_summary && (
            <Card>
              <CardHeader 
                className="cursor-pointer" 
                onClick={() => setShowSummary(!showSummary)}
              >
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-primary" />
                    {t.compare.aiSummary}
                  </span>
                  {showSummary ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                </CardTitle>
              </CardHeader>
              {showSummary && (
                <CardContent>
                  <p className="text-muted-foreground leading-relaxed">{result.ai_summary}</p>
                </CardContent>
              )}
            </Card>
          )}

          {/* Side-by-side Diff View */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitCompare className="h-5 w-5" />
                {t.compare.diffView}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="text-center font-medium p-2 bg-muted rounded">
                  {result.source_a.title || t.compare.documentA}
                </div>
                <div className="text-center font-medium p-2 bg-muted rounded">
                  {result.source_b.title || t.compare.documentB}
                </div>
              </div>
              
              <ScrollArea className="h-[500px]">
                <div className="space-y-3">
                  {result.changes.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      {t.compare.noChanges}
                    </div>
                  ) : (
                    result.changes.map((change, index) => (
                      <div 
                        key={index} 
                        className={`p-4 rounded-lg border ${getChangeColor(change.type)}`}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          {getChangeIcon(change.type)}
                          <Badge variant="outline" className={getCategoryBadge(change.category)}>
                            {getCategoryLabel(change.category)}
                          </Badge>
                          <span className="text-xs text-muted-foreground ml-auto">
                            {t.compare.confidence}: {(change.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="p-3 bg-background rounded border">
                            {change.content_a ? (
                              <pre className="text-sm whitespace-pre-wrap font-mono">
                                {change.content_a}
                              </pre>
                            ) : (
                              <span className="text-muted-foreground italic">
                                {t.compare.empty}
                              </span>
                            )}
                          </div>
                          <div className="p-3 bg-background rounded border">
                            {change.content_b ? (
                              <pre className="text-sm whitespace-pre-wrap font-mono">
                                {change.content_b}
                              </pre>
                            ) : (
                              <span className="text-muted-foreground italic">
                                {t.compare.empty}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
