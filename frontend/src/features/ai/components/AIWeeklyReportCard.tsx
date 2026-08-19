import { FileTextOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Empty,
  Flex,
  List,
  Skeleton,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { ApiError } from '../../../api/errors'
import { useWeeklyReport } from '../hooks'
import type { WeeklyReportResponse } from '../types'

interface AIWeeklyReportCardProps {
  projectId: string
  initialData?: WeeklyReportResponse | null
}

function getAiWeeklyReportErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        return '登录状态失效，请重新登录'
      case 403:
        return '你没有访问该项目的权限'
      case 502:
        return 'AI服务暂时不可用，请稍后重试'
      default:
        return 'AI周报生成失败，请稍后重试'
    }
  }
  return 'AI周报生成失败，请稍后重试'
}

function ReportSection({
  title,
  items,
  emptyText = '暂无',
}: {
  title: string
  items: string[]
  emptyText?: string
}) {
  return (
    <div>
      <Typography.Text strong>{title}</Typography.Text>
      <List
        size="small"
        dataSource={items}
        renderItem={(item) => <List.Item>{item}</List.Item>}
        locale={{ emptyText }}
      />
    </div>
  )
}

function TaskListSection({
  title,
  tasks,
  emptyText = '暂无',
}: {
  title: string
  tasks: { title: string; due_at?: string | null }[]
  emptyText?: string
}) {
  return (
    <div>
      <Typography.Text strong>{title}</Typography.Text>
      <List
        size="small"
        dataSource={tasks}
        renderItem={(task) => (
          <List.Item>
            <Flex vertical gap={4} style={{ width: '100%' }}>
              <Typography.Text>{task.title}</Typography.Text>
              {task.due_at && (
                <Typography.Text type="secondary">
                  截止：{dayjs(task.due_at).format('YYYY-MM-DD HH:mm')}
                </Typography.Text>
              )}
            </Flex>
          </List.Item>
        )}
        locale={{ emptyText }}
      />
    </div>
  )
}

function WeeklyReportResult({ data }: { data: WeeklyReportResponse }) {
  const fileItems = data.file_updates.map(
    (file) =>
      `${file.name}${file.task_title ? `（${file.task_title}）` : ''} · ${dayjs(file.created_at).format('YYYY-MM-DD HH:mm')}`,
  )

  return (
    <Flex vertical gap={16}>
      <Typography.Text type="secondary">
        周期：{data.period_start} 至 {data.period_end}
      </Typography.Text>
      <div>
        <Typography.Text strong>本周总结</Typography.Text>
        <Typography.Paragraph style={{ marginTop: 4, marginBottom: 0 }}>
          {data.summary}
        </Typography.Paragraph>
      </div>
      <TaskListSection title="已完成事项" tasks={data.completed_tasks} />
      <TaskListSection title="未完成事项" tasks={data.unfinished_tasks} />
      <TaskListSection title="延期任务" tasks={data.overdue_tasks} emptyText="无延期任务" />
      <ReportSection title="风险" items={data.risks} emptyText="暂无风险" />
      <ReportSection title="建议" items={data.suggestions} emptyText="暂无建议" />
      <ReportSection title="文件更新" items={fileItems} emptyText="本周暂无文件更新" />
    </Flex>
  )
}

export function AIWeeklyReportCard({
  projectId,
  initialData = null,
}: AIWeeklyReportCardProps) {
  const mutation = useWeeklyReport(projectId)
  const result = mutation.data ?? initialData

  return (
    <Card
      className="content-card"
      title="AI 项目周报"
      extra={
        <Button
          type="primary"
          icon={<FileTextOutlined />}
          loading={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          生成周报
        </Button>
      }
    >
      {mutation.isPending ? (
        <Skeleton active paragraph={{ rows: 6 }} />
      ) : mutation.isError ? (
        <Alert
          showIcon
          type="error"
          message="AI 周报生成失败"
          description={getAiWeeklyReportErrorMessage(mutation.error)}
          action={
            <Button size="small" onClick={() => mutation.mutate()}>
              重试
            </Button>
          }
        />
      ) : result ? (
        <WeeklyReportResult data={result} />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="点击“生成周报”，AI 将汇总本周项目进展、任务完成情况和文件更新。"
        />
      )}
    </Card>
  )
}
