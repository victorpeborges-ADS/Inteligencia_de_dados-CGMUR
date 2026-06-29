import './globals.css'
import type { Metadata } from 'next'
import { AuthProvider } from '@/components/Auth/AuthProvider'

export const metadata: Metadata = {
  title: 'Sinidu+Clima - Inteligência Territorial',
  description: 'Sistema Nacional de Informações para o Desenvolvimento Urbano e Resiliência Climática.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="icon" href="/logo-sinidu-clima.png" />
      </head>
      <body className="bg-background text-zinc-100 antialiased min-h-screen">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
