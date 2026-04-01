import { useState, useEffect } from 'react';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { 
  FileText, Loader2, Copy, Download, RefreshCw, Sparkles,
  Users, Code, Scale, Globe, List, Table, Clock, CheckSquare,
  AlignLeft, BookOpen, X, Plus
} from 'lucide-react';
import {
  createSummary,
  getSummaries,
  deleteSummary,
  type SummaryResult,
  type SummaryAudience,
  type SummaryFormat,
  type SummarizeRequest,
} from '@/lib/api';
import { apiClient } from '@/lib/api';

const AUDIENCES: { value: SummaryAudience; label: string; icon: React.ReactNode; description: string }[] = [
  { value: 'executive', label: 'Executive', icon: <Users className="h-4 w-4" />, description: 'Key decisions, metrics, action items' },
  { value: 'technical', label: 'Technical', icon: <Code className="h-4 w-4" />, description: 'Specs, implementation, architecture' },
  { value: 'legal', label: 'Legal', icon: <Scale className="h-4 w-4" />, description: 'Obligations, risks, compliance' },
  { value: 'general', label: 'General', icon: <Globe className="h-4 w-4" />, description: 'Balanced overview for all' },
];

const FORMATS: { value: SummaryFormat; label: string; icon: React.ReactNode }[] = [
  { value: 'paragraph', label: 'Paragraph', icon: <AlignLeft className="h-4 w-4" /> },
  { value: 'bullet', label: 'Bullet Points', icon: <List className="h-4 w-4" /> },
  { value: 'table', label: 'Table', icon: <Table className="h-4 w-4" /> },
  { value: 'timeline', label: 'Timeline', icon: <Clock className="h-4 w-4" /> },
  { value: 'checklist', label: 'Checklist', icon: <CheckSquare className="h-4 w-4" /> },
];

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'vi', label: 'Tiếng Việt' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' },
];

// Summary Options Panel Component
function SummaryOptionsPanel({
  onGenerate,
  loading,
  selectedDocuments,
}: {
  onGenerate: (request: SummarizeRequest) => void;
  loading: boolean;
  selectedDocuments: string[];
}) {
  const { t } = useI18n();
  const [audience, setAudience] = useState<SummaryAudience>('general');
  const [format, setFormat] = useState<SummaryFormat>('paragraph');
  const [maxLength, setMaxLength] = useState(500);
  const [language, setLanguage] = useState('en');
  const [includeCitations, setIncludeCitations] = useState(true);
  const [focusTopics, setFocusTopics] = useState<string[]>([]);
  const [newTopic, setNewTopic] = useState('');

  const addTopic = () => {
    if (newTopic.trim() && !focusTopics.includes(newTopic.trim())) {
      setFocusTopics([...focusTopics, newTopic.trim()]);
      setNewTopic('');
    }
  };

  const removeTopic = (topic: string) => {
    setFocusTopics(focusTopics.filter(t => t !== topic));
  };

  const handleGenerate = () => {
    onGenerate({
      document_ids: selectedDocuments,
      audience,
      format,
      max_length: maxLength,
      language,
      include_citations: includeCitations,
      focus_topics: focusTopics.length > 0 ? focusTopics : undefined,
    });
  };

  return (
    <div className="space-y-6">
      {/* Audience Selection */}
      <div className="space-y-3">
        <Label className="text-base font-medium">{t.summarize.audience}</Label>
        <div className="grid grid-cols-2 gap-2">
          {AUDIENCES.map((aud) => (
            <Card
              key={aud.value}
              className={`cursor-pointer transition-all ${
                audience === aud.value
                  ? 'border-primary bg-primary/5'
                  : 'hover:border-muted-foreground/50'
              }`}
              onClick={() => setAudience(aud.value)}
            >
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  {aud.icon}
                  <span className="font-medium">{aud.label}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{aud.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Format Selection */}
      <div className="space-y-3">
        <Label className="text-base font-medium">{t.summarize.format}</Label>
        <div className="flex flex-wrap gap-2">
          {FORMATS.map((fmt) => (
            <Button
              key={fmt.value}
              variant={format === fmt.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFormat(fmt.value)}
              className="gap-1"
            >
              {fmt.icon}
              {fmt.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Max Length */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium">{t.summarize.maxLength}</Label>
          <span className="text-sm text-muted-foreground">{maxLength} {t.summarize.words}</span>
        </div>
        <Slider
          value={[maxLength]}
          onValueChange={([value]) => setMaxLength(value)}
          min={100}
          max={2000}
          step={50}
        />
      </div>

      {/* Language */}
      <div className="space-y-2">
        <Label className="text-base font-medium">{t.summarize.language}</Label>
        <Select value={language} onValueChange={setLanguage}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LANGUAGES.map((lang) => (
              <SelectItem key={lang.value} value={lang.value}>
                {lang.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Focus Topics */}
      <div className="space-y-2">
        <Label className="text-base font-medium">{t.summarize.focusTopics}</Label>
        <div className="flex gap-2">
          <Input
            value={newTopic}
            onChange={(e) => setNewTopic(e.target.value)}
            placeholder={t.summarize.addTopic}
            onKeyDown={(e) => e.key === 'Enter' && addTopic()}
          />
          <Button variant="outline" size="icon" onClick={addTopic}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {focusTopics.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {focusTopics.map((topic) => (
              <Badge key={topic} variant="secondary" className="gap-1">
                {topic}
                <X className="h-3 w-3 cursor-pointer" onClick={() => removeTopic(topic)} />
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Include Citations */}
      <div className="flex items-center justify-between">
        <Label>{t.summarize.includeCitations}</Label>
        <Switch checked={includeCitations} onCheckedChange={setIncludeCitations} />
      </div>

      {/* Generate Button */}
      <Button
        className="w-full"
        size="lg"
        disabled={loading || selectedDocuments.length === 0}
        onClick={handleGenerate}
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            {t.summarize.generating}
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4 mr-2" />
            {t.summarize.generate} ({selectedDocuments.length})
          </>
        )}
      </Button>
    </div>
  );
}


// Summary Result View Component
function SummaryResultView({
  result,
  onClose,
  onRegenerate,
}: {
  result: SummaryResult;
  onClose: () => void;
  onRegenerate: () => void;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = () => {
    const blob = new Blob([result.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `summary_${result.id.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const audienceLabel = AUDIENCES.find(a => a.value === result.audience)?.label || result.audience;
  const formatLabel = FORMATS.find(f => f.value === result.format)?.label || result.format;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{audienceLabel}</Badge>
            <Badge variant="secondary">{formatLabel}</Badge>
            <Badge variant="secondary">{result.word_count} {t.summarize.words}</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {result.document_titles.join(', ')}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleCopy}>
            <Copy className="h-4 w-4 mr-1" />
            {copied ? t.common.copied : t.common.copy}
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-1" />
            {t.common.export}
          </Button>
          <Button variant="outline" size="sm" onClick={onRegenerate}>
            <RefreshCw className="h-4 w-4 mr-1" />
            {t.summarize.regenerate}
          </Button>
        </div>
      </div>

      {/* Summary Content */}
      <Card>
        <CardContent className="p-4">
          <ScrollArea className="h-[400px]">
            <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
              {result.content}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Citations */}
      {result.citations.length > 0 && (
        <div className="space-y-2">
          <Label className="text-base font-medium">{t.summarize.citations}</Label>
          <ScrollArea className="h-[200px]">
            <div className="space-y-2">
              {result.citations.map((citation, index) => (
                <Card key={index} className="p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          [{index + 1}]
                        </Badge>
                        <span className="font-medium text-sm">
                          {citation.document_title || citation.document_id}
                        </span>
                        {citation.page_number && (
                          <span className="text-xs text-muted-foreground">
                            p.{citation.page_number}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        "{citation.text_excerpt}"
                      </p>
                    </div>
                    <Badge
                      variant={citation.relevance_score >= 0.7 ? 'default' : 'secondary'}
                      className="text-xs"
                    >
                      {Math.round(citation.relevance_score * 100)}%
                    </Badge>
                  </div>
                </Card>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

      <div className="flex justify-end">
        <Button variant="outline" onClick={onClose}>
          {t.common.close}
        </Button>
      </div>
    </div>
  );
}


// Main Summarize Page Component
export default function Summarize() {
  const { t } = useI18n();
  const [summaries, setSummaries] = useState<SummaryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [selectedResult, setSelectedResult] = useState<SummaryResult | null>(null);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [documents, setDocuments] = useState<{ id: string; title: string }[]>([]);

  useEffect(() => {
    loadSummaries();
    loadDocuments();
  }, []);

  const loadSummaries = async () => {
    try {
      setLoading(true);
      const workspaceId = localStorage.getItem('currentWorkspaceId') || 'default';
      const data = await getSummaries(workspaceId);
      setSummaries(data.summaries);
    } catch (error) {
      console.error('Failed to load summaries:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadDocuments = async () => {
    try {
      const workspaceId = localStorage.getItem('currentWorkspaceId') || 'default';
      const data = await apiClient.getDocuments(workspaceId);
      setDocuments(data.map((d: any) => ({ id: d.id, title: d.title || d.name })));
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  const handleGenerate = async (request: SummarizeRequest) => {
    try {
      setGenerating(true);
      const workspaceId = localStorage.getItem('currentWorkspaceId') || 'default';
      const result = await createSummary(workspaceId, request);
      setSelectedResult(result);
      await loadSummaries();
    } catch (error) {
      console.error('Failed to generate summary:', error);
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (summaryId: string) => {
    if (!confirm(t.summarize.confirmDelete)) return;
    try {
      const workspaceId = localStorage.getItem('currentWorkspaceId') || 'default';
      await deleteSummary(summaryId, workspaceId);
      await loadSummaries();
    } catch (error) {
      console.error('Failed to delete summary:', error);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.summarize.title}</h1>
          <p className="text-muted-foreground">{t.summarize.subtitle}</p>
        </div>
      </div>

      <Tabs defaultValue="generate" className="space-y-4">
        <TabsList>
          <TabsTrigger value="generate">{t.summarize.generate}</TabsTrigger>
          <TabsTrigger value="history">{t.summarize.history}</TabsTrigger>
        </TabsList>

        <TabsContent value="generate" className="space-y-4">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Document Selection */}
            <Card>
              <CardHeader>
                <CardTitle>{t.summarize.selectDocuments}</CardTitle>
                <CardDescription>{t.summarize.selectDocumentsDesc}</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        className={`p-3 rounded cursor-pointer flex items-center gap-2 ${
                          selectedDocuments.includes(doc.id)
                            ? 'bg-primary/10 border border-primary'
                            : 'bg-muted hover:bg-muted/80'
                        }`}
                        onClick={() => {
                          setSelectedDocuments((prev) =>
                            prev.includes(doc.id)
                              ? prev.filter((id) => id !== doc.id)
                              : [...prev, doc.id]
                          );
                        }}
                      >
                        <FileText className="h-4 w-4" />
                        <span className="text-sm flex-1">{doc.title}</span>
                        {selectedDocuments.includes(doc.id) && (
                          <Badge variant="default" className="text-xs">
                            {t.common.selected}
                          </Badge>
                        )}
                      </div>
                    ))}
                    {documents.length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-8">
                        {t.summarize.noDocuments}
                      </p>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Summary Options */}
            <Card>
              <CardHeader>
                <CardTitle>{t.summarize.options}</CardTitle>
                <CardDescription>{t.summarize.optionsDesc}</CardDescription>
              </CardHeader>
              <CardContent>
                <SummaryOptionsPanel
                  onGenerate={handleGenerate}
                  loading={generating}
                  selectedDocuments={selectedDocuments}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : summaries.length === 0 ? (
            <Card className="p-8 text-center">
              <BookOpen className="h-12 w-12 mx-auto text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">{t.summarize.noSummaries}</h3>
              <p className="text-muted-foreground">{t.summarize.noSummariesDesc}</p>
            </Card>
          ) : (
            <div className="space-y-2">
              {summaries.map((summary) => (
                <Card
                  key={summary.id}
                  className="p-4 cursor-pointer hover:bg-muted/50"
                  onClick={() => setSelectedResult(summary)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">
                          {AUDIENCES.find(a => a.value === summary.audience)?.label}
                        </Badge>
                        <Badge variant="secondary">
                          {FORMATS.find(f => f.value === summary.format)?.label}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {summary.word_count} {t.summarize.words}
                        </span>
                      </div>
                      <p className="text-sm mt-1 line-clamp-1">
                        {summary.document_titles.join(', ')}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(summary.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(summary.id);
                      }}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Result Dialog */}
      <Dialog open={!!selectedResult} onOpenChange={() => setSelectedResult(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t.summarize.summaryResult}</DialogTitle>
          </DialogHeader>
          {selectedResult && (
            <SummaryResultView
              result={selectedResult}
              onClose={() => setSelectedResult(null)}
              onRegenerate={() => {
                if (selectedResult) {
                  handleGenerate({
                    document_ids: selectedResult.document_ids,
                    audience: selectedResult.audience,
                    format: selectedResult.format,
                    language: selectedResult.language,
                    include_citations: selectedResult.citations.length > 0,
                    focus_topics: selectedResult.focus_topics,
                  });
                }
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
