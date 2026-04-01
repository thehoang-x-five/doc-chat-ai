// src/lib/auth.tsx
// Auth context wrapper using Zustand store - similar to my-patients pattern
import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { useAuthStore } from './authStore';
import type { User } from './api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  bootstrapped: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, name: string) => Promise<User>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const store = useAuthStore();

  // Bootstrap auth state on mount
  useEffect(() => {
    store.bootstrap();
  }, []);

  // Listen for 401 unauthorized events
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const onUnauthorized = () => {
      store.handleUnauthorized();
    };

    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => {
      window.removeEventListener('auth:unauthorized', onUnauthorized);
    };
  }, [store.handleUnauthorized]);

  // Auto handle token expiration
  useEffect(() => {
    if (!store.accessToken || !store.accessTokenExpiresAt) return;

    const expMs = new Date(store.accessTokenExpiresAt).getTime();
    if (Number.isNaN(expMs)) return;

    const now = Date.now();
    const delay = expMs - now;

    if (delay <= 0) {
      store.handleUnauthorized();
      return;
    }

    const id = setTimeout(() => {
      store.handleUnauthorized();
    }, delay);

    return () => clearTimeout(id);
  }, [store.accessToken, store.accessTokenExpiresAt, store.handleUnauthorized]);

  return (
    <AuthContext.Provider value={{
      user: store.user,
      isLoading: store.loading,
      isAuthenticated: !!store.accessToken,
      bootstrapped: store.bootstrapped,
      error: store.error,
      login: store.login,
      register: store.register,
      logout: store.logout,
      clearError: store.clearError,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Re-export store for direct access
export { useAuthStore } from './authStore';
