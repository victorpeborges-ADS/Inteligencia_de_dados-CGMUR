'use client';

import { useEffect } from 'react';
import { COLOR_MODE_STORAGE_KEY, type ColorMode } from '@/config/theme';
import { useAppStore } from '@/stores/useAppStore';

function applyColorMode(mode: ColorMode) {
  document.documentElement.setAttribute('data-theme', mode);
  document.documentElement.style.colorScheme = mode;
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const colorMode = useAppStore((s) => s.colorMode);
  const setColorMode = useAppStore((s) => s.setColorMode);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(COLOR_MODE_STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') {
        setColorMode(stored);
      }
    } catch {
      /* localStorage indisponível */
    }
  }, [setColorMode]);

  useEffect(() => {
    applyColorMode(colorMode);
    try {
      localStorage.setItem(COLOR_MODE_STORAGE_KEY, colorMode);
    } catch {
      /* localStorage indisponível */
    }
  }, [colorMode]);

  return children;
}
