import type { OcrSettings } from '@/types';
import type { ReactNode } from 'react';
import { useI18n } from '@/lib/i18n';

interface Props {
  settings: OcrSettings;
  onChange: (next: OcrSettings) => void;
  disabled?: boolean;
}

const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="space-y-3 rounded-xl border border-border/70 bg-muted/40 p-4">
    <p className="text-sm font-semibold">{title}</p>
    {children}
  </div>
);

const ToggleRow = ({
  label,
  checked,
  onChange,
  description,
}: {
  label: string;
  checked: boolean;
  onChange: (val: boolean) => void;
  description?: string;
}) => (
  <label className="flex cursor-pointer items-start justify-between gap-3 rounded-lg border border-transparent px-2 py-1 hover:border-border">
    <div>
      <p className="text-sm font-medium">{label}</p>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </div>
    <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
  </label>
);

const OcrSettingsPanel = ({ settings, onChange, disabled }: Props) => {
  const { t } = useI18n();
  
  const update = <K extends keyof OcrSettings>(key: K, value: OcrSettings[K]) =>
    !disabled && onChange({ ...settings, [key]: value });

  return (
    <div className={`space-y-4 ${disabled ? 'opacity-60 pointer-events-none' : ''}`}>
      <Section title={t.ocrSettings.recognition}>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <label className="flex flex-col gap-1">
            {t.ocrSettings.language}
            <select
              value={settings.language}
              onChange={(e) => update('language', e.target.value as OcrSettings['language'])}
              className="input-modern text-sm"
            >
              <option value="auto">{t.ocrSettings.auto}</option>
              <option value="vi">{t.ocrSettings.vietnamese}</option>
              <option value="en">{t.ocrSettings.english}</option>
              <option value="ja">{t.ocrSettings.japanese}</option>
              <option value="ko">{t.ocrSettings.korean}</option>
              <option value="zh">{t.ocrSettings.chinese}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            {t.ocrSettings.mode}
            <select
              value={settings.mode}
              onChange={(e) => update('mode', e.target.value as OcrSettings['mode'])}
              className="input-modern text-sm"
            >
              <option value="fast">{t.ocrSettings.fast}</option>
              <option value="balanced">{t.ocrSettings.balanced}</option>
              <option value="accurate">{t.ocrSettings.accurate}</option>
            </select>
          </label>
        </div>
      </Section>

      <Section title={t.ocrSettings.preprocess}>
        <div className="grid grid-cols-2 gap-2">
          <ToggleRow label={t.ocrSettings.autoOrientation} checked={settings.preprocess.autoOrient} onChange={(val) => update('preprocess', { ...settings.preprocess, autoOrient: val })} />
          <ToggleRow label={t.ocrSettings.deskew} checked={settings.preprocess.deskew} onChange={(val) => update('preprocess', { ...settings.preprocess, deskew: val })} />
          <ToggleRow label={t.ocrSettings.denoise} checked={settings.preprocess.denoise} onChange={(val) => update('preprocess', { ...settings.preprocess, denoise: val })} />
          <ToggleRow label={t.ocrSettings.deblur} checked={settings.preprocess.deblur} onChange={(val) => update('preprocess', { ...settings.preprocess, deblur: val })} />
          <ToggleRow label={t.ocrSettings.binarize} checked={settings.preprocess.binarize} onChange={(val) => update('preprocess', { ...settings.preprocess, binarize: val })} />
          <ToggleRow label={t.ocrSettings.contrastBoost} checked={settings.preprocess.contrastBoost} onChange={(val) => update('preprocess', { ...settings.preprocess, contrastBoost: val })} />
          <ToggleRow label={t.ocrSettings.shadowRemoval} checked={settings.preprocess.shadowRemoval} onChange={(val) => update('preprocess', { ...settings.preprocess, shadowRemoval: val })} />
          <ToggleRow label={t.ocrSettings.removeLines} checked={settings.preprocess.removeLines} onChange={(val) => update('preprocess', { ...settings.preprocess, removeLines: val })} />
          <ToggleRow label={t.ocrSettings.dpiNormalize} checked={settings.preprocess.dpiNormalize} onChange={(val) => update('preprocess', { ...settings.preprocess, dpiNormalize: val })} />
          <label className="col-span-2 flex flex-col gap-1 text-sm">
            {t.ocrSettings.rotate}
            <select
              value={settings.preprocess.rotate}
              onChange={(e) =>
                update('preprocess', { ...settings.preprocess, rotate: Number(e.target.value) as OcrSettings['preprocess']['rotate'] })
              }
              className="input-modern text-sm"
            >
              <option value={0}>0°</option>
              <option value={90}>90°</option>
              <option value={180}>180°</option>
              <option value={270}>270°</option>
            </select>
          </label>
          <label className="col-span-2 flex flex-col gap-1 text-sm">
            {t.ocrSettings.brightness} {settings.preprocess.brightness}
            <input
              type="range"
              min={-50}
              max={50}
              value={settings.preprocess.brightness}
              onChange={(e) =>
                update('preprocess', { ...settings.preprocess, brightness: Number(e.target.value) })
              }
            />
          </label>
          <div className="col-span-2 text-xs text-muted-foreground">
            {t.ocrSettings.qualityScore}: <span className="font-semibold text-foreground">{settings.preprocess.qualityScore}</span> / 100
          </div>
        </div>
      </Section>

      <Section title={t.ocrSettings.layoutAnalysis}>
        <div className="grid grid-cols-2 gap-2">
          <ToggleRow label={t.ocrSettings.preserveLayout} checked={settings.layout.preserveLayout} onChange={(val) => update('layout', { ...settings.layout, preserveLayout: val })} />
          <ToggleRow label={t.ocrSettings.keepLineBreaks} checked={settings.layout.keepLineBreaks} onChange={(val) => update('layout', { ...settings.layout, keepLineBreaks: val })} />
          <ToggleRow label={t.ocrSettings.detectColumns} checked={settings.layout.detectColumns} onChange={(val) => update('layout', { ...settings.layout, detectColumns: val })} />
          <ToggleRow label={t.ocrSettings.detectHeadersFooters} checked={settings.layout.detectHeadersFooters} onChange={(val) => update('layout', { ...settings.layout, detectHeadersFooters: val })} />
          <ToggleRow label={t.ocrSettings.detectLists} checked={settings.layout.detectLists} onChange={(val) => update('layout', { ...settings.layout, detectLists: val })} />
          <ToggleRow label={t.ocrSettings.detectForms} checked={settings.layout.detectForms} onChange={(val) => update('layout', { ...settings.layout, detectForms: val })} />
        </div>
      </Section>

      <Section title={t.ocrSettings.regionRoi}>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <label className="inline-flex items-center gap-1">
              <input
                type="radio"
                checked={settings.region.mode === 'full'}
                onChange={() => update('region', { ...settings.region, mode: 'full' })}
              />
              {t.ocrSettings.fullPage}
            </label>
            <label className="inline-flex items-center gap-1">
              <input
                type="radio"
                checked={settings.region.mode === 'manual'}
                onChange={() => update('region', { ...settings.region, mode: 'manual' })}
              />
              {t.ocrSettings.manualRegion}
            </label>
          </div>
          {settings.region.mode === 'manual' && (
            <div className="space-y-2 text-sm">
              <p className="text-xs text-muted-foreground">{t.ocrSettings.mockMultiRegion}</p>
              {settings.region.regions.map((region, idx) => (
                <div key={region.id} className="grid grid-cols-5 items-center gap-2 rounded-lg border border-border/60 p-2 text-xs">
                  <span className="font-medium">#{idx + 1}</span>
                  {(['x', 'y', 'w', 'h'] as const).map((key) => (
                    <input
                      key={key}
                      type="number"
                      value={region[key]}
                      onChange={(e) =>
                        update('region', {
                          ...settings.region,
                          regions: settings.region.regions.map((r) =>
                            r.id === region.id ? { ...r, [key]: Number(e.target.value) } : r
                          ),
                        })
                      }
                      className="input-modern px-2 py-1 text-xs"
                      placeholder={key.toUpperCase()}
                    />
                  ))}
                  <button
                    className="text-destructive"
                    onClick={() =>
                      update('region', { ...settings.region, regions: settings.region.regions.filter((r) => r.id !== region.id) })
                    }
                  >
                    {t.ocrSettings.remove}
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="text-xs font-semibold text-primary underline"
                onClick={() =>
                  update('region', {
                    ...settings.region,
                    regions: [
                      ...settings.region.regions,
                      { id: `region-${settings.region.regions.length + 1}`, x: 10, y: 10, w: 100, h: 100 },
                    ],
                  })
                }
              >
                {t.ocrSettings.addRegion}
              </button>
            </div>
          )}
        </div>
      </Section>

      <Section title={t.ocrSettings.postProcessing}>
        <div className="grid grid-cols-2 gap-2">
          <ToggleRow label={t.ocrSettings.spellCorrection} checked={settings.post.spellCorrection} onChange={(val) => update('post', { ...settings.post, spellCorrection: val })} />
          <ToggleRow label={t.ocrSettings.normalizeWhitespace} checked={settings.post.normalizeWhitespace} onChange={(val) => update('post', { ...settings.post, normalizeWhitespace: val })} />
          <ToggleRow label={t.ocrSettings.maskSensitive} checked={settings.post.maskSensitive} onChange={(val) => update('post', { ...settings.post, maskSensitive: val })} />
          <ToggleRow label={t.ocrSettings.highlightLowConfidence} checked={settings.post.highlightLowConfidence} onChange={(val) => update('post', { ...settings.post, highlightLowConfidence: val })} />
          <ToggleRow label={t.ocrSettings.regexCleanupPhone} checked={settings.post.regexCleanup.phone} onChange={(val) => update('post', { ...settings.post, regexCleanup: { ...settings.post.regexCleanup, phone: val } })} />
          <ToggleRow label={t.ocrSettings.regexCleanupEmail} checked={settings.post.regexCleanup.email} onChange={(val) => update('post', { ...settings.post, regexCleanup: { ...settings.post.regexCleanup, email: val } })} />
          <ToggleRow label={t.ocrSettings.regexCleanupDate} checked={settings.post.regexCleanup.date} onChange={(val) => update('post', { ...settings.post, regexCleanup: { ...settings.post.regexCleanup, date: val } })} />
          <ToggleRow label={t.ocrSettings.regexCleanupId} checked={settings.post.regexCleanup.id} onChange={(val) => update('post', { ...settings.post, regexCleanup: { ...settings.post.regexCleanup, id: val } })} />
        </div>
        <label className="block text-sm">
          {t.ocrSettings.customVocabulary}
          <textarea
            value={settings.post.customVocabulary}
            onChange={(e) => update('post', { ...settings.post, customVocabulary: e.target.value })}
            placeholder={t.ocrSettings.customVocabularyPlaceholder}
            className="input-modern text-sm"
            rows={3}
          />
        </label>
      </Section>

      <Section title={t.ocrSettings.structuredExtraction}>
        <div className="grid grid-cols-2 gap-2">
          <ToggleRow label={t.ocrSettings.tableExtraction} checked={settings.intelligence.tableExtraction} onChange={(val) => update('intelligence', { ...settings.intelligence, tableExtraction: val })} />
          <ToggleRow label={t.ocrSettings.keyValueExtraction} checked={settings.intelligence.keyValueExtraction} onChange={(val) => update('intelligence', { ...settings.intelligence, keyValueExtraction: val })} />
          <ToggleRow label={t.ocrSettings.entityExtraction} checked={settings.intelligence.entityExtraction} onChange={(val) => update('intelligence', { ...settings.intelligence, entityExtraction: val })} />
        </div>
        <label className="block text-sm">
          {t.ocrSettings.template}
          <select
            value={settings.intelligence.template}
            onChange={(e) =>
              update('intelligence', { ...settings.intelligence, template: e.target.value as OcrSettings['intelligence']['template'] })
            }
            className="input-modern text-sm"
          >
            <option value="none">{t.ocrSettings.none}</option>
            <option value="invoice">{t.ocrSettings.invoice}</option>
            <option value="receipt">{t.ocrSettings.receipt}</option>
            <option value="id">{t.ocrSettings.idCard}</option>
            <option value="form">{t.ocrSettings.form}</option>
          </select>
        </label>
      </Section>

      <Section title={t.ocrSettings.securityCompliance}>
        <div className="grid grid-cols-2 gap-2">
          <ToggleRow label={t.ocrSettings.redaction} checked={settings.security.redaction} onChange={(val) => update('security', { ...settings.security, redaction: val })} />
          <ToggleRow label={t.ocrSettings.piiDetection} checked={settings.security.piiDetection} onChange={(val) => update('security', { ...settings.security, piiDetection: val })} />
        </div>
        <label className="block text-sm">
          {t.ocrSettings.retention}
          <select
            value={settings.security.retention}
            onChange={(e) =>
              update('security', { ...settings.security, retention: e.target.value as OcrSettings['security']['retention'] })
            }
            className="input-modern text-sm"
          >
            <option value="7d">{t.ocrSettings.days7}</option>
            <option value="30d">{t.ocrSettings.days30}</option>
            <option value="90d">{t.ocrSettings.days90}</option>
          </select>
        </label>
      </Section>

      <Section title={t.ocrSettings.output}>
        <div className="grid grid-cols-2 gap-2">
          <ToggleRow label={t.ocrSettings.mergePages} checked={settings.output.mergePages} onChange={(val) => update('output', { ...settings.output, mergePages: val })} />
          <ToggleRow label={t.ocrSettings.includeConfidence} checked={settings.output.includeConfidence} onChange={(val) => update('output', { ...settings.output, includeConfidence: val })} />
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {(['txt', 'md', 'json', 'pdf'] as const).map((format) => (
            <button
              key={format}
              onClick={() => {
                const exists = settings.output.exportFormats.includes(format);
                update('output', {
                  ...settings.output,
                  exportFormats: exists
                    ? settings.output.exportFormats.filter((f) => f !== format)
                    : [...settings.output.exportFormats, format],
                });
              }}
              className={`toggle-chip ${settings.output.exportFormats.includes(format) ? 'active' : ''}`}
            >
              {format.toUpperCase()}
            </button>
          ))}
        </div>
      </Section>
    </div>
  );
};

export default OcrSettingsPanel;
