import { Link } from 'react-router-dom'

/**
 * "Theo team" (Figma v2 · B1): mỗi team một thanh "đã phản hồi / thành viên" — cho BTC biết nhắc team nào.
 * Team còn người chưa phản hồi xếp lên đầu; bấm tên team mở danh sách CBNV của team đó.
 * Dòng phụ là Trưởng nhóm: người chọn ghế Gala cho team, nên thiếu là phải thấy ngay ở đây.
 */
export default function TeamTable({ teams, onAssignLeader }) {
  // sort ổn định: cùng số chưa phản hồi thì giữ thứ tự tên từ backend.
  const rows = [...teams].sort((a, b) => b.not_submitted - a.not_submitted)

  return (
    <section aria-labelledby="dashboard-teams">
      <h2 id="dashboard-teams" className="text-heading-3 text-ink">
        Theo team
      </h2>

      {rows.length === 0 ? (
        <p className="mt-3.5 text-caption text-ink-muted">Chưa có team nào.</p>
      ) : (
        <ul className="mt-3.5 divide-y divide-hairline">
          {rows.map((team) => {
            const responded = team.members - team.not_submitted
            const percent = team.members ? Math.round((responded / team.members) * 100) : 0
            return (
              <li key={team.team_id ?? 'none'} className="py-2.5">
                <div className="flex items-center gap-2.5">
                  <span
                    className="size-2 shrink-0 rounded-full bg-ink-faint"
                    style={team.color ? { backgroundColor: team.color } : undefined}
                    aria-hidden="true"
                  />
                  {team.team_id ? (
                    <Link
                      to={`/admin/users?team_id=${team.team_id}`}
                      className="w-32 shrink-0 truncate text-caption text-ink hover:text-primary hover:underline sm:w-36"
                    >
                      {team.name}
                    </Link>
                  ) : (
                    <span className="w-32 shrink-0 truncate text-caption text-ink-muted sm:w-36">{team.name}</span>
                  )}
                  <span
                    className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-hairline"
                    role="meter"
                    aria-valuenow={responded}
                    aria-valuemin={0}
                    aria-valuemax={team.members}
                    aria-label={`${team.name}: ${responded} trên ${team.members} người đã phản hồi`}
                  >
                    <span
                      className={`block h-full rounded-full ${percent < 75 ? 'bg-accent-orange' : 'bg-accent-green'}`}
                      style={{ width: `${percent}%` }}
                    />
                  </span>
                  <span className="w-12 shrink-0 text-right text-caption tabular-nums">
                    <b className="font-semibold text-ink">{responded}</b>
                    <span className="text-ink-faint">/{team.members}</span>
                  </span>
                </div>

                {team.team_id && (
                  <p className="mt-1 flex flex-wrap items-center gap-x-2 pl-4.5 text-eyebrow font-normal text-ink-faint">
                    <span>
                      Tham gia {team.participating} · không đi {team.not_participating + team.cancelled}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span className={team.needs_leader ? 'font-semibold text-amber-800' : undefined}>
                      {team.leader_name
                        ? `Trưởng nhóm: ${team.leader_name}${team.needs_leader ? ' (không tham gia)' : ''}`
                        : team.needs_leader
                          ? 'Chưa có Trưởng nhóm'
                          : 'Chưa chọn Trưởng nhóm'}
                    </span>
                    {onAssignLeader && (team.needs_leader || team.leader_name) && (
                      <button
                        type="button"
                        onClick={() => onAssignLeader(team)}
                        className="font-semibold text-primary hover:underline"
                      >
                        {team.needs_leader ? 'Chỉ định' : 'Đổi'}
                      </button>
                    )}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
