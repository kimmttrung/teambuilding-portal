import { Link } from 'react-router-dom'
import Card from '../../../components/common/Card'

/**
 * Tỉ lệ phản hồi theo team — cho BTC biết nhắc team nào. Team còn người chưa phản hồi xếp lên đầu;
 * bấm tên team mở danh sách CBNV của team đó.
 */
export default function TeamTable({ teams, onAssignLeader }) {
  // sort ổn định: cùng số chưa phản hồi thì giữ thứ tự tên từ backend.
  const rows = [...teams].sort((a, b) => b.not_submitted - a.not_submitted)

  return (
    <Card
      title="Đăng ký theo team"
      description="Team còn người chưa phản hồi đứng đầu · bấm tên team để xem CBNV"
      bodyClassName="p-0"
    >
      {rows.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">Chưa có team nào.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-180 text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs whitespace-nowrap text-slate-500">
                <th scope="col" className="px-4 py-2 font-medium">Team</th>
                <th scope="col" className="px-3 py-2 font-medium">Trưởng nhóm</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Thành viên</th>
                <th scope="col" className="w-44 px-3 py-2 font-medium">Đã phản hồi</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Tham gia</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Không đi / huỷ</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Chưa phản hồi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((team) => {
                const responsePercent = Math.round(team.response_rate * 100)
                return (
                  <tr key={team.team_id ?? 'none'} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2">
                      <span className="inline-flex min-w-0 items-center gap-2">
                        <span
                          className="size-2.5 shrink-0 rounded-full bg-slate-300"
                          style={team.color ? { backgroundColor: team.color } : undefined}
                          aria-hidden="true"
                        />
                        {team.team_id ? (
                          <Link
                            to={`/admin/users?team_id=${team.team_id}`}
                            className="truncate font-medium text-slate-900 hover:text-brand-700 hover:underline"
                          >
                            {team.name}
                          </Link>
                        ) : (
                          <span className="truncate text-slate-500 italic">{team.name}</span>
                        )}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {team.team_id ? (
                        <div className="flex items-center gap-2">
                          <span
                            className={`min-w-0 truncate ${team.needs_leader ? 'font-medium text-amber-700' : 'text-slate-700'}`}
                          >
                            {team.leader_name
                              ? `${team.leader_name}${team.needs_leader ? ' (không tham gia)' : ''}`
                              : team.needs_leader
                                ? 'Chưa có'
                                : '—'}
                          </span>
                          {onAssignLeader && (team.needs_leader || team.leader_name) && (
                            <button
                              type="button"
                              onClick={() => onAssignLeader(team)}
                              className="shrink-0 text-xs font-semibold text-brand-700 hover:underline"
                            >
                              {team.needs_leader ? 'Chỉ định' : 'Đổi'}
                            </button>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-700 tabular-nums">{team.members}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${responsePercent === 100 ? 'bg-emerald-500' : 'bg-brand-500'}`}
                            style={{ width: `${responsePercent}%` }}
                          />
                        </div>
                        <span className="w-9 text-right text-xs text-slate-600 tabular-nums">{responsePercent}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right font-semibold text-slate-900 tabular-nums">
                      {team.participating}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-500 tabular-nums">
                      {team.not_participating} / {team.cancelled}
                    </td>
                    <td
                      className={`px-4 py-2 text-right tabular-nums ${
                        team.not_submitted ? 'font-semibold text-amber-700' : 'text-slate-400'
                      }`}
                    >
                      {team.not_submitted}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
