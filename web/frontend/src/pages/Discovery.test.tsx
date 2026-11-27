import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import Home, { arxivIdFromInput } from './Home'
const candidate = {
  title: 'Attention Is All You Need',
  authors: ['Vaswani'],
  year: 2017,
  abstract: 'A simple architecture.',
  url: '',
  venue: '',
  arxiv_id: '1706.03762',
  citation_count: null,
  publication_date: null,
  source: 'arxiv',
  score: 9
}
const snapshot = {
  date: '2020-01-01',
  generated_at: '',
  corpus_size: 5,
  candidate_pool_size: 1,
  candidates: [
    {
      ...candidate,
      display_summary: '一句话讲清注意力',
      reason: '与《Deep Learning》相似度92%'
    }
  ],
  degraded: true
}
describe('Discovery interactions', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today'))
          return Response.json(snapshot)
        if (path.startsWith('/api/jobs?')) return Response.json([])
        if (path.startsWith('/api/search')) return Response.json([candidate])
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
  })
  test('selected papers remain visible and can be unselected', async () => {
    const user = userEvent.setup()
    const onUnstage = vi.fn()
    render(
      <Home
        stagedKeys={new Set(['1706.03762'])}
        onStage={vi.fn()}
        onUnstage={onUnstage}
        onIngested={vi.fn()}
      />
    )
    const checkbox = await screen.findByRole('checkbox', { name: /取消选择/ })
    expect(checkbox).toBeChecked()
    await user.click(checkbox)
    expect(onUnstage).toHaveBeenCalledWith('1706.03762')
    expect(
      screen.getByRole('button', { name: candidate.title })
    ).toBeInTheDocument()
  })
  test('explains stale snapshots and degraded ranking without unrelated thumbnails', async () => {
    render(
      <Home stagedKeys={new Set()} onStage={vi.fn()} onIngested={vi.fn()} />
    )
    await screen.findByRole('heading', { name: '最近推荐' })
    expect(screen.getByText(/尚未更新到今天/)).toBeInTheDocument()
    expect(screen.getByText(/未经兴趣相似度排序/)).toBeInTheDocument()
    expect(screen.getByText(/与"Deep Learning"相似度92%/)).toBeInTheDocument()
    expect(screen.getByText('一句话讲清注意力')).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
  })
  test('invalid years do not submit requests', async () => {
    const user = userEvent.setup()
    render(
      <Home stagedKeys={new Set()} onStage={vi.fn()} onIngested={vi.fn()} />
    )
    await user.type(screen.getByRole('textbox'), 'attention')
    await user.click(screen.getByRole('button', { name: /年份/ }))
    await user.clear(screen.getByLabelText('起始年份'))
    await user.type(screen.getByLabelText('起始年份'), '2099')
    await user.click(screen.getByRole('button', { name: '搜索' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请输入有效年份')
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(([url]) => String(url).startsWith('/api/search'))
    ).toBe(false)
  })
  test('failed search preserves previous results and labels their query', async () => {
    const user = userEvent.setup()
    render(
      <Home stagedKeys={new Set()} onStage={vi.fn()} onIngested={vi.fn()} />
    )
    await user.type(screen.getByRole('textbox'), 'attention')
    await user.click(screen.getByRole('button', { name: '搜索' }))
    await screen.findByRole('heading', { name: /检索结果/ })
    vi.mocked(fetch).mockImplementation(async () =>
      Response.json({ detail: 'Network unavailable' }, { status: 503 })
    )
    await user.clear(screen.getByRole('textbox'))
    await user.type(screen.getByRole('textbox'), 'memory')
    await user.click(screen.getByRole('button', { name: '搜索' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '上次成功检索“attention”'
    )
    expect(
      screen.getByRole('heading', { name: /检索结果/ })
    ).toBeInTheDocument()
  })
  test('known papers open directly instead of being generated twice', async () => {
    const user = userEvent.setup()
    const onOpenPaper = vi.fn()
    render(
      <Home
        stagedKeys={new Set()}
        onStage={vi.fn()}
        onIngested={vi.fn()}
        onOpenPaper={onOpenPaper}
        papers={[{ slug: '1706.03762', title: candidate.title } as never]}
      />
    )
    await user.click(await screen.findByRole('button', { name: '打开论文' }))
    expect(onOpenPaper).toHaveBeenCalledWith('1706.03762')
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })
  test('arxiv URLs use the explicit add flow and optional immediate generation', async () => {
    const base = fetch
    const onIngested = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url) === '/api/papers/fetch') {
          expect(JSON.parse(String(init?.body))).toMatchObject({
            arxiv_id: '1706.03762',
            and_ingest: true
          })
          return Response.json({ job_id: 'fetch-1' })
        }
        if (String(url) === '/api/jobs/fetch-1')
          return Response.json({
            status: 'succeeded',
            result: { slug: '1706.03762' }
          })
        return base(url, init)
      })
    )
    const user = userEvent.setup()
    render(
      <Home stagedKeys={new Set()} onStage={vi.fn()} onIngested={onIngested} />
    )
    await user.type(
      screen.getByRole('textbox'),
      'https://arxiv.org/abs/1706.03762'
    )
    await user.click(screen.getByLabelText(/下载后立即生成/))
    await user.click(screen.getByRole('button', { name: '添加论文' }))
    await waitFor(() => expect(onIngested).toHaveBeenCalledWith('1706.03762'))
  })
  test.each([
    ['1706.03762', '1706.03762'],
    ['https://arxiv.org/pdf/2401.12345v2.pdf', '2401.12345v2'],
    ['arXiv:hep-th/9901001', 'hep-th/9901001'],
    ['graph retrieval', null],
    ['https://evil.example/1706.03762', null]
  ])('recognizes paper input %s', (value, expected) => {
    expect(arxivIdFromInput(value)).toBe(expected)
  })
})
