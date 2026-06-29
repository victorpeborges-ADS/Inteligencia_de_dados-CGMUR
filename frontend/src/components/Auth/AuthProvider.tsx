'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { LogIn, LogOut, Shield } from 'lucide-react';
import {
  AUTH_REQUIRED_EVENT,
  api,
  getStoredToken,
  setStoredToken,
  type AuthStatus,
  type LoginResult,
} from '@/utils/api';

type AuthContextValue = {
  authEnabled: boolean;
  authStatusLoaded: boolean;
  user: { username: string; role: string } | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  openLogin: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return ctx;
}

function LoginModal({
  open,
  onClose,
  onLogin,
  error,
  loading,
  oidcEnabled,
  passwordLoginEnabled,
}: {
  open: boolean;
  onClose: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
  error: string | null;
  loading: boolean;
  oidcEnabled: boolean;
  passwordLoginEnabled: boolean;
}) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-center gap-2 text-cyan-300">
          <Shield className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Acesso Sinidu+Clima</h2>
        </div>
        <p className="mb-4 text-sm text-zinc-400">
          Autenticação exigida para operações no sistema.
        </p>
        {error && (
          <div className="mb-3 rounded-lg border border-red-800 bg-red-950/50 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}
        <form
          className="space-y-3"
          onSubmit={async (e) => {
            e.preventDefault();
            await onLogin(username, password);
          }}
        >
          {passwordLoginEnabled && (
            <>
              <div>
                <label className="mb-1 block text-xs text-zinc-400">Usuário</label>
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-zinc-400">Senha</label>
                <input
                  type="password"
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 rounded-lg bg-cyan-700 px-4 py-2 text-sm font-medium hover:bg-cyan-600 disabled:opacity-50"
                >
                  {loading ? 'Entrando…' : 'Entrar'}
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
                >
                  Cancelar
                </button>
              </div>
            </>
          )}
        </form>
        {oidcEnabled && (
          <div className={passwordLoginEnabled ? 'mt-4 border-t border-zinc-800 pt-4' : ''}>
            <a
              href={api.getOidcLoginUrl()}
              className="block w-full rounded-lg border border-emerald-800 bg-emerald-950/40 px-4 py-2 text-center text-sm font-medium text-emerald-300 hover:bg-emerald-900/40"
            >
              Entrar com SSO (OIDC / gov.br)
            </a>
            {!passwordLoginEnabled && (
              <button
                type="button"
                onClick={onClose}
                className="mt-2 w-full rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
              >
                Cancelar
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AuthBar() {
  const { authEnabled, authStatusLoaded, user, logout, openLogin } = useAuth();

  if (!authEnabled && authStatusLoaded) return null;

  return (
    <div className="flex items-center gap-2 text-xs">
      {user ? (
        <>
          <span className="rounded-full border border-zinc-700 bg-zinc-800/80 px-2 py-1 text-zinc-300">
            {user.username} · {user.role}
          </span>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2 py-1 text-zinc-300 hover:bg-zinc-800"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sair
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={openLogin}
          className="inline-flex items-center gap-1 rounded-lg border border-cyan-800 bg-cyan-950/50 px-2 py-1 text-cyan-300 hover:bg-cyan-900/40"
        >
          <LogIn className="h-3.5 w-3.5" />
          Entrar
        </button>
      )}
    </div>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [authStatusLoaded, setAuthStatusLoaded] = useState(false);
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);

  const refreshUser = useCallback(async (enabled: boolean) => {
    if (!enabled || !getStoredToken()) {
      setUser(null);
      return;
    }
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      setStoredToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const oidcToken = params.get('access_token');
        if (oidcToken) {
          setStoredToken(oidcToken);
          const username = params.get('username');
          if (username) setUser({ username, role: params.get('role') || 'leitor' });
          window.history.replaceState({}, '', window.location.pathname);
        }

        const authStatus = await api.getAuthStatus();
        if (cancelled) return;
        setStatus(authStatus);
        setAuthStatusLoaded(true);
        if (authStatus.enabled) {
          await refreshUser(true);
        }
      } catch {
        if (!cancelled) {
          // API inacessível — não força login; evita bloqueio quando CORS/proxy falha
          setStatus({
            enabled: false,
            roles: ['admin', 'gestor_municipal', 'leitor'],
            password_login_enabled: true,
            oidc_enabled: false,
          });
          setAuthStatusLoaded(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  useEffect(() => {
    const onAuthRequired = () => {
      setLoginOpen(true);
      setLoginError('Sessão expirada ou acesso negado. Faça login novamente.');
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setLoginLoading(true);
    setLoginError(null);
    try {
      const result: LoginResult = await api.login(username, password);
      setUser({ username: result.username, role: result.role });
      setLoginOpen(false);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Falha no login');
    } finally {
      setLoginLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    authEnabled: status?.enabled ?? false,
    authStatusLoaded,
    user,
    loading,
    login,
    logout,
    openLogin: () => {
      setLoginError(null);
      setLoginOpen(true);
    },
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLogin={login}
        error={loginError}
        loading={loginLoading}
        oidcEnabled={Boolean(status?.oidc_enabled)}
        passwordLoginEnabled={status?.password_login_enabled !== false}
      />
    </AuthContext.Provider>
  );
}
