import { useMemo, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { twMerge } from 'tailwind-merge';
import { useI18n } from '@/lib/i18n';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

type NavKey = 'dashboard' | 'chat' | 'extract' | 'batch' | 'compare' | 'extraction' | 'summarize' | 'knowledge' | 'memory' | 'workspaces' | 'models' | 'accounts' | 'apikeys' | 'analytics' | 'settings' | 'help';

const navIcons: Record<NavKey, () => JSX.Element> = {
  dashboard: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M4 11h16M4 17h10M10 5h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  chat: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  extract: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <rect x="4" y="4" width="16" height="16" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 12h6M12 9v6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  batch: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M4 11h6V4H4v7Zm10 9h6v-7h-6v7Zm0-9h6V4h-6v7Zm-10 9h6v-7H4v7Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  compare: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M16 3h5v5M8 3H3v5M3 16v5h5M21 16v5h-5M12 8v8M8 12h8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  extraction: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  summarize: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  knowledge: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  memory: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M12 2a3 3 0 0 0-3 3v4a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 15v7M8 22h8M15 9a5 5 0 0 1 5 5v1a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-1a5 5 0 0 1 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  workspaces: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9 22V12h6v10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  models: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  accounts: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="9" cy="7" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  apikeys: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  analytics: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M18 20V10M12 20V4M6 20v-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  settings: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33H15a1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15 1.65 1.65 0 0 0 3 14H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9 1.65 1.65 0 0 0 4.27 7.18l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6V4.5A1.65 1.65 0 0 0 10 3V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9H19.5A1.65 1.65 0 0 0 21 10.65V11a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  help: () => (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.8 2.1c-.7.4-1.3 1-1.3 1.9v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="16.5" r=".85" fill="currentColor" />
    </svg>
  ),
};

interface NavSection {
  title: string;
  titleKey: 'main' | 'documents' | 'management' | 'aiConfig' | 'other';
  items: { to: string; label: string; key: NavKey }[];
}

const Sidebar = ({ collapsed, onToggle }: SidebarProps) => {
  const { pathname } = useLocation();
  const [hovered, setHovered] = useState<string | null>(null);
  const { t } = useI18n();

  // Section titles
  const sectionTitles = {
    main: t.nav?.sectionMain || 'Main',
    documents: t.nav?.sectionDocuments || 'Documents',
    management: t.nav?.sectionManagement || 'Management',
    aiConfig: t.nav?.sectionAiConfig || 'AI Config',
    other: t.nav?.sectionOther || 'Other',
  };

  // Organized nav sections
  const navSections: NavSection[] = [
    {
      title: sectionTitles.main,
      titleKey: 'main',
      items: [
        { to: '/dashboard', label: t.nav.dashboard, key: 'dashboard' },
        { to: '/chat', label: t.nav?.chat || 'Chat', key: 'chat' },
      ],
    },
    {
      title: sectionTitles.documents,
      titleKey: 'documents',
      items: [
        { to: '/extract', label: t.nav.extract, key: 'extract' },
        { to: '/batch', label: t.nav.batch, key: 'batch' },
        { to: '/compare', label: t.compare?.title || 'Compare', key: 'compare' },
        { to: '/extraction', label: t.extraction?.title || 'Extraction', key: 'extraction' },
        { to: '/summarize', label: t.summarize?.title || 'Summarize', key: 'summarize' },
      ],
    },
    {
      title: sectionTitles.management,
      titleKey: 'management',
      items: [
        { to: '/knowledge', label: t.nav?.knowledge || 'Knowledge Base', key: 'knowledge' },
        { to: '/memory', label: t.nav?.memory || 'Memory', key: 'memory' },
        { to: '/workspaces', label: t.nav?.workspaces || 'Workspaces', key: 'workspaces' },
      ],
    },
    {
      title: sectionTitles.aiConfig,
      titleKey: 'aiConfig',
      items: [
        { to: '/models', label: t.nav?.models || 'Models', key: 'models' },
        { to: '/accounts', label: t.nav?.accounts || 'Cloud Code', key: 'accounts' },
        { to: '/apikeys', label: t.nav?.apikeys || 'API Keys', key: 'apikeys' },
      ],
    },
    {
      title: sectionTitles.other,
      titleKey: 'other',
      items: [
        { to: '/analytics', label: t.nav?.analytics || 'Analytics', key: 'analytics' },
        { to: '/settings', label: t.nav.settings, key: 'settings' },
        { to: '/help', label: t.nav.help, key: 'help' },
      ],
    },
  ];

  const allNavLinks = navSections.flatMap(s => s.items);
  // Sort by URL length descending to match longer paths first (e.g., /extraction before /extract)
  const sortedNavLinks = useMemo(() => [...allNavLinks].sort((a, b) => b.to.length - a.to.length), [allNavLinks]);
  const activeKey = useMemo(() => sortedNavLinks.find((l) => pathname.startsWith(l.to))?.to ?? null, [pathname, sortedNavLinks]);

  const quickActions = [
    { to: '/extract', label: t.nav.newOcrJob },
    { to: '/chat', label: t.nav?.newChat || 'New Chat' },
  ];

  return (
    <motion.aside
      animate={{ width: collapsed ? 84 : 260 }}
      style={{ minWidth: collapsed ? 84 : 260, maxWidth: collapsed ? 84 : 260 }}
      transition={{ duration: 0.18 }}
      className="sticky top-0 left-0 z-30 flex h-screen flex-col border-r border-border/70 bg-background/80 backdrop-blur-xl shadow-xl shadow-primary/5"
      aria-label="Sidebar"
    >
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        {!collapsed && (
          <div className="flex items-center gap-3 px-1">
            <div className="relative">
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-primary/60 via-accent/60 to-primary/40 blur-md opacity-70" />
              <div className="relative flex h-9 w-9 items-center justify-center rounded-2xl bg-foreground text-background font-semibold text-sm">
                TD
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <b className="text-sm tracking-tight">{t.app?.name || 'TheDocAI'}</b>
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200/70 bg-emerald-50 dark:bg-emerald-900/30 dark:border-emerald-700 px-1.5 py-0.5 text-[9px] font-medium text-emerald-700 dark:text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live
                </span>
              </div>
              <div className="text-[10px] text-muted-foreground">{t.app?.description || 'Intelligent Document Assistant'}</div>
            </div>
          </div>
        )}

        <button
          aria-label={collapsed ? t.nav.openMenu : t.nav.collapseMenu}
          title={collapsed ? t.nav.openMenu : t.nav.collapseMenu}
          className="flex h-8 w-8 items-center justify-center rounded-xl border border-border text-muted-foreground transition hover:bg-muted/80 hover:text-foreground"
          onClick={onToggle}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" className={`${collapsed ? '' : 'rotate-180'} transition`}>
            <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <nav className="scrollbar-none flex-1 overflow-y-auto px-2 pt-1 pb-2" role="navigation">
        {navSections.map((section, sectionIndex) => (
          <div key={section.titleKey} className={sectionIndex > 0 ? 'mt-3' : ''}>
            {/* Section Header */}
            {!collapsed && (
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {section.title}
              </div>
            )}

            <ul className="flex flex-col gap-1">
              {section.items.map(({ to, label, key }) => {
                const isActive = activeKey === to;
                const isHover = hovered === to;
                const Icon = navIcons[key];
                return (
                  <li key={to} className="relative" onMouseEnter={() => setHovered(to)} onMouseLeave={() => setHovered(null)}>
                    {isActive && (
                      <motion.span
                        layoutId="nav-active"
                        className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-tr from-primary/95 via-primary/70 to-accent/70 shadow-[0_12px_30px_rgba(56,189,248,0.25)]"
                        transition={{ type: 'spring', stiffness: 520, damping: 36, mass: 0.6 }}
                      />
                    )}
                    {isHover && !isActive && (
                      <motion.span
                        layoutId="nav-hover"
                        className="pointer-events-none absolute inset-0 rounded-xl bg-muted/70 ring-1 ring-border/70"
                        transition={{ type: 'spring', stiffness: 640, damping: 28, mass: 0.5 }}
                      />
                    )}

                    <NavLink
                      to={to}
                      end
                      className={({ isActive: active }) =>
                        twMerge(
                          'relative z-20 flex w-full items-center gap-2.5 rounded-xl border border-border/60 bg-card/70 px-3 py-2 transition-all duration-150 text-sm',
                          active || isHover ? 'bg-transparent !border-transparent' : 'hover:bg-muted/90',
                          active ? 'text-white' : isHover ? 'text-primary' : 'text-foreground'
                        )
                      }
                    >
                      <span
                        className={twMerge(
                          'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[11px] transition-all',
                          isActive ? 'bg-white/95 text-primary shadow-md shadow-primary/30' : isHover ? 'bg-white text-primary shadow-sm' : 'bg-muted text-muted-foreground'
                        )}
                      >
                        <Icon />
                      </span>

                      {!collapsed && (
                        <span className={twMerge('text-sm font-medium truncate flex-1', isActive && 'text-white')}>{label}</span>
                      )}

                      {!collapsed && (
                        <motion.span
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: isActive || isHover ? 1 : 0, x: isActive || isHover ? 0 : -4 }}
                          transition={{ duration: 0.18 }}
                          className="flex-shrink-0"
                        >
                          <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none">
                            <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        </motion.span>
                      )}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="space-y-2 px-3 pb-3">
          <div className="rounded-xl border border-border/70 bg-muted/50 px-3 py-2.5 shadow-sm">
            <p className="text-xs text-muted-foreground">{t.nav.quickActions}</p>
            <div className="mt-2 flex flex-col gap-2">
              {quickActions.map((qa) => (
                <NavLink
                  key={qa.to}
                  to={qa.to}
                  className="flex items-center justify-between rounded-lg border border-dashed border-primary/30 bg-primary/5 px-3 py-2 text-sm font-semibold text-primary transition hover:border-primary/60 hover:bg-primary/10"
                >
                  <span>{qa.label}</span>
                  <span className="text-base leading-none">↗</span>
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.aside>
  );
};

export default Sidebar;
