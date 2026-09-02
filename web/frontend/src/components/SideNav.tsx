import { ReactElement } from 'react'
import { BookMarked, ListTodo } from 'lucide-react'

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
}

export default function SideNav({
  items,
  onBrandClick,
  activityCount = 0,
  activityActive = false,
  onOpenActivity
}: Props) {
  return (
    <nav className="flex h-full w-14 flex-none flex-col border-r border-rail-line bg-rail text-white lg:w-60">
      <button
        className="group flex items-center gap-3 px-3 py-6 text-left lg:px-5"
        onClick={onBrandClick}
      >
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-moss text-white shadow-soft transition-transform duration-200 group-hover:scale-[1.03]">
          <BookMarked size={18} />
        </span>
        <span className="hidden min-w-0 lg:block">
          <span className="block font-serif text-[22px] font-medium leading-none tracking-tight">Paper-Wiki</span>
          <span className="mt-1.5 block text-[11px] uppercase tracking-[0.14em] text-rail-mute">Local archive</span>
        </span>
      </button>
      <div className="mt-1 flex flex-1 flex-col gap-1 px-2 lg:px-3">
        <p className="mb-2 hidden px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-rail-mute lg:block">
          Navigate
        </p>
        {items.map((item) => (
          <button
            key={item.key}
            className={`side-nav-button ${item.active ? 'is-active' : ''}`}
            title={item.label}
            onClick={item.onClick}
          >
            <span
              className={`inline-flex h-7 w-7 items-center justify-center rounded-md ${
                item.active ? 'bg-moss/20 text-white' : 'bg-transparent text-rail-mute'
              }`}
            >
              {item.icon}
            </span>
            <span className="hidden truncate lg:inline">{item.label}</span>
          </button>
        ))}
      </div>

      {onOpenActivity ? (
        <div className="border-t border-rail-line px-2 py-3 lg:px-3">
          <button
            type="button"
            className="side-nav-button"
            title="任务"
            aria-label="任务"
            onClick={onOpenActivity}
          >
            <span className="relative inline-flex h-7 w-7 items-center justify-center rounded-md text-rail-mute">
              <ListTodo size={16} className={activityActive ? 'animate-pulse text-moss' : ''} />
              {activityCount > 0 ? (
                <span className="absolute -right-1 -top-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-moss px-1 text-[10px] font-semibold leading-none text-white">
                  {activityCount > 9 ? '9+' : activityCount}
                </span>
              ) : null}
            </span>
            <span className="hidden truncate lg:inline">任务</span>
            {activityCount > 0 ? (
              <span className="ml-auto hidden rounded-md bg-white/10 px-1.5 py-0.5 text-[10px] text-white lg:inline">
                {activityCount}
              </span>
            ) : null}
          </button>
        </div>
      ) : (
        <div className="hidden border-t border-rail-line px-5 py-4 lg:block">
          <p className="text-[11px] leading-5 text-rail-mute">
            读论文、审产物、发笔记。
            <br />
            知识在本地持续沉淀。
          </p>
        </div>
      )}
    </nav>
  )
}
