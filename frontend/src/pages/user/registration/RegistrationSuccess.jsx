import { Link } from 'react-router-dom'
import { CheckCircle2, Map as MapIcon, Pencil, UserRound } from 'lucide-react'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import RegistrationSummary from './RegistrationSummary'
import ChatMascot from '../../../components/chat/ChatMascot'

/** Trang sau khi gửi đăng ký thành công. */
export default function RegistrationSuccess({ registration, event, email, onEdit }) {
  const participating = registration.is_participating

  return (
    <div className="flex min-h-0 flex-col gap-4 max-md:min-h-[calc(100dvh-32px)]">
      <section className="hidden min-h-[calc(100dvh-48px)] flex-col items-center px-0 pb-2 pt-[50px] text-center max-md:flex">
        <ChatMascot size={132} />
        <h1 className="mt-5 text-page-title text-ink">Đăng ký xong rồi!</h1>
        <p className="mt-2 max-w-xs text-center text-body-sm leading-relaxed text-ink-muted">
          Email xác nhận đã gửi tới {email}. BTC sẽ công bố vé, xe, phòng dự kiến 05/10.
        </p>
        <div className="mt-7 w-full overflow-hidden rounded-xl border border-hairline bg-surface text-left">
          <div className="flex justify-between border-b border-hairline px-4 py-4 text-body-sm"><span className="text-ink-muted">Ca đi</span><strong>{registration.shift?.name || '—'}</strong></div>
          <div className="flex justify-between border-b border-hairline px-4 py-4 text-body-sm"><span className="text-ink-muted">Xe BTC</span><strong>{registration.bus_needs?.filter((item) => item.needs_bus).length ?? 0}/{registration.bus_needs?.length ?? 0} chặng</strong></div>
          <div className="flex justify-between px-4 py-4 text-body-sm"><span className="text-ink-muted">Sửa được tới</span><strong>{event.registration_closes_at ? '23:59 · 01/10' : 'Theo hạn BTC'}</strong></div>
        </div>
        <Link to="/my-journey" className="mt-auto flex min-h-12 w-full items-center justify-center rounded-full bg-primary text-button font-semibold text-white">Về trang chủ</Link>
        <Link to="/schedule" className="text-body-sm font-semibold text-primary">Thêm hạn công bố vào lịch</Link>
      </section>
      <section className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-5 max-md:hidden">
        <div className="flex flex-col items-center gap-3 text-center sm:flex-row sm:items-start sm:text-left">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-emerald-500 text-white">
            <CheckCircle2 className="size-6" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 className="text-body-md font-bold text-emerald-900">
              {participating ? 'Đã ghi nhận đăng ký của bạn' : 'Đã ghi nhận: bạn không tham gia'}
            </h2>
            <p className="mt-1 max-w-prose text-sm leading-relaxed text-emerald-800">
              {participating
                ? `BTC sẽ phân bổ chuyến bay, xe đưa đón và phòng khách sạn, rồi công bố trên màn
                   hình Hành trình của bạn. Email xác nhận sẽ được gửi tới ${email}.`
                : 'BTC đã biết bạn không tham gia kỳ này. Bạn vẫn đổi ý được trong thời gian mở đăng ký.'}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 max-md:hidden xl:grid-cols-12">
        <div className="xl:col-span-8">
          <RegistrationSummary registration={registration} title="Nội dung bạn đã gửi" />
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <Card title="Việc tiếp theo">
            {participating ? (
              <ul className="flex flex-col gap-2.5 text-sm text-slate-600">
                <li>
                  Kiểm tra lại số CCCD và ngày sinh trong hồ sơ — BTC dùng đúng thông tin đó để
                  xuất vé máy bay.
                </li>
                <li>
                  Chuyến bay, xe và phòng sẽ hiện ở trang Hành trình ngay khi BTC công bố kết quả
                  phân bổ.
                </li>
                <li>
                  Cần đổi ca hay nhu cầu xe thì sửa lại trước khi BTC đóng đăng ký
                  ({event.status_label || event.status}).
                </li>
              </ul>
            ) : (
              <p className="text-sm text-slate-600">
                Bạn không cần làm gì thêm. Nếu đổi ý, vào lại trang đăng ký và chọn "Có, tôi tham
                gia" trong thời gian còn mở đăng ký.
              </p>
            )}

            <div className="mt-4 flex flex-col gap-2">
              <Link to="/my-journey">
                <Button icon={MapIcon} fullWidth>
                  Về trang Hành trình
                </Button>
              </Link>

              {registration.can_edit ? (
                <Button variant="secondary" icon={Pencil} fullWidth onClick={onEdit}>
                  Sửa lại đăng ký
                </Button>
              ) : (
                <Alert tone="info">
                  Đăng ký đã chốt ({event.status_label || event.status}), không sửa được nữa.
                </Alert>
              )}

              <Link to="/profile">
                <Button variant="ghost" icon={UserRound} fullWidth>
                  Xem hồ sơ cá nhân
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
