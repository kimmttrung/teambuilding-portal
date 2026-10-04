import { initials } from '../../utils/format'

const SIZES = {
  sm: 'size-9 text-caption',
  md: 'size-12 text-body-md',
  lg: 'size-20 text-heading-3',
}

/** Ảnh đại diện (rounded-full, viền hairline), tự rơi về chữ cái đầu của tên khi chưa có ảnh. */
export default function Avatar({ user, size = 'md', className = '' }) {
  const sizeClass = SIZES[size] ?? SIZES.md

  if (user?.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={`Ảnh đại diện của ${user.full_name}`}
        className={`${sizeClass} shrink-0 rounded-full object-cover ring-1 ring-hairline ${className}`}
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      className={`${sizeClass} grid shrink-0 place-items-center rounded-full bg-canvas-soft
        font-semibold text-ink-secondary ring-1 ring-hairline ${className}`}
    >
      {initials(user?.full_name)}
    </span>
  )
}
