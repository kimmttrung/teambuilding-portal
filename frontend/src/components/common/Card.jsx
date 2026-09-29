/**
 * design-notion › feature-card: nền surface, viền hairline, bo rounded-lg (12px), phẳng (Level 0).
 * `elevated` = feature-card-elevated (thêm bóng Level 1) cho thẻ cần nổi lên nền giấy.
 */
export default function Card({
  title,
  description,
  action,
  elevated = false,
  children,
  className = '',
  bodyClassName = '',
}) {
  return (
    <section
      className={`rounded-lg border border-hairline bg-surface text-ink ${elevated ? 'shadow-soft' : ''} ${className}`}
    >
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3 sm:px-6">
          <div className="min-w-0">
            {title && <h2 className="truncate text-body-md font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 truncate text-caption text-ink-muted">{description}</p>}
          </div>
          {action}
        </header>
      )}
      {/* `p-0` (bảng tràn mép thẻ) phải bỏ hẳn padding mặc định: `sm:px-6` đứng sau trong CSS nên
          sẽ thắng `p-0` truyền vào nếu cứ ghép hai chuỗi lại. */}
      <div className={`${/\bp-0\b/.test(bodyClassName) ? '' : 'px-4 py-4 sm:px-6'} ${bodyClassName}`}>
        {children}
      </div>
    </section>
  )
}
