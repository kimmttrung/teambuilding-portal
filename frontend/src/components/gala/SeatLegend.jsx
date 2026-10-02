import { GALA_SEAT_STATE_LABELS } from '../../utils/constants'
import checkIcon from '../../assets/gala/check.svg'
import lockIcon from '../../assets/gala/lock.svg'
import { seatVisual } from '../../utils/gala'

const ITEMS = [
  { key: 'available', state: 'available' },
  { key: 'selected', state: 'available', selected: true },
  { key: 'held_by_me', state: 'held_by_me' },
  { key: 'held_by_other', state: 'held_by_other' },
  { key: 'taken', state: 'taken' },
  { key: 'my_taken', state: 'taken', mine: true },
  { key: 'unavailable', state: 'unavailable' },
]

/** Chú thích trạng thái ghế. `showSelected=false` với người không chọn ghế. */
export default function SeatLegend({ showSelected = true }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-muted">
      {ITEMS.filter((item) => showSelected || item.key !== 'selected').map((item) => {
        const visual = seatVisual(item.state, { selected: item.selected, mine: item.mine, teamId: item.state === 'taken' ? 1 : null })
        return (
          <li key={item.key} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={`grid size-4 place-items-center rounded-full text-[8px] ${visual.className}`}
              style={visual.style}
            >
              {item.state === 'held_by_me' ? (
                <img src={checkIcon} alt="" />
              ) : item.state === 'held_by_other' ? (
                <img src={lockIcon} alt="" />
              ) : null}
            </span>
            {item.key === 'my_taken' ? 'Team bạn · viền xanh' : item.key === 'taken' ? 'Đã xác nhận · màu theo team' : GALA_SEAT_STATE_LABELS[item.key]}
          </li>
        )
      })}
    </ul>
  )
}
