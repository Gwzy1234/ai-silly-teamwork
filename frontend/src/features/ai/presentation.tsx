import { Tag } from 'antd'
import type { RiskLevel } from './types'

const riskPresentation: Record<RiskLevel, { color: string; label: string }> = {
  high: { color: 'red', label: '高风险' },
  medium: { color: 'orange', label: '中风险' },
  low: { color: 'green', label: '低风险' },
}

export function RiskLevelTag({ level }: { level: RiskLevel }) {
  const item = riskPresentation[level]
  return <Tag color={item.color}>{item.label}</Tag>
}
