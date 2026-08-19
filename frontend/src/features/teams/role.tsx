import { CrownOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons'
import { Tag } from 'antd'
import type { TeamRole } from './types'

const rolePresentation = {
  leader: { color: 'gold', icon: <CrownOutlined />, label: '组长' },
  admin: { color: 'blue', icon: <SafetyCertificateOutlined />, label: '管理员' },
  member: { color: 'default', icon: <UserOutlined />, label: '成员' },
} as const

export function TeamRoleTag({ role }: { role: TeamRole }) {
  const presentation = rolePresentation[role]
  return (
    <Tag color={presentation.color} icon={presentation.icon}>
      {presentation.label}
    </Tag>
  )
}
