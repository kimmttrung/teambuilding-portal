/**
 * Làm nổi bật chỗ của người đang tra cứu trên các màn hình phân bổ (docs/13 task 7).
 *
 * Gom về một chỗ để 5 màn hình tô giống hệt nhau — mỗi nơi tự chế một kiểu đỏ thì BTC phải học lại
 * cách đọc ở từng trang.
 */

/**
 * Ref callback: cuộn tới phần tử vừa được tô đỏ.
 *
 * Phải là hàm ở cấp module (định danh không đổi) — truyền arrow function inline thì React coi là ref
 * mới sau MỖI lần render và cuộn lại liên tục, trang giật không dùng được.
 */
export function scrollIntoView(node) {
  node?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/** Dòng bảng: viền trái đỏ + nền đỏ nhạt, vẫn giữ kiểu "đã tắt" của chuyến ngừng khai thác. */
export function rowClass(item, highlighted) {
  const base = item?.is_active === false ? 'bg-slate-50/70' : ''
  return highlighted ? 'bg-rose-50 outline outline-2 -outline-offset-2 outline-rose-500' : base
}

/** Thẻ (xe, phòng): viền đỏ dày hơn viền thường để nhìn phát thấy ngay. */
export function cardClass(highlighted, base = '') {
  return highlighted ? `${base} ring-2 ring-rose-500 bg-rose-50` : base
}
