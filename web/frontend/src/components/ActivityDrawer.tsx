import { ArrowRight, Check, Loader2, RefreshCw, X } from 'lucide-react'
import { JobResponse } from '../api/client'
import { JobState, StagedCandidate } from '../hooks/useBatchGeneration'
import { jobStatusLabel, jobTargetLabel } from '../utils/jobLabels'
import Dialog from './Dialog'
import JobSteps from './JobSteps'
import { CandidateStatusBadge } from './CandidateCard'
type Props = {
  open: boolean
  onClose: () => void
  staged: StagedCandidate[]
  jobStatus: Record<string, JobState>
  jobIds?: Record<string, string>
  generating: boolean
  sending?: boolean
  activeJobs: JobResponse[]
  recentJobs: JobResponse[]
  connectionError?: string | null
  onUnstage: (key: string) => void
  onGenerate: () => void
  onRetry: (key: string) => void
  onDismissJob: (jobId: string) => void
  onDismissAllRecent: () => void
  onOpenManage?: () => void
  onOpenResult: (slug: string, target?: string) => void
}
export default function ActivityDrawer({
  open,
  onClose,
  staged,
  jobStatus,
  jobIds = {},
  sending,
  activeJobs,
  recentJobs,
  connectionError,
  onUnstage,
  onGenerate,
  onRetry,
  onDismissJob,
  onDismissAllRecent,
  onOpenManage,
  onOpenResult
}: Props) {
  if (!open) return null
  const tracked = new Set(Object.values(jobIds))
  const eligible = staged.filter(
    (item) =>
      !['pending', 'running', 'succeeded'].includes(
        jobStatus[item.key]?.status ?? 'idle'
      )
  )
  const jobs = (list: JobResponse[], terminal = false) =>
    list
      .filter((job) => !tracked.has(job.job_id))
      .map((job) => (
        <article className="task-card" key={job.job_id}>
          <p className="text-xs text-body">
            {jobTargetLabel(job.target)} ·{' '}
            {new Date(job.created_at).toLocaleString()}
          </p>
          <h3 className="mt-2 text-sm font-medium">{job.slug}</h3>
          <p className="mt-2 flex items-center gap-1.5 text-xs">
            {!terminal && <Loader2 className="animate-spin" size={12} />}
            {jobStatusLabel(job.status)}
          </p>
          {job.steps?.length ? (
            <div className="mt-3">
              <JobSteps steps={job.steps} compact />
            </div>
          ) : (
            <p className="mt-2 text-xs text-body">{job.progress}</p>
          )}
          {job.error && (
            <p className="mt-3 break-words text-xs text-error">{job.error}</p>
          )}
          {terminal && (
            <div className="mt-3 flex gap-3">
              {job.status === 'succeeded' && (
                <button
                  className="text-link text-xs"
                  onClick={() =>
                    onOpenResult(
                      String(job.result?.slug || job.slug),
                      job.target
                    )
                  }
                >
                  查看结果 <ArrowRight size={12} />
                </button>
              )}
              <button
                className="text-xs text-muted"
                onClick={() => onDismissJob(job.job_id)}
              >
                隐藏这条提示
              </button>
            </div>
          )}
        </article>
      ))
  return (
    <Dialog title="任务中心" className="activity-panel" onClose={onClose}>
      <div className="drawer-body">
        <p className="mb-5 text-xs leading-6 text-body">
          任务在后台执行。关闭面板或切换页面后，仍可回来查看进度。
        </p>
        {connectionError && (
          <p role="status" className="alert-warn mb-4">
            {connectionError}
          </p>
        )}
        <section>
          <div className="section-heading mb-3">
            <h3 className="text-sm font-medium">
              已选论文 <span className="text-muted">{staged.length}</span>
            </h3>
            <button
              className="button-primary h-9 text-xs"
              disabled={sending || !eligible.length}
              onClick={onGenerate}
            >
              {sending
                ? '提交中…'
                : `生成精读${eligible.length ? `（${eligible.length}）` : ''}`}
            </button>
          </div>
          <p className="mb-4 text-xs text-body">
            生成精读笔记、前作分析和创新范式。
          </p>
          {!staged.length && (
            <p className="empty-state px-4 py-6 text-xs text-body">
              在发现页勾选论文，再到这里批量生成。
            </p>
          )}
          {staged.map((item) => {
            const state = jobStatus[item.key]
            const busy = ['pending', 'running'].includes(state?.status)
            return (
              <article key={item.key} className="task-card">
                <div className="flex items-start gap-3">
                  <h3 className="min-w-0 flex-1 text-sm font-medium leading-6">
                    {item.candidate.title}
                  </h3>
                  <CandidateStatusBadge status={state?.status ?? 'idle'} />
                  {!busy && (
                    <button
                      className="text-muted"
                      aria-label={`移除 ${item.candidate.title}`}
                      onClick={() => onUnstage(item.key)}
                    >
                      <X size={15} />
                    </button>
                  )}
                </div>
                <p className="mt-2 text-xs text-muted">
                  {item.key}
                  {!state && ' · 尚未提交'}
                </p>
                {state?.progress && (
                  <p className="mt-3 text-xs leading-6 text-body">
                    {state.progress}
                  </p>
                )}
                {state?.error && (
                  <p className="mt-3 break-words text-xs leading-6 text-error">
                    {state.error}
                  </p>
                )}
                {state?.status === 'failed' && (
                  <button
                    className="action-button mt-3 h-8 text-xs"
                    disabled={sending}
                    onClick={() => onRetry(item.key)}
                  >
                    <RefreshCw size={12} />
                    仅重试这篇
                  </button>
                )}
                {state?.status === 'succeeded' && (
                  <button
                    className="text-link mt-3 text-xs"
                    onClick={() =>
                      onOpenResult(state.slug || item.slug || item.key)
                    }
                  >
                    <Check size={12} />
                    打开精读 <ArrowRight size={12} />
                  </button>
                )}
              </article>
            )
          })}
        </section>
        {activeJobs.some((job) => !tracked.has(job.job_id)) && (
          <section className="mt-6">
            <h3 className="mb-3 text-sm font-medium">其他后台任务</h3>
            {jobs(activeJobs)}
          </section>
        )}
        {recentJobs.some((job) => !tracked.has(job.job_id)) && (
          <section className="mt-6">
            <div className="mb-3 flex justify-between">
              <h3 className="text-sm font-medium">最近完成</h3>
              <button
                className="text-xs text-muted"
                onClick={onDismissAllRecent}
              >
                隐藏完成提示
              </button>
            </div>
            {jobs(recentJobs, true)}
          </section>
        )}
        <button
          className="action-button mt-6 w-full justify-center"
          onClick={onOpenManage}
        >
          查看完整任务历史 <ArrowRight size={13} />
        </button>
      </div>
    </Dialog>
  )
}
