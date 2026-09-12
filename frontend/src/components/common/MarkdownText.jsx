/**
 * Hiển thị nội dung Markdown đơn giản mà BTC nhập: quy định, FAQ, thông báo.
 *
 * Chỉ đỡ tiêu đề, danh sách gạch đầu dòng và chữ in đậm — đúng những gì các tài liệu
 * đó dùng (xem TERMS_MARKDOWN trong scripts/seed.py). Tự cắt khối như vậy để không
 * phải kéo thêm thư viện markdown, và cũng không bao giờ chèn HTML thô từ nội dung
 * do người dùng nhập (dangerouslySetInnerHTML là lỗ XSS gần nhất trong dự án này).
 */
export default function MarkdownText({ content, className = '' }) {
  if (!content) return null

  return (
    <div className={`flex flex-col gap-2.5 text-sm leading-relaxed text-slate-700 ${className}`}>
      {toBlocks(content).map((block, index) => {
        if (block.type === 'heading') {
          const Tag = block.level <= 2 ? 'h3' : 'h4'
          return (
            <Tag
              key={index}
              className={`text-slate-900 ${
                block.level <= 2 ? 'mt-1 text-base font-bold' : 'mt-1 text-sm font-semibold'
              }`}
            >
              {renderInline(block.text)}
            </Tag>
          )
        }

        if (block.type === 'list') {
          return (
            <ul key={index} className="ml-4 list-disc space-y-1.5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          )
        }

        return <p key={index}>{renderInline(block.text)}</p>
      })}
    </div>
  )
}

function toBlocks(content) {
  const blocks = []

  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim()
    const previous = blocks[blocks.length - 1]

    if (!line) continue

    // Dòng thụt đầu là phần tiếp của dòng trước (bullet dài bị gói xuống hàng).
    if (/^\s/.test(rawLine) && previous) {
      if (previous.type === 'list') {
        previous.items[previous.items.length - 1] += ` ${line}`
        continue
      }
      if (previous.type === 'paragraph') {
        previous.text += ` ${line}`
        continue
      }
    }

    const heading = line.match(/^(#{1,4})\s+(.*)$/)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] })
      continue
    }

    const bullet = line.match(/^[-*]\s+(.*)$/)
    if (bullet) {
      if (previous?.type === 'list') previous.items.push(bullet[1])
      else blocks.push({ type: 'list', items: [bullet[1]] })
      continue
    }

    if (previous?.type === 'paragraph') previous.text += ` ${line}`
    else blocks.push({ type: 'paragraph', text: line })
  }

  return blocks
}

function renderInline(text) {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map((part, index) =>
      part.startsWith('**') && part.endsWith('**') ? (
        <strong key={index} className="font-semibold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      ) : (
        part
      ),
    )
}
