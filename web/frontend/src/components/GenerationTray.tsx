import { Sparkles, X } from 'lucide-react'
import { JobState, StagedCandidate } from '../hooks/useBatchGeneration'
import { normalizeQuotes } from '../utils/textFormat'
import { CandidateStatusBadge } from './CandidateCard'

type Props = {
  staged: StagedCandidate[]
  jobStatus: Record<string, JobState>
  generating: boolean
  onUnstage: (key: string) => void
  onGenerate: () => void
}

export default function GenerationTray({ staged, jobStatus, generating, onUnstage, onGenerate }: Props) {
  return (
    <aside className="hidden h-full w-80 flex-none flex-col border-l border-line bg-fog lg:flex">
      <div className="flex-none border-b border-line p-4">
        <h2 className="panel-title">生成暂存区</h2>
        <p className="mt-1 text-xs text-body">已暂存 {staged.length} 篇</p>
        <button
          className="button-primary mt-3 h-10 w-full justify-center"
          disabled={generating || staged.length === 0}
          onClick={onGenerate}
        >
          <Sparkles size={16} className={generating ? 'animate-spin' : ''} />
          {generating ? '批量生成中...' : '批量生成'}
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {staged.length === 0 ? (
          <p className="mt-6 text-center text-sm text-body">从中间栏勾选论文，会加入这里等待批量生成。</p>
        ) : (
          <ul className="space-y-3">
            {staged.map((item) => {
              const state = jobStatus[item.key]
              const busy = state?.status === 'pending' || state?.status === 'running'
              return (
                <li key={item.key} className="rounded-lg border border-line bg-canvas p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="line-clamp-2 min-w-0 flex-1 font-serif text-sm">{item.candidate.title || item.key}</p>
                    <button
                      className="icon-button h-7 w-7 flex-none"
                      title="移出暂存区"
                      disabled={busy}
                      onClick={() => onUnstage(item.key)}
                    >
                      <X size={13} />
                    </button>
                  </div>
                  <div className="mt-2">
                    <CandidateStatusBadge status={state?.status ?? 'idle'} error={state?.error} />
                  </div>
                  {state?.progress ? <p className="mt-1 text-xs text-body">{normalizeQuotes(state.progress)}</p> : null}
                  {state?.status === 'failed' && state.error ? (
                    <p className="mt-1 text-xs text-error">{state.error}</p>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </aside>
  )
}
