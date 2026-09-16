import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import ItineraryPage from '../src/pages/admin/ItineraryPage'
import { EVENT, OPTIONS } from './fixtures.js'

const ITEMS = [
  { id: 1, event_id: 1, day_date: '2026-10-15', start_time: '04:30', end_time: '05:00', title: 'Tập trung tại điểm đón', description: null, location: 'Theo xe đã phân công', audience: 'CA1', display_order: 0 },
  { id: 2, event_id: 1, day_date: '2026-10-15', start_time: '06:30', end_time: '08:40', title: 'Chuyến bay HAN – PQC', description: null, location: 'Sân bay Nội Bài', audience: 'CA1', display_order: 1 },
  { id: 3, event_id: 1, day_date: '2026-10-16', start_time: '18:30', end_time: '22:00', title: 'Gala Dinner & Vinh danh', description: 'Dress code: trắng', location: 'Sảnh Pearl', audience: 'all', display_order: 0 },
  { id: 4, event_id: 1, day_date: '2026-10-16', start_time: '09:00', end_time: null, title: 'Trò chơi theo team', description: null, location: null, audience: 'T1', display_order: 1 },
]

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

render('Lịch trình BTC — có dữ liệu', <ItineraryPage />, (qc) => {
  qc.setQueryData(QUERY_KEYS.itinerary, ITEMS)
})
render('Lịch trình BTC — trống', <ItineraryPage />, (qc) => {
  qc.setQueryData(QUERY_KEYS.itinerary, [])
})
