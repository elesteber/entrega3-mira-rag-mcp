import type { ComponentType } from 'react'
import {
  CheckCircle2,
  Info,
  HelpCircle,
  AlertOctagon,
} from 'lucide-react'
import type { EvidenceStatus } from '../types'

export interface EvidenceBadgeProps {
  status: EvidenceStatus
  className?: string
}

interface StatusConfig {
  label: string
  bgClass: string
  textClass: string
  borderClass: string
  Icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>
}

const STATUS_CONFIGS: Record<EvidenceStatus, StatusConfig> = {
  COMPLETA: {
    label: 'Respuesta con evidencia',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-800',
    borderClass: 'border-emerald-300',
    Icon: CheckCircle2,
  },
  PARCIAL: {
    label: 'Evidencia parcial',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-800',
    borderClass: 'border-blue-300',
    Icon: Info,
  },
  ABSTENCION: {
    label: 'Sin información en el corpus',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-300',
    Icon: HelpCircle,
  },
  CONFLICTO_FUENTES: {
    label: 'Conflicto entre fuentes',
    bgClass: 'bg-rose-50',
    textClass: 'text-rose-800',
    borderClass: 'border-rose-300',
    Icon: AlertOctagon,
  },
}

export function EvidenceBadge({ status, className = '' }: EvidenceBadgeProps) {
  const config = STATUS_CONFIGS[status] || STATUS_CONFIGS.ABSTENCION
  const { label, bgClass, textClass, borderClass, Icon } = config

  return (
    <span
      role="status"
      aria-label={`Estado de evidencia: ${label}`}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${bgClass} ${textClass} ${borderClass} ${className}`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  )
}

export default EvidenceBadge
