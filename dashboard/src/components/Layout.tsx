import { LayoutDashboard, Menu } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { MobileSidebar, Sidebar } from './Sidebar'

function MobileTopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  return (
    <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-surface px-4 py-3 md:hidden">
      <button
        onClick={onOpenMenu}
        aria-label="Open menu"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted transition hover:bg-canvas"
      >
        <Menu size={20} />
      </button>
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink text-white">
          <LayoutDashboard size={14} strokeWidth={2} />
        </div>
        <p className="text-sm font-bold text-ink">Accounts Payable</p>
      </div>
    </div>
  )
}

export function Layout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const location = useLocation()

  // Close the drawer whenever navigation happens (including the browser
  // back/forward buttons, which NavLink's own onClick handler in
  // Sidebar.tsx wouldn't catch).
  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  return (
    <div className="flex md:min-h-screen">
      <Sidebar />
      <MobileSidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="min-w-0 flex-1">
        <MobileTopBar onOpenMenu={() => setMobileNavOpen(true)} />
        <main className="px-4 py-6 sm:px-6 sm:py-8 md:px-10">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
