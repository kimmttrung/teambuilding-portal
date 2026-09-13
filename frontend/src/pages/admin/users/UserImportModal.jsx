import { useState } from 'react'
import { Check, Copy, Download, FileSpreadsheet, KeyRound, Play } from 'lucide-react'
import { useImportUsers } from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { formatNumber } from '../../../utils/format'
import { buildCsv, saveBlob } from '../../../utils/files'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'

const COLUMNS = [
  { name: 'Mã NV', required: true, example: 'NV001 — khớp tài khoản theo mã, không có thì theo email' },
  { name: 'Họ tên', required: true, example: 'Nguyễn Văn An' },
  { name: 'Email', required: true, example: 'an.nguyen@company.vn' },
  { name: 'Giới tính', required: false, example: 'Nam / Nữ / Khác' },
  { name: 'SĐT', required: false, example: '0912345678' },
  { name: 'Team · Phòng ban · Nơi làm việc', required: false, example: 'Ghi theo mã hoặc tên đã có trong hệ thống' },
  { name: 'Chức danh', required: false, example: 'Kỹ sư phần mềm' },
  { name: 'Ngày vào làm · Ngày sinh', required: false, example: '31/12/2020 hoặc ô kiểu ngày' },
  { name: 'Vai trò', required: false, example: 'CBNV / Trưởng nhóm' },
  { name: 'Số CCCD/Hộ chiếu', required: false, example: '001095012345' },
]

/**
 * Import danh sách CBNV: kiểm tra trước, chỉ ghi khi file sạch lỗi (backend tất cả-hoặc-không).
 *
 * Ghi xong mà có tài khoản mới thì chuyển sang màn mật khẩu tạm: đây là lần DUY NHẤT thấy được
 * chúng, nên đóng hộp thoại khi chưa tải/sao chép phải hỏi lại.
 */
export default function UserImportModal({ onClose }) {
  const toast = useToast()
  const { mutateAsync: runImport, isPending } = useImportUsers()
  const [file, setFileState] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [accounts, setAccounts] = useState(null)
  const [saved, setSaved] = useState(false)

  function setFile(value) {
    setFileState(value)
    setResult(null)
    setError(null)
  }

  async function run(dryRun) {
    setError(null)
    try {
      const data = await runImport({ file, dryRun })
      if (dryRun) {
        setResult(data)
        return
      }
      toast.success(
        `Đã import: ${data.to_create} tài khoản mới, ${data.to_update} người được cập nhật.`,
      )
      if (!data.created_accounts?.length) {
        onClose()
        return
      }
      setResult(data)
      setAccounts(data.created_accounts)
    } catch (importError) {
      if (importError.code === 'IMPORT_VALIDATION_FAILED' && importError.details?.errors) {
        setResult(importError.details)
      }
      setError(importError)
    }
  }

  function close() {
    if (
      accounts?.length &&
      !saved &&
      !window.confirm('Mật khẩu tạm chỉ hiện một lần và bạn chưa tải hoặc sao chép. Vẫn đóng?')
    ) {
      return
    }
    onClose()
  }

  if (accounts) {
    return (
      <CreatedAccounts
        accounts={accounts}
        onSaved={() => setSaved(true)}
        onClose={close}
      />
    )
  }

  const clean = result && result.error_count === 0 && result.valid_rows > 0

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title="Import danh sách CBNV"
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
                    <td className="py-1.5 pr-3 font-medium whitespace-nowrap text-slate-900">
                      {column.name}
                      {column.required && <span className="ml-0.5 text-rose-600">*</span>}
                    </td>
                    <td className="py-1.5 text-slate-500">{column.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-relaxed text-slate-500">
            <li>Mẹo: bấm "Xuất Excel" ở trang này để có sẵn file đúng cột, sửa rồi import lại.</li>
            <li>Ô trống giữ nguyên dữ liệu cũ — không xoá số điện thoại hay CCCD CBNV đã tự khai.</li>
            <li>Import không cấp quyền Ban tổ chức và không sửa tài khoản Ban tổ chức.</li>
          </ul>
        </section>

        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 p-5 text-center transition hover:border-brand-400 focus-within:border-brand-500">
          <FileSpreadsheet className="size-7 text-slate-400" aria-hidden="true" />
          <span className="text-sm font-medium text-slate-900">{file ? file.name : 'Chọn file .xlsx'}</span>
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

        {error && !result && (
          <Alert tone="error" title="Không import được">
            {error.message}
          </Alert>
        )}

        {result && <ImportResult result={result} />}
      </div>
    </Modal>
  )
}

function ImportResult({ result }) {
  return (
    <>
      <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-6">
        <Stat label="Tổng dòng" value={result.total_rows} />
        <Stat label="Hợp lệ" value={result.valid_rows} tone="emerald" />
        <Stat label="Lỗi" value={result.error_count} tone={result.error_count ? 'rose' : 'slate'} />
        <Stat label="Tạo mới" value={result.to_create} />
        <Stat label="Cập nhật" value={result.to_update} />
        <Stat label="Giữ nguyên" value={result.unchanged} />
      </div>

      {result.error_count > 0 ? (
        <Alert tone="error" title={`File còn ${result.error_count} dòng lỗi nên chưa ghi dòng nào`}>
          Sửa các dòng dưới đây ngay trên file Excel rồi kiểm tra lại.
        </Alert>
      ) : result.valid_rows > 0 ? (
        <Alert tone="success">
          File hợp lệ. {result.to_create > 0 && `${result.to_create} tài khoản mới sẽ nhận mật khẩu tạm, hiện một lần sau khi ghi.`}
        </Alert>
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
  )
}

function CreatedAccounts({ accounts, onSaved, onClose }) {
  const toast = useToast()

  function downloadCsv() {
    const csv = buildCsv(
      ['Mã NV', 'Họ tên', 'Email', 'Mật khẩu tạm'],
      accounts.map((account) => [account.employee_code, account.full_name, account.email, account.temporary_password]),
    )
    saveBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), 'mat-khau-tam-cbnv.csv')
    onSaved()
  }

  async function copyAll() {
    const text = accounts
      .map((account) => [account.employee_code, account.full_name, account.email, account.temporary_password].join('\t'))
      .join('\n')
    try {
      await navigator.clipboard.writeText(text)
      onSaved()
      toast.success('Đã sao chép — dán thẳng vào Excel được.')
    } catch {
      toast.error('Trình duyệt không cho sao chép. Hãy tải file CSV.')
    }
  }

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Đã tạo ${formatNumber(accounts.length)} tài khoản`}
      description="Mật khẩu tạm chỉ hiện ở đây một lần"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            <Button size="sm" icon={Download} onClick={downloadCsv}>
              Tải file CSV
            </Button>
            <Button size="sm" variant="secondary" icon={Copy} onClick={copyAll}>
              Sao chép tất cả
            </Button>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Xong
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <Alert tone="warning" title="Lưu lại trước khi đóng">
          Hệ thống không lưu mật khẩu dạng đọc được và không gửi qua email. Trao mật khẩu cho từng người qua kênh
          riêng; lần đăng nhập đầu họ sẽ phải đổi mật khẩu. Quên thì dùng "Đặt lại mật khẩu" trong hồ sơ CBNV.
        </Alert>
        <div className="max-h-80 overflow-auto rounded-lg border border-slate-200">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="sticky top-0 bg-slate-50">
              <tr className="text-left text-xs tracking-wide text-slate-500 uppercase">
                <th className="px-3 py-2 font-medium">Mã NV</th>
                <th className="px-3 py-2 font-medium">Họ tên</th>
                <th className="px-3 py-2 font-medium">Email</th>
                <th className="px-3 py-2 font-medium">Mật khẩu tạm</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {accounts.map((account) => (
                <tr key={account.email}>
                  <td className="px-3 py-2 text-slate-500">{account.employee_code}</td>
                  <td className="px-3 py-2 font-medium text-slate-900">{account.full_name}</td>
                  <td className="px-3 py-2 text-slate-600">{account.email}</td>
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-1.5 rounded bg-slate-100 px-2 py-0.5 font-mono text-slate-900">
                      <KeyRound className="size-3.5 text-slate-400" aria-hidden="true" />
                      {account.temporary_password}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
