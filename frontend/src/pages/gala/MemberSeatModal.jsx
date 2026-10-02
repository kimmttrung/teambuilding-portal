import searchIcon from '../../assets/gala/search.svg'
import { useState } from 'react'
import { useAssignGalaMember, useGalaTeamMembers } from '../../hooks/useGala'
import { useToast } from '../../context/ToastContext'
import Alert from '../../components/common/Alert'
import Avatar from '../../components/common/Avatar'
import Button from '../../components/common/Button'
import Input from '../../components/common/Input'
import Modal from '../../components/common/Modal'
import Spinner from '../../components/common/Spinner'

/** Chọn người thay cho kéo thả trên điện thoại; luôn hiển thị chỗ cũ trước khi chuyển. */
export default function MemberSeatModal({
  view,
  seatId,
  tableId,
  teamId,
  forTeam = false,
  onClose,
}) {
  const { data: members = [], isLoading, error } = useGalaTeamMembers(forTeam ? teamId : null)
  const { mutateAsync: assign, isPending } = useAssignGalaMember()
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [memberId, setMemberId] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const table = view.tables.find((t) => t.id === tableId)
  const seat = table?.seats.find((s) => s.id === seatId)
  const person = members.find((p) => p.registration_id === memberId)
  const valid = seat?.state === 'taken' && seat.team_id === teamId
  async function save(registrationId) {
    setSubmitError(null)
    try {
      await assign({ seatId, registrationId })
      toast.success(registrationId ? 'Đã xếp thành viên vào ghế.' : 'Đã bỏ xếp người khỏi ghế.')
      onClose()
    } catch (err) {
      setSubmitError(err.message)
    }
  }
  return (
    <Modal
      open
      title={`Ai ngồi ghế ${seat?.seat_number ?? '—'} · Bàn ${table?.table_code ?? '—'}?`}
      description={
        seat?.occupant_name
          ? `Hiện tại: ${seat.occupant_name}`
          : 'Chọn thành viên tham gia của team'
      }
      onClose={onClose}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          {seat?.registration_id && (
            <Button variant="secondary" disabled={!valid || isPending} onClick={() => save(null)}>
              Bỏ xếp
            </Button>
          )}
          <Button
            fullWidth
            loading={isPending}
            disabled={!valid || !person || Boolean(error)}
            onClick={() => save(memberId)}
          >
            {person ? `Xếp ${person.full_name} vào ghế ${seat.seat_number}` : 'Chọn thành viên'}
          </Button>
        </div>
      }
    >
      {!valid ? (
        <Alert tone="warning">Ghế đã thay đổi. Đóng hộp thoại và chọn lại ghế của team.</Alert>
      ) : (
        <div className="space-y-4">
          {submitError && <Alert tone="error">{submitError}</Alert>}
          <Input
            icon={SearchIcon}
            label="Tìm thành viên"
            placeholder="Tên hoặc mã nhân viên"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {isLoading ? (
            <Spinner />
          ) : error ? (
            <Alert tone="error">{error.message}</Alert>
          ) : (
            <ul className="divide-y divide-hairline">
              {members
                .filter((p) =>
                  `${p.full_name} ${p.employee_code ?? ''}`
                    .toLocaleLowerCase('vi')
                    .includes(search.toLocaleLowerCase('vi')),
                )
                .map((p) => (
                  <li key={p.registration_id}>
                    <label className="flex min-h-16 cursor-pointer items-center gap-3 py-3">
                      <Avatar user={p} size="sm" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-body-md font-semibold text-ink">
                          {p.full_name}
                        </span>
                        <span className="text-caption text-ink-muted">
                          {p.seat_id
                            ? `Đang ở ${p.table_code} · ghế ${p.seat_number}`
                            : 'Chưa có ghế'}
                        </span>
                      </span>
                      <input
                        type="radio"
                        name="gala-seat-member"
                        value={p.registration_id}
                        checked={memberId === p.registration_id}
                        onChange={() => setMemberId(p.registration_id)}
                        className="size-5 accent-primary"
                      />
                    </label>
                  </li>
                ))}
            </ul>
          )}
          {seat?.registration_id && memberId !== seat.registration_id && person && (
            <Alert tone="warning">
              Người đang ngồi ghế này sẽ trở thành chưa có ghế. Chỗ cũ của người được chọn sẽ được
              bỏ xếp.
            </Alert>
          )}
        </div>
      )}
    </Modal>
  )
}

function SearchIcon() {
  return <img src={searchIcon} alt="" />
}
