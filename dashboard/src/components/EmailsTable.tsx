import { ChevronLeft, ChevronRight, Inbox } from 'lucide-react'
import type { EmailRow } from '../lib/api'
import { formatRelativeTime, formatSender } from '../lib/format'
import { StatusBadge, TypeBadge } from './Badge'

function EmailRowView({ email }: { email: EmailRow }) {
  const sender = formatSender(email.sender)
  return (
    <tr className="border-b border-border last:border-0 hover:bg-canvas/60">
      <td className="py-3.5 pr-4">
        <p className="text-sm font-medium text-ink">{sender.name}</p>
        <p className="text-xs text-faint">{sender.address}</p>
      </td>
      <td className="py-3.5 pr-4">
        <p className="max-w-xs truncate text-sm text-ink">{email.subject}</p>
      </td>
      <td className="py-3.5 pr-4">
        <TypeBadge type={email.type} />
      </td>
      <td className="py-3.5 pr-4">
        <StatusBadge status={email.status} />
      </td>
      <td className="py-3.5 text-right text-sm text-muted">{formatRelativeTime(email.received_at)}</td>
    </tr>
  )
}

function TableHead() {
  return (
    <thead>
      <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-faint">
        <th className="pb-3 pr-4 font-medium">Sender</th>
        <th className="pb-3 pr-4 font-medium">Subject</th>
        <th className="pb-3 pr-4 font-medium">Type</th>
        <th className="pb-3 pr-4 font-medium">Status</th>
        <th className="pb-3 text-right font-medium">Received</th>
      </tr>
    </thead>
  )
}

/** Below `xl`, a 5-column table has no room to breathe -- nested
 * horizontal scrolling inside a card works but is a poor mobile pattern
 * (no visual cue there's more, easy to miss columns entirely). `xl`
 * (not `sm`/`md`/`lg`) is deliberate: the persistent sidebar (Sidebar.tsx)
 * appears at `md` and eats ~240px, so even at `lg` (1024px) the table
 * only has ~700px to fit Sender/Subject/Type/Status/Received in --
 * tried it, columns wrapped and clipped. `xl` (1280px) leaves enough
 * room. A stacked card per email reuses the same visual language as the
 * Activity Logs grid instead. */
function MobileEmailCard({ email }: { email: EmailRow }) {
  const sender = formatSender(email.sender)
  return (
    <div className="border-b border-border py-4 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink">{sender.name}</p>
          <p className="truncate text-xs text-faint">{sender.address}</p>
        </div>
        <span className="shrink-0 text-xs text-faint">{formatRelativeTime(email.received_at)}</span>
      </div>
      <p className="mt-1.5 truncate text-sm text-ink">{email.subject}</p>
      <div className="mt-2 flex items-center gap-2">
        <TypeBadge type={email.type} />
        <StatusBadge status={email.status} />
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-faint">
      <Inbox size={28} strokeWidth={1.5} />
      <p className="text-sm">No emails yet</p>
    </div>
  )
}

function EmailList({ emails }: { emails: EmailRow[] }) {
  return (
    <>
      <div className="xl:hidden">
        {emails.map((email) => (
          <MobileEmailCard key={email.email_id} email={email} />
        ))}
      </div>
      <div className="hidden overflow-x-auto xl:block">
        <table className="w-full">
          <TableHead />
          <tbody>
            {emails.map((email) => (
              <EmailRowView key={email.email_id} email={email} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function LoadingSkeleton({ count }: { count: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-11 animate-pulse rounded-lg bg-canvas" />
      ))}
    </div>
  )
}

export function RecentEmailsCard({
  emails,
  loading,
  onViewAll,
}: {
  emails: EmailRow[]
  loading?: boolean
  onViewAll: () => void
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-[0_1px_2px_rgba(20,22,27,0.04)] sm:p-6">
      <div className="mb-2 flex items-center justify-between sm:mb-4">
        <h2 className="text-sm font-semibold text-ink">Recent emails</h2>
        <button
          onClick={onViewAll}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-accent-blue transition hover:bg-accent-blue-soft"
        >
          View all
        </button>
      </div>
      {loading ? <LoadingSkeleton count={5} /> : emails.length === 0 ? <EmptyState /> : <EmailList emails={emails} />}
    </div>
  )
}

export function AllEmailsCard({
  emails,
  loading,
  page,
  totalPages,
  onPageChange,
  onBack,
}: {
  emails: EmailRow[]
  loading?: boolean
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  onBack: () => void
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-[0_1px_2px_rgba(20,22,27,0.04)] sm:p-6">
      <div className="mb-2 flex items-center justify-between sm:mb-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">All emails</h2>
          <p className="text-xs text-faint">Page {page} of {Math.max(totalPages, 1)}</p>
        </div>
        <button
          onClick={onBack}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-muted transition hover:bg-canvas"
        >
          Back to recent
        </button>
      </div>
      {loading ? (
        <LoadingSkeleton count={8} />
      ) : emails.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <EmailList emails={emails} />
          <div className="mt-4 flex items-center justify-end gap-2">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted transition hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted transition hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
