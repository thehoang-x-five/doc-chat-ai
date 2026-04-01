import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useI18n } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api';
import type { Workspace } from '@/lib/api';
import type { Language } from '@/lib/i18n';

interface HeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onToggleTheme?: () => void;
}

const Header = ({ searchQuery, onSearchChange, onToggleTheme }: HeaderProps) => {
  useLocation();
  const navigate = useNavigate();
  const { language, setLanguage, t } = useI18n();
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);
  const [showWorkspaceDropdown, setShowWorkspaceDropdown] = useState(false);

  useEffect(() => {
    // Load workspaces
    apiClient.getWorkspaces().then(ws => {
      setWorkspaces(ws);
      if (ws.length > 0) {
        // Get saved workspace or use first
        const savedId = localStorage.getItem('currentWorkspaceId');
        const found = ws.find(w => w.id === savedId) || ws[0];
        setCurrentWorkspace(found);
      }
    }).catch(() => { });
  }, []);

  const toggleLanguage = () => {
    const newLang: Language = language === 'en' ? 'vi' : 'en';
    setLanguage(newLang);
  };

  const handleSelectWorkspace = (ws: Workspace) => {
    setCurrentWorkspace(ws);
    localStorage.setItem('currentWorkspaceId', ws.id);
    setShowWorkspaceDropdown(false);
  };

  // Get user initials from name
  const getInitials = (name: string) => {
    if (!name) return 'U';
    const parts = name.trim().split(' ');
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
  };

  // Get role display text
  const getRoleDisplay = (role: string) => {
    const roleMap: Record<string, { en: string; vi: string }> = {
      admin: { en: 'Administrator', vi: 'Quản trị viên' },
      user: { en: 'User', vi: 'Người dùng' },
      owner: { en: 'Owner', vi: 'Chủ sở hữu' },
      member: { en: 'Member', vi: 'Thành viên' },
      viewer: { en: 'Viewer', vi: 'Người xem' },
    };
    return roleMap[role]?.[language] || role;
  };

  const userName = user?.name || t.header?.guest || 'Guest';
  const userRole = user?.role || 'user';

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 dark:bg-slate-950/70 backdrop-blur">
      <div className="flex w-full flex-wrap items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
            {getInitials(userName)}
          </div>
          <div className="leading-tight min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{userName}</p>
            <p className="truncate text-xs text-muted-foreground">{getRoleDisplay(userRole)}</p>
          </div>

          {/* Workspace Selector */}
          <div className="hidden sm:block relative pl-3 border-l border-border/50">
            <button
              onClick={() => setShowWorkspaceDropdown(!showWorkspaceDropdown)}
              className="flex items-center gap-2 rounded-lg border border-border/60 bg-card/80 px-3 py-1.5 text-sm transition hover:bg-muted/80 hover:border-primary/30"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4 text-primary" fill="none">
                <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M9 22V12h6v10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="font-medium truncate max-w-[150px]">
                {currentWorkspace?.name || (language === 'vi' ? 'Chọn workspace' : 'Select workspace')}
              </span>
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 text-muted-foreground" fill="none">
                <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            {/* Dropdown */}
            {showWorkspaceDropdown && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowWorkspaceDropdown(false)} />
                <div className="absolute top-full left-3 mt-1 z-50 min-w-[220px] rounded-xl border border-border bg-card shadow-xl">
                  <div className="p-2 border-b border-border/50">
                    <p className="text-xs font-medium text-muted-foreground px-2">
                      {language === 'vi' ? 'Không gian làm việc' : 'Workspaces'}
                    </p>
                  </div>
                  <div className="max-h-[240px] overflow-y-auto p-1">
                    {workspaces.length === 0 ? (
                      <p className="text-sm text-muted-foreground px-3 py-2">
                        {language === 'vi' ? 'Chưa có workspace' : 'No workspaces yet'}
                      </p>
                    ) : (
                      workspaces.map(ws => (
                        <button
                          key={ws.id}
                          onClick={() => handleSelectWorkspace(ws)}
                          className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${currentWorkspace?.id === ws.id
                              ? 'bg-primary/10 text-primary'
                              : 'hover:bg-muted'
                            }`}
                        >
                          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/15 text-xs font-medium text-primary">
                            {ws.name.charAt(0).toUpperCase()}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">{ws.name}</p>
                            {ws.memberCount && (
                              <p className="text-xs text-muted-foreground">
                                {ws.memberCount} {language === 'vi' ? 'thành viên' : 'members'}
                              </p>
                            )}
                          </div>
                          {currentWorkspace?.id === ws.id && (
                            <svg viewBox="0 0 24 24" className="h-4 w-4 text-primary" fill="none">
                              <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                  <div className="p-2 border-t border-border/50">
                    <button
                      onClick={() => {
                        setShowWorkspaceDropdown(false);
                        navigate('/workspaces');
                      }}
                      className="w-full flex items-center justify-center gap-2 rounded-lg border border-dashed border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium text-primary transition hover:bg-primary/10"
                    >
                      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
                        <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                      {language === 'vi' ? 'Quản lý Workspaces' : 'Manage Workspaces'}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="ml-auto flex-1 min-w-[220px] max-w-sm sm:max-w-md">
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card/90 px-3 py-2 shadow-sm dark:bg-slate-900/70">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-muted-foreground">
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
              <path d="m16 16 4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <input
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={t.header.searchPlaceholder}
              className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 pl-2 text-sm flex-shrink-0">
          <button
            className="relative flex h-10 w-10 items-center justify-center rounded-full border border-border text-lg transition hover:bg-muted"
            aria-label={t.header.notifications}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M6 10a6 6 0 0 1 12 0v4.5l1.5 2.5H4.5L6 14.5V10Z"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M10 19.5c.5.6 1.2 1 2 1s1.5-.4 2-1"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-primary" />
          </button>
          {onToggleTheme && (
            <button
              onClick={onToggleTheme}
              className="hidden h-10 w-10 items-center justify-center rounded-full border border-border text-lg transition hover:bg-muted sm:flex"
              aria-label={t.header.toggleTheme}
            >
              ☼
            </button>
          )}
          <button
            onClick={toggleLanguage}
            className="relative flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition"
            title={language === 'en' ? 'Switch to Vietnamese' : 'Chuyển sang Tiếng Anh'}
          >
            <span className="text-sm font-semibold">{language === 'en' ? 'EN' : 'VI'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
