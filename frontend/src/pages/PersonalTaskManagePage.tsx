import { ArrowLeftOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons'
import {
  Alert,
  App,
  Avatar,
  Button,
  Card,
  Descriptions,
  Empty,
  Flex,
  List,
  Popconfirm,
  Progress,
  Result,
  Skeleton,
  Space,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useNavigate, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/errors'
import { FilePanel } from '../features/files/components/FilePanel'
import {
  useDeletePersonalTask,
  usePersonalTask,
  usePersonalTaskAssignments,
} from '../features/personal-tasks/hooks'
import {
  PersonalTaskPriorityTag,
  PersonalTaskStatusTag,
} from '../features/personal-tasks/presentation'

export function PersonalTaskManagePage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const detail = usePersonalTask(taskId)
  const assignments = usePersonalTaskAssignments(taskId)
  const deleteMutation = useDeletePersonalTask(taskId)

  if (detail.isPending || assignments.isPending) {
    return <Card className="content-card"><Skeleton active paragraph={{ rows: 10 }} /></Card>
  }
  if (detail.isError || !detail.data) {
    return <Result status="404" title="个人任务不存在或你无权访问" />
  }
  if (assignments.isError || !assignments.data) {
    return (
      <Result
        status="403"
        title="无权查看成员进度"
        subTitle="只有所属小组组长或系统超级管理员可以使用该管理视图。"
        extra={<Button onClick={() => navigate('/my-tasks')}>返回我的任务</Button>}
      />
    )
  }

  const task = detail.data.task
  const completed = assignments.data.filter((item) => item.status === 'done').length
  const completionPercent = assignments.data.length
    ? Math.round((completed / assignments.data.length) * 100)
    : 0

  const removeTask = async () => {
    try {
      await deleteMutation.mutateAsync()
      message.success('个人任务及所有成员进度已删除')
      navigate(`/projects/${task.project_id}`, { replace: true })
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space align="start">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(`/projects/${task.project_id}`)}
          />
          <div>
            <Space wrap>
              <Typography.Title level={2} style={{ margin: 0 }}>{task.title}</Typography.Title>
              <PersonalTaskPriorityTag priority={task.priority} />
            </Space>
            <Typography.Text type="secondary">
              {task.project.team.name} · {task.project.name} · 个人任务管理
            </Typography.Text>
          </div>
        </Space>
      </Flex>

      <Card className="content-card">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="开始时间">
            {task.starts_at ? dayjs(task.starts_at).format('YYYY-MM-DD HH:mm') : '未设置'}
          </Descriptions.Item>
          <Descriptions.Item label="截止时间">
            {task.due_at ? dayjs(task.due_at).format('YYYY-MM-DD HH:mm') : '未设置'}
          </Descriptions.Item>
          <Descriptions.Item label="附件模式">共享附件</Descriptions.Item>
          <Descriptions.Item label="分配人数">{assignments.data.length} 人</Descriptions.Item>
          <Descriptions.Item label="任务说明" span={2}>
            {task.description || '暂未填写任务说明'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="content-card" title="成员完成情况">
        <Flex vertical gap={20}>
          <div>
            <Flex justify="space-between" gap={12} wrap>
              <Typography.Text strong>
                已完成：{completed} / {assignments.data.length}
              </Typography.Text>
              <Typography.Text type="secondary">整体完成率 {completionPercent}%</Typography.Text>
            </Flex>
            <Progress percent={completionPercent} status={completionPercent === 100 ? 'success' : 'active'} />
          </div>

          {assignments.data.length ? (
            <List
              dataSource={assignments.data}
              renderItem={(assignment) => (
                <List.Item extra={<PersonalTaskStatusTag status={assignment.status} />}>
                  <List.Item.Meta
                    avatar={<Avatar icon={<UserOutlined />} />}
                    title={assignment.user.nickname || assignment.user.username}
                    description={
                      <Space direction="vertical" size={2}>
                        <Typography.Text type="secondary">@{assignment.user.username}</Typography.Text>
                        <Typography.Text type="secondary" className="personal-task-assignment-time">
                          分配：{dayjs(assignment.assigned_at).format('YYYY-MM-DD HH:mm')}
                          {assignment.started_at && ` · 开始：${dayjs(assignment.started_at).format('MM-DD HH:mm')}`}
                          {assignment.completed_at && ` · 完成：${dayjs(assignment.completed_at).format('MM-DD HH:mm')}`}
                        </Typography.Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无成员进度" />
          )}
        </Flex>
      </Card>

      <Card className="content-card" title="任务文件">
        <FilePanel scope="task" ownerId={task.id} title="共享文件" />
      </Card>

      <Card className="content-card danger-zone-card" title="危险操作">
        <Flex justify="space-between" align="center" gap={16} wrap>
          <div>
            <Typography.Text strong>删除个人任务</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
              删除后会同时移除所有成员的个人任务记录，且无法恢复。
            </Typography.Paragraph>
          </div>
          <Popconfirm
            title="确认删除此个人任务？"
            description="该操作会删除全部成员 Assignment，且无法恢复。"
            okText="确认删除"
            cancelText="取消"
            okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
            onConfirm={removeTask}
          >
            <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending}>
              删除个人任务
            </Button>
          </Popconfirm>
        </Flex>
      </Card>

      <Alert
        showIcon
        type="info"
        message="管理员只能查看成员进度，不能代替成员修改状态。"
      />
    </Flex>
  )
}
