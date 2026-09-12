import { useFormContext } from 'react-hook-form'
import { CircleSlash, PartyPopper } from 'lucide-react'
import { formatDate } from '../../../utils/format'
import { missingFlightFields } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Card from '../../../components/common/Card'
import ChoiceCard from '../../../components/common/ChoiceCard'
import Textarea from '../../../components/common/Textarea'

/**
 * Bước 2 — xác nhận tham gia.
 *
 * Chọn "Không tham gia" thì bỏ qua bước ca đi và nhu cầu xe (container lo việc nhảy bước):
 * hỏi tiếp những thứ đó là làm khó người dùng và sinh dữ liệu rác cho thuật toán phân bổ.
 */
export default function ParticipationStep({ event, onGoToProfile }) {
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()

  const choice = watch('is_participating')
  const reason = watch('not_participating_reason') ?? ''
  const missing = missingFlightFields(watch('profile'))

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Bạn có tham gia Team Building lần này không?"
        description={`${event.name} · ${formatDate(event.start_date)} – ${formatDate(event.end_date)}`}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <ChoiceCard
            name="is_participating"
            value="yes"
            icon={PartyPopper}
            checked={choice === 'yes'}
            onChange={(value) => setValue('is_participating', value, { shouldValidate: true })}
            title="Có, tôi tham gia"
            description="BTC sẽ xếp chuyến bay, xe đưa đón, phòng khách sạn và chỗ ngồi Gala cho bạn."
          />
          <ChoiceCard
            name="is_participating"
            value="no"
            icon={CircleSlash}
            checked={choice === 'no'}
            onChange={(value) => setValue('is_participating', value, { shouldValidate: true })}
            title="Không, tôi không tham gia"
            description="Bạn vẫn cần gửi đăng ký để BTC biết và không tính suất cho bạn."
          />
        </div>

        {errors.is_participating && (
          <p className="mt-2.5 text-sm text-rose-600">{errors.is_participating.message}</p>
        )}
      </Card>

      {choice === 'yes' && missing.length > 0 && (
        <Alert tone="error" title="Phải bổ sung hồ sơ trước khi tham gia">
          <p>
            Thiếu <strong>{missing.join(', ')}</strong>. BTC không xuất được vé máy bay khi thiếu
            các thông tin này.
          </p>
          <button
            type="button"
            onClick={onGoToProfile}
            className="mt-1.5 font-semibold underline underline-offset-2"
          >
            Quay lại bước 1 để bổ sung
          </button>
        </Alert>
      )}

      {choice === 'no' && (
        <Card title="Lý do không tham gia" description="Không bắt buộc, nhưng giúp BTC thống kê">
          <Textarea
            rows={3}
            maxLength={512}
            counterValue={reason}
            placeholder="Ví dụ: trùng lịch công tác, lý do sức khoẻ, việc gia đình…"
            error={errors.not_participating_reason?.message}
            {...register('not_participating_reason')}
          />
          <Alert tone="info" className="mt-3.5">
            Gửi đăng ký "không tham gia" xong bạn vẫn sửa lại được trong thời gian mở đăng ký.
          </Alert>
        </Card>
      )}
    </div>
  )
}
