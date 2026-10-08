import { useState } from 'react'
import { UserPlus } from 'lucide-react'
import { useAssignGalaMember, useGalaUnseated } from '../../../hooks/useGala'
import { usePersonLocation } from '../../../hooks/usePeople'
import { scrollIntoView } from '../../../utils/highlight'
import { useToast } from '../../../context/ToastContext'
import { GALA_NO_TEAM_LABEL } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Avatar from '../../../components/common/Avatar'
import Card from '../../../components/common/Card'
import Spinner from '../../../components/common/Spinner'

/**
 * Người tham gia chưa được xếp vào ghế cụ thể — chính là con số chặn kỳ chuyển sang "Đang diễn ra".
 *
 * Người chưa thuộc team nào luôn nằm ở đây: không team nào bốc thăm hộ nên không ai chọn ghế cho
 * họ. BTC gán thẳng vào bất kỳ ghế trống nào; ghế đó nhận team của người ngồi, hoặc không thuộc
 * team nào nếu họ chưa có team.
 */
export default function UnseatedCard({ view, embedded = false }) {
  const toast = useToast()
  const [actionError, setActionError] = useState(null)
  const { data: people, isLoading, error } = useGalaUnseated()
  const { mutateAsync: assign, isPending } = useAssignGalaMember()
  // Người đang tra cứu mà chưa có ghế thì nằm trong danh sách này — tô đỏ để thấy ngay.
  const { location: locatedPerson } = usePersonLocation()
  const locatedRegId = locatedPerson?.registration_id ?? null

  // Ghế xếp được: còn trống hẳn, hoặc đã thuộc team nhưng chưa có ai ngồi.
  const openSeats = view.tables.flatMap((table) =>
    table.seats
      .filter(
        (seat) => seat.state === 'available' || (seat.state === 'taken' && !seat.registration_id),
      )
      .map((seat) => ({ ...seat, table_code: table.table_code })),
  )

  async function choose(person, value) {
    if (!value) return
    const seat = openSeats.find((item) => item.id === Number(value))
    setActionError(null)
    try {
      await assign({ seatId: Number(value), registrationId: person.registration_id })
      toast.success(`${person.full_name} ngồi ${seat?.table_code} – ghế ${seat?.seat_number}.`)
    } catch (assignError) {
      setActionError(assignError.message)
    }
  }

  if (error) {
    return (
      <Card title={embedded ? undefined : "Chưa có ghế"} className={embedded ? "border-0 rounded-none" : ""}>
        <Alert tone="error">{error.message}</Alert>
      </Card>
    )
  }

  return (
    <Card
      title={embedded ? undefined : "Chưa có ghế"}
      className={embedded ? 'rounded-none border-0 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:overflow-hidden' : ''}
      description={
        people
          ? people.length
            ? `${people.length} người tham gia chưa được xếp chỗ — xếp hết mới bắt đầu sự kiện được`
            : undefined
          : undefined
      }
      bodyClassName={embedded ? 'p-0 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:overflow-hidden' : 'p-0'}
    >
      {embedded && people?.length > 0 && <p className="px-4 pt-4 text-caption text-ink-muted">{people.length} người tham gia chưa được xếp chỗ.</p>}
      {actionError && (
        <div className="p-4">
          <Alert tone="error">{actionError}</Alert>
        </div>
      )}
      {isLoading ? (
        <Spinner />
      ) : !people?.length ? (
        <p className="px-4 py-3.5 text-sm text-ink-muted">Mọi người tham gia đều đã có ghế.</p>
      ) : openSeats.length === 0 ? (
        <div className="p-4">
          <Alert tone="warning" title={`${people.length} người chưa có ghế nhưng sơ đồ đã kín`}>
            Thêm bàn hoặc mở khoá ghế trước, rồi quay lại xếp chỗ cho họ.
          </Alert>
        </div>
      ) : (
        <ul className="max-h-[28rem] min-h-0 flex-1 divide-y divide-hairline overflow-y-auto xl:max-h-none">
          {people.map((person) => (
            <li
              key={person.registration_id}
              ref={person.registration_id === locatedRegId ? scrollIntoView : undefined}
              className={`flex items-center gap-2.5 px-4 py-2 ${
                person.registration_id === locatedRegId
                  ? 'border-l-4 border-rose-500 bg-rose-50'
                  : ''
              }`}
            >
              <Avatar user={person} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink">{person.full_name}</p>
                <p className="truncate text-xs text-ink-muted">
                  {person.team_name ?? GALA_NO_TEAM_LABEL}
                  {person.employee_code ? ` · ${person.employee_code}` : ''}
                </p>
              </div>
              <label className="sr-only" htmlFor={`gala-unseated-${person.registration_id}`}>
                Ghế cho {person.full_name}
              </label>
              <select
                id={`gala-unseated-${person.registration_id}`}
                value=""
                disabled={isPending}
                onChange={(changeEvent) => choose(person, changeEvent.target.value)}
                className="min-h-11 w-32 shrink-0 rounded-md border border-input-border bg-surface px-2 text-caption text-ink"
              >
                <option value="">Chọn ghế…</option>
                {openSeats.map((seat) => (
                  <option key={seat.id} value={seat.id}>
                    {seat.table_code} – ghế {seat.seat_number}
                    {seat.team_name ? ` (${seat.team_name})` : ''}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      )}
      {people?.length > 0 && openSeats.length > 0 && (
        <p className="flex shrink-0 items-start gap-1.5 border-t border-hairline px-4 py-2.5 text-xs text-ink-muted">
          <UserPlus className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Chọn ghế trống thì ghế đó thành ghế của người được xếp. Muốn đổi chỗ hoặc gỡ ra thì bấm
          thẳng vào ghế trên sơ đồ.
        </p>
      )}
    </Card>
  )
}
