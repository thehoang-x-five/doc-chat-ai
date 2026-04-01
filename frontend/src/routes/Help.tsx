import { useI18n } from '@/lib/i18n';

const Help = () => {
  const { t } = useI18n();

  const faqs = [
    { q: t.help.faq1q, a: t.help.faq1a },
    { q: t.help.faq2q, a: t.help.faq2a },
    { q: t.help.faq3q, a: t.help.faq3a },
  ];

  const tips = [t.help.tip1, t.help.tip2, t.help.tip3, t.help.tip4];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t.help.title}</h1>
        <p className="text-muted-foreground">{t.help.subtitle}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-border/70 bg-card/80 p-4">
          <h3 className="text-lg font-semibold">{t.help.faqs}</h3>
          {faqs.map((item) => (
            <div key={item.q} className="rounded-lg border border-border/70 bg-muted/30 p-3">
              <p className="font-semibold text-foreground">{item.q}</p>
              <p className="text-sm text-muted-foreground">{item.a}</p>
            </div>
          ))}
        </div>
        <div className="space-y-3 rounded-xl border border-border/70 bg-card/80 p-4 text-sm">
          <h3 className="text-lg font-semibold">{t.help.photoTips}</h3>
          <ul className="list-disc space-y-1 pl-4 text-muted-foreground">
            {tips.map((tip, idx) => (
              <li key={idx}>{tip}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Help;
