import { ChevronLeft, ChevronRight, ClipboardList, Fingerprint } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { StatusBadge, TypeBadge } from '../components/Badge'
import { api, type WorkItemRow } from '../lib/api'
import { formatRelativeTime, formatSender } from '../lib/format'

const PAGE_SIZE = 12

function WorkItemCard({ item }: { item: WorkItemRow }) {
  const sender = formatSender(item.sender)
  return (
    <Link
      to={`/logs/${item.work_id}`}
      className="group flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5 shadow-[0_1px_2px_rgba(20,22,27,0.04)] transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5 rounded-full bg-canvas px-2.5 py-1 text-xs font-mono text-muted">
          <Fingerprint size={13} className="shrink-0 text-faint" />
          <span className="truncate">{item.work_id}</span>
        </div>
        <TypeBadge type={item.type} />
      </div>

      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">{item.subject}</p>
        <p className="truncate text-xs text-faint">
          {sender.name} · {sender.address}
        </p>
      </div>

      <div className="mt-1 flex items-center justify-between">
        <StatusBadge status={item.status} />
        <span className="text-xs text-faint">{formatRelativeTime(item.created_at)}</span>
      </div>

      <div className="flex items-center gap-1 text-xs font-medium text-accent-blue opacity-0 transition group-hover:opacity-100">
        View log trail <ChevronRight size={14} />
      </div>
    </Link>
  )
}

export function ActivityLogsPage() {
  const [items, setItems] = useState<WorkItemRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api
      .workItemsPage(page, PAGE_SIZE)
      .then((res) => {
        setItems(res.work_items)
        setTotal(res.total)
      })
      .catch((err) => console.error('failed to load work items', err))
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-bold tracking-tight text-ink">Activity logs</h1>
        <p className="text-sm text-faint">Every work item processed, with its full status trail. Click one to inspect.</p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-2xl bg-canvas" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-surface py-16 text-faint">
          <ClipboardList size={28} strokeWidth={1.5} />
          <p className="text-sm">No activity yet</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <WorkItemCard key={item.work_id} item={item} />
            ))}
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-faint">
              Page {page} of {totalPages} · {total} total
            </p>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted transition hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted transition hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
