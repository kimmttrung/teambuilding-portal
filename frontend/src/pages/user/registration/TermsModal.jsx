import { useCallback, useEffect, useRef, useState } from 'react'
import { Check } from 'lucide-react'
import { useTerms } from '../../../hooks/useRegistration'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import MarkdownText from '../../../components/common/MarkdownText'
import Modal from '../../../components/common/Modal'
import Spinner from '../../../components/common/Spinner'

/**
 * Quy định chương trình. Nút "Đã đọc và đồng ý" chỉ bật khi người dùng cuộn hết
 * nội dung — bằng chứng đồng ý (bảng consents) mới có ý nghĩa khi người ta thực sự
 * đã thấy phần phí phạt ở cuối văn bản.
 */
export default function TermsModal({ event, open, onClose, onAgree }) {
  // Chỉ dựng nội dung khi mở: đóng rồi mở lại là bắt đầu lại việc cuộn từ đầu,
  // không phải nhớ trạng thái cũ.
  if (!open) return null
  return <TermsDialog event={event} onClose={onClose} onAgree={onAgree} />
}

function TermsDialog({ event, onClose, onAgree }) {
  const bodyRef = useRef(null)
  const [scrolledToEnd, setScrolledToEnd] = useState(false)
  const { data: terms, isLoading, error } = useTerms(event.id)

  const checkScrollEnd = useCallback(() => {
    const body = bodyRef.current
    if (!body) return
    // Nội dung ngắn hơn khung thì không có gì để cuộn, coi như đã đọc hết.
    if (body.scrollTop + body.clientHeight >= body.scrollHeight - 16) setScrolledToEnd(true)
  }, [])

  useEffect(() => {
    // Chờ nội dung render xong mới đo được chiều cao thật.
    const timer = setTimeout(checkScrollEnd, 80)
    return () => clearTimeout(timer)
  }, [terms, checkScrollEnd])

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Quy định chương trình"
      description={terms ? `Bản ${terms.version} · ${terms.event_code}` : event.code}
      bodyRef={bodyRef}
      onBodyScroll={checkScrollEnd}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {scrolledToEnd ? 'Bạn đã xem hết nội dung.' : 'Cuộn xuống hết để bật nút đồng ý.'}
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={onClose}>
              Đóng
            </Button>
            <Button
              type="button"
              size="sm"
              icon={Check}
              disabled={!scrolledToEnd || !terms}
              onClick={() => {
                onAgree(terms.version)
                onClose()
              }}
            >
              Tôi đã đọc và đồng ý
            </Button>
          </div>
        </div>
      }
    >
      {isLoading && <Spinner label="Đang tải quy định…" />}
      {error && <Alert tone="error">{error.message}</Alert>}
      {terms && <MarkdownText content={terms.content} />}
    </Modal>
  )
}
