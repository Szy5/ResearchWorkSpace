import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { JobResponse, listJobs } from '../api/client'
import { isActiveJob } from '../utils/jobLabels'

const RECENT_MS = 30 * 60 * 1000
const ACTIVE_POLL_MS = 1500
const IDLE_POLL_MS = 8000

function isRecentFinished(job: JobResponse, now = Date.now()): boolean {
  if (job.status !== 'succeeded' && job.status !== 'failed') return false
  const stamp = Date.parse(job.finished_at || job.created_at)
  if (Number.isNaN(stamp)) return true
  return now - stamp <= RECENT_MS
}

/**
 * App-level job feed. Polls `/api/jobs` so task progress remains visible after
 * navigating away from the page that started the job (HTML render, publish, etc.).
 */
export function useActivityJobs() {
  const [jobs, setJobs] = useState<JobResponse[]>([])
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set())
  const inFlight = useRef(false)

  const refresh = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const next = await listJobs({ limit: 80 })
      setJobs(next)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      inFlight.current = false
    }
  }, [])

  const activeJobs = useMemo(() => jobs.filter(isActiveJob), [jobs])
  const recentJobs = useMemo(
    () =>
      jobs.filter(
        (job) => !isActiveJob(job) && isRecentFinished(job) && !dismissed.has(job.job_id)
      ),
    [jobs, dismissed]
  )

  useEffect(() => {
    void refresh()
    const intervalMs = activeJobs.length > 0 ? ACTIVE_POLL_MS : IDLE_POLL_MS
    const timer = window.setInterval(() => {
      void refresh()
    }, intervalMs)

    function onVisible() {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [refresh, activeJobs.length])

  const dismissJob = useCallback((jobId: string) => {
    setDismissed((prev) => new Set(prev).add(jobId))
  }, [])

  const dismissAllRecent = useCallback(() => {
    setDismissed((prev) => {
      const next = new Set(prev)
      for (const job of jobs) {
        if (!isActiveJob(job)) next.add(job.job_id)
      }
      return next
    })
  }, [jobs])

  return {
    activeJobs,
    recentJobs,
    error,
    refresh,
    dismissJob,
    dismissAllRecent
  }
}
