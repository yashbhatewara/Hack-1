import type { Metadata } from 'next';
import './globals.css';
import { Providers } from '@/components/providers';
import { Sidebar } from '@/components/layout/Sidebar';

export const metadata: Metadata = {
  title: 'Engineering Memory OS',
  description:
    'AI-powered organizational memory for engineering teams — ingest, explore, and query your engineering knowledge graph.',
  keywords: ['engineering', 'knowledge base', 'AI', 'memory', 'graph'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="font-sans bg-surface text-white antialiased" suppressHydrationWarning>
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
