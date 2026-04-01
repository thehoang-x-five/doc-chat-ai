import { useState, useEffect } from 'react';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Plus, Trash2, Save, Play, FileText, Download, AlertCircle, 
  CheckCircle, XCircle, Edit, FileSpreadsheet, Loader2
} from 'lucide-react';
import {
  getExtractionTemplates,
  createExtractionTemplate,
  updateExtractionTemplate,
  deleteExtractionTemplate,
  extractData,
  batchExtractData,
  getExtractionResults,
  exportExtractionResults,
  type ExtractionTemplate,
  type TemplateField,
  type ExtractionResult,
  type FieldType,
  type ExportFormat,
} from '@/lib/api';
import { apiClient } from '@/lib/api';

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'date', label: 'Date' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'currency', label: 'Currency' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'url', label: 'URL' },
  { value: 'list', label: 'List' },
];


// Template Builder Component
function TemplateBuilder({
  template,
  onSave,
  onCancel,
}: {
  template?: ExtractionTemplate;
  onSave: (data: { name: string; description?: string; fields: TemplateField[] }) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(template?.name || '');
  const [description, setDescription] = useState(template?.description || '');
  const [fields, setFields] = useState<TemplateField[]>(template?.fields || []);

  const addField = () => {
    setFields([
      ...fields,
      {
        name: `field_${fields.length + 1}`,
        type: 'text',
        description: '',
        required: false,
        validation_rules: [],
        examples: [],
      },
    ]);
  };

  const updateField = (index: number, updates: Partial<TemplateField>) => {
    const newFields = [...fields];
    newFields[index] = { ...newFields[index], ...updates };
    setFields(newFields);
  };

  const removeField = (index: number) => {
    setFields(fields.filter((_, i) => i !== index));
  };

  const handleSave = () => {
    if (!name.trim() || fields.length === 0) return;
    onSave({ name, description, fields });
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4">
        <div className="space-y-2">
          <Label>{t.extraction.templateName}</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t.extraction.templateNamePlaceholder}
          />
        </div>
        <div className="space-y-2">
          <Label>{t.extraction.description}</Label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t.extraction.descriptionPlaceholder}
            rows={2}
          />
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-lg">{t.extraction.fields}</Label>
          <Button onClick={addField} size="sm" variant="outline">
            <Plus className="h-4 w-4 mr-1" />
            {t.extraction.addField}
          </Button>
        </div>

        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {fields.map((field, index) => (
              <Card key={index} className="p-4">
                <div className="grid gap-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t.extraction.fieldName}</Label>
                        <Input
                          value={field.name}
                          onChange={(e) => updateField(index, { name: e.target.value })}
                          placeholder="field_name"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t.extraction.fieldType}</Label>
                        <Select
                          value={field.type}
                          onValueChange={(value) => updateField(index, { type: value as FieldType })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {FIELD_TYPES.map((type) => (
                              <SelectItem key={type.value} value={type.value}>
                                {type.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive"
                      onClick={() => removeField(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <Label>{t.extraction.fieldDescription}</Label>
                    <Input
                      value={field.description || ''}
                      onChange={(e) => updateField(index, { description: e.target.value })}
                      placeholder={t.extraction.fieldDescriptionPlaceholder}
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={field.required}
                      onCheckedChange={(checked) => updateField(index, { required: checked })}
                    />
                    <Label>{t.extraction.required}</Label>
                  </div>
                  <div className="space-y-2">
                    <Label>{t.extraction.examples}</Label>
                    <Input
                      value={field.examples.join(', ')}
                      onChange={(e) =>
                        updateField(index, {
                          examples: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                        })
                      }
                      placeholder={t.extraction.examplesPlaceholder}
                    />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          {t.common.cancel}
        </Button>
        <Button onClick={handleSave} disabled={!name.trim() || fields.length === 0}>
          <Save className="h-4 w-4 mr-1" />
          {t.common.save}
        </Button>
      </div>
    </div>
  );
}


// Extraction Results View Component
function ResultsView({
  result,
  onClose,
}: {
  result: ExtractionResult;
  onClose: () => void;
}) {
  const { t } = useI18n();

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{result.document_title || result.document_id}</h3>
          <p className="text-sm text-muted-foreground">
            {t.extraction.template}: {result.template_name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={result.overall_confidence >= 0.7 ? 'default' : 'destructive'}>
            {Math.round(result.overall_confidence * 100)}% {t.extraction.confidence}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 text-center">
        <Card className="p-4">
          <div className="text-2xl font-bold text-green-600">{result.fields_extracted}</div>
          <div className="text-sm text-muted-foreground">{t.extraction.extracted}</div>
        </Card>
        <Card className="p-4">
          <div className="text-2xl font-bold text-red-600">{result.fields_failed}</div>
          <div className="text-sm text-muted-foreground">{t.extraction.failed}</div>
        </Card>
        <Card className="p-4">
          <div className="text-2xl font-bold text-yellow-600">{result.fields_need_review}</div>
          <div className="text-sm text-muted-foreground">{t.extraction.needsReview}</div>
        </Card>
      </div>

      <ScrollArea className="h-[400px]">
        <div className="space-y-3">
          {result.fields.map((field, index) => (
            <Card key={index} className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{field.field_name}</span>
                    <Badge variant="outline" className="text-xs">
                      {field.field_type}
                    </Badge>
                    {field.needs_review && (
                      <Badge variant="destructive" className="text-xs">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        {t.extraction.review}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-2 p-2 bg-muted rounded text-sm">
                    {field.value !== null ? (
                      typeof field.value === 'object' ? (
                        JSON.stringify(field.value)
                      ) : (
                        String(field.value)
                      )
                    ) : (
                      <span className="text-muted-foreground italic">{t.extraction.noValue}</span>
                    )}
                  </div>
                  {field.raw_text && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t.extraction.source}: "{field.raw_text}"
                    </div>
                  )}
                  {field.validation_errors.length > 0 && (
                    <div className="mt-1 text-xs text-red-600">
                      {field.validation_errors.join(', ')}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {field.validation_passed ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  <span className={`text-sm font-medium ${getConfidenceColor(field.confidence)}`}>
                    {Math.round(field.confidence * 100)}%
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </ScrollArea>

      <div className="flex justify-end">
        <Button variant="outline" onClick={onClose}>
          {t.common.close}
        </Button>
      </div>
    </div>
  );
}


// Main Extraction Page Component
export default function Extraction() {
  const { t } = useI18n();
  const [templates, setTemplates] = useState<ExtractionTemplate[]>([]);
  const [results, setResults] = useState<ExtractionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<ExtractionTemplate | null>(null);
  const [selectedResult, setSelectedResult] = useState<ExtractionResult | null>(null);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ExtractionTemplate | undefined>();
  const [extracting, setExtracting] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [documents, setDocuments] = useState<{ id: string; title: string }[]>([]);

  useEffect(() => {
    loadTemplates();
    loadResults();
    loadDocuments();
  }, []);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const data = await getExtractionTemplates();
      setTemplates(data.templates);
    } catch (error) {
      console.error('Failed to load templates:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    try {
      const data = await getExtractionResults();
      setResults(data);
    } catch (error) {
      console.error('Failed to load results:', error);
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

  const handleSaveTemplate = async (data: { name: string; description?: string; fields: TemplateField[] }) => {
    try {
      if (editingTemplate) {
        await updateExtractionTemplate(editingTemplate.id, data);
      } else {
        await createExtractionTemplate(data);
      }
      await loadTemplates();
      setShowBuilder(false);
      setEditingTemplate(undefined);
    } catch (error) {
      console.error('Failed to save template:', error);
    }
  };

  const handleDeleteTemplate = async (templateId: string) => {
    if (!confirm(t.extraction.confirmDelete)) return;
    try {
      await deleteExtractionTemplate(templateId);
      await loadTemplates();
      if (selectedTemplate?.id === templateId) {
        setSelectedTemplate(null);
      }
    } catch (error) {
      console.error('Failed to delete template:', error);
    }
  };

  const handleExtract = async () => {
    if (!selectedTemplate || selectedDocuments.length === 0) return;
    try {
      setExtracting(true);
      if (selectedDocuments.length === 1) {
        const result = await extractData(selectedTemplate.id, selectedDocuments[0]);
        setSelectedResult(result);
      } else {
        const response = await batchExtractData(selectedTemplate.id, selectedDocuments);
        await loadResults();
        if (response.results.length > 0) {
          setSelectedResult(response.results[0]);
        }
      }
      await loadResults();
    } catch (error) {
      console.error('Failed to extract:', error);
    } finally {
      setExtracting(false);
    }
  };

  const handleExport = async (format: ExportFormat) => {
    const resultIds = results.map((r) => r.id);
    if (resultIds.length === 0) return;
    try {
      const blob = await exportExtractionResults(resultIds, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `extraction_results.${format === 'excel' ? 'xlsx' : format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export:', error);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.extraction.title}</h1>
          <p className="text-muted-foreground">{t.extraction.subtitle}</p>
        </div>
        <Button onClick={() => { setEditingTemplate(undefined); setShowBuilder(true); }}>
          <Plus className="h-4 w-4 mr-2" />
          {t.extraction.newTemplate}
        </Button>
      </div>

      <Tabs defaultValue="extract" className="space-y-4">
        <TabsList>
          <TabsTrigger value="extract">{t.extraction.extract}</TabsTrigger>
          <TabsTrigger value="templates">{t.extraction.templates}</TabsTrigger>
          <TabsTrigger value="results">{t.extraction.results}</TabsTrigger>
        </TabsList>

        <TabsContent value="extract" className="space-y-4">
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>{t.extraction.selectTemplate}</CardTitle>
                <CardDescription>{t.extraction.selectTemplateDesc}</CardDescription>
              </CardHeader>
              <CardContent>
                <Select
                  value={selectedTemplate?.id || ''}
                  onValueChange={(value) => {
                    const template = templates.find((t) => t.id === value);
                    setSelectedTemplate(template || null);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t.extraction.chooseTemplate} />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedTemplate && (
                  <div className="mt-4 p-3 bg-muted rounded-lg">
                    <p className="text-sm text-muted-foreground">{selectedTemplate.description}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {selectedTemplate.fields.map((field) => (
                        <Badge key={field.name} variant="outline" className="text-xs">
                          {field.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t.extraction.selectDocuments}</CardTitle>
                <CardDescription>{t.extraction.selectDocumentsDesc}</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[200px]">
                  <div className="space-y-2">
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        className={`p-2 rounded cursor-pointer flex items-center gap-2 ${
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
                        <span className="text-sm">{doc.title}</span>
                      </div>
                    ))}
                    {documents.length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        {t.extraction.noDocuments}
                      </p>
                    )}
                  </div>
                </ScrollArea>
                <div className="mt-4">
                  <Button
                    className="w-full"
                    disabled={!selectedTemplate || selectedDocuments.length === 0 || extracting}
                    onClick={handleExtract}
                  >
                    {extracting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        {t.extraction.extracting}
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        {t.extraction.runExtraction} ({selectedDocuments.length})
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="templates" className="space-y-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : templates.length === 0 ? (
            <Card className="p-8 text-center">
              <FileSpreadsheet className="h-12 w-12 mx-auto text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">{t.extraction.noTemplates}</h3>
              <p className="text-muted-foreground">{t.extraction.noTemplatesDesc}</p>
              <Button className="mt-4" onClick={() => setShowBuilder(true)}>
                <Plus className="h-4 w-4 mr-2" />
                {t.extraction.createFirst}
              </Button>
            </Card>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <Card key={template.id}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{template.name}</CardTitle>
                        <CardDescription>{template.description}</CardDescription>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setEditingTemplate(template);
                            setShowBuilder(true);
                          }}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                          onClick={() => handleDeleteTemplate(template.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-1">
                      {template.fields.slice(0, 5).map((field) => (
                        <Badge key={field.name} variant="outline" className="text-xs">
                          {field.name}
                        </Badge>
                      ))}
                      {template.fields.length > 5 && (
                        <Badge variant="secondary" className="text-xs">
                          +{template.fields.length - 5}
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="results" className="space-y-4">
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => handleExport('json')}>
              <Download className="h-4 w-4 mr-1" />
              JSON
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
              <Download className="h-4 w-4 mr-1" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleExport('excel')}>
              <Download className="h-4 w-4 mr-1" />
              Excel
            </Button>
          </div>
          {results.length === 0 ? (
            <Card className="p-8 text-center">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">{t.extraction.noResults}</h3>
              <p className="text-muted-foreground">{t.extraction.noResultsDesc}</p>
            </Card>
          ) : (
            <div className="space-y-2">
              {results.map((result) => (
                <Card
                  key={result.id}
                  className="p-4 cursor-pointer hover:bg-muted/50"
                  onClick={() => setSelectedResult(result)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{result.document_title || result.document_id}</div>
                      <div className="text-sm text-muted-foreground">
                        {result.template_name} • {new Date(result.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-sm">
                          <span className="text-green-600">{result.fields_extracted}</span>
                          {result.fields_failed > 0 && (
                            <span className="text-red-600 ml-2">{result.fields_failed} failed</span>
                          )}
                        </div>
                        <Progress
                          value={result.overall_confidence * 100}
                          className="w-24 h-2"
                        />
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Template Builder Dialog */}
      <Dialog open={showBuilder} onOpenChange={setShowBuilder}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingTemplate ? t.extraction.editTemplate : t.extraction.newTemplate}
            </DialogTitle>
            <DialogDescription>
              {t.extraction.templateBuilderDesc}
            </DialogDescription>
          </DialogHeader>
          <TemplateBuilder
            template={editingTemplate}
            onSave={handleSaveTemplate}
            onCancel={() => {
              setShowBuilder(false);
              setEditingTemplate(undefined);
            }}
          />
        </DialogContent>
      </Dialog>

      {/* Results View Dialog */}
      <Dialog open={!!selectedResult} onOpenChange={() => setSelectedResult(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t.extraction.extractionResult}</DialogTitle>
          </DialogHeader>
          {selectedResult && (
            <ResultsView result={selectedResult} onClose={() => setSelectedResult(null)} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
