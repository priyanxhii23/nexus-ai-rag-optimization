import {
  Activity, BarChart3, Database, FileText, FlaskConical, GitBranch, Gauge,
  LayoutDashboard, MessageSquare, Settings, type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  summary: string
}

export const NAV: NavItem[] = [
  { path: '/', label: 'Overview', icon: LayoutDashboard, summary: 'Headline metrics, trends and system health.' },
  { path: '/playground', label: 'AI Playground', icon: MessageSquare, summary: 'Chat with your documents and inspect how every answer was produced.' },
  { path: '/documents', label: 'Document Library', icon: FileText, summary: 'Upload, version and delete the documents the assistant answers from.' },
  { path: '/cache', label: 'Semantic Cache', icon: Database, summary: 'Inspect cached answers, why they matched, and tune the similarity threshold.' },
  { path: '/router', label: 'Model Router', icon: GitBranch, summary: 'Query intelligence, routing decisions and model configuration.' },
  { path: '/compare', label: 'Model Comparison', icon: FlaskConical, summary: 'The same question and context, several models side by side.' },
  { path: '/cost', label: 'Cost Intelligence', icon: BarChart3, summary: 'Token usage and spend by model, with savings from caching and routing.' },
  { path: '/benchmarks', label: 'Benchmarking Lab', icon: Gauge, summary: 'Baseline vs cache vs cache + routing on a reproducible test set.' },
  { path: '/monitoring', label: 'Live Monitoring', icon: Activity, summary: 'Live stream of every pipeline event.' },
  { path: '/settings', label: 'Settings', icon: Settings, summary: 'Cache, routing, providers, pricing and appearance.' },
]
