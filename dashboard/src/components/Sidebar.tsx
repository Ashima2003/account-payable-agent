import { LayoutDashboard, ScrollText } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/logs', label: 'Activity logs', icon: ScrollText, end: false },
]

function Brand() {
  return (
    <div className="mb-8 flex items-center gap-3 px-2">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-white">
        <LayoutDashboard size={18} strokeWidth={2} />
      </div>
      <div>
        <p className="text-sm font-bold leading-tight text-ink">Accounts Payable</p>
        <p className="text-xs text-faint">Automation</p>
      </div>
    </div>
  )
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
              isActive
                ? 'bg-accent-blue-soft text-accent-blue'
                : 'text-muted hover:bg-canvas hover:text-ink'
            }`
          }
        >
          <Icon size={18} strokeWidth={2} />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

/** Persistent left column -- desktop and tablet only (md+). */
export function Sidebar() {
  return (
    <aside className="hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface px-4 py-6 md:sticky md:top-0 md:flex">
      <Brand />
      <Nav />
    </aside>
  )
}

/** Slide-in drawer + backdrop -- mobile only, shown when `open`. */
export function MobileSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-ink/30 transition-opacity md:hidden ${
          open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col bg-surface px-4 py-6 shadow-xl transition-transform md:hidden ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Brand />
        <Nav onNavigate={onClose} />
      </aside>
    </>
  )
}
