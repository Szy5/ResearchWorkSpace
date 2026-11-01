import { useEffect } from 'react'
import { AlertCircle, Check, Loader2, Sparkles, X } from 'lucide-react'
import { JobResponse } from '../api/client'
import { JobState, StagedCandidate } from '../hooks/useBatchGeneration'
import { jobStatusLabel, jobTargetLabel } from '../utils/jobLabels'
import { normalizeQuotes } from '../utils/textFormat'
import { CandidateStatusBadge } from './CandidateCard'
import JobSteps from './JobSteps'

type Props = {
  open: boolean
  onClose: () => void
  staged: StagedCandidate[]
  jobStatus: Record<string, JobState>
  generating: boolean
  activeJobs: JobResponse[]
  recentJobs: JobResponse[]
  onUnstage: (key: string) => void
  onGenerate: () => void
  onDismissJob: (jobId: string) => void
  onDismissAllRecent: () => void
  onOpenManage?: () => void
}

function JobCard({
  job,
  onDismiss
}: {
  job: JobResponse
  onDismiss?: () => void
}) {
  const busy = job.status === 'pending' || job.status === 'running'
  return (
    <li className="rounded-xl border border-line bg-canvas p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-moss">
            {jobTargetLabel(job.target)}
          </p>
          <p className="mt-1 truncate font-serif text-[15px] font-medium tracking-tight text-ink">{job.slug}</p>
        </div>
        {onDismiss && !busy ? (
          <button className="icon-button h-7 w-7 flex-none" title="忽略" onClick={onDismiss}>
            <X size={13} />
          </button>
        ) : null}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <JobStatusChip status={job.status} />
        <span className="text-[11px] text-muted">{new Date(job.created_at).toLocaleTimeString()}</span>
      </div>
      {job.steps && job.steps.length > 0 ? (
        <div className="mt-3">
          <JobSteps steps={job.steps} compact />
        </div>
      ) : job.progress ? (
        <p className="mt-2 text-xs leading-5 text-body">{normalizeQuotes(job.progress)}</p>
      ) : null}
      {job.status === 'failed' && job.error ? <p className="mt-1 text-xs text-error">{job.error}</p> : null}
    </li>
  )
}

function JobStatusChip({ status }: { status: JobResponse['status'] }) {
  if (status === 'pending' || status === 'running') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-moss-soft px-2 py-1 text-xs text-moss">
        <Loader2 size={12} className={status === 'running' ? 'animate-spin' : ''} />
        {jobStatusLabel(status)}
      </span>
    )
  }
  if (status === 'succeeded') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-moss-soft px-2 py-1 text-xs text-moss">
        <Check size={12} />
        {jobStatusLabel(status)}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-error-soft px-2 py-1 text-xs text-error">
      <AlertCircle size={12} />
      {jobStatusLabel(status)}
    </span>
  )
}

export default function ActivityDrawer({
  open,
  onClose,
  staged,
  jobStatus,
  generating,
  activeJobs,
  recentJobs,
  onUnstage,
  onGenerate,
  onDismissJob,
  onDismissAllRecent,
  onOpenManage
}: Props) {
  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-ink/25 backdrop-blur-[1px]"
        aria-label="关闭任务面板"
        onClick={onClose}
      />
      <aside
        className="relative flex h-full w-full max-w-md animate-fade-in flex-col border-l border-line bg-canvas shadow-lift"
        role="dialog"
        aria-modal="true"
        aria-labelledby="activity-drawer-title"
      >
        <div className="flex-none border-b border-line px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="panel-title">Activity</p>
              <h2 id="activity-drawer-title" className="mt-1 font-serif text-[22px] font-medium tracking-tight">
                任务
              </h2>
              <p className="mt-1 text-xs text-body">
                {activeJobs.length > 0
                  ? `${activeJobs.length} 个任务进行中`
                  : staged.length > 0
                    ? `已暂存 ${staged.length} 篇，可批量生成`
                    : '后台任务与批量生成'}
              </p>
            </div>
            <button className="icon-button h-9 w-9 flex-none" title="关闭" onClick={onClose}>
              <X size={16} />
            </button>
          </div>
          {onOpenManage ? (
            <button
              className="action-button mt-3 h-9 w-full justify-center text-xs"
              onClick={() => {
                onOpenManage()
                onClose()
              }}
            >
              打开管理页查看完整历史
            </button>
          ) : null}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <section className="border-b border-line p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">进行中</h3>
              <span className="text-[11px] text-body">{activeJobs.length}</span>
            </div>
            {activeJobs.length === 0 ? (
              <p className="rounded-lg border border-dashed border-line px-3 py-4 text-center text-xs text-muted">
                当前没有运行中的任务
              </p>
            ) : (
              <ul className="space-y-3">
                {activeJobs.map((job) => (
                  <JobCard key={job.job_id} job={job} />
                ))}
              </ul>
            )}
          </section>

          {recentJobs.length > 0 ? (
            <section className="border-b border-line p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">最近完成</h3>
                <button className="text-[11px] font-medium text-muted hover:text-ink" onClick={onDismissAllRecent}>
                  全部清除
                </button>
              </div>
              <ul className="space-y-3">
                {recentJobs.slice(0, 8).map((job) => (
                  <JobCard key={job.job_id} job={job} onDismiss={() => onDismissJob(job.job_id)} />
                ))}
              </ul>
            </section>
          ) : null}

          <section className="p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">生成暂存区</h3>
              <span className="text-[11px] text-body">已暂存 {staged.length} 篇</span>
            </div>
            <button
              className="button-primary mb-3 h-10 w-full justify-center"
              disabled={generating || staged.length === 0}
              onClick={onGenerate}
            >
              <Sparkles size={16} className={generating ? 'animate-spin' : ''} />
              {generating ? '批量生成中...' : '批量生成'}
            </button>
            {staged.length === 0 ? (
              <div className="empty-state px-4 py-8">
                <p className="font-serif text-sm font-medium tracking-tight text-ink">暂存区空着</p>
                <p className="mt-2 text-xs leading-5 text-body">从首页勾选论文后，在这里批量生成三件套。</p>
              </div>
            ) : (
              <ul className="space-y-3">
                {staged.map((item) => {
                  const state = jobStatus[item.key]
                  const busy = state?.status === 'pending' || state?.status === 'running'
                  return (
                    <li key={item.key} className="rounded-xl border border-line bg-canvas p-3.5">
                      <div className="flex items-start justify-between gap-2">
                        <p className="line-clamp-2 min-w-0 flex-1 font-serif text-[15px] font-medium leading-snug tracking-tight">
                          {item.candidate.title || item.key}
                        </p>
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
                      {state?.progress ? (
                        <p className="mt-1 text-xs text-body">{normalizeQuotes(state.progress)}</p>
                      ) : null}
                      {state?.status === 'failed' && state.error ? (
                        <p className="mt-1 text-xs text-error">{state.error}</p>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </div>
      </aside>
    </div>
  )
}
