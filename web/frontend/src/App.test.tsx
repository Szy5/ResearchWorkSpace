import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import App from './App'

const paper = {
  slug: 'demo-paper',
  title: 'Demo Paper',
  authors: ['Ada Lovelace'],
  abstract: 'A compact demo artifact.',
  year: 2026,
  venue: 'DemoConf',
  reviewed: false,
  updated_at: '2026-07-14T00:00:00+00:00',
  has_summary: true,
  has_prior_works: true,
  has_sci_pattern: true,
  primary_pattern: 'P05',
  primary_pattern_name: 'Data & Evaluation Engineering'
}

describe('App', () => {
  let failSummarySave = false

  beforeEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
    failSummarySave = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([paper])
        }
        if (path === '/api/papers/demo-paper/summary' && init?.method === 'PATCH') {
          if (failSummarySave) {
            return Response.json({ detail: 'manifest was updated by another writer' }, { status: 409 })
          }
          return Response.json({
            slug: paper.slug,
            updated_at: '2026-07-14T00:00:01+00:00',
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nSaved.',
            prior_works: null,
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path === '/api/papers/demo-paper/meta' && init?.method === 'PATCH') {
          const body = JSON.parse(String(init.body))
          return Response.json({
            slug: paper.slug,
            updated_at: '2026-07-14T00:00:02+00:00',
            meta: {
              title: body.title ?? paper.title,
              authors: body.authors ?? paper.authors,
              abstract: body.abstract ?? paper.abstract,
              year: body.year ?? paper.year,
              venue: body.venue ?? paper.venue,
              arxiv_id: body.arxiv_id ?? '',
              tags: [],
              reviewed: Boolean(body.meta_reviewed) && Boolean(body.prior_works_reviewed),
              meta_reviewed: body.meta_reviewed ?? false,
              prior_works_reviewed: body.prior_works_reviewed ?? false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)',
            prior_works: {
              prior_works: [
                {
                  title: 'Prior Demo',
                  authors: 'Turing',
                  year: 2024,
                  arxiv_id: '',
                  role: 'Foundation',
                  relationship_sentence: 'It frames the demo.'
                }
              ],
              synthesis_narrative: 'Prior Demo frames the demo.'
            },
            sci_pattern: {
              primary_pattern: 'P05',
              primary_pattern_name: 'Data & Evaluation Engineering',
              reasoning: 'The work constructs data.'
            },
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path === '/api/papers/demo-paper/prior-works' && init?.method === 'PATCH') {
          const body = JSON.parse(String(init.body))
          return Response.json({
            slug: paper.slug,
            updated_at: '2026-07-14T00:00:01+00:00',
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)',
            prior_works: { prior_works: body.prior_works, synthesis_narrative: body.synthesis_narrative },
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path === '/api/papers/demo-paper') {
          return Response.json({
            slug: paper.slug,
            updated_at: paper.updated_at,
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)',
            prior_works: {
              prior_works: [
                {
                  title: 'Prior Demo',
                  authors: 'Turing',
                  year: 2024,
                  arxiv_id: '',
                  role: 'Foundation',
                  relationship_sentence: 'It frames the demo.'
                }
              ],
              synthesis_narrative: 'Prior Demo frames the demo.'
            },
            sci_pattern: {
              primary_pattern: 'P05',
              primary_pattern_name: 'Data & Evaluation Engineering',
              reasoning: 'The work constructs data.'
            },
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path.startsWith('/api/jobs?') || path === '/api/jobs') {
          return Response.json([])
        }
        if (path === '/api/publishing/wechat/config') {
          return Response.json({ configured: true, default_author: '', title_limit: 32, digest_limit: 120, author_limit: 8 })
        }
        if (path === '/api/papers/demo-paper/wechat') {
          return Response.json(null)
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
  })

  test('home page shows today feed by default', async () => {
    render(<App />)
    expect(await screen.findByText('还没有今日推荐快照。')).toBeInTheDocument()
    expect(screen.getAllByText('今日推荐').length).toBeGreaterThan(0)
  })

  test('renders dashboard papers under All Papers', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    expect(await screen.findByText('Demo Paper')).toBeInTheDocument()
    expect(screen.getByText('DemoConf')).toBeInTheDocument()
  })

  test('loads paper detail after selection', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    const card = await screen.findByText('Demo Paper')
    card.click()
    await waitFor(() => expect(screen.getByText(/Useful notes with/)).toBeInTheDocument())
    expect(screen.getByText('P05 Data & Evaluation Engineering')).toBeInTheDocument()
    expect(screen.getByText('Prior Demo')).toBeInTheDocument()
    expect(document.querySelector('.katex')).toBeTruthy()
    const figure = screen.getByRole('img', { name: 'Figure one' })
    expect(figure).toHaveAttribute('src', '/api/papers/demo-paper/files/assets/figures/demo.png')

    expect(document.querySelector('.image-lightbox-backdrop')).toBeNull()
    await user.click(figure)
    expect(document.querySelector('.image-lightbox-backdrop')).not.toBeNull()
  })

  test('paper detail opens the publish studio for that paper', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getByText('发布到公众号'))

    expect(await screen.findByRole('heading', { name: '公众号发布' })).toBeInTheDocument()
    expect(await screen.findByText('还没有生成公众号版本')).toBeInTheDocument()
    expect(screen.getByText('一键发布')).toBeEnabled()
  })

  test('one-click publish shows live steps and then the prepared package', async () => {
    const baseFetch = globalThis.fetch
    let prepareBody: Record<string, unknown> | null = null
    let polls = 0
    const steps = (done: boolean) => [
      { key: 'read', label: '读取精读笔记', status: 'succeeded', external: null, detail: null, started_at: null, finished_at: null },
      {
        key: 'headline',
        label: '生成标题与摘要',
        status: done ? 'succeeded' : 'running',
        external: 'LLM',
        detail: null,
        started_at: new Date().toISOString(),
        finished_at: done ? new Date().toISOString() : null
      },
      { key: 'create_draft', label: '创建草稿', status: done ? 'succeeded' : 'pending', external: '微信 API', detail: null, started_at: null, finished_at: null }
    ]
    const job = (done: boolean) => ({
      job_id: 'wx-1',
      slug: 'demo-paper',
      target: 'wechat_publish',
      status: done ? 'succeeded' : 'running',
      created_at: '2026-07-15T00:00:00+00:00',
      started_at: '2026-07-15T00:00:00+00:00',
      finished_at: done ? '2026-07-15T00:00:05+00:00' : null,
      error: null,
      result: null,
      progress: null,
      steps: steps(done)
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path === '/api/papers/demo-paper/wechat/prepare' && init?.method === 'POST') {
          prepareBody = JSON.parse(String(init.body))
          return Response.json(job(false), { status: 202 })
        }
        if (path === '/api/jobs/wx-1') {
          polls += 1
          return Response.json(job(polls >= 2))
        }
        if (path === '/api/papers/demo-paper/wechat' && polls >= 2) {
          return Response.json({
            slug: 'demo-paper',
            title: 'Demo：一句话说清贡献',
            digest: '导语',
            author: null,
            source_title: 'Demo Paper',
            cover_source: 'generated',
            cover_figure: null,
            image_count: 1,
            formula_count: 2,
            warnings: [],
            prepared_at: '2026-07-15T00:00:04+00:00',
            published_at: '2026-07-15T00:00:05+00:00',
            draft_media_id: 'draft-1',
            stale: false
          })
        }
        return baseFetch(url, init)
      })
    )

    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('公众号发布'))
    await user.click(await screen.findByText('Demo Paper'))
    await user.click(await screen.findByText('一键发布'))

    expect(await screen.findByText('正在请求 LLM')).toBeInTheDocument()
    expect(prepareBody).toMatchObject({ publish: true, regenerate_headline: true })
    await waitFor(() => expect(screen.getByDisplayValue('Demo：一句话说清贡献')).toBeInTheDocument(), { timeout: 5000 })
    expect(screen.getByText(/已写入公众号草稿箱/)).toBeInTheDocument()
    expect(screen.getByText('打开公众号后台草稿箱')).toBeInTheDocument()
  }, 10000)

  test('shows API errors from review actions', async () => {
    failSummarySave = true
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getAllByText('Edit')[1])
    await screen.findByDisplayValue(/Useful notes with/)
    await user.click(screen.getByText('Save summary'))

    expect(await screen.findByText('manifest was updated by another writer')).toBeInTheDocument()
  })

  test('editing and reviewing meta fields marks meta_reviewed and shows a success toast', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getAllByText('Edit')[0])
    const titleInput = await screen.findByDisplayValue('Demo Paper')
    await user.clear(titleInput)
    await user.type(titleInput, 'Demo Paper Corrected')
    await user.click(screen.getByText('Review'))

    expect(await screen.findByText('元信息已更新')).toBeInTheDocument()
  })

  test('editing and reviewing prior works marks prior_works_reviewed and shows a success toast', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getAllByText('Edit')[2])
    const priorTitleInput = await screen.findByDisplayValue('Prior Demo')
    await user.clear(priorTitleInput)
    await user.type(priorTitleInput, 'Prior Demo Corrected')
    await user.click(screen.getByText('Review'))

    expect(await screen.findByText('前作信息已更新')).toBeInTheDocument()
  })
})

const stagingCandidate = {
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
  score: 9.1,
  reason: ''
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

describe('App / generation tray', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
  })

  function stubFetch(onJobPoll?: () => Response | Promise<Response>) {
    let jobPolls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json({
            date: '2026-07-14',
            generated_at: '2026-07-14T00:00:00+00:00',
            corpus_size: 1,
            candidate_pool_size: 1,
            candidates: [stagingCandidate],
            degraded: false
          })
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([])
        }
        if (path.startsWith('/api/jobs?') || path === '/api/jobs') {
          return Response.json([])
        }
        if (path === '/api/papers/batch-ingest' && init?.method === 'POST') {
          return Response.json([jobResponse({ status: 'pending' })])
        }
        if (path === '/api/jobs/job-1' && onJobPoll) {
          jobPolls += 1
          return onJobPoll()
        }
        if (path.startsWith('/api/jobs?') || path === '/api/jobs') {
          return Response.json([])
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
    return () => jobPolls
  }

  test('staging a candidate and batch-generating it shows progress in the tray', async () => {
    let polls = 0
    stubFetch(() => {
      polls += 1
      if (polls < 2) {
        return Response.json(
          jobResponse({ status: 'running', started_at: '2026-07-14T00:00:01+00:00', progress: '📥 正在下载论文源码...' })
        )
      }
      return Response.json(
        jobResponse({
          status: 'succeeded',
          started_at: '2026-07-14T00:00:01+00:00',
          finished_at: '2026-07-14T00:00:02+00:00',
          result: { slug: '1706.03762' }
        })
      )
    })

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Attention Is All You Need')
    await user.click(screen.getAllByRole('checkbox')[0])

    await waitFor(() => expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0))
    await user.click(screen.getByText('批量生成'))

    await screen.findByText('📥 正在下载论文源码...')
    await waitFor(() => expect(screen.getByText('Done')).toBeInTheDocument(), { timeout: 5000 })
  }, 10000)

  test('staged candidates survive navigating away to another view', async () => {
    stubFetch()

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Attention Is All You Need')
    await user.click(screen.getAllByRole('checkbox')[0])
    await waitFor(() => expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0))

    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByRole('button', { name: '任务' }))
    expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0)

    await user.click(await screen.findByText('首页'))
    await user.click(await screen.findByRole('button', { name: '任务' }))
    expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0)
  })

  test('active server jobs remain visible after switching pages', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json({
            date: '2026-07-14',
            generated_at: '2026-07-14T00:00:00+00:00',
            corpus_size: 1,
            candidate_pool_size: 1,
            candidates: [stagingCandidate],
            degraded: false
          })
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([])
        }
        if (path.startsWith('/api/jobs?') || path === '/api/jobs') {
          return Response.json([
            jobResponse({
              job_id: 'job-html-active',
              slug: 'demo-paper',
              target: 'render_blog_html',
              status: 'running',
              started_at: '2026-07-14T00:00:01+00:00',
              progress: '正在渲染公众号 HTML...'
            })
          ])
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: '任务' }))
    expect(await screen.findByText('1 个任务进行中')).toBeInTheDocument()
    expect(screen.getAllByText(/生成 HTML/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/正在渲染公众号 HTML/).length).toBeGreaterThan(0)

    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByRole('button', { name: '任务' }))
    expect(await screen.findByText('1 个任务进行中')).toBeInTheDocument()
    expect(screen.getAllByText(/demo-paper/).length).toBeGreaterThan(0)
  })
})
