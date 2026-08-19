import { ArrowRightOutlined, ClockCircleOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Empty, Flex, List, Pagination, Skeleton, Space, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjectPersonalTasks } from '../hooks'
import { PersonalTaskPriorityTag } from '../presentation'

const PAGE_SIZE = 6

export function ProjectPersonalTaskPanel({ projectId }: { projectId: string }) {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const query = useProjectPersonalTasks(projectId, {
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  })

  if (query.isPending) {
    return (
      <Card type="inner" title="个人任务">
        <Skeleton active paragraph={{ rows: 5 }} />
      </Card>
    )
  }

  if (query.isError || !query.data) {
    return (
      <Card type="inner" title="个人任务">
        <Alert
          showIcon
          type="error"
          title="个人任务列表加载失败"
          action={<Button onClick={() => query.refetch()}>重试</Button>}
        />
      </Card>
    )
  }

  return (
    <Card
      type="inner"
      title="个人任务"
      extra={<Typography.Text type="secondary">共 {query.data.total} 项</Typography.Text>}
      className="project-personal-task-panel"
    >
      {query.data.items.length ? (
        <Flex vertical gap={18}>
          <List
            className="project-personal-task-list"
            grid={{ gutter: 12, xs: 1, sm: 2, xl: 3 }}
            dataSource={query.data.items}
            renderItem={(task) => (
              <List.Item>
                <Card size="small" className="project-personal-task-card">
                  <Flex vertical gap={12}>
                    <div>
                      <Flex justify="space-between" align="flex-start" gap={8}>
                        <Typography.Text strong ellipsis={{ tooltip: task.title }}>
                          {task.title}
                        </Typography.Text>
                        <PersonalTaskPriorityTag priority={task.priority} />
                      </Flex>
                      {task.description && (
                        <Typography.Paragraph
                          type="secondary"
                          ellipsis={{ rows: 2, tooltip: task.description }}
                          className="project-personal-task-description"
                        >
                          {task.description}
                        </Typography.Paragraph>
                      )}
                    </div>

                    <Space size={[6, 6]} wrap>
                      <Tag icon={<UserOutlined />}>
                        完成 {task.done_count} / {task.assignment_total}
                      </Tag>
                      {task.in_progress_count > 0 && (
                        <Tag color="processing">进行中 {task.in_progress_count}</Tag>
                      )}
                      {task.in_review_count > 0 && (
                        <Tag color="warning">审核中 {task.in_review_count}</Tag>
                      )}
                    </Space>

                    <Typography.Text type="secondary">
                      <ClockCircleOutlined />{' '}
                      {task.due_at
                        ? `截止 ${dayjs(task.due_at).format('YYYY-MM-DD HH:mm')}`
                        : '无截止时间'}
                    </Typography.Text>

                    <Button
                      block
                      onClick={() => navigate(`/personal-tasks/${task.id}`)}
                    >
                      查看进度 <ArrowRightOutlined />
                    </Button>
                  </Flex>
                </Card>
              </List.Item>
            )}
          />
          {query.data.total > PAGE_SIZE && (
            <Pagination
              current={page}
              pageSize={PAGE_SIZE}
              total={query.data.total}
              showSizeChanger={false}
              hideOnSinglePage
              onChange={setPage}
              responsive
              className="project-personal-task-pagination"
            />
          )}
        </Flex>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该科目还没有发布个人任务"
        />
      )}
    </Card>
  )
}
