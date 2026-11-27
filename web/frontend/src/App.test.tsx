import { render, screen, waitFor, within } from '@testing-library/react'
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
  updated_at: 'v1',
  has_summary: true,
  has_prior_works: true,
  has_sci_pattern: true,
  primary_pattern: 'P05',
  primary_pattern_name: 'Data Engineering'
}
const candidate = {
  title: 'Attention Is All You Need',
  authors: ['Vaswani'],
  year: 2017,
  abstract: 'A new architecture.',
  url: 'https://arxiv.org/abs/1706.03762',
  venue: '',
  arxiv_id: '1706.03762',
  citation_count: null,
  publication_date: null,
  source: 'arxiv',
  score: 9,
  reason: ''
}
const makeDetail = (slug = paper.slug) => ({
  slug,
  updated_at: 'v1',
  meta: {
    title: slug === paper.slug ? paper.title : 'Other Paper',
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
  summary: `# ${slug === paper.slug ? paper.title : 'Other Paper'}\n\n## Motivation\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)`,
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
    synthesis_narrative: 'A lineage of ideas.'
  },
  sci_pattern: {
    primary_pattern: 'P05',
    primary_pattern_name: 'Data Engineering',
    reasoning: 'Builds data.'
  },
  references_count: 1,
  figures_count: 1,
  sections_count: 3
})
const packageData = {
  slug: 'demo-paper',
  title: '公众号标题',
  digest: '导语',
  author: '',
  source_title: 'Demo Paper',
  cover_source: 'generated',
  cover_figure: null,
  image_count: 1,
  formula_count: 2,
  warnings: [],
  prepared_at: '2026-07-15T00:00:00Z',
  published_at: null,
  draft_media_id: null,
  stale: false
}
const job = (overrides = {}) => ({
  job_id: 'job-1',
  slug: paper.slug,
  target: 'summary',
  status: 'succeeded',
  created_at: new Date().toISOString(),
  started_at: null,
  finished_at: new Date().toISOString(),
  error: null,
  result: { slug: paper.slug },
  progress: null,
  ...overrides
})

describe('Research workspace', () => {
  let detail = makeDetail()
  let failSave = false
  let hasPackage = false
  let stale = false
  let prepareCount = 0
  let draftCount = 0
  let updates: Array<{ path: string; body: Record<string, unknown> }> = []
  beforeEach(() => {
    detail = makeDetail()
    failSave = false
    hasPackage = false
    stale = false
    prepareCount = 0
    draftCount = 0
    updates = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        const body = init?.body ? JSON.parse(String(init.body)) : {}
        if (path.startsWith('/api/recommendations/today'))
          return Response.json({
            date: '2026-07-14',
            generated_at: '',
            corpus_size: 3,
            candidate_pool_size: 1,
            candidates: [candidate],
            degraded: true
          })
        if (path === '/api/papers')
          return Response.json([
            paper,
            { ...paper, slug: 'other-paper', title: 'Other Paper' }
          ])
        if (path.startsWith('/api/search')) return Response.json([candidate])
        if (path.startsWith('/api/jobs?')) return Response.json([])
        if (path === '/api/papers/demo-paper/wechat')
          return Response.json(hasPackage ? { ...packageData, stale } : null)
        if (path === '/api/publishing/wechat/config')
          return Response.json({
            configured: true,
            default_author: '',
            title_limit: 32,
            digest_limit: 120,
            author_limit: 8
          })
        if (path === '/api/papers/demo-paper/wechat/prepare') {
          prepareCount++
          hasPackage = true
          updates.push({ path, body })
          return Response.json(
            job({ job_id: 'prepare', target: 'wechat_prepare' })
          )
        }
        if (path === '/api/papers/demo-paper/wechat/publish') {
          draftCount++
          return Response.json(
            job({ job_id: 'publish', target: 'wechat_publish' })
          )
        }
        if (path.startsWith('/api/jobs/'))
          return Response.json(
            job({
              target: path.endsWith('publish')
                ? 'wechat_publish'
                : 'wechat_prepare'
            })
          )
        if (
          path === '/api/papers/demo-paper' &&
          (!init?.method || init.method === 'GET')
        )
          return Response.json(detail)
        if (path === '/api/papers/other-paper')
          return Response.json(makeDetail('other-paper'))
        if (
          path.startsWith('/api/papers/demo-paper/') &&
          init?.method === 'PATCH'
        ) {
          updates.push({ path, body })
          if (failSave)
            return Response.json(
              { detail: 'manifest was updated by another writer' },
              { status: 409 }
            )
          detail = { ...detail, updated_at: 'v' + (updates.length + 1) }
          if (path.endsWith('/summary')) detail.summary = body.summary
          if (path.endsWith('/meta'))
            detail.meta = {
              ...detail.meta,
              ...Object.fromEntries(
                Object.entries(body).filter(
                  ([key]) => key !== 'expected_updated_at'
                )
              )
            }
          if (path.endsWith('/prior-works'))
            detail.prior_works = {
              prior_works: body.prior_works,
              synthesis_narrative: body.synthesis_narrative
            }
          return Response.json(detail)
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
  })
  function reader() {
    window.history.replaceState(null, '', '#/papers/demo-paper')
    return render(<App />)
  }
  test('selection stays in place and does not interrupt with a modal', async () => {
    const user = userEvent.setup()
    render(<App />)
    const checkbox = await screen.findByRole('checkbox', {
      name: `选择 ${candidate.title}`
    })
    await user.click(checkbox)
    expect(checkbox).toBeChecked()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: candidate.title })
    ).toBeInTheDocument()
    await user.click(checkbox)
    expect(checkbox).not.toBeChecked()
  })
  test('candidate previews are separate from selection and restore focus', async () => {
    const user = userEvent.setup()
    render(<App />)
    const title = await screen.findByRole('button', { name: candidate.title })
    await user.click(title)
    expect(screen.getByRole('dialog', { name: '论文预览' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: '选择这篇论文' })
    ).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(title).toHaveFocus()
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })
  test('search results and selection survive navigation and remount', async () => {
    const user = userEvent.setup()
    const app = render(<App />)
    await user.type(
      screen.getByRole('textbox', { name: '搜索 arXiv 或添加论文' }),
      'attention'
    )
    await user.click(screen.getByRole('button', { name: '搜索' }))
    await screen.findByRole('heading', { name: /检索结果/ })
    await user.click(screen.getAllByRole('checkbox')[0])
    await user.click(screen.getByRole('button', { name: '论文库' }))
    await user.click(screen.getByRole('button', { name: '发现' }))
    expect(
      screen.getByRole('textbox', { name: '搜索 arXiv 或添加论文' })
    ).toHaveValue('attention')
    expect(screen.getAllByRole('checkbox')[0]).toBeChecked()
    app.unmount()
    render(<App />)
    expect(
      screen.getByRole('textbox', { name: '搜索 arXiv 或添加论文' })
    ).toHaveValue('attention')
    expect(screen.getAllByRole('checkbox')[0]).toBeChecked()
  })
  test('deep links show one paper title, formatted math and real asset images', async () => {
    const user = userEvent.setup()
    reader()
    await screen.findByText(/Useful notes with/)
    expect(
      within(screen.getByRole('region', { name: '论文阅读区' })).getAllByRole(
        'heading',
        { name: 'Demo Paper' }
      )
    ).toHaveLength(1)
    expect(document.querySelector('.katex')).not.toBeNull()
    const figure = screen.getByAltText('Figure one')
    expect(figure).toHaveAttribute(
      'src',
      '/api/papers/demo-paper/files/assets/figures/demo.png'
    )
    await user.click(
      screen.getByRole('button', { name: '放大图片：Figure one' })
    )
    expect(screen.getByRole('dialog', { name: '论文配图' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  test('unsaved changes block leaving and save failures preserve the draft', async () => {
    const user = userEvent.setup()
    reader()
    await screen.findByText(/Useful notes with/)
    await user.click(screen.getByRole('button', { name: '编辑笔记' }))
    const editor = screen.getByLabelText('精读笔记 Markdown')
    await user.clear(editor)
    await user.type(editor, 'My unsaved idea')
    await user.click(screen.getByRole('button', { name: '发现' }))
    const modal = screen.getByRole('dialog', { name: '还有未保存的修改' })
    failSave = true
    await user.click(within(modal).getByRole('button', { name: '保存并离开' }))
    expect(await within(modal).findByRole('alert')).toHaveTextContent(
      'manifest was updated'
    )
    expect(window.location.hash).toContain('/papers/demo-paper')
    await user.click(within(modal).getByRole('button', { name: '继续编辑' }))
    expect(editor).toHaveValue('My unsaved idea')
    await user.click(screen.getByRole('button', { name: '发现' }))
    await user.click(screen.getByRole('button', { name: '放弃修改' }))
    expect(window.location.hash).toBe('#/home')
  })
  test('save and leave persists content, then navigates', async () => {
    const user = userEvent.setup()
    reader()
    await screen.findByText(/Useful notes with/)
    await user.click(screen.getByRole('button', { name: '编辑笔记' }))
    await user.type(screen.getByLabelText('精读笔记 Markdown'), '\nMy idea')
    await user.click(screen.getByRole('button', { name: '发现' }))
    await user.click(screen.getByRole('button', { name: '保存并离开' }))
    await waitFor(() => expect(window.location.hash).toBe('#/home'))
    expect(updates[0].body.summary).toContain('My idea')
    expect(updates[0].body).not.toHaveProperty('meta_reviewed')
  })
  test('metadata save is independent from explicit human verification', async () => {
    const user = userEvent.setup()
    reader()
    await screen.findByText(/Useful notes with/)
    await user.click(screen.getByRole('button', { name: '核验' }))
    await user.click(screen.getByRole('button', { name: '编辑元信息' }))
    const title = screen.getByLabelText('论文标题')
    await user.clear(title)
    await user.type(title, 'Corrected Title')
    await user.click(screen.getByRole('button', { name: '保存元信息' }))
    await screen.findByText(/修改已保存/)
    expect(updates[0].body.title).toBe('Corrected Title')
    expect(updates[0].body).not.toHaveProperty('meta_reviewed')
    await user.click(screen.getAllByRole('button', { name: '确认核验' })[0])
    await screen.findByText(/元信息与精读笔记已标记为人工核验通过/)
    expect(updates[1].body.meta_reviewed).toBe(true)
    expect(updates[1].body).not.toHaveProperty('prior_works_reviewed')
  })
  test('prior work editing is protected and ordinary save does not verify it', async () => {
    const user = userEvent.setup()
    reader()
    await screen.findByText(/Useful notes with/)
    await user.click(screen.getByRole('button', { name: '前作与范式' }))
    await user.click(screen.getByRole('button', { name: '编辑前作' }))
    const title = screen.getByLabelText('前作 1 标题')
    await user.clear(title)
    await user.type(title, 'Corrected Prior')
    await user.click(screen.getByRole('button', { name: /Other Paper/ }))
    await user.click(screen.getByRole('button', { name: '继续编辑' }))
    expect(title).toHaveValue('Corrected Prior')
    await user.click(screen.getAllByRole('button', { name: '保存修改' })[0])
    await screen.findByText(/修改已保存/)
    expect(updates).toHaveLength(1)
    expect(updates[0].path).toContain('/prior-works')
    expect(updates[0].body.prior_works).toMatchObject([
      { title: 'Corrected Prior' }
    ])
  })
  test('browser back/forward restores library query and selected paper', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: '论文库' }))
    await screen.findByRole('button', { name: /Other Paper/ })
    await user.type(
      screen.getByRole('textbox', { name: '搜索我的论文' }),
      'Demo'
    )
    await user.click(screen.getByRole('button', { name: /Demo Paper Ada/ }))
    await screen.findByText(/Useful notes with/)
    window.history.back()
    await waitFor(() => expect(window.location.hash).toBe('#/papers?q=Demo'))
    expect(screen.getByRole('textbox', { name: '搜索我的论文' })).toHaveValue(
      'Demo'
    )
    window.history.forward()
    await screen.findByText(/Useful notes with/)
    expect(window.location.hash).toBe('#/papers/demo-paper?q=Demo')
  })
  test('cancelling browser back preserves both the draft and the history stack', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: '论文库' }))
    await user.click(
      await screen.findByRole('button', { name: /Demo Paper Ada/ })
    )
    await screen.findByText(/Useful notes with/)
    await user.click(screen.getByRole('button', { name: '编辑笔记' }))
    await user.type(
      screen.getByLabelText('精读笔记 Markdown'),
      '\nDraft in progress'
    )
    window.history.back()
    await screen.findByRole('dialog', { name: '还有未保存的修改' })
    expect(window.location.hash).toBe('#/papers/demo-paper')
    await user.click(screen.getByRole('button', { name: '继续编辑' }))
    expect(
      (screen.getByLabelText('精读笔记 Markdown') as HTMLTextAreaElement).value
    ).toContain('Draft in progress')
    window.history.back()
    await screen.findByRole('dialog', { name: '还有未保存的修改' })
    await user.click(screen.getByRole('button', { name: '放弃修改' }))
    await waitFor(() => expect(window.location.hash).toBe('#/papers'))
    window.history.forward()
    await screen.findByText(/Useful notes with/)
    expect(window.location.hash).toBe('#/papers/demo-paper')
  })

  test('publication requires a preview, then an explicit draft action', async () => {
    const user = userEvent.setup()
    reader()
    await screen.findByText(/Useful notes with/)
    await user.click(screen.getByRole('button', { name: '生成文章' }))
    await screen.findByText('还没有生成公众号版本')
    expect(
      screen.queryByRole('button', { name: '一键发布' })
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '生成文章预览' }))
    await screen.findByDisplayValue('公众号标题')
    expect(prepareCount).toBe(1)
    expect(draftCount).toBe(0)
    expect(updates[0].body.publish).toBe(false)
    await user.dblClick(screen.getByRole('button', { name: '创建公众号草稿' }))
    await screen.findByText(/已写入公众号草稿箱/)
    expect(draftCount).toBe(1)
    await user.click(screen.getByRole('button', { name: '返回来源论文' }))
    await screen.findByText(/Useful notes with/)
  })
  test('uploaded-document task links restore the form and local draft on return', async () => {
    const base = fetch
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path === '/api/publishing/markdown/doc-1')
          return Response.json({
            document_id: 'doc-1',
            filename: 'note.md',
            title: 'Uploaded Note',
            created_at: '',
            html_path: 'article.html',
            cover_path: null,
            html: '<p>Preview</p>'
          })
        if (path === '/api/publishing/markdown') return Response.json([])
        return base(url, init)
      })
    )
    window.history.replaceState(null, '', '#/publish?document=doc-1')
    const user = userEvent.setup()
    render(<App />)
    const title = await screen.findByDisplayValue('Uploaded Note')
    await user.clear(title)
    await user.type(title, 'My edited headline')
    await user.click(screen.getByRole('button', { name: '发现' }))
    await user.click(screen.getByRole('button', { name: '保存并离开' }))
    await waitFor(() => expect(window.location.hash).toBe('#/home'))
    window.history.back()
    expect(
      await screen.findByDisplayValue('My edited headline')
    ).toBeInTheDocument()
    expect(draftCount).toBe(0)
  })

  test('stale preview cannot be submitted as a draft', async () => {
    hasPackage = true
    stale = true
    window.history.replaceState(null, '', '#/publish/demo-paper')
    render(<App />)
    expect(
      await screen.findByRole('button', { name: '创建公众号草稿' })
    ).toBeDisabled()
  })
})

describe('Async reader boundaries', () => {
  test('a slower previous paper response cannot replace the selected paper', async () => {
    let finishFirst!: (response: Response) => void
    const pending = new Promise<Response>((resolve) => {
      finishFirst = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL) => {
        const path = String(url)
        if (path === '/api/papers')
          return Response.json([
            paper,
            { ...paper, slug: 'other-paper', title: 'Other Paper' }
          ])
        if (path === '/api/papers/demo-paper') return pending
        if (path === '/api/papers/other-paper')
          return Response.json(makeDetail('other-paper'))
        if (path.startsWith('/api/recommendations')) return Response.json(null)
        if (path.startsWith('/api/jobs')) return Response.json([])
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
    window.history.replaceState(null, '', '#/papers/demo-paper')
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Other Paper/ }))
    const reader = await screen.findByRole('region', { name: '论文阅读区' })
    expect(
      within(reader).getByRole('heading', { name: 'Other Paper' })
    ).toBeInTheDocument()
    finishFirst(Response.json(makeDetail()))
    await waitFor(() =>
      expect(
        within(reader).queryByRole('heading', { name: 'Demo Paper' })
      ).not.toBeInTheDocument()
    )
  })
})
