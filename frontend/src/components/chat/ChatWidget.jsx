import { useCallback, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { CHAT_ASSISTANT_NAME } from '../../utils/constants'
import ChatMascot from './ChatMascot'
import ChatPanel from './ChatPanel'

/**
 * Nút trợ lý nổi góc phải dưới, có ở mọi trang sau khi đăng nhập (docs/06 §7).
 * Trên điện thoại đặt cao hơn thanh điều hướng dưới; khung chat mở toàn màn hình.
 */
export default function ChatWidget() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [greeted, setGreeted] = useState(() => readGreeted(user?.id))
  const close = useCallback(() => setOpen(false), [])

  function toggle() {
    setOpen((value) => !value)
    if (!greeted) {
      setGreeted(true)
      writeGreeted(user?.id)
    }
  }

  return (
    <>
      {open && <ChatPanel user={user} onClose={close} />}

      <div className={`fixed right-4 bottom-20 z-40 flex items-end gap-2 md:right-6 md:bottom-6 ${open ? 'max-sm:hidden' : ''}`}>
        {!open && !greeted && (
          <button
            type="button"
            onClick={toggle}
            className="mb-2 hidden rounded-2xl rounded-br-sm bg-white px-3 py-2 text-left text-sm text-slate-700 shadow-lg ring-1 ring-slate-200 sm:block"
          >
            Hỏi {CHAT_ASSISTANT_NAME} về lịch trình nhé!
          </button>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-label={open ? 'Đóng trợ lý' : `Mở trợ lý ${CHAT_ASSISTANT_NAME}`}
          title={`Trợ lý ${CHAT_ASSISTANT_NAME}`}
          className="group grid size-15 place-items-center rounded-full bg-white shadow-lg ring-4 ring-brand-100 transition hover:scale-105 hover:ring-brand-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
        >
          <ChatMascot size={48} className="transition group-hover:-rotate-6" />
        </button>
      </div>
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
