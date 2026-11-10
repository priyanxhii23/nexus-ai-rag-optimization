import { animate, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useState, type ReactNode } from 'react'
import { rise } from '../animations/variants'

export function Card({ title, action, children, className = '' }: {
  title?: string; action?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <motion.section variants={rise}
      className={`rounded-xl border border-line bg-surface p-5 transition-colors ${className}`}>
      {title && (
        <header className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-medium text-fg">{title}</h2>
          {action}
        </header>
      )}
      {children}
    </motion.section>
  )
}

/** Number that counts up from 0 when it first appears. */
export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(reduce ? value : 0)
  useEffect(() => {
    if (reduce) { setShown(value); return }
    const controls = animate(0, value, { duration: 0.8, ease: 'easeOut', onUpdate: setShown })
    return () => controls.stop()
  }, [value, reduce])
  return <>{format(shown)}</>
}

export function StatusDot({ status }: { status: 'ok' | 'error' | 'pending' | 'not_configured' | 'offline' }) {
  const color = { ok: 'bg-ok', error: 'bg-err', offline: 'bg-err', pending: 'bg-warn', not_configured: 'bg-muted' }[status]
  return (
    <span className="relative inline-flex h-2 w-2" aria-hidden>
      {status === 'ok' && <span className={`absolute inset-0 animate-ping rounded-full opacity-40 motion-reduce:hidden ${color}`} />}
      <span className={`relative h-2 w-2 rounded-full ${color}`} />
    </span>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surface-2 ${className}`} />
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'accent' | 'ok' | 'warn' }) {
  const tones = {
    neutral: 'bg-surface-2 text-muted',
    accent: 'bg-accent-soft text-accent',
    ok: 'bg-ok/10 text-ok',
    warn: 'bg-warn/10 text-warn',
  }
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export function EmptyState({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line px-6 py-8 text-center">
      <div className="text-muted">{icon}</div>
      <p className="text-sm font-medium text-fg">{title}</p>
      <p className="max-w-xs text-xs leading-relaxed text-muted">{body}</p>
    </div>
  )
}
