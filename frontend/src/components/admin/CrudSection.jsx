import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { useDeleteMasterData, useMasterData, useSaveMasterData } from '../../hooks/useMasterData'
import { useToast } from '../../context/ToastContext'
import Alert from '../common/Alert'
import Button from '../common/Button'
import Card from '../common/Card'
import EmptyState from '../common/EmptyState'
import Input from '../common/Input'
import Modal from '../common/Modal'
import Select from '../common/Select'
import Spinner from '../common/Spinner'

/**
 * Bảng CRUD dùng chung cho 6 loại master data (docs/13 task 4).
 *
 * Sáu loại có cùng khuôn endpoint và cùng kiểu thao tác (liệt kê → thêm → sửa → xoá), khác nhau chỉ ở
 * danh sách trường. Viết sáu màn hình gần giống nhau thì mỗi lần đổi hành vi phải sửa sáu chỗ, nên ở
 * đây mô tả bằng cấu hình `fields`.
 *
 * Không dùng Zod như các form khác: schema sẽ phải sinh động theo `fields`, mà backend đã là nơi
 * quyết định đúng/sai (pattern mã, trùng mã, đang được dùng nên không xoá được). Ở đây chỉ chặn bỏ
 * trống, còn lại để lỗi thật của backend hiện lên toast — đỡ hai nguồn luật lệch nhau.
 */
export default function CrudSection({
  resource,
  title,
  description,
  fields,
  columns,
  emptyTitle = 'Chưa có dữ liệu',
  emptyHint,
  canWrite = true,
  readOnlyNote,
}) {
  const toast = useToast()
  const { data: rows, isLoading, error } = useMasterData(resource)
  const { mutateAsync: save, isPending: saving } = useSaveMasterData(resource)
  const { mutateAsync: remove, isPending: removing } = useDeleteMasterData(resource)
  const [editing, setEditing] = useState(null) // null = đóng; {} = thêm mới; {…} = sửa

  async function onDelete(row) {
    const label = row.name || row.code
    if (!window.confirm(`Xoá "${label}"? Không khôi phục lại được.`)) return
    try {
      await remove(row.id)
      toast.success(`Đã xoá ${label}.`)
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  return (
    <Card
      title={title}
      description={description}
      bodyClassName="p-0"
      action={
        canWrite && (
          <Button size="sm" icon={Plus} onClick={() => setEditing({})}>
            Thêm
          </Button>
        )
      }
    >
      {readOnlyNote && (
        <div className="px-4 pt-4">
          <Alert tone="info">{readOnlyNote}</Alert>
        </div>
      )}

      {isLoading ? (
        <Spinner />
      ) : error ? (
        <div className="p-4">
          <Alert tone="error">{error.message}</Alert>
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title={emptyTitle}
          description={emptyHint}
          action={
            canWrite && (
              <Button size="sm" icon={Plus} onClick={() => setEditing({})}>
                Thêm mục đầu tiên
              </Button>
            )
          }
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
              <tr>
                {columns.map((column) => (
                  <th key={column.key} className="px-4 py-2 font-medium">
                    {column.label}
                  </th>
                ))}
                {canWrite && <th className="px-4 py-2 text-right font-medium">Thao tác</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id} className="text-slate-900">
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-2 align-top">
                      {column.render ? column.render(row) : (row[column.key] ?? '—')}
                    </td>
                  ))}
                  {canWrite && (
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(row)}>
                        Sửa
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={Trash2}
                        disabled={removing}
                        onClick={() => onDelete(row)}
                      >
                        Xoá
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <CrudFormModal
          title={title}
          fields={fields}
          item={editing.id ? editing : null}
          saving={saving}
          onClose={() => setEditing(null)}
          onSubmit={async (payload) => {
            try {
              await save({ itemId: editing.id, payload })
              toast.success(editing.id ? 'Đã lưu thay đổi.' : 'Đã thêm mới.')
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

function CrudFormModal({ title, fields, item, saving, onClose, onSubmit }) {
  const editable = fields.filter((field) => !(item && field.immutable))
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues: defaultsFor(fields, item), mode: 'onTouched' })

  return (
    <Modal
      open
      onClose={onClose}
      title={item ? `Sửa ${title.toLowerCase()}` : `Thêm ${title.toLowerCase()}`}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="crud-form" size="sm" icon={Save} loading={saving}>
            {item ? 'Lưu thay đổi' : 'Thêm'}
          </Button>
        </div>
      }
    >
      <form
        id="crud-form"
        noValidate
        className="grid gap-3.5 sm:grid-cols-2"
        onSubmit={handleSubmit((values) => onSubmit(toPayload(editable, values)))}
      >
        {item && fields.some((field) => field.immutable) && (
          <div className="sm:col-span-2">
            <Alert tone="info">Mã không đổi được sau khi tạo — dữ liệu cũ đang tham chiếu tới nó.</Alert>
          </div>
        )}

        {editable.map((field) => {
          const rules = field.required ? { required: `Nhập ${field.label.toLowerCase()}` } : {}
          const common = { key: field.name, label: field.label, error: errors[field.name]?.message }

          if (field.type === 'checkbox') {
            return (
              <label key={field.name} className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" className="size-4" {...register(field.name)} />
                {field.label}
              </label>
            )
          }
          if (field.type === 'select') {
            return (
              <Select
                {...common}
                required={field.required}
                placeholder={field.placeholder ?? '— Không chọn —'}
                options={field.options ?? []}
                {...register(field.name, rules)}
              />
            )
          }
          return (
            <Input
              {...common}
              type={field.type ?? 'text'}
              required={field.required}
              placeholder={field.placeholder}
              hint={field.hint}
              {...register(field.name, rules)}
            />
          )
        })}
      </form>
    </Modal>
  )
}

function defaultsFor(fields, item) {
  return Object.fromEntries(
    fields.map((field) => {
      const value = item?.[field.name]
      if (field.type === 'checkbox') return [field.name, value ?? field.defaultValue ?? true]
      return [field.name, value ?? field.defaultValue ?? '']
    }),
  )
}

/** Ô trống gửi lên thành `null` chứ không phải chuỗi rỗng: backend coi "" là giá trị hợp lệ. */
function toPayload(fields, values) {
  const payload = {}
  for (const field of fields) {
    const raw = values[field.name]
    if (field.type === 'checkbox') payload[field.name] = Boolean(raw)
    else if (field.type === 'number') payload[field.name] = raw === '' ? 0 : Number(raw)
    else if (field.type === 'select' && field.numeric) payload[field.name] = raw === '' ? null : Number(raw)
    else payload[field.name] = raw === '' ? null : raw
  }
  return payload
}
