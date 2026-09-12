import { Hammer } from 'lucide-react'
import EmptyState from './EmptyState'

/** Màn hình chưa làm xong. Nói rõ đang ở bước nào để không ai tưởng là lỗi. */
export default function ComingSoon({ title, step, description }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white">
      <EmptyState
        icon={Hammer}
        title={title}
        description={
          description ?? `Màn hình này nằm ở bước ${step} của kế hoạch phát triển.`
        }
      />
    </div>
  )
}
