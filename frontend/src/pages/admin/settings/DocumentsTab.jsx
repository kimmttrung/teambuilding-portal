import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Bot, Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { useDeleteDocument, useDocuments, useSaveDocument } from '../../../hooks/useDocuments'
import { useToast } from '../../../context/ToastContext'
import { formatFullDateTime } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import Input from '../../../components/common/Input'
import MarkdownText from '../../../components/common/MarkdownText'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'
import Textarea from '../../../components/common/Textarea'

const DOC_TYPES = [
  { value: 'faq', label: 'Câu hỏi thường gặp' },
  { value: 'guide', label: 'Hướng dẫn' },
]

const TYPE_LABELS = Object.fromEntries(DOC_TYPES.map((item) => [item.value, item.label]))

/**
 * Tài liệu chương trình — đây chính là thứ chatbot Tibi đọc để trả lời (docs/06 §5).
 *
 * Hai điều màn hình phải nói rõ, vì không nói thì BTC không có cách nào biết:
 * 1. Sửa xong chưa có tác dụng với Tibi tới khi nạp lại kiến thức (`is_indexed` = false).
 * 2. Nội dung ở đây đi vào vector store nên **chỉ được chứa thông tin công khai** — không tên, không
 *    số điện thoại, không số phòng của ai.
 */
export default function DocumentsTab() {
  const toast = useToast()
  const { data: documents, isLoading, error } = useDocuments()
  const { mutateAsync: save, isPending: saving } = useSaveDocument()
  const { mutateAsync: remove, isPending: removing } = useDeleteDocument()
  const [editing, setEditing] = useState(null)

  const stale = (documents ?? []).filter((item) => !item.is_indexed).length

  async function onDelete(doc) {
    if (!window.confirm(`Xoá tài liệu "${doc.title}"? Tibi sẽ không còn trả lời theo nội dung này.`)) {
      return
    }
    try {
      await remove(doc.id)
      toast.success('Đã xoá tài liệu.')
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  return (
    <Card
      title="Tài liệu cho chatbot"
      description="Câu hỏi thường gặp và hướng dẫn — nguồn kiến thức của trợ lý Tibi"
      bodyClassName="p-0"
      action={
        <Button size="sm" icon={Plus} onClick={() => setEditing({})}>
          Thêm tài liệu
        </Button>
      }
    >
      <div className="grid gap-3 px-4 pt-4">
        <Alert tone="warning">
          Nội dung ở đây đi thẳng vào bộ nhớ của Tibi và ai hỏi cũng đọc được — chỉ viết thông tin công
          khai, không đưa tên, số điện thoại hay số phòng của bất kỳ ai.
        </Alert>
        {stale > 0 && (
          <Alert tone="info" title={`${stale} tài liệu chưa nạp vào Tibi`}>
            <span className="flex flex-wrap items-center gap-1">
              <Bot className="size-4 shrink-0" aria-hidden="true" />
              Tibi vẫn đang trả lời theo bản cũ. Bấm “Nạp lại kiến thức” ở Tổng quan hoặc ngay trong khung
              chat để cập nhật.
            </span>
          </Alert>
        )}
      </div>

      {isLoading ? (
        <Spinner />
      ) : error ? (
        <div className="p-4">
          <Alert tone="error">{error.message}</Alert>
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          title="Chưa có tài liệu nào"
          description="Thêm câu hỏi thường gặp để Tibi trả lời thay Ban tổ chức."
          action={
            <Button size="sm" icon={Plus} onClick={() => setEditing({})}>
              Thêm tài liệu đầu tiên
            </Button>
          }
        />
      ) : (
        <ul className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
          {documents.map((doc) => (
            <li key={doc.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                  {doc.title}
                  <Badge tone="blue">{TYPE_LABELS[doc.doc_type] ?? doc.doc_type}</Badge>
                  {doc.is_shared && <Badge tone="slate">Dùng chung mọi kỳ</Badge>}
                  {!doc.is_indexed && <Badge tone="amber">Chưa nạp vào Tibi</Badge>}
                </p>
                <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{doc.content}</p>
                <p className="mt-0.5 text-xs text-slate-400">
                  {doc.version} · sửa lần cuối {formatFullDateTime(doc.updated_at)}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Pencil}
                  disabled={!doc.can_edit}
                  onClick={() => setEditing(doc)}
                >
                  Sửa
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Trash2}
                  disabled={!doc.can_edit || removing}
                  onClick={() => onDelete(doc)}
                >
                  Xoá
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <DocumentFormModal
          doc={editing.id ? editing : null}
          saving={saving}
          onClose={() => setEditing(null)}
          onSubmit={async (payload) => {
            try {
              await save({ documentId: editing.id, payload })
              toast.success(editing.id ? 'Đã lưu tài liệu.' : 'Đã thêm tài liệu.')
              setEditing(null)
            } catch (saveError) {
              toast.error(saveError.message)
            }
          }}
        />
      )}
    </Card>
  )
}

function DocumentFormModal({ doc, saving, onClose, onSubmit }) {
  const [preview, setPreview] = useState(false)
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    defaultValues: {
      doc_type: doc?.doc_type ?? 'faq',
      title: doc?.title ?? '',
      version: doc?.version ?? 'v1',
      content: doc?.content ?? '',
    },
    mode: 'onTouched',
  })
  const content = watch('content')

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={doc ? 'Sửa tài liệu' : 'Thêm tài liệu'}
      description="Nội dung viết bằng markdown"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="doc-form" size="sm" icon={Save} loading={saving}>
            {doc ? 'Lưu thay đổi' : 'Thêm tài liệu'}
          </Button>
        </div>
      }
    >
      <form
        id="doc-form"
        noValidate
        onSubmit={handleSubmit((values) => onSubmit({ ...values, title: values.title.trim() }))}
        className="grid gap-3.5 sm:grid-cols-2"
      >
        <Select
          label="Loại"
          required
          options={DOC_TYPES}
          error={errors.doc_type?.message}
          {...register('doc_type', { required: 'Chọn loại tài liệu' })}
        />
        <Input
          label="Phiên bản"
          placeholder="v1"
          error={errors.version?.message}
          {...register('version')}
        />
        <div className="sm:col-span-2">
          <Input
            label="Tiêu đề"
            required
            placeholder="Câu hỏi thường gặp"
            error={errors.title?.message}
            {...register('title', { required: 'Nhập tiêu đề tài liệu' })}
          />
        </div>

        <div className="sm:col-span-2">
          <div className="mb-1 flex justify-end">
            <Button type="button" size="sm" variant="ghost" onClick={() => setPreview((open) => !open)}>
              {preview ? 'Soạn thảo' : 'Xem trước'}
            </Button>
          </div>
          {preview ? (
            <div className="min-h-40 rounded-lg border border-slate-200 p-3">
              {content?.trim() ? (
                <MarkdownText content={content} />
              ) : (
                <p className="text-sm text-slate-500">Chưa có nội dung.</p>
              )}
            </div>
          ) : (
            <Textarea
              label="Nội dung (markdown)"
              rows={14}
              required
              error={errors.content?.message}
              {...register('content', { required: 'Nhập nội dung tài liệu' })}
            />
          )}
        </div>
      </form>
    </Modal>
  )
}
