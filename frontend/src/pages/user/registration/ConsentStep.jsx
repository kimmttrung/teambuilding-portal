import { useState } from 'react'
import { useFormContext } from 'react-hook-form'
import { FileText } from 'lucide-react'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import Textarea from '../../../components/common/Textarea'
import TermsModal from './TermsModal'

/**
 * Bước 5 — mong muốn và đồng ý quy định.
 *
 * Checkbox đồng ý chỉ bật sau khi người dùng mở modal và cuộn hết quy định. Người
 * không tham gia không phải đồng ý gì: backend cũng chỉ đòi consent khi tham gia.
 */
export default function ConsentStep({ event }) {
  const [termsOpen, setTermsOpen] = useState(false)
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()

  const participating = watch('is_participating') === 'yes'
  const agreed = watch('agreed_terms')
  const wishNote = watch('wish_note') ?? ''

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Mong muốn gửi BTC"
        description="Không bắt buộc — BTC cân nhắc trong khả năng cho phép"
      >
        <Textarea
          label="Nguyện vọng, đề xuất hoặc lưu ý riêng"
          rows={4}
          maxLength={2000}
          counterValue={wishNote}
          placeholder="Ví dụ: muốn ở cùng phòng với anh Nam (team Kinh doanh), bị say xe nên xin ngồi ghế đầu…"
          error={errors.wish_note?.message}
          {...register('wish_note')}
        />

        {participating && (
          <div className="mt-3.5 sm:max-w-xs">
            <Input
              label="Số người đi cùng"
              type="number"
              min={0}
              max={5}
              hint="Vợ/chồng, con… BTC sẽ liên hệ xác nhận nếu chương trình cho phép"
              error={errors.companion_count?.message}
              {...register('companion_count')}
            />
          </div>
        )}
      </Card>

      {participating ? (
        <Card title="Quy định chương trình và phí phạt">
          <p className="text-sm text-slate-600">
            Đọc hết quy định trước khi gửi đăng ký. Phần quan trọng nhất là mục huỷ đăng ký:
            huỷ sau hạn đăng ký, bạn có thể phải chịu chi phí vé máy bay và phòng đã đặt.
          </p>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={FileText}
            className="mt-3"
            onClick={() => setTermsOpen(true)}
          >
            {agreed ? 'Xem lại quy định' : 'Đọc quy định chương trình'}
          </Button>

          <label
            className={`mt-3.5 flex items-start gap-3 rounded-lg border p-3 transition
              ${agreed ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-slate-50'}
              ${agreed ? 'cursor-pointer' : 'cursor-not-allowed'}`}
          >
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 accent-brand-600"
              // Chỉ cho tick sau khi đã đọc trong modal. Bỏ tick thì luôn được.
              disabled={!agreed}
              checked={Boolean(agreed)}
              onChange={(changeEvent) =>
                setValue('agreed_terms', changeEvent.target.checked, { shouldValidate: true })
              }
            />
            <span className="text-sm text-slate-700">
              Tôi đã đọc và đồng ý quy định chương trình, bao gồm quy định về huỷ đăng ký và phí
              phạt.
              {!agreed && (
                <span className="mt-0.5 block text-xs text-slate-500">
                  Bấm "Đọc quy định chương trình" và cuộn hết nội dung để bật ô này.
                </span>
              )}
            </span>
          </label>

          {errors.agreed_terms && (
            <p className="mt-2 text-sm text-rose-600">{errors.agreed_terms.message}</p>
          )}

          <TermsModal
            event={event}
            open={termsOpen}
            onClose={() => setTermsOpen(false)}
            onAgree={(version) => {
              setValue('agreed_terms', true, { shouldValidate: true })
              setValue('agreed_terms_version', version)
            }}
          />
        </Card>
      ) : (
        <Alert tone="info" title="Bạn đang chọn không tham gia">
          Không cần đồng ý quy định. Bấm "Gửi đăng ký" để BTC ghi nhận, và bạn vẫn đổi ý được
          trong thời gian còn mở đăng ký.
        </Alert>
      )}
    </div>
  )
}
