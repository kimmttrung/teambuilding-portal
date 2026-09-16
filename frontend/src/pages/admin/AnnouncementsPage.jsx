import { useEffect, useState } from 'react'
import {
  Eye,
  Megaphone,
  Pencil,
  Plus,
  Send,
  Trash2,
  Undo2,
} from 'lucide-react'
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
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import MarkdownText from '../../components/common/MarkdownText'
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import AnnouncementFormModal from './announcements/AnnouncementFormModal'

/**
 * BTC soạn và đăng thông báo cho CBNV.
 *
 * Bản nháp chỉ BTC thấy. Bấm Đăng mới hiện trong My Journey đúng nhóm đối tượng —
 * tick thêm "gửi email" thì xếp thư cho đúng nhóm đó. Muốn sửa nội dung đã đăng
 * thì bấm Sửa; đăng nhầm đối tượng thì Gỡ về nháp rồi đăng lại.
 */
export default function AnnouncementsPage() {
  const toast = useToast()
  const { data: event } = useActiveEvent()
  const { data: items, isLoading, error } = useAnnouncements()
  const { mutateAsync: removeItem, isPending: isDeleting } = useDeleteAnnouncement()
  const { mutateAsync: unpublish, isPending: isUnpublishing } = useUnpublishAnnouncement()

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [publishing, setPublishing] = useState(null)

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
        title="Thông báo từ BTC"
        description={event ? `${event.name} · ${statusMeta?.label ?? event.status}` : undefined}
        action={
          <Button
            icon={Plus}
            onClick={() => {
              setEditing(null)
              setFormOpen(true)
            }}
          >
            Soạn thông báo
          </Button>
        }
      />

      <Alert tone="info" className="mb-4" title="CBNV thấy gì từ đây?">
        Bản nháp chỉ BTC thấy. Đăng xong mới hiện trong My Journey đúng nhóm đối tượng (tất cả /
        team / chuyến bay / xe / cá nhân), tin khẩn có banner đỏ. Thông báo gửi tất cả được đưa
        vào kiến thức trợ lý Tibi sau khi BTC nạp lại — tin riêng team/người thì không.
      </Alert>

      {rows.length === 0 && (
        <Card>
          <EmptyState
            icon={Megaphone}
            title="Chưa có thông báo nào"
            description="Soạn tin đầu tiên — ví dụ đổi giờ bay, đổi điểm đón, dặn mang giấy tờ."
            action={
              <Button
                size="sm"
                icon={Plus}
                onClick={() => {
                  setEditing(null)
                  setFormOpen(true)
                }}
              >
                Soạn thông báo
              </Button>
            }
          />
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-6">
          <Card title={`Bản nháp (${drafts.length})`} description="Chưa ai ngoài BTC thấy">
            {drafts.length === 0 ? (
              <p className="py-2 text-sm text-slate-500">Không có bản nháp nào.</p>
            ) : (
              <ol className="flex flex-col divide-y divide-slate-100">
                {drafts.map((item) => (
                  <AnnouncementRow
                    key={item.id}
                    item={item}
                    onEdit={() => {
                      setEditing(item)
                      setFormOpen(true)
                    }}
                    onPublish={() => setPublishing(item)}
                    onDelete={() => setDeleting(item)}
                  />
                ))}
              </ol>
            )}
          </Card>
        </div>
        <div className="xl:col-span-6">
          <Card title={`Đã đăng (${published.length})`} description="CBNV đúng đối tượng đang thấy">
            {published.length === 0 ? (
              <p className="py-2 text-sm text-slate-500">Chưa đăng thông báo nào.</p>
            ) : (
              <ol className="flex flex-col divide-y divide-slate-100">
                {published.map((item) => (
                  <AnnouncementRow
                    key={item.id}
                    item={item}
                    onEdit={() => {
                      setEditing(item)
                      setFormOpen(true)
                    }}
                    onPublish={() => setPublishing(item)}
                    onDelete={() => setDeleting(item)}
                  />
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>

      {formOpen && (
        <AnnouncementFormModal
          open
          item={editing}
          onClose={() => {
            setFormOpen(false)
            setEditing(null)
          }}
        />
      )}

      <PublishDialog item={publishing} onClose={() => setPublishing(null)} onUnpublish={confirmUnpublish} unpublishing={isUnpublishing} />

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
    <li className="py-3">
      <details open={!item.published_at}>
        <summary className="cursor-pointer list-none">
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={meta.tone}>{meta.label}</Badge>
            {!item.published_at && <Badge tone="slate">Nháp</Badge>}
            <span className="min-w-0 flex-1 text-sm font-medium text-slate-900">{item.title}</span>
          </span>
          <span className="mt-1 block text-xs text-slate-500">
            {item.target_label} · {item.recipient_count} người nhận
            {item.published_at ? ` · đăng ${formatRelative(item.published_at)}` : ''}
          </span>
        </summary>
        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2">
          <MarkdownText content={item.content} />
        </div>
      </details>
      <span className="mt-2 flex items-center gap-0.5">
        <IconButton label="Sửa" onClick={onEdit}>
          <Pencil className="size-4" aria-hidden="true" />
        </IconButton>
        <IconButton
          label={item.published_at ? 'Đăng lại / gửi email' : 'Đăng'}
          onClick={onPublish}
        >
          {item.published_at ? (
            <Eye className="size-4" aria-hidden="true" />
          ) : (
            <Send className="size-4" aria-hidden="true" />
          )}
        </IconButton>
        <IconButton label="Xoá" tone="danger" onClick={onDelete}>
          <Trash2 className="size-4" aria-hidden="true" />
        </IconButton>
      </span>
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
      <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 px-3 py-2.5">
        <input
          type="checkbox"
          className="mt-1 size-4 accent-indigo-600"
          checked={sendEmail}
          onChange={(changeEvent) => setSendEmail(changeEvent.target.checked)}
        />
        <span className="text-sm">
          <span className="font-medium text-slate-900">Gửi email cho cả nhóm nhận</span>
          <span className="block text-xs text-slate-500">
            Mỗi người một thư riêng. Email đang {preview?.email_enabled ?? true ? 'bật' : 'tắt — chỉ ghi nhật ký, vẫn hiện trong My Journey'}.
          </span>
        </span>
      </label>
      {preview && preview.recipients.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
            {preview.total > 10 ? `10/${preview.total} người đầu tiên` : 'Người nhận'}
          </p>
          <ul className="max-h-40 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
            {preview.recipients.slice(0, 10).map((person) => (
              <li key={person.user_id} className="flex items-center justify-between gap-2 px-3 py-1.5 text-sm">
                <span className="truncate font-medium text-slate-800">{person.full_name}</span>
                <span className="shrink-0 text-xs text-slate-500">
                  {person.team_name ?? person.email}
                </span>
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
      className={`rounded-lg p-1.5 transition disabled:cursor-not-allowed disabled:opacity-30 ${
        tone === 'danger'
          ? 'text-slate-400 hover:bg-rose-50 hover:text-rose-600'
          : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'
      }`}
    />
  )
}
