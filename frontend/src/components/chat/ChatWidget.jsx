import { useCallback, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { sideOf, useDraggablePosition } from '../../hooks/useDraggablePosition'
import { CHAT_ASSISTANT_NAME } from '../../utils/constants'
import ChatMascot from './ChatMascot'
import ChatPanel from './ChatPanel'

/**
 * Nút trợ lý nổi, có ở mọi trang sau khi đăng nhập (docs/06 §7).
 *
 * Mặc định nằm góc phải dưới (trên điện thoại đặt cao hơn thanh điều hướng dưới). Người dùng kéo nó
 * đi đâu cũng được — bằng chuột hoặc ngón tay — để nó khỏi che nội dung đang đọc; bấm thì vẫn mở
 * chat. Khung chat mở sát mép cùng bên với icon; trên điện thoại mở toàn màn hình. Khi khung đang mở
 * thì icon ẩn đi (đóng bằng nút X của khung) để không đè lên nội dung trò chuyện.
 */
export default function ChatWidget() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [greeted, setGreeted] = useState(() => readGreeted(user?.id))
  const close = useCallback(() => setOpen(false), [])
  const { position, dragging, guardClick, handlers } = useDraggablePosition(
    user?.id ? `tb_chat_pos_${user.id}` : null,
  )
  const side = sideOf(position)

  function toggle() {
    setOpen((value) => !value)
    if (!greeted) {
      setGreeted(true)
      writeGreeted(user?.id)
    }
  }

  return (
    <>
      {open && <ChatPanel user={user} side={side} onClose={close} />}

      {!open && (
        <div
          className={`fixed z-40 flex items-end gap-2 ${
            position ? '' : 'right-4 bottom-20 md:right-6 md:bottom-6'
          } ${side === 'left' ? 'flex-row-reverse' : ''}`}
          style={position ? { left: position.x, top: position.y } : undefined}
        >
          {/* Lời mời nằm ngoài luồng (absolute) để toạ độ của khung luôn là toạ độ của icon. */}
          {!greeted && !dragging && (
            <button
              type="button"
              onClick={toggle}
              className={`absolute bottom-2 block w-47.5 rounded-2xl bg-white px-3 py-2 text-left text-caption text-slate-700 shadow-lg ring-1 ring-slate-200 ${
                side === 'left' ? 'left-full ml-2 rounded-bl-sm' : 'right-full mr-2 rounded-br-sm'
              }`}
            >
              <strong className="block text-body-sm text-ink">Hỏi {CHAT_ASSISTANT_NAME} nè!</strong>
              Ca bay, giấy tờ, trang phục...
            </button>
          )}
          <button
            type="button"
            onClick={guardClick(toggle)}
            {...handlers}
            aria-expanded={open}
            aria-label={`Mở trợ lý ${CHAT_ASSISTANT_NAME}`}
            title={`Trợ lý ${CHAT_ASSISTANT_NAME} — giữ và kéo để di chuyển`}
            className={`group grid size-15 touch-none place-items-center rounded-full bg-white shadow-lg ring-4 ring-brand-100 select-none hover:ring-brand-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
              dragging ? 'scale-105 cursor-grabbing' : 'cursor-grab transition hover:scale-105'
            }`}
          >
            <ChatMascot size={48} className="pointer-events-none transition group-hover:-rotate-6" />
          </button>
        </div>
      )}
    </>
  )
}

function readGreeted(userId) {
  try {
    return localStorage.getItem(`tb_chat_greeted_${userId}`) === '1'
  } catch {
    return true
  }
}

function writeGreeted(userId) {
  try {
    localStorage.setItem(`tb_chat_greeted_${userId}`, '1')
  } catch {
    // Không lưu được thì lần sau vẫn hiện lời mời — không sao.
  }
}
