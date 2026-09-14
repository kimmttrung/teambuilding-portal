import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import ChatWidget from '../src/components/chat/ChatWidget'
import ChatPanel from '../src/components/chat/ChatPanel'
import ChatBubble from '../src/components/chat/ChatBubble'
import ChatHistory from '../src/components/chat/ChatHistory'
import ChatMascot from '../src/components/chat/ChatMascot'

const STAMP = '2026-09-14T04:00:00+00:00'
const USER = { id: 1, full_name: 'Nguyễn Văn Trung' }

function render(label, element, seed = () => {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seed(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/my-journey']}>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

render('Nút trợ lý Tibi', <ChatWidget />)
render('Linh vật — đang nghĩ', <ChatMascot mood="thinking" size={64} />)
render('Khung chat — lời chào, chế độ thử, chưa nạp tài liệu', <ChatPanel user={USER} onClose={() => {}} />, (qc) => {
  qc.setQueryData(QUERY_KEYS.chatStatus, { enabled: true, llm_configured: false, indexed_chunks: 0, model: 'gemini-2.5-flash' })
})
render('Khung chat — chưa tải trạng thái', <ChatPanel user={null} onClose={() => {}} />)
render('Tin trợ lý đang trả lời', <ChatBubble message={{ key: 'a', role: 'assistant', content: '', status: 'streaming', sources: [] }} />)
render(
  'Tin trợ lý có markdown + nguồn',
  <ChatBubble
    message={{
      key: 'b', role: 'assistant', status: 'done',
      content: '**Gala Dinner** tổ chức tại Sảnh Pearl.\n- 18:30 đón khách\n- 19:00 khai mạc',
      sources: [{ index: 1, title: 'Gala Dinner – Đêm hội Phú Quốc', source_type: 'gala' }, { index: 2, title: 'Lịch trình 16/10', source_type: 'itinerary' }],
    }}
  />,
)
render('Tin lỗi có nút thử lại', <ChatBubble message={{ key: 'c', role: 'assistant', content: '', status: 'error', error: 'Bạn hỏi nhanh quá, thử lại sau ít phút.' }} onRetry={() => {}} />)
render('Tin đã dừng', <ChatBubble message={{ key: 'd', role: 'assistant', content: 'Lịch trình ngày', status: 'stopped' }} />)
render('Tin người dùng', <ChatBubble message={{ key: 'u', role: 'user', content: 'Gala ở đâu?\nMấy giờ bắt đầu?' }} />)
render('Lịch sử trò chuyện', <ChatHistory currentId={2} onOpen={() => {}} />, (qc) => {
  qc.setQueryData(QUERY_KEYS.chatSessions, [
    { id: 2, title: 'Gala Dinner ở đâu', created_at: STAMP, updated_at: STAMP, message_count: 4 },
    { id: 1, title: null, created_at: STAMP, updated_at: null, message_count: 2 },
  ])
})
render('Lịch sử trống', <ChatHistory onOpen={() => {}} />, (qc) => qc.setQueryData(QUERY_KEYS.chatSessions, []))

import('../src/pages/admin/dashboard/AssistantCard').then(({ default: AssistantCard }) => {
  render('Thẻ trợ lý trên dashboard — đã công bố nhưng nạp cũ', <AssistantCard published />, (qc) => {
    qc.setQueryData(QUERY_KEYS.ragStatus, {
      enabled: true, llm_configured: true, model: 'gemini-2.5-flash', embedding_model: 'paraphrase-multilingual-MiniLM-L12-v2',
      indexed_chunks: 29, last_indexed_at: STAMP, last_index_published_logistics: false,
    })
  })
  render('Thẻ trợ lý — chưa nạp, chế độ thử', <AssistantCard published={false} />, (qc) => {
    qc.setQueryData(QUERY_KEYS.ragStatus, {
      enabled: true, llm_configured: false, model: 'extractive', embedding_model: 'x', indexed_chunks: 0,
      last_indexed_at: null, last_index_published_logistics: null,
    })
  })
})
