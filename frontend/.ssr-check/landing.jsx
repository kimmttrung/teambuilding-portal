import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import LandingPage from '../src/pages/public/LandingPage'

function render(label, element) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/']}>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const hasVideo = html.includes('/video_intro.mp4')
    const hasLogin =
      html.includes('/login') ||
      html.includes('/home') ||
      html.includes('/my-journey') ||
      html.includes('/admin')
    console.log(
      `${label}: OK (${html.length} ký tự, video=${hasVideo ? 'có' : 'THIẾU'}, login=${hasLogin ? 'có' : 'THIẾU'})`,
    )
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

// Stub AuthContext mặc định trả phiên đã đăng nhập (xem stub-auth.js).
render('Landing giới thiệu — đã đăng nhập', <LandingPage />)
