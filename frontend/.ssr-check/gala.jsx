import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import { parseSseBlock } from '../src/api/sse'
import GalaPage from '../src/pages/gala/GalaPage'
import GalaAdminPage from '../src/pages/admin/GalaAdminPage'
import SeatAdminModal from '../src/pages/admin/gala/SeatAdminModal'
import TableFormModal from '../src/pages/admin/gala/TableFormModal'
import LayoutFormModal from '../src/pages/admin/gala/LayoutFormModal'
import UnseatedCard from '../src/pages/admin/gala/UnseatedCard'
import SeatMap from '../src/components/gala/SeatMap'
import { EVENT, OPTIONS } from './fixtures.js'

const NOW = '2026-10-16T10:00:00+00:00'
const LATER = '2026-10-16T10:04:00+00:00'

const seat = (id, number, state, extra = {}) => ({
  id, seat_number: number, state, team_id: null, team_name: null, team_color: null,
  registration_id: null, occupant_name: null, hold_expires_at: null, ...extra,
})

const TABLES = [
  {
    id: 1, table_code: 'B01', table_name: 'Bàn VIP', seat_count: 6, pos_x: 1, pos_y: 1, is_vip: true, is_available: true,
    available_seats: 2,
    seats: [
      seat(11, 1, 'taken', { team_id: 1, team_name: 'Team Alpha', team_color: '#4f46e5', registration_id: 7, occupant_name: 'Nguyễn Văn Trung' }),
      seat(12, 2, 'taken', { team_id: 1, team_name: 'Team Alpha', team_color: '#4f46e5' }),
      seat(13, 3, 'held_by_me', { team_id: 1, team_name: 'Team Alpha', hold_expires_at: LATER }),
      seat(14, 4, 'held_by_other', { team_id: 2, team_name: 'Team Beta' }),
      seat(15, 5, 'available'),
      seat(16, 6, 'available'),
    ],
  },
  {
    id: 2, table_code: 'B02', table_name: null, seat_count: 4, pos_x: 4, pos_y: 1, is_vip: false, is_available: false,
    available_seats: 0,
    seats: [1, 2, 3, 4].map((number) => seat(20 + number, number, 'unavailable')),
  },
]

const order = (position, teamId, name, status, extra = {}) => ({
  position, team_id: teamId, team_code: `T${teamId}`, team_name: name, team_color: '#4f46e5', quota: 5,
  confirmed: 0, held: 0, remaining: 5, status, turn_started_at: null, turn_ends_at: null, ...extra,
})

const view = (status, overrides = {}) => ({
  layout: {
    id: 1, name: 'Gala Dinner – Đêm hội Phú Quốc', venue: 'Sảnh Pearl', starts_at: '2026-10-16T11:30:00+00:00',
    stage_position: 'top', grid_width: 12, grid_height: 8, selection_status: status, turn_seconds: 300,
    hold_seconds: 120, draw_seed: status === 'closed' ? null : 20261016,
  },
  tables: TABLES,
  draw: {
    selection_status: status,
    draw_seed: null,
    active_team_id: status === 'open' ? 1 : null,
    active_turn_ends_at: status === 'open' ? LATER : null,
    orders:
      status === 'closed'
        ? []
        : [
            order(1, 1, 'Team Alpha', status === 'open' ? 'active' : status === 'finalized' ? 'done' : 'waiting', {
              confirmed: 2, held: 1, remaining: 2, turn_ends_at: status === 'open' ? LATER : null,
            }),
            order(2, 2, 'Team Beta', 'waiting', { held: 1, remaining: 4 }),
          ],
    total_quota: status === 'closed' ? 0 : 10,
    total_seats: 6,
    unteamed_participants: 3,
    server_time: NOW,
  },
  my_team: {
    team_id: 1, team_name: 'Team Alpha', team_color: '#4f46e5', is_leader: true, draw_position: 1,
    status: 'active', quota: 5, confirmed: 2, held: 1, remaining: 2, is_my_turn: status === 'open',
    turn_ends_at: status === 'open' ? LATER : null, hold_expires_at: LATER,
  },
  totals: { seats: 10, available: 2, held: 2, taken: 2, unavailable: 4 },
  can_manage: false,
  server_time: NOW,
  ...overrides,
})

const MEMBERS = [
  { registration_id: 7, user_id: 1, full_name: 'Nguyễn Văn Trung', employee_code: 'NV001', avatar_url: null, seat_id: 11, table_code: 'B01', seat_number: 1 },
  { registration_id: 8, user_id: 2, full_name: 'Lê Thị Hoa', employee_code: 'NV002', avatar_url: null, seat_id: null, table_code: null, seat_number: null },
]

// Người chưa có ghế: người chưa thuộc team nào đứng trước (không ai xếp hộ được).
const UNSEATED = [
  { registration_id: 30, user_id: 9, full_name: 'Ban Tổ Chức', employee_code: null, avatar_url: null, team_id: null, team_name: null },
  { registration_id: 8, user_id: 2, full_name: 'Lê Thị Hoa', employee_code: 'NV002', avatar_url: null, team_id: 1, team_name: 'Team Alpha' },
]

function render(label, element, seed = () => {}, entry = '/gala') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seed(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[entry]}>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

const seedView = (data) => (qc) => {
  qc.setQueryData(QUERY_KEYS.galaView, data)
  qc.setQueryData(QUERY_KEYS.galaMembers(null), MEMBERS)
  qc.setQueryData(QUERY_KEYS.galaMembers(1), MEMBERS)
  qc.setQueryData(QUERY_KEYS.galaUnseated, UNSEATED)
  qc.setQueryData(QUERY_KEYS.activeEvent, { ...EVENT, status: 'information_published' })
  qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
}

render('Gala — Trưởng nhóm đang tới lượt', <GalaPage />, seedView(view('open')))
render('Gala — CBNV, chưa tới lượt', <GalaPage />, seedView(view('open', {
  my_team: { ...view('open').my_team, is_leader: false, is_my_turn: false, status: 'waiting', draw_position: 2 },
})))
render('Gala — chưa bốc thăm, không có team', <GalaPage />, seedView(view('closed', { my_team: null })))
render('Gala — đã chốt', <GalaPage />, seedView(view('finalized')))
render('Gala — đang tải', <GalaPage />)

render('Gala BTC — chưa bốc thăm', <GalaAdminPage />, seedView(view('closed')), '/admin/gala')
render('Gala BTC — đã bốc thăm, kỳ chưa công bố', <GalaAdminPage />, (qc) => {
  seedView(view('drawing'))(qc)
  qc.setQueryData(QUERY_KEYS.activeEvent, EVENT)
}, '/admin/gala')
render('Gala BTC — đang chọn ghế', <GalaAdminPage />, seedView(view('open')), '/admin/gala')
render('Gala BTC — sơ đồ trống', <GalaAdminPage />, seedView(view('finalized', { tables: [] })), '/admin/gala')

render('Chưa có ghế — có người chưa thuộc team', <UnseatedCard view={view('finalized')} />, seedView(view('finalized')), '/admin/gala')
render('Chưa có ghế — mọi người đã có ghế', <UnseatedCard view={view('finalized')} />, (qc) => {
  seedView(view('finalized'))(qc)
  qc.setQueryData(QUERY_KEYS.galaUnseated, [])
}, '/admin/gala')
render('Chưa có ghế — sơ đồ đã kín', <UnseatedCard view={view('finalized', { tables: [] })} />, seedView(view('finalized')), '/admin/gala')
render('Chưa có ghế — đang tải', <UnseatedCard view={view('finalized')} />, () => {}, '/admin/gala')

render('Sơ đồ ghế — sân khấu bên trái', <SeatMap view={view('open', { layout: { ...view('open').layout, stage_position: 'left' } })} />)
render('BTC sửa ghế đã có team', <SeatAdminModal seatId={11} tableId={1} view={view('open')} onClose={() => {}} />, seedView(view('open')))
render('BTC sửa ghế đang bị giữ', <SeatAdminModal seatId={14} tableId={1} view={view('open')} onClose={() => {}} />, seedView(view('open')))
render('BTC ghế không tồn tại', <SeatAdminModal seatId={999} tableId={1} view={view('open')} onClose={() => {}} />)
render('Thêm bàn', <TableFormModal table={null} view={view('open')} onClose={() => {}} />)
render('Sửa bàn', <TableFormModal table={TABLES[0]} view={view('open')} onClose={() => {}} />)
render('Tạo sơ đồ', <LayoutFormModal layout={null} onClose={() => {}} />)
render('Sửa sơ đồ', <LayoutFormModal layout={view('open').layout} onClose={() => {}} />)

function check(label, ok) {
  console.log(`${label}: ${ok ? 'OK' : 'LỖI'}`)
}
const change = parseSseBlock('event: change\ndata: {"version": "ab12"}')
check('Đọc sự kiện SSE change', change.event === 'change' && change.data.version === 'ab12')
check('Bỏ qua ping và retry', parseSseBlock(': ping').event === null && parseSseBlock('retry: 3000').event === null)

// --- Mở lại chọn ghế, banner lượt, xếp ngẫu nhiên ---
import('../src/components/gala/GalaTurnBanner').then(({ default: GalaTurnBanner }) => {
  render('Banner lượt Gala (CBNV thường: không hiện)', <GalaTurnBanner />, (qc) => {
    qc.setQueryData(QUERY_KEYS.galaMyTurn, {
      configured: true, is_leader: true, selection_status: 'open', team_id: 1, team_name: 'Team Alpha',
      draw_position: 1, status: 'active', is_my_turn: true, turn_ends_at: LATER, teams_ahead: 0,
      active_team_name: 'Team Alpha', quota: 5, confirmed: 2, remaining: 3, server_time: NOW,
    })
  }, '/my-journey')
})

// F7: quota thay đổi/lượt mới không giữ lại lựa chọn cũ; khung luôn bao hết ghế.
import { availablePicks, galaFloorGeometry, galaTableRadius } from '../src/utils/gala'
import { galaDrawSchema, galaSeatAdminSchema } from '../src/utils/schemas'
import MemberSeatModal from '../src/pages/gala/MemberSeatModal'
const selecting = { scope: `1:1:${LATER}`, ids: [15, 16] }
check('Gala picks — chỉ giữ ghế còn trống', availablePicks(view('open'), selecting).length === 2)
check(
  'Gala picks — quota giảm thì cắt lựa chọn',
  availablePicks(view('open', { my_team: { ...view('open').my_team, remaining: 1 } }), selecting)
    .length === 1,
)
check(
  'Gala picks — sơ đồ mới không mang ghế cũ',
  availablePicks(view('open', { layout: { ...view('open').layout, id: 2 } }), selecting).length ===
    0,
)
check(
  'Gala picks — hết lượt hoặc mất quyền thì rỗng',
  availablePicks(view('finalized'), selecting).length === 0 &&
    availablePicks(
      view('open', { my_team: { ...view('open').my_team, is_leader: false } }),
      selecting,
    ).length === 0,
)
const largeTable = { id: 9, pos_x: 0, pos_y: 0, seat_count: 24 }
const floor = galaFloorGeometry([largeTable])
const radius = galaTableRadius(24)
check(
  'Gala floor — bàn 24 ghế sát góc không bị cắt',
  floor.positions[largeTable.id].x >= radius + 12 &&
    floor.positions[largeTable.id].y >= radius + 12 &&
    floor.height >= radius * 2 + 24,
)
const adjacentTables = [
  { id: 1, pos_x: 0, pos_y: 0, seat_count: 24 },
  { id: 2, pos_x: 1, pos_y: 0, seat_count: 10 },
  { id: 3, pos_x: 0, pos_y: 1, seat_count: 24 },
  { id: 4, pos_x: 1, pos_y: 1, seat_count: 24 },
]
const adjacentFloor = galaFloorGeometry(adjacentTables)
check('Gala floor — bàn sát nhau, số ghế khác nhau không chồng vòng ghế', adjacentTables.every((table, index) => (
  adjacentTables.slice(index + 1).every((other) => {
    const a = adjacentFloor.positions[table.id]
    const b = adjacentFloor.positions[other.id]
    const requiredDistance = galaTableRadius(table.seat_count) + galaTableRadius(other.seat_count) + 24
    return Math.abs(a.x - b.x) >= requiredDistance || Math.abs(a.y - b.y) >= requiredDistance
  })
)))
check(
  'Gala form — can thiệp bắt buộc lý do/team',
  !galaSeatAdminSchema.safeParse({
    action: 'release',
    team_id: '',
    registration_id: '',
    reason: '  ',
  }).success &&
    !galaSeatAdminSchema.safeParse({
      action: 'assign',
      team_id: '',
      registration_id: '',
      reason: 'Điều chỉnh',
    }).success,
)
check(
  'Gala form — seed đúng giới hạn backend',
  !galaDrawSchema.safeParse({ seed: '0' }).success &&
    galaDrawSchema.safeParse({ seed: '2147483647' }).success,
)
render(
  'Gala chọn người — ghế còn thuộc team',
  <MemberSeatModal view={view('open')} seatId={11} tableId={1} teamId={1} onClose={() => {}} />,
  seedView(view('open')),
)
render(
  'Gala chọn người — ghế đã bị BTC nhả',
  <MemberSeatModal view={view('open')} seatId={15} tableId={1} teamId={1} onClose={() => {}} />,
  seedView(view('open')),
)
render(
  'Gala BTC — ghế người chưa có team',
  <SeatAdminModal
    seatId={15}
    tableId={1}
    view={view('open', {
      tables: [
        {
          ...TABLES[0],
          seats: [
            seat(15, 5, 'taken', { registration_id: 30, occupant_name: 'Người chưa có team' }),
          ],
        },
      ],
    })}
    onClose={() => {}}
  />,
  seedView(view('open')),
)


// Thời gian đóng băng và màu team phải giữ nguyên khi render/tải lại.
import Countdown from '../src/components/gala/Countdown'
import GalaControlPanel from '../src/pages/admin/gala/GalaControlPanel'
import { seatVisual, galaTeamDot } from '../src/utils/gala'
const pausedView = view('open')
pausedView.draw.paused_at = NOW
render(
  'Gala tạm dừng — điều khiển BTC',
  <GalaControlPanel view={pausedView} event={EVENT} />,
  seedView(pausedView),
)
render('Gala tạm dừng — Trưởng nhóm', <GalaPage />, seedView(pausedView))
const frozenCountdown = renderToString(<Countdown endsAt={LATER} pausedAt={NOW} />)
if (!frozenCountdown.includes('04:00')) throw new Error('Đồng hồ tạm dừng không đóng băng')
console.log('Gala tạm dừng — countdown không chạy theo giờ máy: OK')
if (availablePicks(pausedView, { scope: `${pausedView.layout.id}:1:${LATER}`, ids: [15] }).length)
  throw new Error('Vẫn chọn được ghế khi tạm dừng')
console.log('Gala tạm dừng — chặn chọn ghế: OK')
const teamSeats = Array.from(
  { length: 8 },
  (_, i) => seatVisual('taken', { teamId: i + 1 }).className,
)
if (new Set(teamSeats).size !== 8) throw new Error('Màu trong bảng team bị trùng')
for (let i = 1; i <= 8; i++) {
  const visual = seatVisual('taken', { teamId: i, mine: true }).className
  if (!visual.includes(galaTeamDot(i)) || !visual.includes('ring-2 ring-primary'))
    throw new Error('Ghế của team mình đổi màu hoặc mất viền')
}
console.log('Gala màu team — đồng bộ ghế/chấm team, viền riêng team mình: OK')
