import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { allocateFlights } from '../../../api/flights'
import { ArrowLeft, ArrowRight, Check, Lock, Play, Plus } from 'lucide-react'
import { useAllocateFlights, useFlightBoard } from '../../../hooks/useFlights'
import { useActiveEvent } from '../../../hooks/useEvent'
import { useToast } from '../../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS } from '../../../utils/constants'
import { formatPercent } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import FlagList from '../../../components/admin/FlagList'
import Spinner from '../../../components/common/Spinner'
import { allocationDiff, boardPeople, boardStats, groupDiff, teamColor } from './boardData'

const CHANGE_META = {
  add: { label: 'Thêm', symbol: '+', className: 'text-accent-green bg-accent-green/10' },
  move: { label: 'Chuyển', symbol: '↔', className: 'text-primary bg-primary/10' },
  remove: { label: 'Bỏ', symbol: '−', className: 'text-accent-orange bg-accent-orange/10' },
  keep: { label: 'Giữ nguyên', symbol: '—', className: 'text-ink-muted bg-black/5' },
}

/** Màn xem trước riêng: không ghi cho đến khi BTC bấm Áp dụng. */
export default function AllocationPreviewModal({ open, onClose, direction = 'outbound' }) {
  const { data: event } = useActiveEvent()
  const board = useFlightBoard(direction, { enabled: open })
  const { mutateAsync: allocate, isPending } = useAllocateFlights()
  const toast = useToast()
  const [priority, setPriority] = useState(null)
  const [error, setError] = useState(null)
  const [retry, setRetry] = useState(0)
  const [expandedGroups, setExpandedGroups] = useState({})
  const [appliedData, setAppliedData] = useState(null)
  const seed = useRef(undefined)
  const currentSignature = board.data ? JSON.stringify(board.data) : null

  const previewQuery = useQuery({
    queryKey: ['flights', 'preview', direction, priority, retry, currentSignature],
    enabled: open && Boolean(currentSignature) && !appliedData,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    queryFn: async () => {
      const result = await allocateFlights({
        direction,
        dryRun: true,
        forceReallocate: false,
        priority,
        seed: seed.current,
      })
      seed.current = result.seed
      return { result, baseline: currentSignature }
    },
  })
  const applied = Boolean(appliedData)
  const preview = appliedData?.result ?? previewQuery.data?.result
  const baseline = appliedData?.baseline ?? previewQuery.data?.baseline
  const running = isPending || previewQuery.isFetching

  if (!open) return null
  const comparison = baseline ? JSON.parse(baseline) : board.data
  const people = boardPeople(comparison)
  const flights = comparison?.flights ?? []
  const current = boardStats(people, flights)
  const diff = preview ? allocationDiff(people, preview, flights) : []
  const displayRows = groupDiff(diff).flatMap((group) => [
    { ...group, grouped: group.rows.length > 1 },
    ...(expandedGroups[group.key] && group.rows.length > 1
      ? group.rows.map((row) => ({
          ...row,
          key: `${group.key}-${row.person.registration_id}`,
          child: true,
        }))
      : []),
  ])
  const counts = Object.fromEntries(
    Object.keys(CHANGE_META).map((key) => [key, diff.filter((r) => r.kind === key).length]),
  )
  const canCommit =
    preview &&
    !running &&
    baseline === currentSignature &&
    !applied &&
    [
      'registration_closed',
      'allocation_processing',
      'information_published',
      'event_started',
      'completed',
    ].includes(event?.status)

  async function apply() {
    if (!canCommit) return
    setError(null)
    try {
      const result = await allocate({
        direction,
        dryRun: false,
        forceReallocate: false,
        priority,
        seed: preview.seed,
        expectedAssignments: preview.assignments,
      })
      setAppliedData({ result, baseline })
      toast.success(
        `Đã ghi phân bổ: ${result.summary.assigned} người có chuyến. Giữ nguyên bản ghi chỉnh tay.`,
      )
    } catch (requestError) {
      setError(requestError)
    }
  }

  return (
    <div className="space-y-6 text-ink">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-hairline pb-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-title">
            {applied ? 'Đã áp dụng phân bổ' : 'Chạy phân bổ thử'} ·{' '}
            {FLIGHT_DIRECTION_LABELS[direction]?.toLowerCase()}
          </h1>
          <span
            className={`rounded-xs px-2 py-1 text-eyebrow ${applied ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-purple/20 text-accent-purple-deep'}`}
          >
            {applied ? 'Đã ghi' : 'Xem trước · chưa ghi'}
          </span>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={running}
            icon={applied ? ArrowLeft : undefined}
            onClick={onClose}
          >
            {applied ? 'Về bảng chuyến bay' : 'Huỷ bản thử'}
          </Button>
          {!applied && (
            <Button
              shape="pill"
              icon={Check}
              loading={isPending}
              disabled={!canCommit}
              onClick={apply}
            >
              Áp dụng thay đổi
            </Button>
          )}
        </div>
      </header>
      {(board.isLoading || (previewQuery.isFetching && !preview)) && (
        <Spinner label="Đang tính phân bổ thử…" />
      )}
      {(error || board.error || previewQuery.error) && (
        <Alert tone="error" title="Chưa áp dụng thay đổi">
          {(error || board.error || previewQuery.error).message}
          <div className="mt-3">
            <Button
              variant="secondary"
              icon={Play}
              disabled={running}
              onClick={() => {
                board.refetch()
                setRetry((n) => n + 1)
              }}
            >
              Chạy xem trước lại
            </Button>
          </div>
        </Alert>
      )}
      {preview &&
        !applied &&
        !canCommit &&
        !running &&
        event &&
        ![
          'registration_closed',
          'allocation_processing',
          'information_published',
          'event_started',
          'completed',
        ].includes(event.status) && (
          <Alert tone="info">
            Có thể xem trước lúc này. Đóng đăng ký trước khi áp dụng phân bổ.
          </Alert>
        )}
      {preview && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Đã xếp"
              value={
                <>
                  {preview.summary.assigned}
                  <span className="text-ink-faint">/{preview.summary.total_participants}</span>
                </>
              }
              detail={`${preview.summary.assigned - current.assigned >= 0 ? '+' : ''}${preview.summary.assigned - current.assigned} so với hiện tại`}
            />
            <Metric
              label="Team bị tách"
              value={preview.summary.teams_split}
              detail={`${preview.summary.teams_split - current.split} so với hiện tại`}
            />
            <Metric
              label="Đúng ca đăng ký"
              value={formatPercent(preview.summary.shift_satisfaction_rate)}
              detail={`${preview.flags.filter((f) => f.type === 'SHIFT_NOT_SATISFIED').length} người lệch ca`}
            />
            <Metric
              label="Giữ nguyên chỉnh tay"
              value={preview.assignments.filter((a) => a.pinned).length}
              detail="Bản ghi BTC chỉnh tay không bị đổi"
            />
          </div>
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="mr-2 text-title">
                  {applied ? 'Kết quả đã ghi' : 'Thay đổi so với hiện tại'}
                </h2>
                {['add', 'move', 'remove'].map((kind) => (
                  <span
                    key={kind}
                    className={`rounded-xs px-2 py-1 text-eyebrow ${CHANGE_META[kind].className}`}
                  >
                    {CHANGE_META[kind].symbol} {CHANGE_META[kind].label} {counts[kind]}
                  </span>
                ))}
              </div>
              {!applied && (
                <div className="flex items-center gap-2 text-caption text-ink-muted">
                  Ưu tiên:
                  <div className="flex rounded-full bg-black/5 p-1">
                    {[
                      ['team', 'Giữ team'],
                      ['shift', 'Đúng ca'],
                    ].map(([value, label]) => (
                      <button
                        type="button"
                        key={value}
                        disabled={running}
                        aria-pressed={
                          (priority ??
                            (preview.params.team_weight >= preview.params.shift_weight
                              ? 'team'
                              : 'shift')) === value
                        }
                        onClick={() => {
                          setError(null)
                          setPriority(value)
                        }}
                        className={`min-h-11 rounded-full px-5 text-caption font-semibold disabled:opacity-50 sm:min-h-8 ${(priority ?? (preview.params.team_weight >= preview.params.shift_weight ? 'team' : 'shift')) === value ? 'bg-surface text-ink shadow-soft' : ''}`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <Card bodyClassName="p-0">
              {!diff.length ? (
                <EmptyState
                  icon={Plus}
                  title="Chưa có người tham gia"
                  description="Phân bổ sẽ có dữ liệu sau khi người tham gia gửi đăng ký."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[700px] text-left text-body-sm">
                    <thead className="bg-canvas-soft text-eyebrow text-ink-muted">
                      <tr>
                        {['', 'Người / nhóm', 'Team', 'Hiện tại', 'Đề xuất', 'Lý do'].map(
                          (heading, i) => (
                            <th key={i} className="px-4 py-3 font-medium">
                              {heading}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      {displayRows.map((row) => (
                        <tr key={row.key} className={row.child ? 'bg-canvas-soft' : undefined}>
                          <td className="px-4 py-3">
                            <span
                              aria-label={
                                row.pinned ? 'Chỉnh tay, giữ nguyên' : CHANGE_META[row.kind].label
                              }
                              className={`inline-flex size-6 items-center justify-center rounded-xs ${CHANGE_META[row.kind].className}`}
                            >
                              {row.pinned ? (
                                <Lock className="size-3" />
                              ) : (
                                CHANGE_META[row.kind].symbol
                              )}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold">
                            {row.grouped ? (
                              <button
                                type="button"
                                className="min-h-11 text-left"
                                aria-expanded={Boolean(expandedGroups[row.key])}
                                onClick={() =>
                                  setExpandedGroups({
                                    ...expandedGroups,
                                    [row.key]: !expandedGroups[row.key],
                                  })
                                }
                              >
                                {row.person.team_name} ({row.rows.length}){' '}
                                <span className="ml-1 text-caption text-ink-faint">
                                  {expandedGroups[row.key] ? '−' : '+'}
                                </span>
                              </button>
                            ) : (
                              row.person.full_name
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="mr-2 inline-block size-2 rounded-full"
                              style={{ backgroundColor: teamColor(row.person.team_color) }}
                            />
                            {row.person.team_name ?? 'Chưa có team'}
                          </td>
                          <td className="px-4 py-3 text-ink-muted">
                            {row.before?.flight_code ?? '—'}
                          </td>
                          <td className="px-4 py-3 font-semibold">
                            {row.after?.flight_code ?? '—'}
                            {row.kind === 'move' && (
                              <ArrowRight className="ml-2 inline size-3 text-primary" />
                            )}
                          </td>
                          <td className="max-w-80 px-4 py-3 text-caption text-ink-muted">
                            {row.reason}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </section>
          {preview.flags.length > 0 && (
            <Card title={`Cảnh báo cần kiểm tra (${preview.flags.length})`}>
              <FlagList flags={preview.flags} />
            </Card>
          )}
          <p className="text-caption text-ink-muted">
            Giữ nguyên các bản ghi chỉnh tay. Những người chưa được xếp hoặc lệch ca có thể điều
            chỉnh trên board sau khi áp dụng.
          </p>
        </>
      )}
    </div>
  )
}

function Metric({ label, value, detail }) {
  return (
    <Card>
      <p className="text-caption text-ink-muted">{label}</p>
      <p className="mt-2 text-heading-1 tabular-nums">{value}</p>
      <p className="mt-2 text-caption text-ink-muted">{detail}</p>
    </Card>
  )
}
