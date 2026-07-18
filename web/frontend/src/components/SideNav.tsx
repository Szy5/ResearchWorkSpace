import { ReactElement } from 'react'
import { BookOpen } from 'lucide-react'

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
}

export default function SideNav({ items, onBrandClick }: Props) {
  return (
    <nav className="flex h-full w-14 flex-none flex-col border-r border-line bg-fog lg:w-56">
      <button
        className="flex items-center gap-2 px-4 py-5 text-left font-serif text-lg font-semibold lg:px-5"
        onClick={onBrandClick}
      >
        <BookOpen size={22} className="text-moss" />
        <span className="hidden lg:inline">Paper-Wiki</span>
      </button>
      <div className="flex flex-col gap-1 px-2 lg:px-3">
        {items.map((item) => (
          <button
            key={item.key}
            className={`side-nav-button ${item.active ? 'is-active' : ''}`}
            title={item.label}
            onClick={item.onClick}
          >
            {item.icon}
            <span className="hidden lg:inline">{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
