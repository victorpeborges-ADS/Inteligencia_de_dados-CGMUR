'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/** Captura exceções de render na árvore React e evita tela branca total. */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary capturou uma exceção:', error, info.componentStack);
  }

  private handleReload = () => {
    if (typeof window !== 'undefined') window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-6">
        <div className="max-w-md rounded-2xl border border-rose-700/50 bg-rose-950/30 p-6 text-center shadow-2xl">
          <h2 className="text-lg font-bold text-rose-200">Algo deu errado nesta tela</h2>
          <p className="mt-2 text-sm text-zinc-300">
            Ocorreu um erro inesperado na interface. Seus dados no servidor não foram afetados.
          </p>
          {this.state.error?.message && (
            <p className="mt-3 break-words rounded-lg bg-zinc-900/80 p-2 font-mono text-[10px] text-rose-300/80">
              {this.state.error.message}
            </p>
          )}
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-5 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold uppercase text-white hover:bg-rose-500"
          >
            Recarregar aplicação
          </button>
        </div>
      </div>
    );
  }
}
