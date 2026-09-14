import { MessageSquare, Trash2 } from 'lucide-react'
import { useChatSessions, useDeleteChatSession } from '../../hooks/useChat'
import { useToast } from '../../context/ToastContext'
import { formatRelative } from '../../utils/format'
import Spinner from '../common/Spinner'

/** Các cuộc trò chuyện cũ của chính người dùng: mở lại hoặc xoá. */
export default function ChatHistory({ currentId, onOpen, onDeleted }) {
  const toast = useToast()
  const { data: sessions, isLoading, error } = useChatSessions()
  const { mutateAsync: remove, isPending } = useDeleteChatSession()

  async function handleDelete(session) {
    if (!window.confirm(`Xoá cuộc trò chuyện "${session.title || 'Không tên'}"?`)) return
    try {
      await remove(session.id)
      onDeleted?.(session.id)
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  if (isLoading) return <Spinner label="Đang tải lịch sử…" />
  if (error) return <p className="p-4 text-sm text-rose-600">{error.message}</p>
  if (!sessions?.length) {
    return <p className="p-6 text-center text-sm text-slate-500">Chưa có cuộc trò chuyện nào.</p>
  }

  return (
    <ul className="divide-y divide-slate-100">
      {sessions.map((session) => (
        <li key={session.id} className={`flex items-center gap-2 px-3 py-2 ${session.id === currentId ? 'bg-brand-50' : ''}`}>
          <button
            type="button"
            onClick={() => onOpen(session.id)}
            className="flex min-w-0 flex-1 items-start gap-2.5 rounded-lg px-1 py-1 text-left hover:bg-slate-50"
          >
            <MessageSquare className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-slate-900">{session.title || 'Không tên'}</span>
              <span className="block text-xs text-slate-500">
                {session.message_count} tin · {formatRelative(session.updated_at ?? session.created_at)}
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={() => handleDelete(session)}
            disabled={isPending}
            className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
            aria-label={`Xoá cuộc trò chuyện ${session.title || ''}`}
          >
            <Trash2 className="size-4" aria-hidden="true" />
          </button>
        </li>
      ))}
    </ul>
  )
}
