import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import Home from './Home'

const candidate = {
  title: 'Attention Is All You Need',
  authors: ['Vaswani'],
  year: 2017,
  abstract: 'A new simple network architecture.',
  url: 'https://arxiv.org/abs/1706.03762',
  venue: '',
  arxiv_id: '1706.03762',
  citation_count: null,
  publication_date: null,
  source: 'arxiv',
  score: 9.1
}

function jobResponse(overrides: Record<string, unknown>) {
  return {
    job_id: 'job-1',
    slug: '1706.03762',
    target: 'fetch_and_ingest',
    status: 'pending',
    created_at: '2026-07-14T00:00:00+00:00',
    started_at: null,
    finished_at: null,
    error: null,
    result: null,
    progress: null,
    ...overrides
  }
}

describe('Home / RecommendedSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  test('staging a recommended candidate removes it from the pool and reports it via onStage', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json({
            date: '2026-07-14',
            generated_at: '2026-07-14T00:00:00+00:00',
            corpus_size: 5,
            candidate_pool_size: 1,
            candidates: [{ ...candidate, reason: '与 "Deep Learning" 相似度92%' }],
            degraded: false
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    const onStage = vi.fn()
    const user = userEvent.setup()
    render(<Home stagedKeys={new Set()} onStage={onStage} onIngested={vi.fn()} />)

    await screen.findByText('Attention Is All You Need')
    expect(screen.getByText(/相似度92%/)).toBeInTheDocument()

    await user.click(screen.getAllByRole('checkbox')[0])
    expect(onStage).toHaveBeenCalledWith([{ key: '1706.03762', candidate: expect.objectContaining({ arxiv_id: '1706.03762' }), slug: undefined }])
  })

  test('a candidate already present in stagedKeys is not shown in the pool', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json({
            date: '2026-07-14',
            generated_at: '2026-07-14T00:00:00+00:00',
            corpus_size: 5,
            candidate_pool_size: 1,
            candidates: [{ ...candidate, reason: '' }],
            degraded: false
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    render(<Home stagedKeys={new Set(['1706.03762'])} onStage={vi.fn()} onIngested={vi.fn()} />)

    await screen.findByText('今日候选都已加入生成暂存区。')
    expect(screen.queryByText('Attention Is All You Need')).not.toBeInTheDocument()
  })

  test('prefers the LLM display_summary over the raw abstract', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json({
            date: '2026-07-14',
            generated_at: '2026-07-14T00:00:00+00:00',
            corpus_size: 5,
            candidate_pool_size: 1,
            candidates: [{ ...candidate, reason: '', display_summary: '一句话讲清楚注意力机制。' }],
            degraded: false
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    render(<Home stagedKeys={new Set()} onStage={vi.fn()} onIngested={vi.fn()} />)

    await screen.findByText('一句话讲清楚注意力机制。')
    expect(screen.queryByText('A new simple network architecture.')).not.toBeInTheDocument()
  })
})

describe('Home / SearchSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  test('checking a keyword search result stages it directly', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/search')) {
          return Response.json([candidate])
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    const onStage = vi.fn()
    const user = userEvent.setup()
    render(<Home stagedKeys={new Set()} onStage={onStage} onIngested={vi.fn()} />)

    await user.type(screen.getByPlaceholderText(/transformer attention mechanism/), 'attention')
    await user.click(screen.getByText('搜索'))

    await screen.findByText('Attention Is All You Need')
    await user.click(screen.getByRole('checkbox'))

    expect(onStage).toHaveBeenCalledWith([{ key: '1706.03762', candidate, slug: undefined }])
  })

  test('fetch by arXiv id with immediate ingest notifies the caller', async () => {
    let fetchPolls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path === '/api/papers/fetch' && init?.method === 'POST') {
          return Response.json(jobResponse({ status: 'pending', slug: '1706.03762' }))
        }
        if (path === '/api/jobs/job-1') {
          fetchPolls += 1
          if (fetchPolls < 2) {
            return Response.json(jobResponse({ status: 'running', progress: '📄 已找到论文主文件，正在下载 PDF...' }))
          }
          return Response.json(jobResponse({ status: 'succeeded', result: { slug: '1706.03762' } }))
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    const onIngested = vi.fn()
    const user = userEvent.setup()
    render(<Home stagedKeys={new Set()} onStage={vi.fn()} onIngested={onIngested} />)

    await user.click(screen.getByText('或按 arXiv ID 直接添加'))
    await user.type(screen.getByPlaceholderText('2401.12345'), '1706.03762')
    await user.click(screen.getByLabelText(/拉取后立即生成/))
    await user.click(screen.getByText('拉取'))

    await screen.findByText('📄 已找到论文主文件，正在下载 PDF...')
    await waitFor(() => expect(onIngested).toHaveBeenCalledWith('1706.03762'), { timeout: 5000 })
  }, 10000)
})
