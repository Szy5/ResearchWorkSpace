import { CheckCircle2, Circle } from 'lucide-react'

type Props = {
  reviewed: boolean
  label: string
}

export default function ReviewBadge({ reviewed, label }: Props) {
  return (
    <span
      className={`inline-flex flex-none items-center gap-1 whitespace-nowrap text-xs ${reviewed ? 'text-moss' : 'text-muted'}`}
    >
      {reviewed ? <CheckCircle2 size={14} /> : <Circle size={14} />}
      {label}
      {reviewed ? '已审查' : '待审查'}
    </span>
  )
}
