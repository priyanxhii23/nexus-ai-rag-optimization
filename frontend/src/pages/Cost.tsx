import { motion } from 'framer-motion'
import { BarChart3, Calculator, Coins, Hash, PiggyBank, Scale, TrendingDown } from 'lucide-react'
import { useState } from 'react'
import { stagger } from '../animations/variants'
import { BarsChart, SERIES, TIER_COLOR, TrendChart } from '../components/charts'
import { Alert, Badge, Card, EmptyState, Kpi, MockBadge, PageHeader, Segmented, SectionNote, Skeleton, Table } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api } from '../services/api'
import { int, ms, pct, usd } from '../services/format'

export default function Cost() {
  const [days, setDays] = useState('30')
  const r = usePolling(() => api.costs(Number(days)), 15000, [days])
  const c = r.data
  const spendLabel = c?.is_simulated ? 'Simulated spend' : 'Estimated spend'
  const spend = c ? c.actual_cost_usd + c.simulated_cost_usd : null

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Cost Intelligence" description="Token usage and spend by model, and what caching and routing saved. Real spend, simulated test-mode spend and counterfactual savings are always kept apart."
        actions={<Segmented label="Time window" value={days} onChange={setDays} options={[{ value: '7', label: '7d' }, { value: '30', label: '30d' }, { value: '90', label: '90d' }]} />} />
      {r.error && <Alert>{r.error}</Alert>}
      {c?.is_simulated && <Alert tone="warn" title="Test-mode costs are simulated">All answers so far came from the mock provider. Their costs are calculated with the real list prices of the Claude models the mocks stand in for, so the savings logic can be demonstrated - but no money was spent.</Alert>}
      {!!c?.unpriced_calls && <Alert tone="warn">{c.unpriced_calls} call(s) used a model with no price configured, so they are not included in spend. Set its price in Settings.</Alert>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi loading={r.loading} label={spendLabel} icon={Coins} value={c?.has_data ? spend : null} format={usd} hint={c?.is_simulated ? 'test mode' : 'tokens × list price'} />
        <Kpi loading={r.loading} label="Saved by cache" icon={PiggyBank} tone="ok" value={c?.has_data ? c.saved_by_cache_usd : null} format={usd} hint="counterfactual" />
        <Kpi loading={r.loading} label="Saved by routing" icon={TrendingDown} tone="ok" value={c?.has_data ? c.saved_by_routing_usd : null} format={usd} hint="vs largest available model" />
        <Kpi loading={r.loading} label="Savings vs baseline" icon={Scale} tone="accent" value={c?.savings_pct} format={n => pct(n)} hint={c ? `baseline estimate ${usd(c.baseline_estimate_usd)}` : undefined} />
        <Kpi loading={r.loading} label="Input tokens" icon={Hash} value={c?.has_data ? c.total_input_tokens : null} format={int} />
        <Kpi loading={r.loading} label="Output tokens" icon={Hash} value={c?.has_data ? c.total_output_tokens : null} format={int} />
        <Kpi loading={r.loading} label="Avg cost per LLM query" icon={Calculator} value={c?.avg_cost_per_llm_query_usd} format={usd} />
        <Kpi loading={r.loading} label="Models used" icon={BarChart3} value={c?.has_data ? c.models.length : null} format={int} />
      </div>

      {r.loading ? <Skeleton className="h-64" /> : !c?.has_data ? (
        <Card><EmptyState icon={<Coins size={18} />} title="No cost data yet" body="Spend is recorded for every LLM call (provider-reported tokens when available) as soon as questions are answered." /></Card>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Daily spend vs savings" action={c.is_simulated ? <MockBadge /> : <Badge>estimated</Badge>}>
              <TrendChart data={c.daily.map(d => ({ date: d.date, spend: d.cost_usd + d.simulated_cost_usd, saved: d.saved_usd }))} xKey="date" format={usd}
                series={[{ key: 'spend', name: spendLabel, color: SERIES[0] }, { key: 'saved', name: 'Savings (counterfactual)', color: SERIES[2], dashed: true }]} />
            </Card>
            <Card title="Weekly spend vs savings" subtitle="ISO weeks">
              <BarsChart data={c.weekly.map(w => ({ week: w.week, spend: w.cost_usd + w.simulated_cost_usd, saved: w.saved_usd }))} xKey="week" format={usd}
                series={[{ key: 'spend', name: spendLabel, color: SERIES[0] }, { key: 'saved', name: 'Savings (counterfactual)', color: SERIES[2] }]} />
            </Card>
          </div>
          <Card title="Spend by model">
            <BarsChart horizontal data={c.models.map(m => ({ name: m.name, cost: m.cost_usd }))} xKey="name" format={usd} height={Math.max(140, c.models.length * 44)}
              series={[{ key: 'cost', name: 'Cost', color: SERIES[0] }]} />
          </Card>
          <Card title="Model-wise usage" subtitle="Usage source shows how many calls had provider-reported token counts vs estimates">
            <Table head={['Model', 'Tier', 'Calls', 'Failed', 'Input tok', 'Output tok', 'Usage source', 'Cost', 'Avg / p95 latency']}>
              {c.models.map(m => (
                <tr key={m.model_id}>
                  <td className="py-2.5 pr-4 font-medium">{m.name}</td>
                  <td className="py-2.5 pr-4"><span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[m.tier ?? 'small'] }} />{m.tier}</span></td>
                  <td className="py-2.5 pr-4 tabular">{m.calls}</td>
                  <td className="py-2.5 pr-4 tabular">{m.failed_calls || '—'}</td>
                  <td className="py-2.5 pr-4 tabular">{int(m.input_tokens)}</td>
                  <td className="py-2.5 pr-4 tabular">{int(m.output_tokens)}</td>
                  <td className="py-2.5 pr-4 text-xs text-muted">{m.provider_reported_calls ? `${m.provider_reported_calls} provider-reported` : ''}{m.provider_reported_calls && m.estimated_usage_calls ? ' · ' : ''}{m.estimated_usage_calls ? `${m.estimated_usage_calls} ${c.is_simulated ? 'mock/estimated' : 'estimated'}` : ''}</td>
                  <td className="py-2.5 pr-4 tabular">{usd(m.cost_usd)} <Badge className="ml-1">{m.cost_status === 'priced' ? 'est.' : m.cost_status}</Badge></td>
                  <td className="py-2.5 tabular text-muted">{ms(m.avg_latency_ms)} / {ms(m.p95_latency_ms)}</td>
                </tr>
              ))}
            </Table>
          </Card>
          <Card title="How these numbers are calculated">
            <ul className="space-y-1.5">{c.notes.map(n => <li key={n}><SectionNote>{n}</SectionNote></li>)}</ul>
          </Card>
        </>
      )}
    </motion.div>
  )
}
