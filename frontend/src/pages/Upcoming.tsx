import { motion } from 'framer-motion'
import { Construction } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge, Card } from '../components/ui'
import { stagger } from '../animations/variants'
import type { NavItem } from '../navigation'

/** Honest placeholder for a page whose feature is built in a later milestone. No fake controls. */
export default function Upcoming({ item }: { item: NavItem }) {
  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-3xl p-6">
      <Card>
        <div className="flex items-start gap-4">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
            <item.icon size={18} />
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <h2 className="font-medium">{item.label}</h2>
              <Badge tone="warn">Milestone {item.milestone}</Badge>
            </div>
            <p className="text-sm leading-relaxed text-muted">{item.summary}</p>
            <p className="flex items-center gap-2 pt-2 text-xs text-muted">
              <Construction size={13} /> Not built yet — this page will be wired to the real backend in Milestone {item.milestone}.
            </p>
            <Link to="/" className="inline-block pt-1 text-sm text-accent hover:underline">← Back to Overview</Link>
          </div>
        </div>
      </Card>
    </motion.div>
  )
}
