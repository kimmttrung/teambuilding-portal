import { initials } from '../../utils/format'

const SIZES = {
  sm: 'size-9 text-sm',
  md: 'size-12 text-base',
  lg: 'size-20 text-2xl',
}

/** Ảnh đại diện, tự rơi về chữ cái đầu của tên khi chưa có ảnh. */
export default function Avatar({ user, size = 'md', className = '' }) {
  const sizeClass = SIZES[size] ?? SIZES.md

  if (user?.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={`Ảnh đại diện của ${user.full_name}`}
        className={`${sizeClass} shrink-0 rounded-full object-cover ring-1 ring-slate-200 ${className}`}
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      className={`${sizeClass} grid shrink-0 place-items-center rounded-full bg-slate-200
        font-semibold text-slate-600 ${className}`}
    >
      {initials(user?.full_name)}
    </span>
  )
}
