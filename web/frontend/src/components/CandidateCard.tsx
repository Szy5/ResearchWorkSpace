import { ReactNode } from 'react'
import {
  AlertCircle,
  Check,
  ExternalLink,
  Loader2,
  Sparkles
} from 'lucide-react'
import { RankedCandidate, SearchCandidate } from '../api/client'
import { normalizeQuotes } from '../utils/textFormat'
export type CandidateStatus =
  'idle' | 'pending' | 'running' | 'succeeded' | 'failed'
type Props = {
  candidate: SearchCandidate | RankedCandidate
  selected?: boolean
  onToggleSelect?: () => void
  onPreview?: () => void
  onOpenPaper?: () => void
  status?: CandidateStatus
  statusError?: string | null
  statusProgress?: string | null
  footer?: ReactNode
}
export default function CandidateCard({
  candidate,
  selected,
  onToggleSelect,
  onPreview,
  onOpenPaper,
  status = 'idle',
  statusError,
  statusProgress,
  footer
}: Props) {
  const reason = 'reason' in candidate ? candidate.reason : ''
  const busy = status === 'pending' || status === 'running'
  return (
    <article
      className={`candidate-card ${selected ? 'candidate-card-selected' : ''} ${status === 'failed' ? 'candidate-card-failed' : ''}`}
    >
      <div className="flex items-start gap-3">
        {onToggleSelect && !onOpenPaper && (
          <input
            type="checkbox"
            className="check mt-1"
            checked={Boolean(selected)}
            disabled={busy || status === 'succeeded'}
            onChange={onToggleSelect}
            aria-label={`${selected ? '取消选择' : '选择'} ${candidate.title}`}
          />
        )}
        <div className="min-w-0 flex-1">
          <h3>
            <button
              className="candidate-title"
              onClick={onOpenPaper || onPreview}
            >
              {candidate.title}
            </button>
          </h3>
          <p className="mt-2 truncate text-xs text-body">
            {candidate.authors.join(', ') || '作者信息待补充'}
            {candidate.year ? ` · ${candidate.year}` : ''}
            {candidate.venue ? ` · ${candidate.venue}` : ''}
          </p>
        </div>
        {onOpenPaper ? (
          <button className="text-link flex-none text-xs" onClick={onOpenPaper}>
            打开论文
          </button>
        ) : (
          <CandidateStatusBadge status={status} error={statusError} />
        )}
      </div>
      <p className="mt-3 line-clamp-2 text-sm leading-6 text-body">
        {normalizeQuotes(
          candidate.display_summary ||
            candidate.abstract ||
            '暂无摘要，打开原文了解更多。'
        )}
      </p>
      {busy && statusProgress && (
        <p className="mt-2 text-xs text-body">{statusProgress}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span>{candidate.arxiv_id}</span>
        {selected && status === 'idle' && (
          <span className="text-moss">已选择</span>
        )}
        <a
          className="inline-flex items-center gap-1 hover:text-ink"
          href={`https://arxiv.org/abs/${candidate.arxiv_id}`}
          target="_blank"
          rel="noreferrer"
        >
          原文 <ExternalLink size={11} />
        </a>
      </div>
      {reason && (
        <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-body">
          <Sparkles size={12} className="mt-1 flex-none text-moss" />
          {normalizeQuotes(reason)}
        </p>
      )}
      {footer}
    </article>
  )
}
export function CandidateStatusBadge({
  status,
  error
}: {
  status: CandidateStatus
  error?: string | null
}) {
  if (status === 'idle') return null
  return (
    <span
      className={`inline-flex flex-none items-center gap-1 rounded-md px-2 py-1 text-xs ${status === 'failed' ? 'bg-error-soft text-error' : 'bg-moss-soft text-moss'}`}
      title={error || undefined}
    >
      {status === 'pending' || status === 'running' ? (
        <Loader2 size={12} className="animate-spin" />
      ) : status === 'succeeded' ? (
        <Check size={12} />
      ) : (
        <AlertCircle size={12} />
      )}
      {
        {
          pending: '排队中',
          running: '生成中',
          succeeded: '已完成',
          failed: '失败'
        }[status]
      }
    </span>
  )
}
