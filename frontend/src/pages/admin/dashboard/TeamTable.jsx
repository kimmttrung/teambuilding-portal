import Card from '../../../components/common/Card'

/** Tỉ lệ phản hồi và tham gia theo team — cho BTC biết cần nhắc team nào. */
export default function TeamTable({ teams }) {
  return (
    <Card
      title="Đăng ký theo team"
      description="Team còn nhiều người chưa phản hồi cần được nhắc sớm"
      bodyClassName="p-0"
    >
      {teams.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">Chưa có team nào.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs tracking-wide text-slate-400 uppercase">
                <th scope="col" className="px-4 py-2 font-medium">Team</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Thành viên</th>
                <th scope="col" className="w-40 px-3 py-2 font-medium">Đã phản hồi</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Đi</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Không đi</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Huỷ</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Chưa phản hồi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {teams.map((team) => {
                const responsePercent = Math.round(team.response_rate * 100)
                return (
                  <tr key={team.team_id ?? 'none'} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2.5">
                      <span className="inline-flex min-w-0 items-center gap-2">
                        <span
                          className="size-2.5 shrink-0 rounded-full bg-slate-300"
                          style={team.color ? { backgroundColor: team.color } : undefined}
                          aria-hidden="true"
                        />
                        <span className={`truncate font-medium ${team.team_id ? 'text-slate-900' : 'text-slate-500 italic'}`}>
                          {team.name}
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right text-slate-700 tabular-nums">{team.members}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${responsePercent === 100 ? 'bg-emerald-500' : 'bg-brand-500'}`}
                            style={{ width: `${responsePercent}%` }}
                          />
                        </div>
                        <span className="w-9 text-right text-xs text-slate-600 tabular-nums">
                          {responsePercent}%
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold text-slate-900 tabular-nums">
                      {team.participating}
                    </td>
                    <td className="px-3 py-2.5 text-right text-slate-600 tabular-nums">{team.not_participating}</td>
                    <td className="px-3 py-2.5 text-right text-slate-600 tabular-nums">{team.cancelled}</td>
                    <td
                      className={`px-4 py-2.5 text-right tabular-nums ${
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
