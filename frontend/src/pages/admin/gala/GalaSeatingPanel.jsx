import { useState } from 'react'
import { useGalaUnseated } from '../../../hooks/useGala'
import Card from '../../../components/common/Card'
import Select from '../../../components/common/Select'
import MemberSeatingCard from '../../gala/MemberSeatingCard'
import UnseatedCard from './UnseatedCard'

/** Một nơi xếp người: xử lý người chưa có ghế hoặc quản lý toàn bộ thành viên của team. */
export default function GalaSeatingPanel({ view }) {
  const [tab, setTab] = useState('unseated')
  const [teamId, setTeamId] = useState('')
  const { data: unseatedPeople } = useGalaUnseated()
  const teamOptions = view.draw.orders.map((order) => ({
    value: order.team_id,
    label: order.team_name,
  }))
  const tabs = [
    ['unseated', `Chưa có ghế${unseatedPeople ? ` (${unseatedPeople.length})` : ''}`],
    ['team', 'Theo team'],
  ]

  function moveTab(event) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 'unseated'
      : event.key === 'End' ? 'team'
      : tab === 'unseated' ? 'team' : 'unseated'
    setTab(next)
    event.currentTarget.querySelector(`#gala-seating-tab-${next}`)?.focus()
  }

  const teamContent = teamOptions.length === 0 ? (
    <p className="p-4 text-body-sm text-ink-muted">
      Bốc thăm thứ tự team trước khi xếp chỗ theo team. Bạn vẫn có thể xếp từng người tại tab Chưa có ghế.
    </p>
  ) : (
    <>
      <div className="p-4">
        <Select
          label="Team cần xếp chỗ"
          placeholder="Chọn team"
          value={teamId}
          onChange={(event) => setTeamId(event.target.value)}
          options={teamOptions}
        />
      </div>
      {teamId ? (
        <MemberSeatingCard key={teamId} view={view} teamId={Number(teamId)} forTeam embedded />
      ) : (
        <p className="px-4 pb-4 text-body-sm text-ink-muted">
          Chọn team để xem thành viên, xếp ngẫu nhiên hoặc đổi chỗ.
        </p>
      )}
    </>
  )

  return (
    <Card title="Xếp chỗ" bodyClassName="p-0">
      <div
        className="flex gap-1 border-b border-hairline px-4 pt-2"
        role="tablist"
        aria-label="Cách xếp chỗ"
        onKeyDown={moveTab}
      >
        {tabs.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            id={`gala-seating-tab-${value}`}
            aria-controls={`gala-seating-panel-${value}`}
            aria-selected={tab === value}
            tabIndex={tab === value ? 0 : -1}
            onClick={() => setTab(value)}
            className={`min-h-11 border-b-2 px-3 text-caption font-medium ${tab === value ? 'border-primary text-primary' : 'border-transparent text-ink-muted hover:text-ink'}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`gala-seating-panel-${tab}`}
        aria-labelledby={`gala-seating-tab-${tab}`}
      >
        {tab === 'unseated' ? <UnseatedCard view={view} embedded /> : teamContent}
      </div>
    </Card>
  )
}
