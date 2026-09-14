import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save, Trash2 } from 'lucide-react'
import { useDeleteGalaTable, useSaveGalaTable } from '../../../hooks/useGala'
import { useToast } from '../../../context/ToastContext'
import { galaTableSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'

/** Thêm / sửa / xoá bàn. Bàn mới được gợi ý mã và ô trống kế tiếp trên lưới. */
export default function TableFormModal({ table, view, onClose }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveGalaTable()
  const { mutateAsync: remove, isPending: removing } = useDeleteGalaTable()
  const { grid_width: width, grid_height: height } = view.layout
  const confirmedSeats = table ? table.seats.filter((seat) => seat.state === 'taken').length : 0

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(galaTableSchema),
    mode: 'onTouched',
    defaultValues: table ? toFormValues(table) : suggest(view),
  })

  async function onSubmit(values) {
    if (Number(values.pos_x) >= width || Number(values.pos_y) >= height) {
      toast.error(`Vị trí phải nằm trong lưới: cột 0–${width - 1}, hàng 0–${height - 1}.`)
      return
    }
    try {
      await save({ tableId: table?.id, payload: toPayload(values, Boolean(table)) })
      toast.success(table ? `Đã cập nhật bàn ${values.table_code}.` : `Đã thêm bàn ${values.table_code}.`)
      onClose()
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Xoá bàn ${table.table_code} và ${table.seat_count} ghế?`)) return
    try {
      await remove(table.id)
      toast.success(`Đã xoá bàn ${table.table_code}.`)
      onClose()
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={table ? `Sửa bàn ${table.table_code}` : 'Thêm bàn'}
      description={`Lưới ${width} cột × ${height} hàng, toạ độ tính từ 0`}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          {table ? (
            <Button
              variant="ghost"
              size="sm"
              icon={Trash2}
              loading={removing}
              disabled={confirmedSeats > 0}
              title={confirmedSeats ? 'Bàn đã có ghế thuộc team' : undefined}
              onClick={handleDelete}
              className="text-rose-600"
            >
              Xoá bàn
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Huỷ
            </Button>
            <Button type="submit" form="gala-table-form" size="sm" icon={Save} loading={isPending}>
              {table ? 'Lưu' : 'Thêm bàn'}
            </Button>
          </div>
        </div>
      }
    >
      <form id="gala-table-form" onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5 sm:grid-cols-2" noValidate>
        <Input label="Mã bàn" required placeholder="B01" error={errors.table_code?.message} {...register('table_code')} />
        <Input label="Tên bàn" placeholder="Bàn Công nghệ" error={errors.table_name?.message} {...register('table_name')} />
        <Input
          label="Số ghế"
          type="number"
          min={1}
          max={24}
          required
          hint={confirmedSeats ? `${confirmedSeats} ghế đã thuộc team — không bớt được các ghế đó` : undefined}
          error={errors.seat_count?.message}
          {...register('seat_count')}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Cột" type="number" min={0} max={width - 1} required error={errors.pos_x?.message} {...register('pos_x')} />
          <Input label="Hàng" type="number" min={0} max={height - 1} required error={errors.pos_y?.message} {...register('pos_y')} />
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="size-4 accent-brand-600" {...register('is_vip')} />
          Bàn VIP
        </label>
        {table && (
          <label className="inline-flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="size-4 accent-brand-600" {...register('is_available')} />
            Cho phép chọn ghế ở bàn này
          </label>
        )}
      </form>
    </Modal>
  )
}

function toFormValues(table) {
  return {
    table_code: table.table_code,
    table_name: table.table_name ?? '',
    seat_count: String(table.seat_count),
    pos_x: String(table.pos_x),
    pos_y: String(table.pos_y),
    is_vip: table.is_vip,
    is_available: table.is_available,
  }
}

/** Mã kế tiếp (B13) và ô trống đầu tiên, cách bàn khác 3 cột / 2 hàng như sơ đồ mẫu. */
function suggest(view) {
  const taken = new Set(view.tables.map((table) => `${table.pos_x}:${table.pos_y}`))
  let position = { x: 0, y: 0 }
  search: for (let y = 1; y < view.layout.grid_height; y += 2) {
    for (let x = 1; x < view.layout.grid_width; x += 3) {
      if (!taken.has(`${x}:${y}`)) {
        position = { x, y }
        break search
      }
    }
  }
  return {
    table_code: `B${String(view.tables.length + 1).padStart(2, '0')}`,
    table_name: '',
    seat_count: '10',
    pos_x: String(position.x),
    pos_y: String(position.y),
    is_vip: false,
    is_available: true,
  }
}

function toPayload(values, isEdit) {
  const payload = {
    table_code: values.table_code,
    table_name: values.table_name || null,
    seat_count: Number(values.seat_count),
    pos_x: Number(values.pos_x),
    pos_y: Number(values.pos_y),
    is_vip: values.is_vip,
  }
  if (isEdit) payload.is_available = values.is_available
  return payload
}
