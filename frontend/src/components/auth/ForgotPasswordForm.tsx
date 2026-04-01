// src/components/auth/ForgotPasswordForm.tsx
import { useState } from 'react';

interface ForgotPasswordFormProps {
  onSubmit: (data: { email: string; newPassword: string; confirmPassword: string }) => void;
  onBackToLogin: () => void;
  loading?: boolean;
}

export function ForgotPasswordForm({ onSubmit, onBackToLogin, loading }: ForgotPasswordFormProps) {
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ email, newPassword, confirmPassword });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Đặt lại mật khẩu</h2>
        <p className="text-sm text-muted-foreground">
          Nhập email và mật khẩu mới của bạn
        </p>
      </div>

      {/* Email */}
      <div className="space-y-1.5">
        <label htmlFor="email-forgot" className="text-sm font-medium">
          Email
        </label>
        <input
          id="email-forgot"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          placeholder="you@example.com"
        />
      </div>

      {/* New Password */}
      <div className="space-y-1.5">
        <label htmlFor="new-password" className="text-sm font-medium">
          Mật khẩu mới
        </label>
        <div className="relative">
          <input
            id="new-password"
            type={showNewPassword ? 'text' : 'password'}
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full rounded-xl border border-border bg-background px-4 py-3 pr-16 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="••••••••"
          />
          <button
            type="button"
            onClick={() => setShowNewPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-xs px-2 py-1 rounded-md bg-muted hover:bg-muted/80 text-muted-foreground"
          >
            {showNewPassword ? 'Ẩn' : 'Hiện'}
          </button>
        </div>
      </div>

      {/* Confirm Password */}
      <div className="space-y-1.5">
        <label htmlFor="confirm-password" className="text-sm font-medium">
          Xác nhận mật khẩu
        </label>
        <div className="relative">
          <input
            id="confirm-password"
            type={showConfirmPassword ? 'text' : 'password'}
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full rounded-xl border border-border bg-background px-4 py-3 pr-16 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="••••••••"
          />
          <button
            type="button"
            onClick={() => setShowConfirmPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-xs px-2 py-1 rounded-md bg-muted hover:bg-muted/80 text-muted-foreground"
          >
            {showConfirmPassword ? 'Ẩn' : 'Hiện'}
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBackToLogin}
          className="text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          ← Quay lại đăng nhập
        </button>
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? 'Đang xử lý...' : 'Tiếp tục'}
        </button>
      </div>
    </form>
  );
}
