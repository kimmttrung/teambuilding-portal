import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { FormProvider, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ToastProvider } from '../src/context/ToastContext'
import { registrationFormSchema } from '../src/utils/schemas'
import ProfileStep from '../src/pages/user/registration/ProfileStep'
import ParticipationStep from '../src/pages/user/registration/ParticipationStep'
import ShiftStep from '../src/pages/user/registration/ShiftStep'
import BusStep from '../src/pages/user/registration/BusStep'
import ConsentStep from '../src/pages/user/registration/ConsentStep'
import RegistrationSuccess from '../src/pages/user/registration/RegistrationSuccess'
import { EVENT, OPTIONS, REGISTRATION, DEFAULT_VALUES } from './fixtures.js'

function Harness({ children, values }) {
  const form = useForm({ resolver: zodResolver(registrationFormSchema), defaultValues: values })
  return <FormProvider {...form}>{children}</FormProvider>
}

function render(label, node) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ToastProvider>{node}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 5).join('\n'))
  }
}

const yes = { ...DEFAULT_VALUES, is_participating: 'yes' }
const no = { ...DEFAULT_VALUES, is_participating: 'no' }

render('Bước 1 hồ sơ', <Harness values={DEFAULT_VALUES}><ProfileStep /></Harness>)
render('Bước 2 tham gia (chưa chọn)', <Harness values={DEFAULT_VALUES}><ParticipationStep event={EVENT} onGoToProfile={() => {}} /></Harness>)
render('Bước 2 tham gia (chọn Không)', <Harness values={no}><ParticipationStep event={EVENT} onGoToProfile={() => {}} /></Harness>)
render('Bước 3 chọn ca', <Harness values={yes}><ShiftStep options={OPTIONS} /></Harness>)
render('Bước 3 khi chưa có ca nào', <Harness values={yes}><ShiftStep options={{ ...OPTIONS, shifts: [] }} /></Harness>)
render('Bước 4 nhu cầu xe', <Harness values={yes}><BusStep options={OPTIONS} /></Harness>)
render('Bước 4 khi chưa có chặng nào', <Harness values={{ ...yes, bus_needs: [] }}><BusStep options={{ ...OPTIONS, trip_legs: [] }} /></Harness>)
render('Bước 5 quy định (tham gia)', <Harness values={yes}><ConsentStep event={EVENT} /></Harness>)
render('Bước 5 quy định (không tham gia)', <Harness values={no}><ConsentStep event={EVENT} /></Harness>)
render('Trang gửi thành công', <RegistrationSuccess registration={REGISTRATION} event={EVENT} email="a@b.vn" onEdit={() => {}} />)
render('Gửi thành công (không tham gia)', <RegistrationSuccess registration={{ ...REGISTRATION, is_participating: false, not_participating_reason: 'Trùng lịch công tác' }} event={EVENT} email="a@b.vn" onEdit={() => {}} />)
