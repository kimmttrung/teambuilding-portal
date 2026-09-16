import { useState } from 'react'
import { UserCheck } from 'lucide-react'
import { useParticipants } from '../../../hooks/useRegistration'
import { useAssignTeamLeader } from '../../../hooks/useTeams'
import { useToast } from '../../../context/ToastContext'
import { teamLeaderOptions } from '../../../utils/teams'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'

/**
 * Chỉ định Trưởng nhóm cho một team (dòng của bảng "Đăng ký theo team" hoặc "Việc cần làm").
 * Chỉ liệt kê thành viên team đang xác nhận tham gia — Trưởng nhóm là người chọn ghế Gala cho cả team.
 */
export default function TeamLeaderDialog({ team, onClose }) {
  const toast = useToast()
  const { data, isLoading } = useParticipants()
  const { mutateAsync, isPending } = useAssignTeamLeader()
  const [userId, setUserId] = useState('')
  const options = teamLeaderOptions(data?.items, team.team_id, team.needs_leader ? null : team.leader_user_id)

  async function submit() {
    try {
      const result = await mutateAsync({ teamId: team.team_id, userId: Number(userId) })
      toast.success(`Đã chỉ định ${result.leader_name} làm Trưởng nhóm ${result.team_name}.`)
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  const current = team.leader_name
    ? `Hiện tại: ${team.leader_name}${team.needs_leader ? ' (không còn tham gia)' : ''}`
    : 'Team chưa có Trưởng nhóm'

  return (
    <Modal
      open
      onClose={onClose}
      title={`Chỉ định Trưởng nhóm — ${team.name}`}
      description={current}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Để sau
          </Button>
          <Button size="sm" icon={UserCheck} loading={isPending} disabled={!userId} onClick={submit}>
            Chỉ định
          </Button>
        </div>
      }
    >
      {isLoading ? (
        <Spinner label="Đang tải thành viên…" />
      ) : (
        <div className="flex flex-col gap-3.5">
          <Alert tone="info" title="Trưởng nhóm làm gì">
            Giữ và xác nhận ghế Gala cho cả team khi tới lượt, rồi xếp từng thành viên vào ghế. Người được
            chọn nhận vai trò "Trưởng nhóm"; người giữ chức trước (nếu có) trở về CBNV.
          </Alert>
          {options.length === 0 ? (
            <Alert tone="warning">Team chưa có thành viên nào khác đang xác nhận tham gia.</Alert>
          ) : (
            <Select
              label="Thành viên đang tham gia"
              required
              placeholder="Chọn người"
              value={userId}
              onChange={(changeEvent) => setUserId(changeEvent.target.value)}
              options={options}
            />
          )}
        </div>
      )}
    </Modal>
  )
}
