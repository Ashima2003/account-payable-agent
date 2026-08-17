const TYPE_CLASSES: Record<string, string> = {
  INVOICE: 'bg-accent-blue-soft text-accent-blue',
  HELPDESK: 'bg-accent-amber-soft text-accent-amber',
  OTHER: 'bg-canvas text-muted',
}

const STATUS_CLASSES: Record<string, string> = {
  EXTRACTION_COMPLETED: 'bg-accent-green-soft text-accent-green',
  HELPDESK_ANSWERED: 'bg-accent-green-soft text-accent-green',
  EXTRACTION_FAILED: 'bg-accent-rose-soft text-accent-rose',
  HELPDESK_FAILED: 'bg-accent-rose-soft text-accent-rose',
  SKIPPED: 'bg-accent-amber-soft text-accent-amber',
  EXTRACTION_STARTED: 'bg-accent-blue-soft text-accent-blue',
}

function Pill({ text, className }: { text: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${className}`}>
      {text}
    </span>
  )
}

export function TypeBadge({ type }: { type: string }) {
  return <Pill text={type} className={TYPE_CLASSES[type] ?? TYPE_CLASSES.OTHER} />
}

export function StatusBadge({ status }: { status: string | null }) {
  if (!status) {
    return <Pill text="PENDING" className="bg-canvas text-faint" />
  }
  const className = STATUS_CLASSES[status] ?? 'bg-canvas text-muted'
  return <Pill text={status.replaceAll('_', ' ')} className={className} />
}
