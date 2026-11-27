import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  JobResponse,
  SearchCandidate,
  batchIngest,
  getJob,
  listJobs
} from '../api/client'
import { CandidateStatus } from '../components/CandidateCard'
import { readStored, writeStored } from '../utils/storage'
export type StagedCandidate = {
  key: string
  candidate: SearchCandidate
  slug?: string
}
export type JobState = {
  status: CandidateStatus
  error?: string | null
  progress?: string | null
  slug?: string
}
type Persisted = {
  staged: StagedCandidate[]
  jobStatus: Record<string, JobState>
  jobIds: Record<string, string>
}
const STORAGE_KEY = 'paper-wiki.batch-generation.v1'
const empty: Persisted = { staged: [], jobStatus: {}, jobIds: {} }
export function useBatchGeneration() {
  const [state, setState] = useState<Persisted>(() => {
    const saved = readStored<Persisted>(STORAGE_KEY, empty)
    return {
      staged: Array.isArray(saved.staged)
        ? saved.staged.filter(
            (x) => x && typeof x.key === 'string' && x.candidate
          )
        : [],
      jobStatus: saved.jobStatus ?? {},
      jobIds: saved.jobIds ?? {}
    }
  })
  const latest = useRef(state)
  latest.current = state
  const submitting = useRef(false)
  const [sending, setSending] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  useEffect(() => {
    writeStored(STORAGE_KEY, state)
  }, [state])
  const updateJob = useCallback((key: string, job: JobResponse) => {
    setState((prev) => ({
      ...prev,
      jobStatus: {
        ...prev.jobStatus,
        [key]: {
          status: job.status,
          error: job.error,
          progress: job.progress,
          slug: String(job.result?.slug || job.slug)
        }
      }
    }))
  }, [])
  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    async function tick() {
      const saved = latest.current
      const entries = Object.entries(saved.jobIds).filter(
        ([key]) =>
          !['succeeded', 'failed'].includes(saved.jobStatus[key]?.status ?? '')
      )
      const unconfirmed = submitting.current
        ? []
        : saved.staged.filter(
            (item) =>
              ['pending', 'running'].includes(
                saved.jobStatus[item.key]?.status
              ) && !saved.jobIds[item.key]
          )
      const recovery = await Promise.allSettled(
        unconfirmed.map(async (item) => {
          const jobs = await listJobs({
            slug: item.slug || item.key,
            limit: 10
          })
          if (stopped || submitting.current) return
          const accepted = jobs.find((job) =>
            ['ingest', 'fetch_and_ingest'].includes(job.target)
          )
          if (accepted) {
            setState((prev) => ({
              ...prev,
              jobIds: { ...prev.jobIds, [item.key]: accepted.job_id }
            }))
            updateJob(item.key, accepted)
          } else {
            setState((prev) => ({
              ...prev,
              jobStatus: {
                ...prev.jobStatus,
                [item.key]: {
                  status: 'failed',
                  error:
                    '提交过程被中断，未找到对应任务。请确认任务历史后再重试。'
                }
              }
            }))
          }
        })
      )
      const results = await Promise.allSettled(
        entries.map(async ([key, id]) => {
          const job = await getJob(id)
          if (!stopped) updateJob(key, job)
        })
      )
      if (stopped) return
      setConnectionError(
        [...results, ...recovery].some((r) => r.status === 'rejected')
          ? '暂时无法同步任务状态，正在重新连接。后台任务可能仍在执行。'
          : null
      )
      timer = setTimeout(() => void tick(), 1500)
    }
    void tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [updateJob])
  const stage = useCallback(
    (items: StagedCandidate[]) =>
      setState((prev) => {
        const seen = new Set(prev.staged.map((item) => item.key))
        return {
          ...prev,
          staged: [
            ...prev.staged,
            ...items.filter((item) => {
              if (seen.has(item.key)) return false
              seen.add(item.key)
              return true
            })
          ]
        }
      }),
    []
  )
  const unstage = useCallback(
    (key: string) =>
      setState((prev) => {
        if (['running', 'pending'].includes(prev.jobStatus[key]?.status))
          return prev
        const jobStatus = { ...prev.jobStatus },
          jobIds = { ...prev.jobIds }
        delete jobStatus[key]
        delete jobIds[key]
        return {
          staged: prev.staged.filter((item) => item.key !== key),
          jobStatus,
          jobIds
        }
      }),
    []
  )
  const generate = useCallback(
    async (onSubmitted?: () => void, onlyKey?: string) => {
      if (submitting.current) return
      const saved = latest.current
      const items = saved.staged.filter(
        (item) =>
          (!onlyKey || item.key === onlyKey) &&
          !['pending', 'running', 'succeeded'].includes(
            saved.jobStatus[item.key]?.status ?? 'idle'
          )
      )
      if (!items.length) return
      submitting.current = true
      setSending(true)
      setState((prev) => ({
        ...prev,
        jobStatus: {
          ...prev.jobStatus,
          ...Object.fromEntries(
            items.map((item) => [item.key, { status: 'pending' }])
          )
        }
      }))
      // Submit individually so one failed submission cannot hide jobs already accepted.
      try {
        for (const item of items) {
          try {
            const [job] = await batchIngest([
              item.slug ? { slug: item.slug } : { arxiv_id: item.key }
            ])
            if (!job) throw new Error('未收到任务编号')
            setState((prev) => ({
              ...prev,
              jobIds: { ...prev.jobIds, [item.key]: job.job_id },
              jobStatus: {
                ...prev.jobStatus,
                [item.key]: {
                  status: job.status,
                  slug: job.slug,
                  progress: job.progress,
                  error: job.error
                }
              }
            }))
          } catch (err) {
            // A lost response can still mean the server accepted the job. Reconcile before offering a retry.
            try {
              const jobs = await listJobs({
                slug: item.slug || item.key,
                limit: 10
              })
              const accepted = jobs.find(
                (job) =>
                  ['ingest', 'fetch_and_ingest'].includes(job.target) &&
                  ['pending', 'running'].includes(job.status)
              )
              if (accepted) {
                setState((prev) => ({
                  ...prev,
                  jobIds: { ...prev.jobIds, [item.key]: accepted.job_id }
                }))
                updateJob(item.key, accepted)
                continue
              }
            } catch {
              /* Keep the submission error visible. */
            }
            setState((prev) => {
              const jobIds = { ...prev.jobIds }
              delete jobIds[item.key]
              return {
                ...prev,
                jobIds,
                jobStatus: {
                  ...prev.jobStatus,
                  [item.key]: {
                    status: 'failed',
                    error: `${err instanceof Error ? err.message : '提交失败'}；重试前可在任务历史确认是否已有任务。`
                  }
                }
              }
            })
          }
        }
      } finally {
        submitting.current = false
        setSending(false)
        onSubmitted?.()
      }
    },
    [updateJob]
  )
  const active = Object.values(state.jobStatus).some(
    (job) => job.status === 'pending' || job.status === 'running'
  )
  return {
    ...state,
    stagedKeys: useMemo(
      () => new Set(state.staged.map((item) => item.key)),
      [state.staged]
    ),
    generating: sending || active,
    sending,
    connectionError,
    stage,
    unstage,
    generate
  }
}
