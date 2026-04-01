import { useState } from 'react';
import Card from '@/components/common/Card';

const templates = [
  {
    name: 'Invoice (PDF)',
    desc: 'Vendor, due date, line items',
    fields: ['Invoice #', 'Vendor', 'Amount', 'Due date', 'Line items'],
    fileType: 'PDF',
    purpose: 'Billing & AP automation',
    demos: ['Invoice A4', 'Invoice US Letter'],
  },
  {
    name: 'Receipt (JPG)',
    desc: 'Store receipt from POS',
    fields: ['Store', 'Total', 'Payment', 'Timestamp'],
    fileType: 'JPG',
    purpose: 'Expense claims',
    demos: ['Grocery slip', 'Fuel pump'],
  },
  {
    name: 'ID Card (PNG)',
    desc: 'Front/back identity',
    fields: ['Full name', 'DOB', 'ID #', 'Expiry'],
    fileType: 'PNG',
    purpose: 'KYC onboarding',
    demos: ['National ID', 'Driver license'],
  },
  {
    name: 'Contract (DOCX)',
    desc: 'Legal contract paragraphs',
    fields: ['Parties', 'Clauses', 'Dates', 'Signatures'],
    fileType: 'DOCX',
    purpose: 'Contract review',
    demos: ['MS Word contract'],
  },
  {
    name: 'Transcript (TXT)',
    desc: 'Plain text transcript',
    fields: ['Speaker', 'Timestamp', 'Content'],
    fileType: 'TXT',
    purpose: 'Speech-to-text cleanup',
    demos: ['Interview.txt'],
  },
  {
    name: 'Notebook (MD)',
    desc: 'Markdown technical notes',
    fields: ['Headings', 'Code blocks', 'Lists'],
    fileType: 'MD',
    purpose: 'Engineering docs',
    demos: ['Tech_notes.md'],
  },
  {
    name: 'API Spec (JSON)',
    desc: 'Structured API schema',
    fields: ['Paths', 'Params', 'Responses'],
    fileType: 'JSON',
    purpose: 'API ingestion',
    demos: ['openapi.json'],
  },
  {
    name: 'Screenshot (WEBP)',
    desc: 'UI capture with text',
    fields: ['UI labels', 'CTA text', 'Tables'],
    fileType: 'WEBP',
    purpose: 'UI OCR',
    demos: ['Dashboard.webp'],
  },
];

const Templates = () => {
  const [previewTpl, setPreviewTpl] = useState<(typeof templates)[number] | null>(null);

  const renderPreviewPage = (fileType: string, label: string, index: number) => {
    const baseStyles =
      'relative w-64 h-44 rounded-xl border border-border/60 bg-white shadow-sm ring-1 ring-border/40 overflow-hidden';
    const headerBadge =
      'rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700 text-[11px] font-semibold';

    if (fileType === 'PDF' || fileType === 'DOCX') {
      return (
        <div className={baseStyles} key={label}>
          <div className="flex items-center justify-between bg-slate-100 px-3 py-1.5 text-[11px] text-slate-600">
            <span>Page {index + 1}</span>
            <span className={headerBadge}>{fileType}</span>
          </div>
          <div className="p-3 space-y-2 text-slate-700">
            <div className="h-2 w-32 rounded-full bg-slate-200" />
            <div className="h-2 w-40 rounded-full bg-slate-200" />
            <div className="grid grid-cols-2 gap-2">
              <div className="h-16 rounded-md bg-slate-50 border border-slate-200" />
              <div className="space-y-1">
                <div className="h-2 w-full rounded-full bg-slate-200" />
                <div className="h-2 w-24 rounded-full bg-slate-200" />
                <div className="h-2 w-20 rounded-full bg-slate-200" />
              </div>
            </div>
            <div className="h-2 w-36 rounded-full bg-slate-200" />
          </div>
          <div className="absolute left-2 bottom-2 rounded-full bg-white/90 px-2 py-0.5 text-[11px] text-slate-600 shadow">
            {label}
          </div>
        </div>
      );
    }

    if (fileType === 'JPG' || fileType === 'PNG' || fileType === 'WEBP') {
      return (
        <div className={baseStyles} key={label}>
          <div className="absolute inset-0 bg-gradient-to-br from-sky-300/60 via-purple-300/50 to-amber-200/50" />
          <div className="absolute inset-0 opacity-60">
            <div className="h-full w-full bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.5),transparent_35%),radial-gradient(circle_at_80%_30%,rgba(255,255,255,0.6),transparent_30%),radial-gradient(circle_at_50%_80%,rgba(255,255,255,0.4),transparent_35%)]" />
          </div>
          <div className="relative h-full p-3 flex flex-col justify-between text-white drop-shadow">
            <div className="flex items-center justify-between text-[11px] font-semibold">
              <span>Shot {index + 1}</span>
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-sky-700">{fileType}</span>
            </div>
            <div className="space-y-1">
              <div className="h-2 w-36 rounded-full bg-white/80" />
              <div className="h-2 w-28 rounded-full bg-white/70" />
              <div className="h-2 w-20 rounded-full bg-white/60" />
            </div>
            <div className="h-16 rounded-lg bg-white/20 border border-white/30" />
            <div className="self-start rounded-full bg-white/85 px-2 py-0.5 text-[11px] text-sky-700">
              {label}
            </div>
          </div>
        </div>
      );
    }

    if (fileType === 'JSON') {
      return (
        <div className={baseStyles} key={label}>
          <div className="flex items-center justify-between bg-slate-900 px-3 py-1.5 text-[11px] text-emerald-300">
            <span>object {index + 1}</span>
            <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-emerald-200">JSON</span>
          </div>
          <div className="bg-slate-950 text-[11px] text-emerald-100 h-full p-3 font-mono space-y-1">
            <div>{`{`}</div>
            <div className="pl-4">"path": "/api/{id}",</div>
            <div className="pl-4">"method": "GET",</div>
            <div className="pl-4">"response": {"{"} ... {"}"}</div>
            <div>{`}`}</div>
          </div>
          <div className="absolute left-2 bottom-2 rounded-full bg-slate-900/90 px-2 py-0.5 text-[11px] text-emerald-200 shadow">
            {label}
          </div>
        </div>
      );
    }

    if (fileType === 'MD' || fileType === 'TXT') {
      return (
        <div className={baseStyles} key={label}>
          <div className="flex items-center justify-between bg-slate-100 px-3 py-1.5 text-[11px] text-slate-600">
            <span>{fileType === 'MD' ? 'Markdown' : 'Plain text'}</span>
            <span className={headerBadge}>{fileType}</span>
          </div>
          <div className="p-3 space-y-2 text-[12px] text-slate-700 font-mono">
            <div className="font-bold text-slate-800"># Sample heading</div>
            <div>- bullet item 1</div>
            <div>- bullet item 2</div>
            <div>``` code block ```</div>
          </div>
          <div className="absolute left-2 bottom-2 rounded-full bg-white/90 px-2 py-0.5 text-[11px] text-slate-600 shadow">
            {label}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {templates.map((tpl) => (
          <Card
            key={tpl.name}
            title={tpl.name}
            description={tpl.desc}
            actions={
              <button className="btn-gradient px-3 py-1.5 text-sm" onClick={() => setPreviewTpl(tpl)}>
                Preview demo
              </button>
            }
          >
            <div className="space-y-2 text-sm">
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-muted px-2 py-1 text-foreground/80">{tpl.fileType}</span>
                <span className="rounded-full bg-muted px-2 py-1 text-foreground/80">{tpl.purpose}</span>
              </div>
              <p className="text-xs text-muted-foreground">Fields mapping</p>
              <div className="flex flex-wrap gap-2">
                {tpl.fields.map((field) => (
                  <span key={field} className="rounded-full border border-border/70 bg-card/70 px-3 py-1 text-xs">
                    {field}
                  </span>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {previewTpl && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-label={`${previewTpl.name} demo previews`}
        >
          <div className="relative w-full max-w-4xl rounded-2xl border border-border/70 bg-card shadow-2xl">
            <button
              onClick={() => setPreviewTpl(null)}
              className="absolute right-3 top-3 rounded-full bg-muted px-3 py-1 text-xs font-semibold text-foreground shadow-sm"
            >
              Close
            </button>
            <div className="space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-foreground">{previewTpl.name} demo</h3>
                  <p className="text-sm text-muted-foreground">{previewTpl.purpose}</p>
                </div>
                <div className="flex gap-2 text-xs">
                  <span className="rounded-full bg-muted px-2 py-1 text-foreground/80">{previewTpl.fileType}</span>
                  <span className="rounded-full bg-muted px-2 py-1 text-foreground/80">{previewTpl.desc}</span>
                </div>
              </div>
              <div className="rounded-xl border border-border/60 bg-muted/40 p-3">
                <p className="mb-2 text-xs text-muted-foreground">Swipe/scroll horizontally to view sample pages</p>
                <div className="overflow-x-auto scrollbar-none">
                  <div className="flex min-w-max gap-3 py-1">
                    {previewTpl.demos.map((demo, idx) => renderPreviewPage(previewTpl.fileType, demo, idx))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Templates;
