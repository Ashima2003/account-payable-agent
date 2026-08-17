import { CircleCheck, FileText, Inbox, MessageCircleQuestion, Wallet } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { AllEmailsCard, RecentEmailsCard } from '../components/EmailsTable'
import { Header } from '../components/Header'
import { StatCard } from '../components/StatCard'
import { TrendChart } from '../components/TrendChart'
import { api, type EmailRow, type Metrics, type TrendPoint } from '../lib/api'
import { formatCurrency } from '../lib/format'

const REFRESH_MS = 30_000
const PAGE_SIZE = 20

export function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [recentEmails, setRecentEmails] = useState<EmailRow[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const [view, setView] = useState<'recent' | 'all'>('recent')
  const [allEmails, setAllEmails] = useState<EmailRow[]>([])
  const [page, setPage] = useState(1)
  const [totalEmails, setTotalEmails] = useState(0)
  const [pageLoading, setPageLoading] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [m, t, e] = await Promise.all([api.metrics(), api.trend(14), api.recentEmails(5)])
      setMetrics(m)
      setTrend(t)
      setRecentEmails(e)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('failed to refresh dashboard data', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, REFRESH_MS)
    return () => clearInterval(id)
  }, [refresh])

  useEffect(() => {
    if (view !== 'all') return
    setPageLoading(true)
    api
      .emailsPage(page, PAGE_SIZE)
      .then((res) => {
        setAllEmails(res.emails)
        setTotalEmails(res.total)
      })
      .catch((err) => console.error('failed to load emails page', err))
      .finally(() => setPageLoading(false))
  }, [view, page])

  const totalPages = Math.max(1, Math.ceil(totalEmails / PAGE_SIZE))

  return (
    <div className="flex flex-col gap-6">
      <Header lastUpdated={lastUpdated} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<FileText size={22} />}
          label="Invoices processed"
          value={metrics ? metrics.total_invoices.toLocaleString() : '—'}
          sublabel={metrics ? `${metrics.emails_today} email${metrics.emails_today === 1 ? '' : 's'} today` : undefined}
          accent="blue"
          loading={loading}
        />
        <StatCard
          icon={<MessageCircleQuestion size={22} />}
          label="Helpdesk queries answered"
          value={metrics ? metrics.total_helpdesk_queries.toLocaleString() : '—'}
          accent="amber"
          loading={loading}
        />
        <StatCard
          icon={<Wallet size={22} />}
          label="Total invoice value"
          value={metrics ? formatCurrency(metrics.total_invoice_value, metrics.total_invoice_value_currency) : '—'}
          accent="green"
          loading={loading}
        />
        <StatCard
          icon={<CircleCheck size={22} />}
          label="Extraction success rate"
          value={metrics && metrics.success_rate !== null ? `${metrics.success_rate}%` : '—'}
          accent="rose"
          loading={loading}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <TrendChart data={trend} loading={loading} />
        </div>
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-[0_1px_2px_rgba(20,22,27,0.04)]">
          <h2 className="mb-4 text-sm font-semibold text-ink">Pipeline status</h2>
          {loading ? (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-8 animate-pulse rounded-lg bg-canvas" />
              ))}
            </div>
          ) : metrics && Object.keys(metrics.status_breakdown).length > 0 ? (
            <ul className="space-y-3">
              {Object.entries(metrics.status_breakdown).map(([status, count]) => (
                <li key={status} className="flex items-center justify-between text-sm">
                  <span className="text-muted">{status.replaceAll('_', ' ')}</span>
                  <span className="font-semibold text-ink">{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 py-8 text-faint">
              <Inbox size={24} strokeWidth={1.5} />
              <p className="text-sm">No invoices processed yet</p>
            </div>
          )}
        </div>
      </div>

      {view === 'recent' ? (
        <RecentEmailsCard
          emails={recentEmails}
          loading={loading}
          onViewAll={() => {
            setView('all')
            setPage(1)
          }}
        />
      ) : (
        <AllEmailsCard
          emails={allEmails}
          loading={pageLoading}
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
          onBack={() => setView('recent')}
        />
      )}
    </div>
  )
}
