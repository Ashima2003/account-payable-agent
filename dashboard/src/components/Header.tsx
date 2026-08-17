import { LayoutDashboard } from 'lucide-react'

export function Header({ lastUpdated }: { lastUpdated: Date | null }) {
  return (
    <header className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-white">
          <LayoutDashboard size={20} strokeWidth={2} />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-ink">Accounts Payable</h1>
          <p className="text-xs text-faint">Automation dashboard</p>
        </div>
      </div>
      <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-muted">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-green opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-green" />
        </span>
        {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Connecting…'}
      </div>
    </header>
  )
}
