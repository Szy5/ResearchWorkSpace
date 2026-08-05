import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BatchIngestItem, JobResponse, SearchCandidate, batchIngest, pollJob } from '../api/client'
import { CandidateStatus } from '../components/CandidateCard'

export type StagedCandidate = {
  key: string
  candidate: SearchCandidate
  slug?: string
}

export type JobState = {
  status: CandidateStatus
  error?: string | null
  progress?: string | null
}

type PersistedBatchState = {
  staged: StagedCandidate[]
  jobStatus: Record<string, JobState>
  jobIds: Record<string, string>
}

const STORAGE_KEY = 'paper-wiki.batch-generation.v1'

function loadPersistedState(): PersistedBatchState {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<PersistedBatchState>
    return {
      staged: Array.isArray(parsed.staged) ? parsed.staged : [],
      jobStatus: parsed.jobStatus ?? {},
      jobIds: parsed.jobIds ?? {}
    }
  } catch {
    return { staged: [], jobStatus: {}, jobIds: {} }
  }
}

/**
 * Owns the "staging → batch generation" state for the whole app. Instantiated once in
 * App.tsx so navigating between views never unmounts it (that unmounting was the root
 * cause of generation progress disappearing when the user switched pages).
 */
export function useBatchGeneration() {
  const initial = useMemo(loadPersistedState, [])
  const [staged, setStaged] = useState<StagedCandidate[]>(initial.staged)
  const [jobStatus, setJobStatus] = useState<Record<string, JobState>>(initial.jobStatus)
  const [jobIds, setJobIds] = useState<Record<string, string>>(initial.jobIds)
  const [generating, setGenerating] = useState(false)
  const polling = useRef(new Set<string>())

  const stagedKeys = useMemo(() => new Set(staged.map((item) => item.key)), [staged])

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ staged, jobStatus, jobIds }))
  }, [staged, jobStatus, jobIds])

  const watchJob = useCallback((key: string, jobId: string) => {
    if (polling.current.has(jobId)) return Promise.resolve<JobResponse | null>(null)
    polling.current.add(jobId)
    setGenerating(true)
    setJobStatus((prev) => ({ ...prev, [key]: { ...prev[key], status: 'running' } }))
    return pollJob(jobId, (update: JobResponse) => {
      setJobStatus((prev) => ({
        ...prev,
        [key]: { status: update.status, error: update.error, progress: update.progress }
      }))
    })
      .then((settled) => {
        setJobStatus((prev) => ({
          ...prev,
          [key]: { status: settled.status, error: settled.error, progress: settled.progress }
        }))
        return settled
      })
      .finally(() => {
        polling.current.delete(jobId)
        if (polling.current.size === 0) setGenerating(false)
      })
  }, [])

  useEffect(() => {
    for (const [key, jobId] of Object.entries(jobIds)) {
      const status = jobStatus[key]?.status
      if (status === 'succeeded' || status === 'failed') continue
      void watchJob(key, jobId)
    }
  }, [jobIds, jobStatus, watchJob])

  const stage = useCallback((items: StagedCandidate[]) => {
    setStaged((prev) => {
      const seen = new Set(prev.map((item) => item.key))
      return [...prev, ...items.filter((item) => !seen.has(item.key))]
    })
  }, [])

  const unstage = useCallback((key: string) => {
    setStaged((prev) => prev.filter((item) => item.key !== key))
    setJobStatus((prev) => {
      if (!(key in prev)) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
    setJobIds((prev) => {
      if (!(key in prev)) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [])

  const generate = useCallback(
    async (onSettled?: () => void) => {
      const items = staged.filter((item) => {
        const state = jobStatus[item.key]
        return !state || (state.status !== 'running' && state.status !== 'succeeded')
      })
      if (items.length === 0) return
      setGenerating(true)
      setJobStatus((prev) => {
        const next = { ...prev }
        for (const item of items) next[item.key] = { status: 'pending' }
        return next
      })
      try {
        const batchItems: BatchIngestItem[] = items.map((item) =>
          item.slug ? { slug: item.slug } : { arxiv_id: item.key }
        )
        const jobs = await batchIngest(batchItems)
        setJobIds((prev) => {
          const next = { ...prev }
          jobs.forEach((job, index) => {
            next[items[index].key] = job.job_id
          })
          return next
        })
        await Promise.all(
          jobs.map((job, index) => {
            const key = items[index].key
            return watchJob(key, job.job_id)
          })
        )
      } finally {
        setGenerating(false)
        onSettled?.()
      }
    },
    [staged, jobStatus, watchJob]
  )

  return { staged, stagedKeys, jobStatus, generating, stage, unstage, generate }
}
