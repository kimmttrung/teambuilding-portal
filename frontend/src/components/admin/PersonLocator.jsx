import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BedDouble, Bus, PartyPopper, Plane, Search, UserRound, X } from 'lucide-react'
import { usePeopleSearch, usePersonLocation } from '../../hooks/usePeople'
import { REGISTRATION_STATUS_META } from '../../utils/constants'
import Badge from '../common/Badge'
import Spinner from '../common/Spinner'

/**
 * Tìm một người rồi cho biết họ đang ở đâu — gắn trên cả 5 màn hình phân bổ (docs/13 task 7).
 *
 * Người đang tra cứu nằm trong URL (`?person=`), nên bấm từ thanh tóm tắt sang màn hình khác thì họ đi
 * theo, và F5 không mất. Màn hình nào tự đọc `usePersonLocation()` để tô đỏ phần của mình.
 *
 * Cố ý **không lọc** danh sách bên dưới: BTC cần thấy người đó ngồi cạnh ai và chuyến còn mấy chỗ thì
 * mới đổi chỗ được. Từng màn hình tự quyết cách làm nổi bật (viền đỏ, nền đỏ nhạt).
 */
export default function PersonLocator({ compact = false }) {
  const { userId, location, isLoading, select } = usePersonLocation()
  const [text, setText] = useState('')
  const { data: matches, isFetching } = usePeopleSearch(text, { enabled: !userId })

  if (userId) {
    return (
      <div className="rounded-xl border-2 border-rose-300 bg-rose-50/70 px-3.5 py-2.5">
        {isLoading ? (
          <Spinner label="Đang tra cứu…" />
        ) : location ? (
          <LocationSummary location={location} compact={compact} onClear={() => select(null)} />
        ) : (
          <div className="flex items-center justify-between gap-2 text-sm text-rose-800">
            Không tra cứu được người này.
            <ClearButton onClick={() => select(null)} />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3.5 py-2.5">
      <label htmlFor="person-locator" className="mb-1 flex items-center gap-1.5 text-xs font-medium text-slate-500">
        <Search className="size-3.5 shrink-0" aria-hidden="true" />
        Tìm người: họ đang ở chuyến nào, xe nào, phòng nào, ghế nào
      </label>
      <input
        id="person-locator"
        type="search"
        value={text}
        onChange={(changeEvent) => setText(changeEvent.target.value)}
        placeholder="Tên, email hoặc mã nhân viên — gõ không dấu cũng được"
        className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-900"
      />

      {text.trim().length >= 2 && (
        <div className="mt-1.5">
          {isFetching && !matches ? (
            <p className="text-xs text-slate-500">Đang tìm…</p>
          ) : matches?.length ? (
            <ul className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
              {matches.map((person) => (
                <li key={person.user_id}>
                  <button
                    type="button"
                    onClick={() => {
                      select(person.user_id)
                      setText('')
                    }}
                    className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-sm hover:bg-slate-50"
                  >
                    <UserRound className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-slate-900">{person.full_name}</span>
                      <span className="block truncate text-xs text-slate-500">
                        {[person.employee_code, person.team_name, person.email].filter(Boolean).join(' · ')}
                      </span>
                    </span>
                    {person.registration_status !== 'submitted' && (
                      <Badge tone="slate">
                        {REGISTRATION_STATUS_META[person.registration_status]?.label ?? 'Chưa đăng ký'}
                      </Badge>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-500">Không tìm thấy ai khớp “{text.trim()}”.</p>
          )}
        </div>
      )}
    </div>
  )
}

function LocationSummary({ location, compact, onClear }) {
  const notJoining = location.registration_status !== 'submitted' || !location.is_participating
  const flights = location.flights ?? {}

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="inline-block size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: location.team_color || '#e11d48' }}
          aria-hidden="true"
        />
        <span className="text-sm font-semibold text-rose-900">{location.full_name}</span>
        {location.employee_code && <span className="text-xs text-rose-700">{location.employee_code}</span>}
        {location.team_name && <Badge tone="rose">{location.team_name}</Badge>}
        {notJoining && (
          <Badge tone="slate">
            {REGISTRATION_STATUS_META[location.registration_status]?.label ?? 'Chưa đăng ký'}
          </Badge>
        )}
        <span className="ml-auto">
          <ClearButton onClick={onClear} />
        </span>
      </div>

      {notJoining ? (
        <p className="mt-1 text-sm text-rose-800">
          Người này không tham gia kỳ đang xem nên không có chỗ nào được xếp.
        </p>
      ) : (
        <ul className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-rose-900">
          <li className="flex items-center gap-1.5">
            <Plane className="size-4 shrink-0 text-rose-600" aria-hidden="true" />
            <Link
              to={`/admin/flights?person=${location.user_id}`}
              className="underline-offset-2 hover:underline"
            >
              {flights.outbound
                ? `${flights.outbound.flight_code}${flights.outbound.seat_number ? ` ghế ${flights.outbound.seat_number}` : ''}`
                : 'chưa có chuyến đi'}
              {' · '}
              {flights.return ? flights.return.flight_code : 'chưa có chuyến về'}
            </Link>
            {(flights.outbound || flights.return) && (
              <Link
                to={`/admin/flights/board?person=${location.user_id}`}
                title="Mở bảng điều khiển, tự bung thẻ team và tô đỏ dòng tên họ"
                className="rounded-md bg-rose-600 px-1.5 py-0.5 text-xs font-medium text-white hover:bg-rose-500"
              >
                Bảng điều khiển
              </Link>
            )}
          </li>

          <Item icon={Bus} to="/admin/buses" person={location.user_id}>
            {busLabel(location.buses)}
          </Item>

          <Item icon={BedDouble} to="/admin/rooms" person={location.user_id}>
            {location.room
              ? `Phòng ${location.room.room_number}${location.room.floor ? ` (tầng ${location.room.floor})` : ''}`
              : 'chưa có phòng'}
          </Item>

          <Item icon={PartyPopper} to="/admin/gala" person={location.user_id}>
            {location.gala
              ? `Bàn ${location.gala.table_code} – ghế ${location.gala.seat_number}`
              : 'chưa có ghế Gala'}
          </Item>

          {!compact && location.shift && (
            <li className="text-xs text-rose-700">Nguyện vọng: {location.shift.name}</li>
          )}
        </ul>
      )}
    </>
  )
}

function Item({ icon: Icon, to, person, children }) {
  return (
    <li>
      <Link
        to={`${to}?person=${person}`}
        className="flex items-center gap-1.5 underline-offset-2 hover:underline"
      >
        <Icon className="size-4 shrink-0 text-rose-600" aria-hidden="true" />
        {children}
      </Link>
    </li>
  )
}

/** "XE-03, XE-06 · thiếu 2 chặng" — nói cả phần chưa xếp, đó mới là thứ BTC cần xử lý. */
function busLabel(legs = []) {
  const assigned = legs.filter((leg) => leg.bus_id)
  const missing = legs.length - assigned.length
  if (assigned.length === 0) return legs.length ? `chưa có xe (${legs.length} chặng)` : 'kỳ chưa có chặng xe'
  const codes = assigned.map((leg) => leg.bus_code).join(', ')
  return missing > 0 ? `${codes} · thiếu ${missing} chặng` : codes
}

function ClearButton({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-xs font-medium text-rose-700 hover:bg-rose-100"
    >
      <X className="size-3.5" aria-hidden="true" />
      Bỏ tra cứu
    </button>
  )
}
