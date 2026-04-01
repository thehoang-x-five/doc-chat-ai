// src/routes/Login.tsx
// Login page with forgot password flow - similar to my-patients pattern
import { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth, useAuthStore } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';
import { ForgotPasswordForm } from '@/components/auth/ForgotPasswordForm';
import { OtpVerificationModal } from '@/components/auth/OtpVerificationModal';
import { apiClient } from '@/lib/api';

export default function Login() {
  const { t } = useI18n();
  const { login, isAuthenticated, bootstrapped, error, clearError } = useAuth();
  const bootstrap = useAuthStore((s) => s.bootstrap);
  const navigate = useNavigate();
  const location = useLocation();
  
  const [mode, setMode] = useState<'login' | 'forgot'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // OTP modal state
  const [otpOpen, setOtpOpen] = useState(false);
  const [otpEmail, setOtpEmail] = useState('');
  const [pendingForgot, setPendingForgot] = useState<{
    email: string;
    newPassword: string;
  } | null>(null);

  // Bootstrap auth state
  useEffect(() => {
    if (!bootstrapped) {
      bootstrap();
    }
  }, [bootstrapped, bootstrap]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as any)?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (!email || !password) {
      setLocalError('Vui lòng nhập đầy đủ email và mật khẩu');
      return;
    }

    setIsLoading(true);
    try {
      await login(email, password);
      // Navigation handled by useEffect above
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgot = (data: { email: string; newPassword: string; confirmPassword: string }) => {
    setLocalError('');
    
    if (!data.email) {
      setLocalError('Vui lòng nhập email');
      return;
    }
    if (!data.newPassword || !data.confirmPassword) {
      setLocalError('Vui lòng nhập đầy đủ mật khẩu mới');
      return;
    }
    if (data.newPassword !== data.confirmPassword) {
      setLocalError('Mật khẩu xác nhận không khớp');
      return;
    }

    // Save pending data and open OTP modal
    setPendingForgot({ email: data.email, newPassword: data.newPassword });
    setOtpEmail(data.email);
    setOtpOpen(true);
  };

  const handleOtpVerified = async (otp: string) => {
    if (!pendingForgot) return;

    setIsLoading(true);
    try {
      // Call forgot password API with OTP
      await apiClient.forgotPassword(pendingForgot.email, otp, pendingForgot.newPassword);
      setLocalError('');
      setMode('login');
      setOtpOpen(false);
      setPendingForgot(null);
      // Show success message
      alert('Đặt lại mật khẩu thành công. Vui lòng đăng nhập.');
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Đặt lại mật khẩu thất bại');
      setOtpOpen(false);
    } finally {
      setIsLoading(false);
    }
  };

  const displayError = localError || error;

  return (
    <>
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background via-background to-muted/40 px-4">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground text-2xl font-bold">
              OCR
            </div>
            <h2 className="mt-6 text-3xl font-bold tracking-tight">
              {mode === 'login' ? (t.auth?.login || 'Đăng nhập') : 'Đặt lại mật khẩu'}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {mode === 'login' 
                ? (t.auth?.loginSubtitle || 'Đăng nhập để tiếp tục sử dụng')
                : 'Nhập email và mật khẩu mới của bạn'
              }
            </p>
          </div>

          {displayError && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {displayError}
            </div>
          )}

          {mode === 'login' ? (
            <form className="mt-8 space-y-6" onSubmit={handleLogin}>
              <div className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium">
                    {t.auth?.email || 'Email'}
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="mt-1 block w-full rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="you@example.com"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-sm font-medium">
                    {t.auth?.password || 'Mật khẩu'}
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="mt-1 block w-full rounded-xl border border-border bg-background px-4 py-3 pr-16 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="••••••••"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 mt-0.5 text-xs px-2 py-1 rounded-md bg-muted hover:bg-muted/80 text-muted-foreground"
                    >
                      {showPassword ? 'Ẩn' : 'Hiện'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    className="rounded border-border bg-background text-primary focus:ring-primary/20"
                    defaultChecked
                  />
                  Ghi nhớ đăng nhập
                </label>
                <button
                  type="button"
                  onClick={() => { setMode('forgot'); setLocalError(''); }}
                  className="text-sm text-primary hover:underline"
                >
                  {t.auth?.forgotPassword || 'Quên mật khẩu?'}
                </button>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
              >
                {isLoading ? 'Đang đăng nhập...' : (t.auth?.signIn || 'Đăng nhập')}
              </button>

              <p className="text-center text-sm text-muted-foreground">
                {t.auth?.noAccount || 'Chưa có tài khoản?'}{' '}
                <Link to="/register" className="font-medium text-primary hover:underline">
                  {t.auth?.signUp || 'Đăng ký'}
                </Link>
              </p>
            </form>
          ) : (
            <div className="mt-8">
              <ForgotPasswordForm
                onSubmit={handleForgot}
                onBackToLogin={() => { setMode('login'); setLocalError(''); }}
                loading={isLoading}
              />
            </div>
          )}
        </div>
      </div>

      {/* OTP Modal */}
      <OtpVerificationModal
        open={otpOpen}
        email={otpEmail}
        purpose="forgot"
        onClose={() => { setOtpOpen(false); setPendingForgot(null); }}
        onVerified={handleOtpVerified}
      />
    </>
  );
}
