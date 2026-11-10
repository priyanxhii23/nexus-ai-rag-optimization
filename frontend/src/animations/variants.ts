import type { Variants } from 'framer-motion'

export const ease = [0.22, 1, 0.36, 1] as const

export const page: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease } },
  exit: { opacity: 0, y: -4, transition: { duration: 0.15 } },
}

export const stagger: Variants = {
  animate: { transition: { staggerChildren: 0.05 } },
}

export const rise: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
}
