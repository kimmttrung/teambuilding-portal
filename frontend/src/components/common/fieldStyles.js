/*
 * Kiểu dùng chung cho Input / Select / Textarea — design-notion › text-input:
 * nền surface, chữ ink, viền 1px #dddddd, bo rounded-xs (4px, KHÔNG bao giờ pill), focus thêm bóng Level 1.
 *
 * Cỡ chữ: body-sm (15px) từ màn sm trở lên. Trên điện thoại giữ 16px vì iOS tự phóng to trang khi
 * focus vào ô có chữ nhỏ hơn 16px — CBNV điền form đăng ký bằng điện thoại.
 */
export const FIELD_BASE = `min-h-10 w-full rounded-xs max-sm:min-h-11 border bg-surface px-2.5 py-1.5 text-base text-ink transition
  placeholder:text-ink-faint focus:border-primary focus:shadow-soft focus:outline-none
  disabled:bg-canvas-soft disabled:text-ink-muted sm:text-body-sm`

export const FIELD_BORDER = {
  normal: 'border-input-border',
  error: 'border-rose-500',
}

export const LABEL_CLASS = 'text-caption font-semibold text-ink-secondary'
export const HINT_CLASS = 'text-caption text-ink-muted'
export const ERROR_CLASS = 'text-caption text-rose-600'
