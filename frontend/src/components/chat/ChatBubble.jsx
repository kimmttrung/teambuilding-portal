import { RotateCcw } from 'lucide-react'
import { CHAT_SOURCE_LABELS } from '../../utils/constants'
import MarkdownText from '../common/MarkdownText'
import ChatMascot from './ChatMascot'

/** Một tin nhắn. Tin của trợ lý hiện markdown (không bao giờ chèn HTML thô) + nguồn trích dẫn. */
export default function ChatBubble({ message, onRetry }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-600 px-3.5 py-2 text-sm leading-relaxed break-words whitespace-pre-wrap text-white">
          {message.content}
        </p>
      </div>
    )
  }

  const streaming = message.status === 'streaming'

  return (
    <div className="flex items-start gap-2">
      <ChatMascot size={30} mood={streaming ? 'thinking' : 'happy'} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="inline-block max-w-full rounded-2xl rounded-tl-md bg-slate-100 px-3.5 py-2.5 break-words">
          {message.content ? (
            <MarkdownText content={message.content} />
          ) : streaming ? (
            <TypingDots />
          ) : (
            <p className="text-sm text-slate-500 italic">Không có nội dung.</p>
          )}
        </div>

        {message.status === 'error' && (
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-rose-600">
            {message.error}
            {onRetry && (
              <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 font-medium underline">
                <RotateCcw className="size-3" aria-hidden="true" />
                Thử lại
              </button>
            )}
          </p>
        )}
        {message.status === 'stopped' && <p className="mt-1 text-xs text-slate-500">Đã dừng trả lời.</p>}

        {message.sources?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <span className="text-[11px] text-slate-500">Nguồn:</span>
            {message.sources.map((source) => (
              <span
                key={`${source.index}-${source.title}`}
                title={CHAT_SOURCE_LABELS[source.source_type] ?? source.source_type}
                className="max-w-full truncate rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200"
              >
                {source.title}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TypingDots() {
  return (
    <span className="flex h-5 items-center gap-1" role="status" aria-label="Đang trả lời">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="size-1.5 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  )
}
