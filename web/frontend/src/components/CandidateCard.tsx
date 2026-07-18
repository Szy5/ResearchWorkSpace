import { ReactNode } from 'react'
import { AlertCircle, Check, Loader2, Sparkles } from 'lucide-react'
import { RankedCandidate, SearchCandidate } from '../api/client'
import { normalizeQuotes } from '../utils/textFormat'

export type CandidateStatus = 'idle' | 'pending' | 'running' | 'succeeded' | 'failed'

const THUMBNAILS = Array.from({ length: 20 }, (_, index) => {
  const number = String(index + 1).padStart(2, '0')
  const extension = [6, 8, 10, 12, 19].includes(index + 1) ? 'jpg' : 'png'
  return `/thumbnails/thumb-${number}.${extension}`
})

function pickThumbnail(seed: string): string {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  }
  return THUMBNAILS[hash % THUMBNAILS.length]
}

type Props = {
  candidate: SearchCandidate | RankedCandidate
  selected?: boolean
  onToggleSelect?: () => void
  status?: CandidateStatus
  statusError?: string | null
  statusProgress?: string | null
  footer?: ReactNode
  showThumbnail?: boolean
}

export default function CandidateCard({
  candidate,
  selected,
  onToggleSelect,
  status = 'idle',
  statusError,
  statusProgress,
  footer,
  showThumbnail
}: Props) {
  const reason = 'reason' in candidate ? candidate.reason : ''
  const busy = status === 'pending' || status === 'running'
  const thumbnail = showThumbnail ? pickThumbnail(candidate.arxiv_id || candidate.title) : null

  return (
    <div
      className={`candidate-card flex gap-3 ${selected ? 'candidate-card-selected' : ''} ${status === 'failed' ? 'candidate-card-failed' : ''}`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-3">
          {onToggleSelect ? (
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 flex-none accent-moss"
              checked={Boolean(selected)}
              disabled={busy || status === 'succeeded'}
              onChange={onToggleSelect}
            />
          ) : null}
          <div className="min-w-0 flex-1">
            <h3 className="line-clamp-2 font-serif text-[15px] font-semibold">{candidate.title}</h3>
            <p className="mt-1 truncate text-xs text-body">{candidate.authors.join(', ') || candidate.arxiv_id}</p>
          </div>
          <CandidateStatusBadge status={status} error={statusError} />
        </div>
        {busy && statusProgress ? <p className="mt-2 text-xs text-body">{statusProgress}</p> : null}
        <p className="mt-3 line-clamp-3 text-sm leading-6 text-body">
          {normalizeQuotes(candidate.display_summary || candidate.abstract || 'No abstract')}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          {candidate.venue ? <span className="badge">{candidate.venue}</span> : null}
          {candidate.year ? <span className="badge">{candidate.year}</span> : null}
          {candidate.arxiv_id ? <span className="badge">{candidate.arxiv_id}</span> : null}
        </div>
        {reason ? (
          <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-copper">
            <Sparkles size={12} />
            {normalizeQuotes(reason)}
          </div>
        ) : null}
        {footer ? <div className="mt-3">{footer}</div> : null}
      </div>
      {thumbnail ? (
        <img
          src={thumbnail}
          alt=""
          className="aspect-[3/4] w-20 flex-none self-center rounded-lg border border-line object-cover object-top sm:w-24"
        />
      ) : null}
    </div>
  )
}

export function CandidateStatusBadge({ status, error }: { status: CandidateStatus; error?: string | null }) {
  if (status === 'idle') return null
  if (status === 'pending' || status === 'running') {
    return (
      <span className="inline-flex flex-none items-center gap-1 text-xs text-body">
        <Loader2 size={14} className="animate-spin" />
        {status === 'pending' ? 'Queued' : 'Running'}
      </span>
    )
  }
  if (status === 'succeeded') {
    return (
      <span className="inline-flex flex-none items-center gap-1 text-xs text-moss">
        <Check size={14} />
        Done
      </span>
    )
  }
  return (
    <span className="inline-flex flex-none items-center gap-1 text-xs text-error" title={error ?? 'Failed'}>
      <AlertCircle size={14} />
      Failed
    </span>
  )
}
