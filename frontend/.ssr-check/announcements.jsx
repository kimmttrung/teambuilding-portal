import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import AnnouncementsPage from '../src/pages/admin/AnnouncementsPage'
import AnnouncementFormModal from '../src/pages/admin/announcements/AnnouncementFormModal'
import { EVENT, OPTIONS } from './fixtures.js'

const ITEMS = [
  {
    id: 1, event_id: 1, title: 'VN1234 đổi giờ khởi hành', content: 'Bay sớm hơn **30 phút**.',
    severity: 'urgent', target_type: 'flight', target_id: 3, target_label: 'Chuyến bay VN1234',
    published_at: '2026-09-12T06:00:00+00:00', send_email: true, recipient_count: 40,
  },
  {
    id: 2, event_id: 1, title: 'Nhắc mang CCCD', content: 'Mang theo CCCD bản gốc.',
    severity: 'warning', target_type: 'team', target_id: 1, target_label: 'Team Team Alpha',
    published_at: null, send_email: false, recipient_count: 10,
  },
]

const PREVIEW_ALL = {
  target_type: 'all', target_id: null, target_label: 'Tất cả CBNV', total: 122,
  email_enabled: false, recipients: [],
}

function render(label, element, seed) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(QUERY_KEYS.activeEvent, EVENT)
  queryClient.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
  seed(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
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

render('Thông báo BTC — có nháp và đã đăng', <AnnouncementsPage />, (qc) => {
  qc.setQueryData(QUERY_KEYS.announcements, ITEMS)
})
render('Thông báo BTC — trống', <AnnouncementsPage />, (qc) => {
  qc.setQueryData(QUERY_KEYS.announcements, [])
})
render('Hộp soạn thông báo — mới', <AnnouncementFormModal open onClose={() => {}} item={null} />, (qc) => {
  qc.setQueryData(QUERY_KEYS.flights({}), [])
  qc.setQueryData(QUERY_KEYS.buses({}), [])
  qc.setQueryData(
    QUERY_KEYS.announcementRecipients({ targetType: 'all', targetId: null }),
    PREVIEW_ALL,
  )
})
