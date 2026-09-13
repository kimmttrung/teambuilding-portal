import { useState } from 'react'
import { Check, FileSpreadsheet, Play } from 'lucide-react'
import { useImportRooms } from '../../../hooks/useRooms'
import { useToast } from '../../../context/ToastContext'
import { formatNumber } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'

const COLUMNS = [
  { name: 'Số phòng', required: true, example: '1204' },
  { name: 'Mã NV (hoặc Email)', required: true, example: 'NV001' },
  { name: 'Khách sạn', required: false, example: 'Chỉ cần khi có nhiều khách sạn' },
  { name: 'Trưởng phòng', required: false, example: 'x / 1 / có' },
]

/**
 * Import phân phòng từ Excel: kiểm tra trước, chỉ ghi khi file sạch lỗi.
 *
 * Backend "tất cả hoặc không gì cả": còn một dòng lỗi là không ghi dòng nào, và trả số dòng
 * Excel để BTC sửa ngay trên file. Đổi file hoặc tuỳ chọn thì kết quả kiểm tra cũ bị xoá —
 * không để BTC ghi một file khác với file vừa kiểm tra.
 */
export default function RoomImportModal({ onClose }) {
  const toast = useToast()
  const { mutateAsync: runImport, isPending } = useImportRooms()
  const [file, setFileState] = useState(null)
  const [replaceExisting, setReplaceState] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  function setFile(value) {
    setFileState(value)
    setResult(null)
    setError(null)
  }

  function setReplaceExisting(value) {
    setReplaceState(value)
    setResult(null)
    setError(null)
  }

  async function run(dryRun) {
    setError(null)
    try {
      const data = await runImport({ file, dryRun, replaceExisting })
      if (dryRun) {
        setResult(data)
        return
      }
      toast.success(
        `Đã import phân phòng: ${data.to_create} người xếp mới, ${data.to_move} người chuyển phòng.`,
      )
      onClose()
    } catch (importError) {
      // Ghi thật mà dữ liệu đã đổi từ lúc kiểm tra: backend trả lại đủ danh sách lỗi.
      if (importError.code === 'IMPORT_VALIDATION_FAILED' && importError.details?.errors) {
        setResult(importError.details)
      }
      setError(importError)
    }
  }

  const clean = result && result.error_count === 0 && result.valid_rows > 0

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title="Import phân phòng từ Excel"
      description="Kiểm tra trước không ghi gì vào hệ thống"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {clean ? 'File hợp lệ — có thể ghi.' : 'Bấm "Kiểm tra file" trước khi ghi.'}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={Play}
              disabled={!file || isPending}
              loading={isPending && !clean}
              onClick={() => run(true)}
            >
              Kiểm tra file
            </Button>
            <Button size="sm" icon={Check} disabled={!clean || isPending} loading={isPending && clean} onClick={() => run(false)}>
              Ghi vào hệ thống
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <section>
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Cột trong sheet đầu tiên</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <tbody className="divide-y divide-slate-100">
                {COLUMNS.map((column) => (
                  <tr key={column.name}>
                    <td className="py-1.5 pr-3 font-medium text-slate-900">
                      {column.name}
                      {column.required && <span className="ml-0.5 text-rose-600">*</span>}
                    </td>
                    <td className="py-1.5 text-slate-500">{column.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            Tên cột không phân biệt hoa thường hay dấu. Mỗi dòng một người; phòng và giới tính được kiểm tra
            như khi xếp tay.
          </p>
        </section>

        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 p-5 text-center transition hover:border-brand-400 focus-within:border-brand-500">
          <FileSpreadsheet className="size-7 text-slate-400" aria-hidden="true" />
          <span className="text-sm font-medium text-slate-900">
            {file ? file.name : 'Chọn file .xlsx'}
          </span>
          <span className="text-xs text-slate-500">
            {file ? `${formatNumber(Math.ceil(file.size / 1024))} KB — bấm để chọn file khác` : 'Tối đa 2000 dòng'}
          </span>
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            onChange={(changeEvent) => setFile(changeEvent.target.files?.[0] ?? null)}
          />
        </label>

        <label className="flex items-start gap-2.5 rounded-lg bg-slate-50 p-3">
          <input
            type="checkbox"
            className="mt-0.5 size-4 shrink-0 accent-brand-600"
            checked={replaceExisting}
            onChange={(changeEvent) => setReplaceExisting(changeEvent.target.checked)}
          />
          <span className="text-xs leading-relaxed text-slate-600">
            <span className="block font-medium text-slate-900">Cho phép chuyển người đang ở phòng khác</span>
            Mặc định người đã có phòng mà file ghi phòng khác sẽ báo lỗi, để file cũ không ghi đè các chỉnh
            sửa tay của BTC.
          </span>
        </label>

        {error && !result && (
          <Alert tone="error" title="Không import được">
            {error.message}
          </Alert>
        )}

        {result && (
          <>
            <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-6">
              <Stat label="Tổng dòng" value={result.total_rows} />
              <Stat label="Hợp lệ" value={result.valid_rows} tone="emerald" />
              <Stat label="Lỗi" value={result.error_count} tone={result.error_count ? 'rose' : 'slate'} />
              <Stat label="Xếp mới" value={result.to_create} />
              <Stat label="Chuyển phòng" value={result.to_move} />
              <Stat label="Giữ nguyên" value={result.unchanged} />
            </div>

            {result.error_count > 0 ? (
              <Alert tone="error" title={`File còn ${result.error_count} dòng lỗi nên chưa ghi dòng nào`}>
                Sửa các dòng dưới đây ngay trên file Excel rồi kiểm tra lại.
              </Alert>
            ) : result.valid_rows > 0 ? (
              <Alert tone="success">File hợp lệ. Bấm "Ghi vào hệ thống" để áp dụng.</Alert>
            ) : (
              <Alert tone="warning">File không có dòng dữ liệu nào.</Alert>
            )}

            {result.errors?.length > 0 && (
              <div className="max-h-72 overflow-auto rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-50">
                    <tr className="text-left text-xs tracking-wide text-slate-500 uppercase">
                      <th className="w-20 px-3 py-2 font-medium">Dòng</th>
                      <th className="px-3 py-2 font-medium">Lỗi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.errors.map((item, index) => (
                      <tr key={`${item.row}-${item.code}-${index}`}>
                        <td className="px-3 py-2 text-slate-900 tabular-nums">{item.row}</td>
                        <td className="px-3 py-2 text-slate-700">{item.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}

const TONES = { slate: 'text-slate-900', emerald: 'text-emerald-700', rose: 'text-rose-700' }

function Stat({ label, value, tone = 'slate' }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-0.5 text-lg font-bold tabular-nums ${TONES[tone]}`}>{formatNumber(value)}</p>
    </div>
  )
}
