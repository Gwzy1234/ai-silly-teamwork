import { CrownOutlined, UserOutlined } from '@ant-design/icons'
import { Tag } from 'antd'
import type { ProjectRole, ProjectStatus } from './types'

const statusPresentation = {
  planning: { color: 'default', label: '规划中' },
  active: { color: 'processing', label: '进行中' },
  completed: { color: 'success', label: '已完成' },
  archived: { color: 'default', label: '已归档' },
} as const

export function ProjectStatusTag({ status }: { status: ProjectStatus }) {
  const item = statusPresentation[status]
  return <Tag color={item.color}>{item.label}</Tag>
}

export function ProjectRoleTag({ role }: { role: ProjectRole }) {
  return role === 'owner' ? (
    <Tag color="gold" icon={<CrownOutlined />}>科目负责人</Tag>
  ) : (
    <Tag icon={<UserOutlined />}>科目成员</Tag>
  )
}
