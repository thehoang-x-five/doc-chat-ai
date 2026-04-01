import { useEffect } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, bootstrapped } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Force redirect when authentication state changes to false
  useEffect(() => {
    if (bootstrapped && !isAuthenticated && !isLoading) {
      console.log('[ProtectedRoute] Not authenticated - redirecting to login');
      navigate('/login', { replace: true, state: { from: location } });
    }
  }, [bootstrapped, isAuthenticated, isLoading, navigate, location]);

  // Show loading while bootstrapping auth state
  if (!bootstrapped || isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Đang kiểm tra phiên đăng nhập...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    console.log('[ProtectedRoute] Initial check - not authenticated, redirecting');
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
