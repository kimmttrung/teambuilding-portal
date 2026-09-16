import { useSearchParams } from 'react-router-dom'
import { Building2, MapPin, Users } from 'lucide-react'
import { useMasterData } from '../../hooks/useMasterData'
import Badge from '../../components/common/Badge'
import CrudSection from '../../components/admin/CrudSection'
import PageHeader from '../../components/common/PageHeader'
import TabNav from '../../components/admin/TabNav'

/**
 * Master data dùng chung cho mọi kỳ: phòng ban, địa điểm làm việc, team.
 *
 * Khác `/admin/settings` ở chỗ dữ liệu ở đây **không gắn kỳ** — sửa một dòng là đổi cho cả kỳ năm
 * ngoái lẫn kỳ năm sau. Vì vậy mỗi mục đều nói rõ hệ quả trước khi người dùng bấm.
 *
 * Chỉ định Trưởng nhóm KHÔNG nằm ở đây: đó là việc vận hành từng kỳ (người cũ huỷ đăng ký thì phải
 * có người thay ngay), làm ở dashboard BTC.
 */
const TABS = [
  { id: 'departments', label: 'Phòng ban', icon: Building2 },
  { id: 'locations', label: 'Địa điểm làm việc', icon: MapPin },
  { id: 'teams', label: 'Team', icon: Users },
]

export default function MasterDataPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: departments } = useMasterData('departments')

  const tab = TABS.some((item) => item.id === searchParams.get('tab'))
    ? searchParams.get('tab')
    : TABS[0].id

  const departmentOptions = (departments ?? []).map((item) => ({
    value: item.id,
    label: item.name,
  }))

  return (
    <>
      <PageHeader
        title="Master data"
        description="Dữ liệu dùng chung cho mọi kỳ Team Building"
      />

      <TabNav
        tabs={TABS}
        current={tab}
        onChange={(next) => setSearchParams({ tab: next }, { replace: true })}
      />

      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-12">
          {tab === 'departments' && (
            <CrudSection
              resource="departments"
              title="Phòng ban"
              description="Dùng cho hồ sơ CBNV và trọng số xếp phòng"
              emptyTitle="Chưa có phòng ban nào"
              columns={[
                { key: 'code', label: 'Mã' },
                { key: 'name', label: 'Tên' },
                { key: 'display_order', label: 'Thứ tự' },
                { key: 'is_active', label: 'Trạng thái', render: activeBadge },
              ]}
              fields={[
                { name: 'code', label: 'Mã', required: true, immutable: true, placeholder: 'IT' },
                { name: 'name', label: 'Tên phòng ban', required: true },
                { name: 'display_order', label: 'Thứ tự hiển thị', type: 'number', defaultValue: 0 },
                { name: 'is_active', label: 'Đang dùng', type: 'checkbox' },
              ]}
            />
          )}

          {tab === 'locations' && (
            <CrudSection
              resource="workLocations"
              title="Địa điểm làm việc"
              description="Quyết định CBNV bay từ sân bay nào và thấy điểm đón nào"
              emptyTitle="Chưa có địa điểm nào"
              columns={[
                { key: 'code', label: 'Mã' },
                { key: 'name', label: 'Tên' },
                { key: 'city', label: 'Thành phố' },
                { key: 'airport_code', label: 'Sân bay' },
                { key: 'is_active', label: 'Trạng thái', render: activeBadge },
              ]}
              fields={[
                { name: 'code', label: 'Mã', required: true, immutable: true, placeholder: 'HN' },
                { name: 'name', label: 'Tên địa điểm', required: true },
                { name: 'city', label: 'Thành phố' },
                {
                  name: 'airport_code',
                  label: 'Mã sân bay',
                  placeholder: 'HAN',
                  hint: '3 chữ in hoa theo IATA',
                },
                { name: 'display_order', label: 'Thứ tự hiển thị', type: 'number', defaultValue: 0 },
                { name: 'is_active', label: 'Đang dùng', type: 'checkbox' },
              ]}
            />
          )}

          {tab === 'teams' && (
            <CrudSection
              resource="teams"
              title="Team"
              description="Đơn vị chia nhóm khi phân bổ chuyến bay, xe, phòng và bàn Gala"
              emptyTitle="Chưa có team nào"
              readOnlyNote="Chỉ định Trưởng nhóm làm ở Tổng quan — đó là việc của từng kỳ, không phải cơ cấu công ty."
              columns={[
                { key: 'code', label: 'Mã' },
                { key: 'name', label: 'Tên' },
                { key: 'member_count', label: 'Thành viên' },
                {
                  key: 'color',
                  label: 'Màu',
                  render: (row) =>
                    row.color ? (
                      <span className="flex items-center gap-1.5">
                        <span
                          className="inline-block size-3.5 rounded-full ring-1 ring-slate-300"
                          style={{ backgroundColor: row.color }}
                          aria-hidden="true"
                        />
                        {row.color}
                      </span>
                    ) : (
                      '—'
                    ),
                },
                { key: 'is_active', label: 'Trạng thái', render: activeBadge },
              ]}
              fields={[
                { name: 'code', label: 'Mã', required: true, immutable: true, placeholder: 'KDHN' },
                { name: 'name', label: 'Tên team', required: true },
                {
                  name: 'department_id',
                  label: 'Phòng ban',
                  type: 'select',
                  numeric: true,
                  options: departmentOptions,
                },
                {
                  name: 'color',
                  label: 'Màu nhận diện',
                  type: 'color',
                  hint: 'Dùng để tô thẻ team trên bảng phân bổ và sơ đồ Gala',
                },
                { name: 'is_active', label: 'Đang dùng', type: 'checkbox' },
              ]}
            />
          )}
        </div>
      </div>
    </>
  )
}

function activeBadge(row) {
  return row.is_active ? (
    <Badge tone="emerald">Đang dùng</Badge>
  ) : (
    <Badge tone="slate">Đã tắt</Badge>
  )
}
