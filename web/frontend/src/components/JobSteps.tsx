import { useEffect, useState } from 'react'
import { Check, Circle, Globe, Loader2, Minus, X } from 'lucide-react'
import { JobStep } from '../api/client'

type Props = {
  steps: JobStep[]
  compact?: boolean
}

function elapsed(step: JobStep, now: number): string {
  if (!step.started_at) return ''
  const start = Date.parse(step.started_at)
  const end = step.finished_at ? Date.parse(step.finished_at) : now
  if (Number.isNaN(start) || Number.isNaN(end)) return ''
  const seconds = Math.max(0, (end - start) / 1000)
  if (seconds < 1) return '<1s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 60)}m${Math.round(seconds % 60)}s`
}

function StepIcon({ status }: { status: JobStep['status'] }) {
  const base = 'inline-flex h-5 w-5 flex-none items-center justify-center rounded-full'
  switch (status) {
    case 'running':
      return (
        <span className={`${base} bg-moss-soft text-moss`}>
          <Loader2 size={12} className="animate-spin" />
        </span>
      )
    case 'succeeded':
      return (
        <span className={`${base} bg-moss text-white`}>
          <Check size={12} />
        </span>
      )
    case 'failed':
      return (
        <span className={`${base} bg-error text-white`}>
          <X size={12} />
        </span>
      )
    case 'skipped':
      return (
        <span className={`${base} bg-fog text-muted`}>
          <Minus size={12} />
        </span>
      )
    default:
      return (
        <span className={`${base} text-line-strong`}>
          <Circle size={12} />
        </span>
      )
  }
}

/** Vertical step list for a background job; shows which step is calling an external API. */
export default function JobSteps({ steps, compact = false }: Props) {
  const running = steps.some((step) => step.status === 'running')
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])

  if (steps.length === 0) return null

  return (
    <ol className={compact ? 'space-y-1.5' : 'space-y-2.5'} aria-label="任务步骤">
      {steps.map((step) => {
        const active = step.status === 'running'
        const time = elapsed(step, now)
        return (
          <li key={step.key} className="flex items-start gap-2.5" data-status={step.status}>
            <StepIcon status={step.status} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`text-sm ${
                    active
                      ? 'font-medium text-ink'
                      : step.status === 'pending' || step.status === 'skipped'
                        ? 'text-muted'
                        : step.status === 'failed'
                          ? 'text-error'
                          : 'text-ink-soft'
                  } ${compact ? 'text-xs' : ''}`}
                >
                  {step.label}
                </span>
                {step.external ? (
                  <span
                    className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      active ? 'bg-copper-soft text-copper' : 'bg-fog text-muted'
                    }`}
                    title={`此步骤会调用外部服务：${step.external}`}
                  >
                    <Globe size={10} />
                    {active ? `正在请求 ${step.external}` : step.external}
                  </span>
                ) : null}
                {time ? <span className="text-[11px] tabular-nums text-muted">{time}</span> : null}
              </div>
              {step.detail && !compact ? (
                <p className={`mt-0.5 text-xs leading-5 ${step.status === 'failed' ? 'text-error' : 'text-body'}`}>
                  {step.detail}
                </p>
              ) : null}
              {step.detail && compact && (active || step.status === 'failed') ? (
                <p className={`text-[11px] ${step.status === 'failed' ? 'text-error' : 'text-body'}`}>{step.detail}</p>
              ) : null}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
