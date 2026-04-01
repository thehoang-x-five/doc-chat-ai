import { useMemo, useState } from 'react';
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { queryClient } from '@/lib/queryClient';
import Sidebar from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';
import Toast from '@/components/common/Toast';
import Dashboard from '@/routes/Dashboard';
import Extract from '@/routes/Extract';
import BatchJobs from '@/routes/BatchJobs';
import Settings from '@/routes/Settings';
import Help from '@/routes/Help';
import Login from '@/routes/Login';
import Register from '@/routes/Register';
import Chat from '@/routes/Chat';
import KnowledgeBase from '@/routes/KnowledgeBase';
import Models from '@/routes/Models';
import Accounts from '@/routes/Accounts';
import ApiKeys from '@/routes/ApiKeys';
import Workspaces from '@/routes/Workspaces';
import Analytics from '@/routes/Analytics';
import Compare from '@/routes/Compare';
import Extraction from '@/routes/Extraction';
import Summarize from '@/routes/Summarize';
import MemoryManagement from '@/routes/MemoryManagement';
import NotFound from '@/pages/NotFound';
import { useToastQueue } from '@/hooks/useToastQueue';
import { I18nProvider } from '@/lib/i18n';
import { AuthProvider } from '@/lib/auth';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import type { ToastMessage } from '@/types';

export type AppOutletContext = {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  pushToast: (toast: Omit<ToastMessage, 'id'>) => void;
};

const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const { toasts, pushToast, removeToast } = useToastQueue();
  const location = useLocation();

  const layoutContext: AppOutletContext = useMemo(
    () => ({ searchQuery, setSearchQuery, pushToast }),
    [pushToast, searchQuery]
  );

  const toggleTheme = () => {
    document.documentElement.classList.toggle('dark');
  };

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((prev) => !prev)} />
      <div className="flex min-h-screen flex-1 flex-col">
        <Header searchQuery={searchQuery} onSearchChange={setSearchQuery} onToggleTheme={toggleTheme} />
        <main className="flex-1 overflow-y-auto bg-gradient-to-b from-background via-background to-muted/40">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="mx-auto w-full max-w-[1600px] px-3 py-3  sm:px-3 lg:px-4"
            >
              <Outlet context={layoutContext} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <Toast toasts={toasts} removeToast={removeToast} />
    </div>
  );
};



const App = () => (
  <QueryClientProvider client={queryClient}>
    <I18nProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Auth routes (no sidebar, no protection) */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Protected routes (with sidebar, require authentication) */}
            <Route element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/extract" element={<Extract />} />
              <Route path="/batch" element={<BatchJobs />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/knowledge" element={<KnowledgeBase />} />
              <Route path="/models" element={<Models />} />
              <Route path="/accounts" element={<Accounts />} />
              <Route path="/apikeys" element={<ApiKeys />} />
              <Route path="/workspaces" element={<Workspaces />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/extraction" element={<Extraction />} />
              <Route path="/summarize" element={<Summarize />} />
              <Route path="/memory" element={<MemoryManagement />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/help" element={<Help />} />
            </Route>

            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </I18nProvider>
  </QueryClientProvider>
);

export default App;
