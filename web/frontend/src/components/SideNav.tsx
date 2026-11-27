import { ReactElement } from 'react'
import { BookOpen, ListTodo, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
export type SideNavItem = {
  key: string
  label: string
  icon: ReactElement
  active: boolean
  onClick: () => void
}
type Props = {
  items: SideNavItem[]
  onBrandClick: () => void
  activityCount?: number
  activityActive?: boolean
  onOpenActivity?: () => void
  collapsed?: boolean
  onToggle?: () => void
}
export default function SideNav({
  items,
  onBrandClick,
  activityCount = 0,
  activityActive,
  onOpenActivity,
  collapsed,
  onToggle
}: Props) {
  return (
    <nav
      className={`app-sidebar ${collapsed ? 'is-compact' : ''}`}
      aria-label="主导航"
    >
      <button
        className="brand"
        onClick={onBrandClick}
        aria-label="Paper-Wiki 发现页"
      >
        <BookOpen size={23} />
        <span className="nav-label">
          Paper<span className="font-normal text-muted"> / </span>Wiki
        </span>
      </button>
      <p className="nav-section-label nav-label">个人研究工作台</p>
      <div className="nav-items">
        {items
          .filter((item) => item.key !== 'manage')
          .map((item) => (
            <button
              key={item.key}
              className={`side-nav-button ${item.active ? 'is-active' : ''} ${item.key === 'review' ? 'nav-review' : ''}`}
              title={item.label}
              aria-label={item.label}
              aria-current={item.active ? 'page' : undefined}
              onClick={item.onClick}
            >
              {item.icon}
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
      </div>
      <div className="nav-footer">
        {onOpenActivity && (
          <button
            className="side-nav-button"
            title="任务中心"
            aria-label="任务中心"
            onClick={onOpenActivity}
          >
            <span className="relative">
              <ListTodo size={17} />
              {activityActive && <i className="task-dot" />}
            </span>
            <span className="nav-label">任务中心</span>
            {activityCount > 0 && (
              <span className="nav-count">{activityCount}</span>
            )}
          </button>
        )}
        {items
          .filter((item) => item.key === 'manage')
          .map((item) => (
            <button
              key={item.key}
              title={item.label}
              aria-label={item.label}
              className={`side-nav-button ${item.active ? 'is-active' : ''}`}
              onClick={item.onClick}
            >
              {item.icon}
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        <button
          className="side-nav-button sidebar-toggle"
          onClick={onToggle}
          title={collapsed ? '展开导航' : '收起导航'}
          aria-label={collapsed ? '展开导航' : '收起导航'}
        >
          {collapsed ? (
            <PanelLeftOpen size={16} />
          ) : (
            <PanelLeftClose size={16} />
          )}
          <span className="nav-label text-xs">收起侧栏</span>
        </button>
        <p className="nav-footnote nav-label">
          好论文，慢慢读。
          <br />
          <span>知识留在你的本地。</span>
        </p>
      </div>
    </nav>
  )
}
