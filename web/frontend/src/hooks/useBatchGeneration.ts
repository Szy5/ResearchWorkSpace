import { useCallback, useMemo, useState } from 'react'
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

/**
 * Owns the "staging → batch generation" state for the whole app. Instantiated once in
 * App.tsx so navigating between views never unmounts it (that unmounting was the root
 * cause of generation progress disappearing when the user switched pages).
 */
export function useBatchGeneration() {
  const [staged, setStaged] = useState<StagedCandidate[]>([])
  const [jobStatus, setJobStatus] = useState<Record<string, JobState>>({})
  const [generating, setGenerating] = useState(false)

  const stagedKeys = useMemo(() => new Set(staged.map((item) => item.key)), [staged])

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
        await Promise.all(
          jobs.map((job, index) => {
            const key = items[index].key
            setJobStatus((prev) => ({ ...prev, [key]: { status: 'running' } }))
            return pollJob(job.job_id, (update: JobResponse) => {
              setJobStatus((prev) => ({
                ...prev,
                [key]: { status: update.status, error: update.error, progress: update.progress }
              }))
            })
          })
        )
      } finally {
        setGenerating(false)
        onSettled?.()
      }
    },
    [staged, jobStatus]
  )

  return { staged, stagedKeys, jobStatus, generating, stage, unstage, generate }
}
