import { useState } from 'react'
import Alert from '../../../components/common/Alert'
import ExportButton from '../../../components/common/ExportButton'
import Modal from '../../../components/common/Modal'

const CHOICES = [
  {
    value: false,
    title: 'Danh sách cơ bản',
    description: 'Mã NV, họ tên, email, SĐT, team, phòng ban, chức danh, vai trò, trạng thái đăng ký kỳ này.',
  },
  {
    value: true,
    title: 'Kèm giấy tờ cá nhân',
    description: 'Thêm ngày sinh, số CCCD/hộ chiếu, địa chỉ, liên hệ khẩn cấp — dùng khi đặt vé, làm bảo hiểm.',
  },
]

/** Chọn mức dữ liệu trước khi xuất danh sách CBNV. Không bao giờ có ghi chú sức khoẻ. */
export default function UserExportModal({ onClose }) {
  const [sensitive, setSensitive] = useState(false)

  return (
    <Modal
      open
      onClose={onClose}
      title="Xuất danh sách CBNV"
      description="File .xlsx — sheet đầu import lại được"
      footer={
        <div className="flex justify-end">
          <ExportButton
            variant={sensitive ? 'danger' : 'primary'}
            size="sm"
            url="/admin/users/export"
            params={{ include_sensitive: sensitive }}
            fallbackName="cbnv.xlsx"
            onDone={onClose}
          >
            Tải file
          </ExportButton>
        </div>
      }
    >
      <div className="flex flex-col gap-3" role="radiogroup" aria-label="Mức dữ liệu">
        {CHOICES.map((choice) => (
          <label
            key={String(choice.value)}
            className={`flex cursor-pointer items-start gap-3 rounded-lg p-3 ring-1 transition ring-inset ${
              sensitive === choice.value ? 'bg-brand-50 ring-brand-400' : 'ring-slate-200 hover:bg-slate-50'
            }`}
          >
            <input
              type="radio"
              name="export-level"
              className="mt-0.5 size-4 shrink-0 accent-brand-600"
              checked={sensitive === choice.value}
              onChange={() => setSensitive(choice.value)}
            />
            <span>
              <span className="block text-sm font-medium text-slate-900">{choice.title}</span>
              <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">{choice.description}</span>
            </span>
          </label>
        ))}

        {sensitive && (
          <Alert tone="warning" title="File có dữ liệu cá nhân nhạy cảm">
            Mỗi lần tải được ghi vào nhật ký hệ thống. Không gửi file qua email hay nhóm chat; xoá khỏi máy
            khi dùng xong.
          </Alert>
        )}
      </div>
    </Modal>
  )
}
