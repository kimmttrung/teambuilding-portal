import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eye, Mail, Megaphone, Pencil, Send, Trash2, Undo2 } from 'lucide-react'
import { useActiveEvent } from '../../hooks/useEvent'
import {
  useAnnouncements,
  useDeleteAnnouncement,
  usePublishAnnouncement,
  useRecipientPreview,
  useUnpublishAnnouncement,
} from '../../hooks/useAnnouncements'
import { useToast } from '../../context/ToastContext'
import { ANNOUNCEMENT_SEVERITY_META, EVENT_STATUS_META } from '../../utils/constants'
import { formatRelative } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import EmptyState from '../../components/common/EmptyState'
import MarkdownText from '../../components/common/MarkdownText'
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import AnnouncementForm from './announcements/AnnouncementForm'
import AnnouncementFormModal from './announcements/AnnouncementFormModal'

const COMPOSE_FORM_ID = 'announcement-compose-form'
const FILTERS = ['all', 'draft', 'published']

/**
 * BTC soạn và đăng thông báo cho CBNV (Figma v2 · B11): thẻ soạn bên trái, danh sách bên phải.
 *
 * Bản nháp chỉ BTC thấy. Bấm Đăng mới hiện trong My Journey đúng nhóm đối tượng — tick thêm
 * "gửi email" thì xếp thư cho đúng nhóm đó. Muốn sửa nội dung đã đăng thì bấm Sửa; đăng nhầm
 * đối tượng thì Gỡ về nháp rồi đăng lại.
 */
export default function AnnouncementsPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: event } = useActiveEvent()
  const { data: items, isLoading, error } = useAnnouncements()
  const { mutateAsync: removeItem, isPending: isDeleting } = useDeleteAnnouncement()
  const { mutateAsync: unpublish, isPending: isUnpublishing } = useUnpublishAnnouncement()

  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [publishing, setPublishing] = useState(null)
  const [composePending, setComposePending] = useState(false)
  const [composePreview, setComposePreview] = useState(null)

  if (isLoading) return <Spinner label="Đang tải thông báo…" />
  if (error) {
    return (
      <Alert tone="error" title="Không tải được thông báo">
        {error.message}
      </Alert>
    )
  }

  const statusMeta = event ? EVENT_STATUS_META[event.status] : null
  const rows = items ?? []
  const drafts = rows.filter((item) => !item.published_at)
  const published = rows.filter((item) => item.published_at)
  // Bộ lọc nằm trên URL để F5 hay gửi link cho nhau không mất.
  const filter = FILTERS.includes(searchParams.get('view')) ? searchParams.get('view') : 'all'
  const shown = filter === 'draft' ? drafts : filter === 'published' ? published : [...drafts, ...published]

  function setFilter(next) {
    const params = new URLSearchParams(searchParams)
    if (next === 'all') params.delete('view')
    else params.set('view', next)
    setSearchParams(params, { replace: true })
  }

  async function confirmDelete() {
    try {
      await removeItem(deleting.id)
      toast.success('Đã xoá thông báo.')
      setDeleting(null)
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  async function confirmUnpublish() {
    try {
      // Đóng hộp thoại trước: nút Gỡ nằm trong hộp Đăng nên phải dọn state cả hai.
      const item = publishing
      setPublishing(null)
      await unpublish(item.id)
      toast.success('Đã gỡ về nháp — CBNV không còn thấy thông báo này.')
    } catch (unpublishError) {
      toast.error(unpublishError.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Thông báo & email"
        description={event ? `${event.name} · ${statusMeta?.label ?? event.status}` : undefined}
        action={
          <Link
            to="/admin/email-logs"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-hairline bg-surface px-3 text-caption font-medium text-ink hover:bg-canvas-soft sm:min-h-8"
          >
            <Mail className="size-3.5" aria-hidden="true" />
            Nhật ký email
          </Link>
        }
      />

      <div className="grid gap-8 xl:grid-cols-[440px_minmax(0,1fr)] xl:items-start">
        <section className="rounded-lg border border-hairline bg-surface p-4 sm:p-6" aria-labelledby="compose-title">
          <h2 id="compose-title" className="mb-4 text-title text-ink">
            Thông báo mới
          </h2>
          <AnnouncementForm
            formId={COMPOSE_FORM_ID}
            onPendingChange={setComposePending}
            onPreview={setComposePreview}
            onSaved={(saved, intent) => {
              // "Đăng" luôn đi qua hộp xác nhận: ở đó mới tick gửi email và xem lại người nhận.
              if (intent === 'publish') setPublishing(saved)
            }}
          />
          <div className="mt-4.5 flex flex-wrap gap-2.5">
            <Button
              type="submit"
              form={COMPOSE_FORM_ID}
              value="draft"
              variant="secondary"
              shape="pill"
              disabled={composePending}
            >
              Lưu nháp
            </Button>
            <Button
              type="submit"
              form={COMPOSE_FORM_ID}
              value="publish"
              shape="pill"
              icon={Send}
              loading={composePending}
              className="flex-1"
            >
              {composePreview ? `Đăng cho ${composePreview.total} người` : 'Đăng thông báo'}
            </Button>
          </div>
          <p className="mt-3 text-eyebrow font-normal text-ink-faint">
            Thông báo gửi tất cả được đưa vào kiến thức trợ lý Tibi sau khi BTC nạp lại — tin riêng
            team hay cá nhân thì không.
          </p>
        </section>

        <section className="min-w-0" aria-labelledby="announcement-list-title">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
            <h2 id="announcement-list-title" className="text-title text-ink">
              Đã soạn
            </h2>
            <div className="ml-auto flex rounded-full bg-black/5 p-1" role="group" aria-label="Lọc thông báo">
              {[
                ['all', 'Tất cả'],
                ['draft', `Nháp · ${drafts.length}`],
                ['published', `Đã đăng · ${published.length}`],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                  className={`min-h-11 rounded-full px-4 text-caption whitespace-nowrap transition sm:min-h-8 ${
                    filter === value ? 'bg-surface font-semibold text-ink shadow-soft' : 'font-medium text-ink-muted'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3 overflow-hidden rounded-lg border border-hairline bg-surface">
            {shown.length === 0 ? (
              <EmptyState
                icon={Megaphone}
                title={rows.length === 0 ? 'Chưa có thông báo nào' : 'Không có thông báo ở mục này'}
                description={
                  rows.length === 0
                    ? 'Soạn tin đầu tiên ở thẻ bên cạnh — ví dụ đổi giờ bay, đổi điểm đón, dặn mang giấy tờ.'
                    : 'Đổi bộ lọc để xem các thông báo khác.'
                }
              />
            ) : (
              <ol className="divide-y divide-hairline">
                {shown.map((item) => (
                  <AnnouncementRow
                    key={item.id}
                    item={item}
                    onEdit={() => setEditing(item)}
                    onPublish={() => setPublishing(item)}
                    onDelete={() => setDeleting(item)}
                  />
                ))}
              </ol>
            )}
          </div>
        </section>
      </div>

      {editing && <AnnouncementFormModal open item={editing} onClose={() => setEditing(null)} />}

      <PublishDialog
        item={publishing}
        onClose={() => setPublishing(null)}
        onUnpublish={confirmUnpublish}
        unpublishing={isUnpublishing}
      />

      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Xoá thông báo?"
        description={
          deleting
            ? `"${deleting.title}"${deleting.published_at ? ' — đang hiện với CBNV, xoá là biến mất ngay.' : ' — bản nháp chưa ai thấy.'}`
            : undefined
        }
        footer={
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={() => setDeleting(null)}>
              Giữ lại
            </Button>
            <Button size="sm" variant="danger" loading={isDeleting} onClick={confirmDelete}>
              Xoá thông báo
            </Button>
          </div>
        }
      />
    </>
  )
}

function AnnouncementRow({ item, onEdit, onPublish, onDelete }) {
  const meta = ANNOUNCEMENT_SEVERITY_META[item.severity] ?? ANNOUNCEMENT_SEVERITY_META.info
  return (
    <li className="px-4 py-3.5 sm:px-5">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1 basis-56">
          <p className="flex flex-wrap items-center gap-2">
            <Badge tone={meta.tone}>{meta.label}</Badge>
            {!item.published_at && <Badge tone="slate">Nháp</Badge>}
            <span className="min-w-0 text-body-sm font-semibold text-ink">{item.title}</span>
          </p>
          <p className="mt-1 text-caption text-ink-muted">
            {item.target_label} · {item.recipient_count} người nhận
            {item.published_at ? ` · đăng ${formatRelative(item.published_at)}` : ''}
            {item.send_email ? ' · đã gửi email' : ''}
          </p>
        </div>
        <div className="flex shrink-0 items-center">
          <IconButton label="Sửa" onClick={onEdit}>
            <Pencil className="size-4" aria-hidden="true" />
          </IconButton>
          <IconButton label={item.published_at ? 'Đăng lại / gửi email' : 'Đăng'} onClick={onPublish}>
            {item.published_at ? (
              <Eye className="size-4" aria-hidden="true" />
            ) : (
              <Send className="size-4" aria-hidden="true" />
            )}
          </IconButton>
          <IconButton label="Xoá" tone="danger" onClick={onDelete}>
            <Trash2 className="size-4" aria-hidden="true" />
          </IconButton>
        </div>
      </div>
      <details className="mt-2" open={!item.published_at}>
        <summary className="cursor-pointer text-caption font-medium text-primary">Nội dung</summary>
        <div className="mt-2 rounded-md bg-canvas-soft px-3 py-2.5">
          <MarkdownText content={item.content} />
        </div>
      </details>
    </li>
  )
}

/** Hộp xác nhận đăng: tick gửi email + xem trước đúng nhóm nhận trước khi bấm. */
function PublishDialog({ item, onClose, onUnpublish, unpublishing }) {
  const toast = useToast()
  const { mutateAsync: publish, isPending } = usePublishAnnouncement()
  const [sendEmail, setSendEmail] = useState(false)

  const { data: preview } = useRecipientPreview({
    targetType: item?.target_type,
    targetId: item?.target_id,
    enabled: Boolean(item),
  })

  // Mở sang tin khác thì reset tick gửi mail — tránh bấm nhầm gửi cho cả trăm người.
  useEffect(() => {
    setSendEmail(false)
  }, [item?.id])

  if (!item) return null

  async function confirm() {
    try {
      const result = await publish({ itemId: item.id, sendEmail })
      toast.success(
        sendEmail
          ? `Đã đăng và xếp ${result.queued} email.${result.email_enabled ? '' : ' (Email đang tắt — chỉ ghi nhật ký.)'}`
          : 'Đã đăng — CBNV đúng đối tượng thấy ngay trong My Journey.',
      )
      onClose()
    } catch (publishError) {
      toast.error(publishError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={item.published_at ? 'Đăng lại / gửi email' : `Đăng "${item.title}"?`}
      description={`${preview?.target_label ?? item.target_label} · ${preview?.total ?? item.recipient_count} người nhận`}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          {item.published_at && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={Undo2}
              loading={unpublishing}
              onClick={onUnpublish}
            >
              Gỡ về nháp
            </Button>
          )}
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Để sau
          </Button>
          <Button size="sm" icon={Send} loading={isPending} onClick={confirm}>
            {item.published_at ? 'Xác nhận' : 'Đăng ngay'}
          </Button>
        </div>
      }
    >
      <label className="flex cursor-pointer items-start gap-3 rounded-md border border-hairline px-3 py-3">
        <input
          type="checkbox"
          className="mt-0.5 size-4 shrink-0 accent-primary"
          checked={sendEmail}
          onChange={(changeEvent) => setSendEmail(changeEvent.target.checked)}
        />
        <span>
          <span className="block text-body-sm font-semibold text-ink">Gửi kèm email cho cả nhóm nhận</span>
          <span className="block text-caption text-ink-muted">
            Mỗi người một thư riêng, có link về hệ thống. Email đang{' '}
            {preview?.email_enabled ?? true ? 'bật' : 'tắt — chỉ ghi nhật ký, vẫn hiện trong My Journey'}.
          </span>
        </span>
      </label>
      {preview && preview.recipients.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-eyebrow text-ink-faint">
            {preview.total > 10 ? `10/${preview.total} người đầu tiên` : 'Người nhận'}
          </p>
          <ul className="max-h-40 divide-y divide-hairline overflow-y-auto rounded-md border border-hairline">
            {preview.recipients.slice(0, 10).map((person) => (
              <li key={person.user_id} className="flex items-center justify-between gap-2 px-3 py-2 text-caption">
                <span className="truncate font-medium text-ink">{person.full_name}</span>
                <span className="shrink-0 text-ink-muted">{person.team_name ?? person.email}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  )
}

function IconButton({ label, tone, ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      {...props}
      className={`grid size-11 place-items-center rounded-md text-ink-faint transition disabled:cursor-not-allowed disabled:opacity-30 sm:size-8 ${
        tone === 'danger' ? 'hover:bg-rose-50 hover:text-rose-600' : 'hover:bg-black/5 hover:text-ink-secondary'
      }`}
    />
  )
}
