import {
  Activity, BarChart3, Database, FileText, FlaskConical, GitBranch, Gauge,
  LayoutDashboard, MessageSquare, Settings, type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  milestone: number      // milestone in which the page becomes functional
  summary: string
}

export const NAV: NavItem[] = [
  { path: '/', label: 'Overview', icon: LayoutDashboard, milestone: 3, summary: 'Headline metrics, trends and system health.' },
  { path: '/playground', label: 'AI Playground', icon: MessageSquare, milestone: 6, summary: 'Chat with your documents; see cache status, routing, tokens and cost per answer.' },
  { path: '/documents', label: 'Document Library', icon: FileText, milestone: 4, summary: 'Upload PDF/TXT files, index them into ChromaDB, manage versions and deletions.' },
  { path: '/cache', label: 'Semantic Cache', icon: Database, milestone: 5, summary: 'Inspect cached answers, similarity scores, TTL and why a query matched.' },
  { path: '/router', label: 'Model Router', icon: GitBranch, milestone: 6, summary: 'Query classification and the model chosen for each request.' },
  { path: '/compare', label: 'Model Comparison', icon: FlaskConical, milestone: 8, summary: 'Same question, same context, several models side by side.' },
  { path: '/cost', label: 'Cost Intelligence', icon: BarChart3, milestone: 7, summary: 'Token usage and estimated spend by model, with savings from caching and routing.' },
  { path: '/benchmarks', label: 'Benchmarking Lab', icon: Gauge, milestone: 8, summary: 'Baseline vs cache vs cache+routing on a fixed test set.' },
  { path: '/monitoring', label: 'Live Monitoring', icon: Activity, milestone: 9, summary: 'Live stream of every pipeline event.' },
  { path: '/settings', label: 'Settings', icon: Settings, milestone: 3, summary: 'Theme and backend configuration status.' },
]
