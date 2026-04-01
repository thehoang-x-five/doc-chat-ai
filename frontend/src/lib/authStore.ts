// src/lib/authStore.ts
// Auth store using Zustand - similar to my-patients pattern
import { create } from 'zustand';
import { apiClient, type User } from './api';

const AUTH_STORAGE_KEY = 'ocr-ink-auth';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  accessTokenExpiresAt: string | null;
  bootstrapped: boolean;
  loading: boolean;
  error: string | null;
  refreshing: boolean;
  refreshPromise: Promise<void> | null; // Track ongoing refresh
}

interface AuthActions {
  bootstrap: () => void;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, name: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  handleUnauthorized: () => Promise<void>;
  clearError: () => void;
}

type AuthStore = AuthState & AuthActions;

function loadStoredAuth(): Partial<AuthState> {
  if (typeof window === 'undefined') {
    return { user: null, accessToken: null, refreshToken: null, accessTokenExpiresAt: null };
  }

  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return { user: null, accessToken: null, refreshToken: null, accessTokenExpiresAt: null };
    }
    const parsed = JSON.parse(raw);
    return {
      user: parsed.user || null,
      accessToken: parsed.accessToken || null,
      refreshToken: parsed.refreshToken || null,
      accessTokenExpiresAt: parsed.accessTokenExpiresAt || null,
    };
  } catch {
    return { user: null, accessToken: null, refreshToken: null, accessTokenExpiresAt: null };
  }
}

function saveStoredAuth(auth: Partial<AuthState>) {
  if (typeof window === 'undefined') return;

  try {
    if (!auth || !auth.accessToken) {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }

    window.localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        user: auth.user || null,
        accessToken: auth.accessToken,
        refreshToken: auth.refreshToken || null,
        accessTokenExpiresAt: auth.accessTokenExpiresAt || null,
      })
    );
  } catch {
    // ignore
  }
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  accessTokenExpiresAt: null,
  bootstrapped: false,
  loading: false,
  error: null,
  refreshing: false,
  refreshPromise: null,

  bootstrap() {
    if (get().bootstrapped) return;
    
    console.log('[AuthStore] Bootstrapping...');
    const stored = loadStoredAuth();
    
    // Check if token is expired
    let isExpired = false;
    if (stored.accessToken && stored.accessTokenExpiresAt) {
      const expMs = new Date(stored.accessTokenExpiresAt).getTime();
      if (!Number.isNaN(expMs) && expMs <= Date.now()) {
        isExpired = true;
        console.log('[AuthStore] Token expired, clearing...');
      }
    }

    if (isExpired) {
      saveStoredAuth({});
      set({
        user: null,
        accessToken: null,
        refreshToken: null,
        accessTokenExpiresAt: null,
        bootstrapped: true,
        loading: false,
        error: null,
        refreshing: false,
        refreshPromise: null,
      });
      console.log('[AuthStore] Bootstrap complete - no valid token');
      return;
    }

    // Token still valid
    set({
      user: stored.user || null,
      accessToken: stored.accessToken || null,
      refreshToken: stored.refreshToken || null,
      accessTokenExpiresAt: stored.accessTokenExpiresAt || null,
      bootstrapped: true,
    });
    console.log('[AuthStore] Bootstrap complete - token valid:', !!stored.accessToken);
  },

  async login(email: string, password: string) {
    set({ loading: true, error: null });

    try {
      const user = await apiClient.login(email, password);
      
      // Get tokens from apiClient (it stores them internally)
      const accessToken = localStorage.getItem('accessToken');
      const refreshToken = localStorage.getItem('refreshToken');
      
      const authState = {
        user,
        accessToken,
        refreshToken,
        accessTokenExpiresAt: null, // Will be set from token if needed
      };

      saveStoredAuth(authState);
      set({
        ...authState,
        bootstrapped: true,
        loading: false,
        error: null,
      });

      return user;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Đăng nhập thất bại';
      set({ loading: false, error: msg });
      throw err;
    }
  },

  async register(email: string, password: string, name: string) {
    set({ loading: true, error: null });

    try {
      const user = await apiClient.register(email, password, name);
      
      const accessToken = localStorage.getItem('accessToken');
      const refreshToken = localStorage.getItem('refreshToken');
      
      const authState = {
        user,
        accessToken,
        refreshToken,
        accessTokenExpiresAt: null,
      };

      saveStoredAuth(authState);
      set({
        ...authState,
        bootstrapped: true,
        loading: false,
        error: null,
      });

      return user;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Đăng ký thất bại';
      set({ loading: false, error: msg });
      throw err;
    }
  },

  async refresh() {
    try {
      console.log('[AuthStore] Attempting to refresh token...');
      // apiClient handles refresh internally
      const user = await apiClient.getMe();
      const accessToken = localStorage.getItem('accessToken');
      const refreshToken = localStorage.getItem('refreshToken');
      
      const authState = {
        user,
        accessToken,
        refreshToken,
        accessTokenExpiresAt: get().accessTokenExpiresAt,
      };

      saveStoredAuth(authState);
      set(authState);
      console.log('[AuthStore] Token refresh successful');
    } catch (error) {
      // If refresh fails, clear everything and throw
      console.error('[AuthStore] Token refresh failed:', error);
      saveStoredAuth({});
      set({
        user: null,
        accessToken: null,
        refreshToken: null,
        accessTokenExpiresAt: null,
      });
      throw error;
    }
  },

  async handleUnauthorized() {
    const { bootstrapped, accessToken, refreshing, refreshPromise } = get();

    // Chưa bootstrap xong hoặc đã không có token thì bỏ qua
    if (!bootstrapped || !accessToken) {
      // Nếu đã bootstrap xong mà không có token -> đảm bảo đã logout
      if (bootstrapped && !accessToken) {
        saveStoredAuth({});
      }
      return;
    }
    
    // Nếu đang có refresh đang chạy, chờ nó xong thay vì tạo mới
    if (refreshing && refreshPromise) {
      console.log('[AuthStore] Refresh already in progress, waiting...');
      try {
        await refreshPromise;
        return;
      } catch {
        // Refresh failed, will logout below
      }
    }

    console.log('[AuthStore] Handling unauthorized - attempting refresh');
    set({ refreshing: true });

    // Create refresh promise
    const promise = (async () => {
      try {
        // Thử refresh token
        await get().refresh();
        const { accessToken: newToken } = get();
        
        // Nếu refresh thành công nhưng không có token mới -> logout ngay
        if (!newToken) {
          console.warn('[AuthStore] Refresh succeeded but no new token - logging out');
          await get().logout();
        }
      } catch (error) {
        // Refresh thất bại -> logout ngay lập tức
        console.error('[AuthStore] Token refresh failed - logging out:', error);
        await get().logout();
      } finally {
        set({ refreshing: false, refreshPromise: null });
      }
    })();

    set({ refreshPromise: promise });
    await promise;
  },

  async logout() {
    console.log('[AuthStore] Logging out...');
    
    // Clear state immediately to trigger redirect
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      accessTokenExpiresAt: null,
      loading: false,
      error: null,
      bootstrapped: true,
      refreshing: false,
      refreshPromise: null,
    });

    // Clear storage
    saveStoredAuth({});

    // Call backend logout (best effort, don't wait)
    try {
      await apiClient.logout();
      console.log('[AuthStore] Backend logout successful');
    } catch (error) {
      console.warn('[AuthStore] Backend logout failed (ignored):', error);
    }
  },

  clearError() {
    set({ error: null });
  },
}));
