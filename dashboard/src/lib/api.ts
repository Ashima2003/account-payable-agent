export interface Metrics {
  total_invoices: number
  total_helpdesk_queries: number
  total_emails: number
  emails_today: number
  total_invoice_value: number
  total_invoice_value_currency: string | null
  success_rate: number | null
  status_breakdown: Record<string, number>
}

export interface TrendPoint {
  day: string
  count: number
}

export type EmailType = 'INVOICE' | 'HELPDESK' | 'OTHER'

export interface EmailRow {
  email_id: string
  sender: string
  subject: string
  received_at: string | null
  type: EmailType
  status: string | null
}

export interface EmailsPage {
  emails: EmailRow[]
  total: number
  page: number
  page_size: number
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`${url} -> ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  metrics: () => getJson<Metrics>('/api/metrics'),
  trend: (days = 14) => getJson<TrendPoint[]>(`/api/trend?days=${days}`),
  recentEmails: (limit = 5) => getJson<EmailRow[]>(`/api/emails/recent?limit=${limit}`),
  emailsPage: (page: number, pageSize = 20) =>
    getJson<EmailsPage>(`/api/emails?page=${page}&page_size=${pageSize}`),
}
