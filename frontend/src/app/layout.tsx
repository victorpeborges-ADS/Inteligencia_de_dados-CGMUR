import './globals.css'
import type { Metadata } from 'next'
import { AuthProvider } from '@/components/Auth/AuthProvider'
import ThemeProvider from '@/components/UI/ThemeProvider'
import ErrorBoundary from '@/components/UI/ErrorBoundary'
import { COLOR_MODE_STORAGE_KEY } from '@/config/theme'

export const metadata: Metadata = {
  title: 'Sinidu+Clima - Inteligência Territorial',
  description: 'Sistema Nacional de Informações para o Desenvolvimento Urbano e Resiliência Climática.',
}

const themeInitScript = `(function(){try{var m=localStorage.getItem('${COLOR_MODE_STORAGE_KEY}');var t=m==='light'?'light':'dark';document.documentElement.setAttribute('data-theme',t);document.documentElement.style.colorScheme=t;}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR" data-theme="dark" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <link rel="icon" href="/logo-sinidu-clima.png" />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="bg-background text-foreground antialiased min-h-screen">
        <ThemeProvider>
          <ErrorBoundary>
            <AuthProvider>{children}</AuthProvider>
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  )
}
