import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, History, RefreshCw, SendHorizontal, ShieldCheck, Square, SquarePen, X } from 'lucide-react'
import { fetchChatMessages, streamChat } from '../../api/chat'
import { useChatMessages, useChatStatus, useReindexRag } from '../../hooks/useChat'
import { useToast } from '../../context/ToastContext'
import { formatNumber } from '../../utils/format'
import { ADMIN_ROLES, CHAT_ASSISTANT_NAME, CHAT_MAX_LENGTH, CHAT_SUGGESTIONS, QUERY_KEYS } from '../../utils/constants'
import ChatBubble from './ChatBubble'
import ChatHistory from './ChatHistory'
import ChatMascot from './ChatMascot'

let keySeed = 0
const nextKey = () => `m${Date.now()}-${keySeed++}`

const toView = (message) => ({
  key: `db-${message.id}`,
  id: message.id,
  role: message.role,
  content: message.content,
  sources: message.sources ?? [],
  status: 'done',
})

/**
 * Khung chat: lời chào + câu hỏi gợi ý, luồng trả lời, lịch sử, dừng / thử lại.
 *
 * Cuộc trò chuyện đang mở là state của màn hình (tin đang stream chưa có trên server); lịch sử cũ
 * lấy qua TanStack Query. Nhớ phiên gần nhất trong localStorage để mở lại thấy hội thoại cũ.
 */
export default function ChatPanel({ user, onClose }) {
  const queryClient = useQueryClient()
  const storageKey = user ? `tb_chat_session_${user.id}` : null
  const [sessionId, setSessionId] = useState(() => readStored(storageKey))
  // null = chưa gõ gì trong lần mở này → hiện lịch sử của phiên đã lưu.
  const [messages, setMessages] = useState(null)
  const [view, setView] = useState('chat')
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const abortRef = useRef(null)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  const toast = useToast()
  const isAdmin = ADMIN_ROLES.includes(user?.role)
  const { mutateAsync: reindex, isPending: reindexing } = useReindexRag()
  const { data: status, error: statusError } = useChatStatus()
  const history = useChatMessages(sessionId, { enabled: messages === null })
  // Phiên đã bị xoá ở tab khác (404): coi như cuộc trò chuyện mới.
  const activeSessionId = history.isError ? null : sessionId
  const shown = messages ?? (history.data ?? []).map(toView)
  const lastContent = shown[shown.length - 1]?.content

  // Cuộn theo chữ đang stream về: chỉ đồng bộ vị trí cuộn, không fetch dữ liệu.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [shown.length, lastContent])

  useEffect(() => {
    function onKeyDown(keyEvent) {
      if (keyEvent.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    inputRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      abortRef.current?.abort()
    }
  }, [onClose])

  function rememberSession(id) {
    setSessionId(id)
    writeStored(storageKey, id)
  }

  async function send(text, base = shown) {
    const question = text.trim()
    if (!question || pending) return

    const botKey = nextKey()
    setMessages([
      ...base,
      { key: nextKey(), role: 'user', content: question },
      { key: botKey, role: 'assistant', content: '', sources: [], status: 'streaming' },
    ])
    setInput('')
    setPending(true)

    const patch = (changes) =>
      setMessages((current) =>
        (current ?? []).map((item) =>
          item.key === botKey ? { ...item, ...(typeof changes === 'function' ? changes(item) : changes) } : item,
        ),
      )

    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamChat({
        sessionId: activeSessionId,
        message: question,
        signal: controller.signal,
        onEvent: ({ event, data }) => {
          if (event === 'session') rememberSession(data.session_id)
          else if (event === 'sources') patch({ sources: data ?? [] })
          else if (event === 'delta') patch((item) => ({ content: item.content + (data?.text ?? '') }))
          else if (event === 'done') patch({ status: 'done', id: data?.message_id })
          else if (event === 'error') patch({ status: 'error', error: data?.message ?? 'Trợ lý gặp sự cố.' })
        },
      })
      patch((item) => (item.status === 'streaming' ? { status: 'done' } : {}))
    } catch (streamError) {
      if (streamError.name === 'AbortError') patch({ status: 'stopped' })
      else patch({ status: 'error', error: streamError.message })
    } finally {
      abortRef.current = null
      setPending(false)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.chatSessions })
    }
  }

  function retry(botKey) {
    const index = shown.findIndex((item) => item.key === botKey)
    const question = shown[index - 1]
    if (!question || question.role !== 'user') return
    send(question.content, shown.slice(0, index - 1))
  }

  /**
   * BTC nạp lại knowledge base NGAY TRONG tiến trình server. Chạy `scripts/rag_reindex.py` ở terminal khác
   * lúc server đang chạy làm vector store của server lệch với đĩa ("Nothing found on disk").
   */
  async function runReindex() {
    try {
      const result = await reindex()
      toast.success(
        `Tibi đã nạp ${formatNumber(result.documents)} tài liệu (${formatNumber(result.chunks)} đoạn)` +
          (result.published_logistics ? ', gồm chuyến bay, xe, khách sạn, Gala.' : '. Chưa công bố nên chưa có chuyến bay, xe, khách sạn.'),
      )
    } catch (reindexError) {
      toast.error(reindexError.message)
    }
  }

  function startNew() {
    abortRef.current?.abort()
    setMessages([])
    setSessionId(null)
    writeStored(storageKey, null)
    setView('chat')
    inputRef.current?.focus()
  }

  async function openSession(id) {
    setView('chat')
    if (id === activeSessionId && messages === null) return
    try {
      const data = await queryClient.fetchQuery({
        queryKey: QUERY_KEYS.chatMessages(id),
        queryFn: () => fetchChatMessages(id),
      })
      rememberSession(id)
      setMessages(data.map(toView))
    } catch {
      startNew()
    }
  }

  const firstName = user?.full_name?.trim().split(/\s+/).pop()
  const offline = statusError?.code === 'NO_ACTIVE_EVENT'
  // Máy chủ chưa có API chatbot (404) hoặc đang lỗi: vẫn cho gõ, lỗi cụ thể hiện dưới câu hỏi.
  const unavailable = Boolean(statusError) && !offline
  const lastIsStreaming = shown[shown.length - 1]?.status === 'streaming'

  return (
    <section
      role="dialog"
      aria-label={`Trợ lý ${CHAT_ASSISTANT_NAME}`}
      className="fixed inset-0 z-50 flex flex-col bg-white sm:inset-auto sm:right-6 sm:bottom-24 sm:h-[min(640px,calc(100dvh-8rem))] sm:w-100 sm:overflow-hidden sm:rounded-2xl sm:shadow-2xl sm:ring-1 sm:ring-slate-200"
    >
      <header className="flex items-center gap-2.5 bg-linear-to-r from-brand-600 to-brand-500 px-3 py-2.5 text-white">
        {view === 'history' ? (
          <button type="button" onClick={() => setView('chat')} className="rounded-lg p-1.5 hover:bg-white/15" aria-label="Quay lại">
            <ArrowLeft className="size-5" />
          </button>
        ) : (
          <span className="grid size-10 place-items-center rounded-full bg-white/95">
            <ChatMascot size={34} mood={lastIsStreaming ? 'thinking' : 'happy'} />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{view === 'history' ? 'Lịch sử trò chuyện' : CHAT_ASSISTANT_NAME}</p>
          {view === 'chat' && (
            <p className="truncate text-xs text-white/80">
              {reindexing
                ? 'Đang nạp kiến thức… lần đầu có thể mất khoảng 1 phút'
                : lastIsStreaming
                  ? 'Đang trả lời…'
                  : 'Trợ lý Team Building · thông tin BTC đã công bố'}
            </p>
          )}
        </div>
        {view === 'chat' && (
          <>
            {isAdmin && (
              <button
                type="button"
                onClick={runReindex}
                disabled={reindexing}
                className="rounded-lg p-2 hover:bg-white/15 disabled:opacity-70"
                aria-label="Nạp lại kiến thức cho trợ lý"
                title="Nạp lại kiến thức (sau khi sửa tài liệu, công bố, hoặc đổi database)"
              >
                <RefreshCw className={`size-4.5 ${reindexing ? 'animate-spin' : ''}`} />
              </button>
            )}
            <button type="button" onClick={() => setView('history')} className="rounded-lg p-2 hover:bg-white/15" aria-label="Lịch sử trò chuyện" title="Lịch sử">
              <History className="size-4.5" />
            </button>
            <button type="button" onClick={startNew} className="rounded-lg p-2 hover:bg-white/15" aria-label="Cuộc trò chuyện mới" title="Cuộc trò chuyện mới">
              <SquarePen className="size-4.5" />
            </button>
          </>
        )}
        <button type="button" onClick={onClose} className="rounded-lg p-2 hover:bg-white/15" aria-label="Đóng trợ lý">
          <X className="size-5" />
        </button>
      </header>

      {view === 'history' ? (
        <div className="flex-1 overflow-y-auto">
          <ChatHistory
            currentId={activeSessionId}
            onOpen={openSession}
            onDeleted={(id) => {
              if (id === activeSessionId) startNew()
            }}
          />
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto overscroll-contain px-3 py-4" aria-live="polite">
            {shown.length === 0 ? (
              <Welcome
                firstName={firstName}
                status={status}
                offline={offline}
                unavailable={unavailable}
                isAdmin={isAdmin}
                reindexing={reindexing}
                onReindex={runReindex}
                disabled={pending}
                onPick={(question) => send(question, [])}
              />
            ) : (
              <div className="flex flex-col gap-3.5">
                {shown.map((message) => (
                  <ChatBubble
                    key={message.key}
                    message={message}
                    onRetry={message.status === 'error' && !pending ? () => retry(message.key) : undefined}
                  />
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form
            className="border-t border-slate-200 bg-white p-2.5"
            onSubmit={(submitEvent) => {
              submitEvent.preventDefault()
              send(input)
            }}
          >
            <div className="flex items-end gap-2 rounded-2xl bg-slate-100 px-3 py-1.5 focus-within:ring-2 focus-within:ring-brand-400">
              <label htmlFor="chat-input" className="sr-only">
                Câu hỏi cho trợ lý
              </label>
              <textarea
                id="chat-input"
                ref={inputRef}
                rows={Math.min(4, Math.max(1, input.split('\n').length))}
                maxLength={CHAT_MAX_LENGTH}
                value={input}
                disabled={offline}
                placeholder={offline ? 'Chưa có chương trình nào đang mở' : `Hỏi ${CHAT_ASSISTANT_NAME} về lịch trình, khách sạn, Gala…`}
                onChange={(changeEvent) => setInput(changeEvent.target.value)}
                onKeyDown={(keyEvent) => {
                  if (keyEvent.key === 'Enter' && !keyEvent.shiftKey && !keyEvent.nativeEvent.isComposing) {
                    keyEvent.preventDefault()
                    send(input)
                  }
                }}
                className="max-h-28 flex-1 resize-none bg-transparent py-1.5 text-sm text-slate-900 outline-none placeholder:text-slate-400"
              />
              {pending ? (
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="mb-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-slate-700 text-white"
                  aria-label="Dừng trả lời"
                >
                  <Square className="size-3.5 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim() || offline}
                  className="mb-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-brand-600 text-white transition disabled:bg-slate-300"
                  aria-label="Gửi câu hỏi"
                >
                  <SendHorizontal className="size-4" />
                </button>
              )}
            </div>
            <p className="mt-1 px-1 text-[11px] text-slate-400">
              Enter để gửi · Shift+Enter xuống dòng{input.length > CHAT_MAX_LENGTH * 0.8 ? ` · ${input.length}/${CHAT_MAX_LENGTH}` : ''}
            </p>
          </form>
        </>
      )}
    </section>
  )
}

function Welcome({ firstName, status, offline, unavailable, isAdmin, reindexing, onReindex, disabled, onPick }) {
  return (
    <div className="flex flex-col items-center gap-3 px-2 pt-2 text-center">
      <ChatMascot size={88} className="drop-shadow-sm" />
      <div>
        <p className="font-semibold text-slate-900">
          Xin chào{firstName ? ` ${firstName}` : ''}! Mình là {CHAT_ASSISTANT_NAME} 👋
        </p>
        <p className="mt-1 text-sm text-slate-600">
          Mình trả lời về lịch trình, chuyến bay, xe, khách sạn, Gala Dinner và quy định mà Ban tổ chức đã công bố.
        </p>
      </div>

      {offline && <Notice tone="amber">Chưa có chương trình Team Building nào đang mở.</Notice>}
      {unavailable && <Notice tone="amber">Trợ lý chưa sẵn sàng trên máy chủ. Bạn thử lại sau ít phút nhé.</Notice>}
      {status && !status.llm_configured && (
        <Notice tone="amber">Trợ lý đang chạy chế độ thử: trả lời bằng trích đoạn tài liệu, chưa dùng AI.</Notice>
      )}
      {status && status.indexed_chunks === 0 && (
        <Notice tone="amber">
          Ban tổ chức chưa nạp tài liệu cho trợ lý, câu trả lời có thể còn thiếu.
          {isAdmin && (
            <button
              type="button"
              onClick={onReindex}
              disabled={reindexing}
              className="mt-1.5 flex items-center gap-1.5 font-semibold text-amber-900 underline disabled:no-underline disabled:opacity-70"
            >
              <RefreshCw className={`size-3.5 ${reindexing ? 'animate-spin' : ''}`} aria-hidden="true" />
              {reindexing ? 'Đang nạp kiến thức…' : 'Nạp kiến thức ngay'}
            </button>
          )}
        </Notice>
      )}

      {!offline && (
        <div className="flex w-full flex-col gap-1.5">
          {CHAT_SUGGESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              disabled={disabled}
              onClick={() => onPick(question)}
              className="rounded-xl border border-brand-200 bg-brand-50/60 px-3 py-2 text-left text-sm text-brand-800 transition hover:bg-brand-100"
            >
              {question}
            </button>
          ))}
        </div>
      )}

      <p className="flex items-start gap-1.5 rounded-lg bg-slate-50 px-3 py-2 text-left text-xs text-slate-500">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-600" aria-hidden="true" />
        <span>
          Mình không tra cứu thông tin cá nhân của bất kỳ ai. Chuyến bay, xe, phòng của riêng bạn xem ở{' '}
          <Link to="/my-journey" className="font-medium text-brand-700 underline">
            Hành trình
          </Link>
          .
        </span>
      </p>
    </div>
  )
}

function Notice({ tone, children }) {
  const tones = { amber: 'bg-amber-50 text-amber-800 ring-amber-200' }
  return <p className={`w-full rounded-lg px-3 py-2 text-xs ring-1 ring-inset ${tones[tone]}`}>{children}</p>
}

function readStored(key) {
  if (!key) return null
  try {
    const value = Number(localStorage.getItem(key))
    return Number.isInteger(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

function writeStored(key, value) {
  if (!key) return
  try {
    if (value) localStorage.setItem(key, String(value))
    else localStorage.removeItem(key)
  } catch {
    // Trình duyệt chặn localStorage (chế độ riêng tư): chỉ mất tính năng nhớ phiên.
  }
}
