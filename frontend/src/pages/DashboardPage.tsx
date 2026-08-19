import {
  ArrowRightOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  ClockCircleOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Alert, Card, Col, Empty, Flex, List, Row, Skeleton, Statistic, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import { useEffect, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useCurrentUser } from '../features/auth/hooks'
import {
  useOverdueTasks,
  useUpcomingTasks,
} from '../features/dashboard/hooks'
import { useNotifications } from '../features/notifications/hooks'
import { useMyPersonalTaskCount } from '../features/personal-tasks/hooks'
import type { DashboardTask } from '../features/dashboard/types'
import { TaskStatusTag } from '../features/tasks/presentation'
import { useTeams } from '../features/teams/hooks'
import { usePreferencesStore } from '../features/settings/store'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

interface MetricCardProps {
  title: string
  value?: number
  loading: boolean
  error: boolean
  icon: ReactNode
  color: string
  to: string
}

function MetricCard({ title, value, loading, error, icon, color, to }: MetricCardProps) {
  return (
    <Link className="metric-card-link" to={to} aria-label={`${title}，查看详情`}>
      <Card className="metric-card metric-card-interactive">
        <Flex align="center" justify="space-between">
          <div>
            <Typography.Text type="secondary">{title}</Typography.Text>
            {loading ? (
              <Skeleton.Input active size="small" style={{ display: 'block', marginTop: 8 }} />
            ) : error ? (
              <Typography.Title level={3} type="secondary" style={{ margin: '8px 0 0' }}>
                --
              </Typography.Title>
            ) : (
              <Statistic value={value ?? 0} valueStyle={{ fontWeight: 700 }} />
            )}
          </div>
          <Flex align="center" gap={10}>
            <span className="metric-icon" style={{ color, backgroundColor: `${color}18` }}>
              {icon}
            </span>
            <ArrowRightOutlined className="metric-card-arrow" />
          </Flex>
        </Flex>
      </Card>
    </Link>
  )
}

function TaskList({
  tasks,
  emptyText,
  showStatus = false,
}: {
  tasks: DashboardTask[]
  emptyText: string
  showStatus?: boolean
}) {
  if (!tasks.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
  return (
    <List
      dataSource={tasks}
      renderItem={(task) => (
        <List.Item>
          <List.Item.Meta
            title={<Link to={`/tasks/${task.id}`}>{task.title}</Link>}
            description={
              task.due_at ? `截止时间 ${dayjs(task.due_at).format('MM月DD日 HH:mm')}` : '无截止时间'
            }
          />
          <Flex gap={8} wrap>
            {showStatus && <TaskStatusTag status={task.status} />}
            <Tag color={task.priority === 'urgent' ? 'red' : task.priority === 'high' ? 'orange' : 'blue'}>
              {task.priority}
            </Tag>
          </Flex>
        </List.Item>
      )}
    />
  )
}

export function DashboardPage() {
  const location = useLocation()
  const user = useCurrentUser().data
  const teams = useTeams()
  const deadlineHours = usePreferencesStore((state) => state.dashboardDeadlineHours)
  const upcoming = useUpcomingTasks(deadlineHours)
  const overdue = useOverdueTasks()
  const notifications = useNotifications()
  const personalTaskCount = useMyPersonalTaskCount()
  const unreadCount = notifications.data?.filter((item) => !item.is_read).length

  useEffect(() => {
    if (!location.hash) return
    const target = document.getElementById(location.hash.slice(1))
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [location.hash])

  return (
    <Flex vertical gap={24}>
      <Card className="dashboard-hero">
        <Typography.Title level={2} style={{ margin: 0 }}>
          你好，{user?.nickname || user?.username}
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ margin: '8px 0 0' }}>
          这里汇总了你的团队协作和最近截止事项。
        </Typography.Paragraph>
      </Card>

      {[teams, upcoming, overdue, notifications, personalTaskCount].some((query) => query.isError) && (
        <Alert showIcon type="warning" message="部分数据暂时加载失败，其他模块仍可正常使用。" />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="我的任务"
            value={personalTaskCount.data?.unfinished}
            loading={personalTaskCount.isPending}
            error={personalTaskCount.isError}
            icon={<CheckSquareOutlined />}
            color="#2f9e44"
            to="/my-tasks"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="我的团队"
            value={teams.data?.length}
            loading={teams.isPending}
            error={teams.isError}
            icon={<TeamOutlined />}
            color="#1677ff"
            to="/teams"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title={`${deadlineHours} 小时内截止`}
            value={upcoming.data?.length}
            loading={upcoming.isPending}
            error={upcoming.isError}
            icon={<CalendarOutlined />}
            color="#13a8a8"
            to="/dashboard#upcoming-tasks"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="已逾期任务"
            value={overdue.data?.length}
            loading={overdue.isPending}
            error={overdue.isError}
            icon={<ClockCircleOutlined />}
            color="#ff4d4f"
            to="/dashboard#overdue-tasks"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="未读通知"
            value={unreadCount}
            loading={notifications.isPending}
            error={notifications.isError}
            icon={<BellOutlined />}
            color="#722ed1"
            to="/notifications"
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12} id="upcoming-tasks" className="dashboard-section-anchor">
          <Card title="即将截止" className="content-card" loading={upcoming.isPending}>
            {upcoming.isError ? (
              <Alert type="error" message="即将截止任务加载失败" showIcon />
            ) : (
              <TaskList tasks={upcoming.data ?? []} emptyText={`未来 ${deadlineHours} 小时暂无截止任务`} />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={12} id="overdue-tasks" className="dashboard-section-anchor">
          <Card title="逾期任务" className="content-card" loading={overdue.isPending}>
            {overdue.isError ? (
              <Alert type="error" message="逾期任务加载失败" showIcon />
            ) : (
              <TaskList
                tasks={overdue.data ?? []}
                emptyText="太好了，目前没有逾期任务"
                showStatus
              />
            )}
          </Card>
        </Col>
      </Row>
    </Flex>
  )
}
