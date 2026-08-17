import { AlertTriangle, ArrowLeft, Fingerprint } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatusBadge, TypeBadge } from '../components/Badge'
import { api, type WorkItemDetail } from '../lib/api'
import { formatSender } from '../lib/format'

const DOT_CLASSES: Record<string, string> = {
  EXTRACTION_COMPLETED: 'bg-accent-green',
  HELPDESK_ANSWERED: 'bg-accent-green',
  EXTRACTION_FAILED: 'bg-accent-rose',
  HELPDESK_FAILED: 'bg-accent-rose',
  SKIPPED: 'bg-accent-amber',
  EXTRACTION_STARTED: 'bg-accent-blue',
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  })
}

function Timeline({ log }: { log: WorkItemDetail['log'] }) {
  if (log.length === 0) {
    return <p className="py-8 text-center text-sm text-faint">No log entries recorded for this work item.</p>
  }
  return (
    <ol className="relative border-l-2 border-border pl-6">
      {log.map((entry, i) => (
        <li key={i} className="mb-8 last:mb-0">
          <span
            className={`absolute -left-[9px] flex h-4 w-4 items-center justify-center rounded-full ring-4 ring-surface ${
              DOT_CLASSES[entry.status] ?? 'bg-faint'
            }`}
          />
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={entry.status} />
            <span className="text-xs text-faint">{formatTimestamp(entry.timestamp)}</span>
          </div>
          {entry.detail && (
            <p className="mt-2 max-w-2xl whitespace-pre-wrap rounded-xl bg-canvas px-4 py-3 text-sm text-muted">
              {entry.detail}
            </p>
          )}
        </li>
      ))}
    </ol>
  )
}

export function WorkItemDetailPage() {
  const { workId } = useParams<{ workId: string }>()
  const [detail, setDetail] = useState<WorkItemDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!workId) return
    setLoading(true)
    setNotFound(false)
    api
      .workItemDetail(workId)
      .then(setDetail)
      .catch((err) => {
        console.error('failed to load work item detail', err)
        setNotFound(true)
      })
      .finally(() => setLoading(false))
  }, [workId])

  return (
    <div className="flex flex-col gap-6">
      <Link to="/logs" className="flex w-fit items-center gap-1.5 text-sm font-medium text-muted transition hover:text-ink">
        <ArrowLeft size={16} /> Back to activity logs
      </Link>

      {loading ? (
        <div className="space-y-4">
          <div className="h-24 animate-pulse rounded-2xl bg-canvas" />
          <div className="h-64 animate-pulse rounded-2xl bg-canvas" />
        </div>
      ) : notFound || !detail ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-surface py-16 text-faint">
          <AlertTriangle size={28} strokeWidth={1.5} />
          <p className="text-sm">No work item found for this id.</p>
        </div>
      ) : (
        <>
          <div className="rounded-2xl border border-border bg-surface p-6 shadow-[0_1px_2px_rgba(20,22,27,0.04)]">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1.5 text-xs font-mono text-muted">
                <Fingerprint size={13} className="text-faint" />
                {detail.work_id}
              </div>
              <TypeBadge type={detail.type} />
              <StatusBadge status={detail.status} />
            </div>
            <h1 className="mt-3 text-lg font-bold tracking-tight text-ink">{detail.subject}</h1>
            <p className="text-sm text-faint">
              {formatSender(detail.sender).name} · {formatSender(detail.sender).address}
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 shadow-[0_1px_2px_rgba(20,22,27,0.04)]">
            <h2 className="mb-6 text-sm font-semibold text-ink">Log trail</h2>
            <Timeline log={detail.log} />
          </div>
        </>
      )}
    </div>
  )
}
