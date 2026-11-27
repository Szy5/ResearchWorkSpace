import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Compass,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Settings,
  Sparkles
} from 'lucide-react'
import { listPapers, PaperListItem } from './api/client'
import Dashboard from './pages/Dashboard'
import PaperDetail from './pages/PaperDetail'
import Home from './pages/Home'
import Management from './pages/Management'
import WeChatStudio from './pages/WeChatStudio'
import SideNav from './components/SideNav'
import ActivityDrawer from './components/ActivityDrawer'
import { useBatchGeneration } from './hooks/useBatchGeneration'
import { useActivityJobs } from './hooks/useActivityJobs'
import useWorkspaceRoute, { WorkspaceRoute } from './hooks/useWorkspaceRoute'
import {
  NavigationGuardProvider,
  useNavigationGuard
} from './context/NavigationGuard'
import useScrollMemory from './hooks/useScrollMemory'
import { readStored, writeStored } from './utils/storage'

export default function App() {
  return (
    <NavigationGuardProvider>
      <Workspace />
    </NavigationGuardProvider>
  )
}
function Workspace() {
  const { route, navigate } = useWorkspaceRoute()
  const { request: requestNavigation } = useNavigationGuard()
  const [readerRefresh, setReaderRefresh] = useState(0)
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activityOpen, setActivityOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    readStored('paper-wiki.sidebar-collapsed', false)
  )
  const [listCollapsed, setListCollapsed] = useState(() =>
    readStored('paper-wiki.list-collapsed', false)
  )
  const [recentSlug, setRecentSlug] = useState<string | null>(() =>
    readStored('paper-wiki.recent-paper', null)
  )
  const main = useRef<HTMLElement>(null)
  const requestId = useRef(0)
  const batch = useBatchGeneration()
  const jobs = useActivityJobs()
  const libraryContext = useRef<WorkspaceRoute>({ view: 'papers' })
  if (route.view === 'papers') libraryContext.current = route
  useScrollMemory(main, `paper-wiki.page-scroll.${route.view}`)
  const loadPapers = useCallback(async () => {
    const id = ++requestId.current
    setLoading(true)
    try {
      const next = await listPapers()
      if (id === requestId.current) {
        setPapers(next)
        setError(null)
      }
    } catch (err) {
      if (id === requestId.current)
        setError(err instanceof Error ? err.message : String(err))
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    void loadPapers()
  }, [loadPapers])
  const finished = Object.values(batch.jobStatus).filter(
    (state) => state.status === 'succeeded'
  ).length
  useEffect(() => {
    if (finished) void loadPapers()
  }, [finished, loadPapers])
  useEffect(() => {
    if (batch.generating) void jobs.refresh()
  }, [batch.generating, jobs.refresh])
  useEffect(() => {
    if (route.view === 'papers' && route.slug) {
      setRecentSlug(route.slug)
      writeStored('paper-wiki.recent-paper', route.slug)
    }
  }, [route.view, route.slug])
  const query = route.q || ''
  const visiblePapers = useMemo(
    () =>
      papers.filter((paper) => {
        const matches =
          route.reviewed === undefined || paper.reviewed === route.reviewed
        return (
          matches &&
          (!query ||
            `${paper.title} ${paper.authors.join(' ')} ${paper.slug} ${paper.arxiv_id || ''}`
              .toLowerCase()
              .includes(query.toLowerCase()))
        )
      }),
    [papers, route.reviewed, query]
  )
  function go(next: WorkspaceRoute) {
    navigate(next)
    setActivityOpen(false)
  }
  function openPaper(slug: string) {
    go({ ...libraryContext.current, view: 'papers', slug })
  }
  const pendingCount = papers.filter((paper) => !paper.reviewed).length
  const selectable = batch.staged.filter(
    (item) =>
      !['pending', 'running', 'succeeded'].includes(
        batch.jobStatus[item.key]?.status ?? 'idle'
      )
  )
  const activeIds = new Set([
    ...jobs.activeJobs.map((job) => job.job_id),
    ...Object.entries(batch.jobIds)
      .filter(([key]) =>
        ['pending', 'running'].includes(batch.jobStatus[key]?.status)
      )
      .map(([, id]) => id)
  ])
  const navItems = [
    {
      key: 'home',
      label: '发现',
      icon: <Compass size={18} />,
      active: route.view === 'home',
      onClick: () => go({ view: 'home' })
    },
    {
      key: 'papers',
      label: '论文库',
      icon: <BookOpen size={18} />,
      active: route.view === 'papers' && route.reviewed === undefined,
      onClick: () =>
        go({ ...libraryContext.current, view: 'papers', reviewed: undefined })
    },
    {
      key: 'review',
      label: `待核验 (${pendingCount})`,
      icon: <CheckCircle2 size={17} />,
      active: route.view === 'papers' && route.reviewed === false,
      onClick: () =>
        go({ ...libraryContext.current, view: 'papers', reviewed: false })
    },
    {
      key: 'publish',
      label: '写作与发布',
      icon: <Send size={17} />,
      active: route.view === 'publish',
      onClick: () =>
        go({
          view: 'publish',
          slug: route.view === 'papers' ? route.slug : undefined
        })
    },
    {
      key: 'manage',
      label: '管理',
      icon: <Settings size={17} />,
      active: route.view === 'manage',
      onClick: () => go({ view: 'manage' })
    }
  ]
  return (
    <div className="app-shell">
      <SideNav
        items={navItems}
        onBrandClick={() => go({ view: 'home' })}
        activityCount={activeIds.size + selectable.length}
        activityActive={activeIds.size > 0}
        onOpenActivity={() => setActivityOpen(true)}
        collapsed={sidebarCollapsed}
        onToggle={() =>
          setSidebarCollapsed((prev) => {
            writeStored('paper-wiki.sidebar-collapsed', !prev)
            return !prev
          })
        }
      />
      <div className="workspace-body">
        <header className="workspace-topbar">
          <div className="flex min-w-0 items-center gap-2 text-xs text-body">
            <span className="hidden sm:inline">我的工作台</span>
            <span className="hidden text-line-strong sm:inline">/</span>
            <span className="text-ink">
              {
                {
                  home: '发现',
                  papers: '论文库',
                  publish: '写作与发布',
                  manage: '管理'
                }[route.view]
              }
            </span>
          </div>
          <button className="topbar-task" onClick={() => setActivityOpen(true)}>
            {activeIds.size ? (
              <>
                <span className="status-dot" />
                {activeIds.size} 个任务进行中
              </>
            ) : (
              <>
                任务中心 <ArrowRight size={12} />
              </>
            )}
          </button>
        </header>
        <main
          ref={main}
          className={`workspace-main ${route.view === 'papers' ? 'is-library' : ''}`}
          id="main-content"
        >
          <div hidden={route.view !== 'home'}>
            {error && (
              <p role="alert" className="alert-warn mx-6 mt-4">
                论文库暂时无法同步，已入库状态可能不完整。
                <button
                  className="ml-3 underline"
                  onClick={() => void loadPapers()}
                >
                  重新同步
                </button>
              </p>
            )}
            <Home
              stagedKeys={batch.stagedKeys}
              jobStatus={batch.jobStatus}
              papers={papers}
              recentSlug={recentSlug}
              onStage={batch.stage}
              onUnstage={batch.unstage}
              onIngested={(slug) => {
                void loadPapers()
                openPaper(slug)
              }}
              onOpenPaper={openPaper}
            />
          </div>
          {route.view === 'papers' && (
            <div
              className={`library-workspace ${route.slug ? 'has-paper' : ''} ${listCollapsed && route.slug ? 'list-collapsed' : ''}`}
            >
              <div className="library-column">
                <Dashboard
                  papers={visiblePapers}
                  selectedSlug={route.slug || null}
                  loading={loading}
                  error={error}
                  reviewedFilter={route.reviewed}
                  onSelect={openPaper}
                  onReviewedFilter={(reviewed) => go({ ...route, reviewed })}
                  query={query}
                  onQuery={(q) =>
                    navigate({ ...route, q: q || undefined }, true)
                  }
                  onRetry={() => void loadPapers()}
                />
              </div>
              <div className="reader-column">
                <div className="reader-navigation">
                  {route.slug && (
                    <>
                      <button
                        className="action-button reader-back"
                        onClick={() => go({ ...route, slug: undefined })}
                      >
                        <ArrowLeft size={14} />
                        返回列表
                      </button>
                      <button
                        className="icon-button reader-list-toggle"
                        aria-label={
                          listCollapsed ? '展开论文列表' : '收起论文列表'
                        }
                        onClick={() =>
                          setListCollapsed((prev) => {
                            writeStored('paper-wiki.list-collapsed', !prev)
                            return !prev
                          })
                        }
                      >
                        {listCollapsed ? (
                          <PanelLeftOpen size={16} />
                        ) : (
                          <PanelLeftClose size={16} />
                        )}
                      </button>
                      <span className="text-xs text-muted">精读工作区</span>
                    </>
                  )}
                </div>
                <PaperDetail
                  refreshKey={readerRefresh}
                  slug={route.slug || null}
                  onChanged={() => void loadPapers()}
                  onOpenPublish={(slug) => go({ view: 'publish', slug })}
                />
              </div>
            </div>
          )}
          {route.view === 'publish' && (
            <div className="workspace-page">
              {route.slug && (
                <button
                  className="action-button mb-5"
                  onClick={() => openPaper(route.slug!)}
                >
                  <ArrowLeft size={14} />
                  返回来源论文
                </button>
              )}
              <WeChatStudio
                key={route.slug || route.document || 'studio'}
                initialSlug={route.slug || null}
                initialDocumentId={route.document}
              />
            </div>
          )}
          {route.view === 'manage' && (
            <div className="workspace-page">
              <Management
                onChanged={() => void loadPapers()}
                onOpenPaper={openPaper}
              />
            </div>
          )}
        </main>
        {route.view === 'home' && batch.staged.length > 0 && (
          <div className="selection-bar" role="status">
            <span>
              <strong>{batch.staged.length}</strong> 篇已选
              <span className="ml-2 hidden text-muted sm:inline">
                {selectable.length
                  ? '准备生成精读笔记与分析'
                  : '查看生成进度与结果'}
              </span>
            </span>
            <div className="flex items-center gap-2">
              <button
                className="action-button"
                onClick={() => setActivityOpen(true)}
              >
                查看已选
              </button>
              <button
                className="button-primary h-9"
                disabled={batch.sending || !selectable.length}
                onClick={() => {
                  void batch.generate(() => void jobs.refresh())
                }}
              >
                <Sparkles size={14} />
                {batch.sending
                  ? '提交中…'
                  : `生成精读${selectable.length ? ` (${selectable.length})` : ''}`}
              </button>
            </div>
          </div>
        )}
      </div>
      <ActivityDrawer
        open={activityOpen}
        onClose={() => setActivityOpen(false)}
        {...batch}
        activeJobs={jobs.activeJobs}
        recentJobs={jobs.recentJobs}
        connectionError={batch.connectionError || jobs.error}
        onUnstage={batch.unstage}
        onGenerate={() => void batch.generate(() => void jobs.refresh())}
        onRetry={(key) => void batch.generate(() => void jobs.refresh(), key)}
        onDismissJob={jobs.dismissJob}
        onDismissAllRecent={jobs.dismissAllRecent}
        onOpenManage={() => go({ view: 'manage' })}
        onOpenResult={(slug, target) => {
          setActivityOpen(false)
          requestNavigation(() => {
            if (target === 'recommend_refresh' || target === 'fetch')
              go({ view: 'home' })
            else if (target === 'markdown_publish')
              go({ view: 'publish', document: slug })
            else if (
              target?.includes('wechat') ||
              target === 'render_blog_html'
            )
              go({ view: 'publish', slug })
            else {
              setReaderRefresh((value) => value + 1)
              openPaper(slug)
            }
          })
        }}
      />
    </div>
  )
}
