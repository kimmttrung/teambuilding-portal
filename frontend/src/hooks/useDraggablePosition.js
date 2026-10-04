import { useCallback, useEffect, useRef, useState } from 'react'

const DRAG_THRESHOLD = 6 // px — nhích ít hơn thế này vẫn tính là bấm
const EDGE = 8 // lề tối thiểu với mép màn hình
const MOBILE_NAV = 72 // thanh điều hướng dưới trên điện thoại (bề rộng < 768px)

/**
 * Cho một phần tử `position: fixed` kéo đi được bằng chuột lẫn ngón tay, mà bấm vẫn là bấm.
 *
 * Dùng Pointer Events nên chuột, cảm ứng và bút đi chung một đường. Phân biệt kéo với bấm bằng
 * quãng đường: nhích dưới 6px coi như bấm (ngón tay không bao giờ đứng yên tuyệt đối). Vừa kéo xong
 * thì `click` kế tiếp bị nuốt, không thì thả tay ra là mở luôn thứ đang kéo.
 *
 * `position` là `null` cho tới khi người dùng kéo lần đầu — lúc đó phần tử nằm ở vị trí mặc định do
 * CSS quyết định. Vị trí được nhớ trong localStorage theo `storageKey`; đây chỉ là tiện ích riêng
 * của từng trình duyệt, không đọc/ghi được thì vẫn chạy bình thường.
 */
export function useDraggablePosition(storageKey) {
  const [position, setPosition] = useState(() => readPosition(storageKey))
  const [dragging, setDragging] = useState(false)
  const gesture = useRef(null)
  const swallowClick = useRef(false)

  // Xoay màn hình / đổi cỡ cửa sổ: kéo phần tử về lại trong khung nhìn.
  useEffect(() => {
    function onResize() {
      setPosition((current) => (current ? clamp(current, current.width, current.height) : current))
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const onPointerDown = useCallback((event) => {
    if (event.button !== undefined && event.button !== 0) return
    const rect = event.currentTarget.getBoundingClientRect()
    gesture.current = {
      id: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      width: rect.width,
      height: rect.height,
      moved: false,
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }, [])

  const onPointerMove = useCallback((event) => {
    const active = gesture.current
    if (!active || active.id !== event.pointerId) return
    if (!active.moved) {
      const distance = Math.hypot(event.clientX - active.startX, event.clientY - active.startY)
      if (distance < DRAG_THRESHOLD) return
      active.moved = true
      setDragging(true)
    }
    setPosition(
      clamp(
        { x: event.clientX - active.offsetX, y: event.clientY - active.offsetY },
        active.width,
        active.height,
      ),
    )
  }, [])

  const finish = useCallback(
    (event) => {
      const active = gesture.current
      if (!active || active.id !== event.pointerId) return
      gesture.current = null
      event.currentTarget.releasePointerCapture?.(event.pointerId)
      if (!active.moved) return
      swallowClick.current = true
      setDragging(false)
      setPosition((current) => {
        if (current) writePosition(storageKey, current)
        return current
      })
    },
    [storageKey],
  )

  /** Bọc `onClick` của phần tử: bỏ qua cú click sinh ra do thả tay sau khi kéo. */
  const guardClick = useCallback(
    (handler) => (event) => {
      if (swallowClick.current) {
        swallowClick.current = false
        event.preventDefault()
        return
      }
      handler(event)
    },
    [],
  )

  return {
    position,
    dragging,
    guardClick,
    handlers: { onPointerDown, onPointerMove, onPointerUp: finish, onPointerCancel: finish },
  }
}

/** Phần tử đang nằm nửa trái hay nửa phải màn hình. Chưa kéo lần nào thì ở góc phải mặc định. */
export function sideOf(position) {
  if (!position || typeof window === 'undefined') return 'right'
  return position.x + (position.width ?? 0) / 2 < window.innerWidth / 2 ? 'left' : 'right'
}

function clamp({ x, y }, width = 0, height = 0) {
  if (typeof window === 'undefined') return { x, y, width, height }
  const bottomReserve = window.innerWidth < 768 ? MOBILE_NAV : 0
  const maxX = Math.max(EDGE, window.innerWidth - width - EDGE)
  const maxY = Math.max(EDGE, window.innerHeight - height - EDGE - bottomReserve)
  return {
    x: Math.round(Math.min(Math.max(x, EDGE), maxX)),
    y: Math.round(Math.min(Math.max(y, EDGE), maxY)),
    width,
    height,
  }
}

function readPosition(storageKey) {
  if (!storageKey) return null
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) ?? 'null')
    if (!saved || !Number.isFinite(saved.x) || !Number.isFinite(saved.y)) return null
    // Vị trí lưu từ màn hình khác cỡ (máy tính → điện thoại) có thể nằm ngoài khung nhìn.
    return clamp(saved, saved.width, saved.height)
  } catch {
    return null
  }
}

function writePosition(storageKey, position) {
  if (!storageKey) return
  try {
    localStorage.setItem(storageKey, JSON.stringify(position))
  } catch {
    // Không lưu được thì lần sau icon về lại góc mặc định — không sao.
  }
}
