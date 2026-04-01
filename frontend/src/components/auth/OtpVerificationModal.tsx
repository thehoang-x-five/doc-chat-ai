// src/components/auth/OtpVerificationModal.tsx
// OTP verification modal for forgot password and change password flows
import { useEffect, useRef, useState } from 'react';
import { apiClient } from '@/lib/api';

interface OtpVerificationModalProps {
  open: boolean;
  email: string;
  purpose: 'forgot' | 'change';
  onVerified: (otp: string) => void;
  onClose: () => void;
}

export function OtpVerificationModal({
  open,
  email,
  purpose,
  onVerified,
  onClose,
}: OtpVerificationModalProps) {
  const [digits, setDigits] = useState<string[]>(Array(6).fill(''));
  const inputsRef = useRef<(HTMLInputElement | null)[]>([]);
  const [requesting, setRequesting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [expiresLeft, setExpiresLeft] = useState<number | null>(null);
  const [cooldownLeft, setCooldownLeft] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const displayEmail = email?.trim() || 'email của bạn';
  const intentId = purpose === 'change' ? 'password_change' : 'password_reset';

  // Request OTP when modal opens
  useEffect(() => {
    if (!open) {
      setDigits(Array(6).fill(''));
      setExpiresLeft(null);
      setCooldownLeft(null);
      setMessage('');
      setError('');
      return;
    }

    setRequesting(true);
    setMessage('');
    setError('');

    apiClient.requestOtp(email, intentId)
      .then((res) => {
        setMessage('Đã gửi mã OTP đến email của bạn.');
        setExpiresLeft(res.expiresLeft || 300);
        setCooldownLeft(res.cooldownLeft || 60);
        setTimeout(() => {
          inputsRef.current?.[0]?.focus();
        }, 200);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Không thể gửi OTP');
      })
      .finally(() => setRequesting(false));
  }, [open, email, intentId]);

  // Countdown timer
  useEffect(() => {
    if (!open) return;

    const timer = setInterval(() => {
      setExpiresLeft((prev) =>
        typeof prev === 'number' && prev > 0 ? prev - 1 : prev
      );
      setCooldownLeft((prev) =>
        typeof prev === 'number' && prev > 0 ? prev - 1 : prev
      );
    }, 1000);

    return () => clearInterval(timer);
  }, [open]);

  const handleChangeDigit = (index: number, value: string) => {
    if (!/^[0-9]?$/.test(value)) return;
    setDigits((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
    if (value && index < digits.length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      e.preventDefault();
      inputsRef.current[index - 1]?.focus();
    }
    if (e.key === 'ArrowLeft' && index > 0) {
      e.preventDefault();
      inputsRef.current[index - 1]?.focus();
    }
    if (e.key === 'ArrowRight' && index < digits.length - 1) {
      e.preventDefault();
      inputsRef.current[index + 1]?.focus();
    }
  };

  const code = digits.join('');

  const handleVerify = async () => {
    if (code.length !== 6) {
      setError('Vui lòng nhập đủ 6 số OTP.');
      return;
    }

    setVerifying(true);
    setError('');
    setMessage('');

    try {
      const valid = await apiClient.verifyOtp(email, code, intentId);
      if (valid) {
        setMessage('Xác thực OTP thành công.');
        // Pass the OTP code back to parent for use in forgot/change password
        onVerified(code);
      } else {
        setError('Mã OTP không hợp lệ hoặc đã hết hạn.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể xác thực OTP');
    } finally {
      setVerifying(false);
    }
  };

  const handleResend = () => {
    if (requesting || (cooldownLeft && cooldownLeft > 0)) return;
    
    setRequesting(true);
    setError('');
    setMessage('');

    apiClient.requestOtp(email, intentId)
      .then((res) => {
        setMessage('Đã gửi lại mã OTP.');
        setExpiresLeft(res.expiresLeft || 300);
        setCooldownLeft(res.cooldownLeft || 60);
        setDigits(Array(6).fill(''));
        setTimeout(() => {
          inputsRef.current?.[0]?.focus();
        }, 200);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Không thể gửi lại OTP');
      })
      .finally(() => setRequesting(false));
  };

  const disabled = verifying || requesting;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 rounded-2xl bg-background border border-border shadow-xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">
              {purpose === 'change' ? 'Xác thực đổi mật khẩu' : 'Xác thực đặt lại mật khẩu'}
            </h2>
            <p className="text-sm text-muted-foreground">
              Nhập mã OTP được gửi đến email của bạn
            </p>
          </div>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-sm px-2 py-1 rounded-md hover:bg-muted"
            onClick={onClose}
          >
            Đóng
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6 space-y-6 text-center">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Mã OTP đã được gửi tới <span className="font-semibold text-foreground">{displayEmail}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              Nhập <span className="font-semibold">6 chữ số</span> để tiếp tục
            </p>

            {/* OTP Input */}
            <div className="flex gap-2 mt-4 justify-center">
              {digits.map((d, idx) => (
                <input
                  key={idx}
                  ref={(el) => (inputsRef.current[idx] = el)}
                  type="tel"
                  inputMode="numeric"
                  maxLength={1}
                  className="w-12 h-12 rounded-xl bg-muted border border-border text-center text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                  value={d}
                  onChange={(e) => handleChangeDigit(idx, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(idx, e)}
                />
              ))}
            </div>
          </div>

          {/* Timer */}
          {expiresLeft !== null && expiresLeft > 0 && (
            <p className="text-xs text-muted-foreground">
              Mã OTP sẽ hết hạn sau <span className="font-semibold">{expiresLeft}s</span>
            </p>
          )}

          {/* Messages */}
          {message && (
            <p className="text-sm text-green-600">{message}</p>
          )}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={disabled}
              className="px-4 py-2 text-sm rounded-xl border border-border hover:bg-muted disabled:opacity-50"
            >
              Hủy
            </button>
            
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleResend}
                disabled={disabled || (cooldownLeft !== null && cooldownLeft > 0)}
                className="px-4 py-2 text-sm rounded-xl border border-border hover:bg-muted disabled:opacity-50"
              >
                {cooldownLeft && cooldownLeft > 0 ? `Gửi lại (${cooldownLeft}s)` : 'Gửi lại OTP'}
              </button>
              
              <button
                type="button"
                onClick={handleVerify}
                disabled={disabled || code.length !== 6}
                className="px-4 py-2 text-sm rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {verifying ? 'Đang xác thực...' : 'Xác nhận'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
