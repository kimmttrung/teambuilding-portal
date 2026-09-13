import { useState } from 'react'
import { Download } from 'lucide-react'
import { downloadFile } from '../../api/downloads'
import { useToast } from '../../context/ToastContext'
import Button from './Button'

/** Nút tải file Excel từ một endpoint export. Lỗi (403, chưa có kỳ đang chạy...) hiện bằng toast. */
export default function ExportButton({
  url,
  params,
  fallbackName,
  onDone,
  variant = 'secondary',
  size = 'md',
  children = 'Xuất Excel',
  ...props
}) {
  const toast = useToast()
  const [pending, setPending] = useState(false)

  async function handleClick() {
    setPending(true)
    try {
      const filename = await downloadFile(url, { params, fallbackName })
      toast.success(`Đã tải ${filename}`)
      onDone?.()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Button {...props} variant={variant} size={size} icon={Download} loading={pending} onClick={handleClick}>
      {children}
    </Button>
  )
}
