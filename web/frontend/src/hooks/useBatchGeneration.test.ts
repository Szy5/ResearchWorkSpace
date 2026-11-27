import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { batchIngest, getJob, listJobs } from '../api/client'
import { useBatchGeneration } from './useBatchGeneration'
vi.mock('../api/client', () => ({
  batchIngest: vi.fn(),
  getJob: vi.fn(),
  listJobs: vi.fn()
}))
const candidate = (id: string) => ({
  key: id,
  candidate: {
    arxiv_id: id,
    title: id,
    authors: [],
    year: null,
    abstract: '',
    url: '',
    venue: '',
    citation_count: null,
    publication_date: null,
    source: 'arxiv',
    score: null
  }
})
const job = (
  id: string,
  status: 'failed' | 'succeeded' | 'pending' = 'pending'
) => ({
  job_id: id,
  slug: id,
  target: 'fetch_and_ingest',
  status,
  created_at: '',
  started_at: null,
  finished_at: null,
  error: status === 'failed' ? 'failed generation' : null,
  result: { slug: id },
  progress: null
})
describe('Batch generation recovery', () => {
  beforeEach(() => {
    vi.mocked(listJobs).mockReset().mockResolvedValue([])
    vi.mocked(batchIngest).mockReset()
    vi.mocked(getJob).mockReset()
  })
  test('deduplicates one selection batch and guards duplicate submissions', async () => {
    let resolve!: (jobs: ReturnType<typeof job>[]) => void
    vi.mocked(batchIngest).mockReturnValue(
      new Promise((done) => {
        resolve = done
      })
    )
    const { result } = renderHook(useBatchGeneration)
    act(() => result.current.stage([candidate('a'), candidate('a')]))
    expect(result.current.staged).toHaveLength(1)
    let submitted!: Promise<void>
    act(() => {
      submitted = result.current.generate()
      void result.current.generate()
    })
    expect(batchIngest).toHaveBeenCalledTimes(1)
    await act(async () => {
      resolve([job('a')])
      await submitted
    })
    expect(result.current.jobIds.a).toBe('a')
  })
  test('a failed submission is visible and successful items are not retried', async () => {
    vi.mocked(batchIngest).mockImplementation(async (items) => {
      const id = 'arxiv_id' in items[0] ? items[0].arxiv_id! : items[0].slug!
      if (id === 'bad') throw new Error('network down')
      return [job(id, 'succeeded')]
    })
    const { result } = renderHook(useBatchGeneration)
    act(() => result.current.stage([candidate('ok'), candidate('bad')]))
    await act(async () => {
      await result.current.generate()
    })
    expect(result.current.jobStatus.ok.status).toBe('succeeded')
    expect(result.current.jobStatus.bad.status).toBe('failed')
    expect(result.current.generating).toBe(false)
    vi.mocked(batchIngest)
      .mockClear()
      .mockResolvedValue([job('bad', 'succeeded')])
    await act(async () => {
      await result.current.generate()
    })
    expect(batchIngest).toHaveBeenCalledExactlyOnceWith([{ arxiv_id: 'bad' }])
  })
  test('server progress resumes after remount and polling failure is not task failure', async () => {
    localStorage.setItem(
      'paper-wiki.batch-generation.v1',
      JSON.stringify({
        staged: [candidate('a')],
        jobStatus: { a: { status: 'running' } },
        jobIds: { a: 'a' }
      })
    )
    vi.mocked(getJob)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(job('a', 'succeeded'))
    const { result } = renderHook(useBatchGeneration)
    await waitFor(() =>
      expect(result.current.connectionError).toContain('重新连接')
    )
    expect(result.current.jobStatus.a.status).toBe('running')
    await waitFor(
      () => expect(result.current.jobStatus.a.status).toBe('succeeded'),
      { timeout: 3000 }
    )
    expect(result.current.connectionError).toBeNull()
  })
  test('running items cannot be removed from tracking', async () => {
    localStorage.setItem(
      'paper-wiki.batch-generation.v1',
      JSON.stringify({
        staged: [candidate('a')],
        jobStatus: { a: { status: 'running' } },
        jobIds: { a: 'a' }
      })
    )
    vi.mocked(getJob).mockResolvedValue(job('a'))
    const { result } = renderHook(useBatchGeneration)
    act(() => result.current.unstage('a'))
    expect(result.current.staged).toHaveLength(1)
  })
})

test('an interrupted submission without a job id becomes recoverable after reload', async () => {
  localStorage.setItem(
    'paper-wiki.batch-generation.v1',
    JSON.stringify({
      staged: [candidate('a')],
      jobStatus: { a: { status: 'pending' } },
      jobIds: {}
    })
  )
  vi.mocked(listJobs).mockResolvedValue([])
  const { result } = renderHook(useBatchGeneration)
  await waitFor(() => expect(result.current.jobStatus.a.status).toBe('failed'))
  expect(result.current.jobStatus.a.error).toContain('未找到对应任务')
  expect(result.current.generating).toBe(false)
})
