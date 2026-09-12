import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import AppRoutes from './routes/AppRoutes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Mạng 4G ở sân bay hay chập chờn: thử lại 1 lần, nhưng đừng thử lại lỗi
      // phân quyền hay dữ liệu không tồn tại vì có thử lại cũng thế.
      retry: (failureCount, error) => {
        if ([401, 403, 404, 409, 422].includes(error?.status)) return false
        return failureCount < 1
      },
      staleTime: 30 * 1000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <AppRoutes />
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
