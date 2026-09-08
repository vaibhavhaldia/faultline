import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Faultline — Change-impact workbench', description: 'Trace distributed-system changes across APIs, events and data. Evidence-first impact analysis for AI coding agents.' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
