import { useState } from 'react'
import { Search } from 'lucide-react'
import Button from './Button'
import Input from './Input'

/**
 * Ô tìm kiếm: chỉ tìm khi bấm Enter hoặc nút — không gọi API theo từng phím gõ.
 * Nơi dùng đặt `key` theo giá trị trên URL để ô tự làm mới khi bộ lọc bị xoá từ bên ngoài.
 */
export default function SearchBox({ initial = '', onSearch, label = 'Tìm kiếm', placeholder }) {
  const [value, setValue] = useState(initial)

  return (
    <form
      role="search"
      className="flex items-end gap-2"
      onSubmit={(submitEvent) => {
        submitEvent.preventDefault()
        onSearch(value.trim())
      }}
    >
      <div className="min-w-0 flex-1">
        <Input
          label={label}
          type="search"
          placeholder={placeholder}
          value={value}
          onChange={(changeEvent) => setValue(changeEvent.target.value)}
        />
      </div>
      <Button type="submit" variant="secondary" icon={Search} aria-label="Tìm">
        <span className="sr-only sm:not-sr-only">Tìm</span>
      </Button>
    </form>
  )
}
