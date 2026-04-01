export type ThemeMode = 'light' | 'dark';

export type OcrLanguage = 'auto' | 'vi' | 'en' | 'ja' | 'ko' | 'zh';
export type OcrMode = 'fast' | 'balanced' | 'accurate';

export interface PreprocessSettings {
  autoOrient: boolean;
  rotate: 0 | 90 | 180 | 270;
  deskew: boolean;
  denoise: boolean;
  deblur: boolean;
  binarize: boolean;
  contrastBoost: boolean;
  brightness: number;
  shadowRemoval: boolean;
  removeLines: boolean;
  dpiNormalize: boolean;
  qualityScore: number;
}

export interface LayoutSettings {
  preserveLayout: boolean;
  keepLineBreaks: boolean;
  detectColumns: boolean;
  detectHeadersFooters: boolean;
  detectLists: boolean;
  detectForms: boolean;
}

export interface RegionBox {
  id: string;
  label?: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface RegionSelection {
  mode: 'full' | 'manual';
  regions: RegionBox[];
  activePage: number;
}

export interface PostProcessing {
  spellCorrection: boolean;
  customVocabulary: string;
  regexCleanup: {
    phone: boolean;
    email: boolean;
    date: boolean;
    id: boolean;
  };
  normalizeWhitespace: boolean;
  maskSensitive: boolean;
  highlightLowConfidence: boolean;
}

export interface DocumentIntelligence {
  tableExtraction: boolean;
  keyValueExtraction: boolean;
  entityExtraction: boolean;
  template: 'none' | 'invoice' | 'receipt' | 'id' | 'form';
}

export interface SecuritySettings {
  retention: '7d' | '30d' | '90d';
  piiDetection: boolean;
  redaction: boolean;
}

export interface OutputOptions {
  exportFormats: Array<'txt' | 'md' | 'json' | 'pdf'>;
  mergePages: boolean;
  includeConfidence: boolean;
}

export interface OcrSettings {
  language: OcrLanguage;
  mode: OcrMode;
  preprocess: PreprocessSettings;
  layout: LayoutSettings;
  region: RegionSelection;
  post: PostProcessing;
  intelligence: DocumentIntelligence;
  security: SecuritySettings;
  output: OutputOptions;
  
  // Backend-specific settings
  parser?: 'docling' | 'mineru';
  parseMethod?: 'auto' | 'ocr' | 'txt';
  preserveLayout?: boolean;
  returnLayout?: boolean;
  startPage?: number;
  endPage?: number;
  extract?: {
    tables?: boolean;
    equations?: boolean;
    images?: boolean;
  };
}

export interface OcrPage {
  page: number;
  text: string;
  confidence: number;
  lowConfidenceRanges?: Array<[number, number]>;
}

export interface BoundingBox {
  x: number; // 0..1 normalized
  y: number; // 0..1 normalized
  w: number; // 0..1 normalized
  h: number; // 0..1 normalized
}

export interface OcrWord {
  text: string;
  bbox: BoundingBox;
  confidence: number;
  fontSize?: number;
}

export interface OcrLine {
  text: string;
  bbox: BoundingBox;
  confidence: number;
  words: OcrWord[];
}

export interface OcrBlock {
  id: string;
  bbox: BoundingBox;
  lines: OcrLine[];
}

export interface OcrLayoutPage {
  page: number;
  width: number;
  height: number;
  blocks: OcrBlock[];
}

export interface StructuredResult {
  tables: Array<{
    id: string;
    name: string;
    rows: string[][];
  }>;
  keyValues: Array<{ key: string; value: string }>;
  entities: Array<{ type: string; value: string }>;
}

export interface OcrResult {
  fullText: string;
  pages: OcrPage[];
  language: string;
  avgConfidence: number;
  structured: StructuredResult;
  layoutPages?: OcrLayoutPage[];
  version: string;
  status: 'queued' | 'processing' | 'done' | 'error';
}

export type ProcessStatus = 'idle' | 'running' | 'done' | 'error';
export type TabType = 'extract' | 'convert';

export interface ProgressState {
  current: number;
  total: number;
  label: string;
}

export type OutputFormat = 'txt' | 'pdf' | 'docx' | 'md' | 'json';

export interface ConvertOptions {
  format: OutputFormat;
  fileName?: string;
  includeMetadata?: boolean;
  includeHeader?: boolean;
  pageSize?: 'A4' | 'Letter' | 'auto';
  fontSize?: number;
}

export interface BatchJob {
  id: string;
  fileName: string;
  type: 'ocr' | 'convert';
  status: 'queued' | 'preprocessing' | 'running' | 'postprocessing' | 'done' | 'error' | 'canceled';
  progress: number;
  createdAt: string;
  updatedAt: string;
  attempt: number;
  resultUrl?: string;
  message?: string;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title?: string;
  message: string;
}

export interface HighlightMatch {
  start: number;
  end: number;
}

export const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'pdf', 'docx', 'txt', 'md'];

export const ALLOWED_TYPES = [
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/tiff',
  'image/bmp',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/markdown',
];

export const MAX_FILE_SIZE = 15 * 1024 * 1024;
