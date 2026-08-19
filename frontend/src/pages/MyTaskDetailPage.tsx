import {
  ArrowLeftOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  PaperClipOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Flex,
  Form,
  Result,
  Select,
  Skeleton,
  Space,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/errors'
import { FilePanel } from '../features/files/components/FilePanel'
import { personalTaskStatusOptions } from '../features/personal-tasks/constants'
import {
  usePersonalTask,
  useTaskAssignment,
  useUpdateTaskAssignmentStatus,
} from '../features/personal-tasks/hooks'
import {
  DeadlineStateTag,
  PersonalTaskPriorityTag,
  PersonalTaskStatusTag,
} from '../features/personal-tasks/presentation'
import type { TaskStatusUpdate } from '../features/personal-tasks/types'

export function MyTaskDetailPage() {
  const { assignmentId = '' } = useParams()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const assignment = useTaskAssignment(assignmentId)
  const taskId = assignment.data?.task_id || ''
  const detail = usePersonalTask(taskId)
  const statusMutation = useUpdateTaskAssignmentStatus(assignmentId, taskId)
  const [statusForm] = Form.useForm<TaskStatusUpdate>()

  useEffect(() => {
    if (assignment.data) {
      statusForm.setFieldValue('status', assignment.data.status)
    }
  }, [assignment.data, statusForm])

  const updateStatus = async () => {
    try {
      await statusMutation.mutateAsync(await statusForm.validateFields())
      message.success('个人任务状态已更新')
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  if (assignment.isPending || (taskId && detail.isPending)) {
    return <Card className="content-card"><Skeleton active paragraph={{ rows: 9 }} /></Card>
  }
  if (assignment.isError || !assignment.data || detail.isError || !detail.data) {
    return (
      <Result
        status="404"
        title="个人任务不存在或你无权访问"
        extra={<Button onClick={() => navigate('/my-tasks')}>返回我的任务</Button>}
      />
    )
  }

  const task = detail.data.task
  const currentAssignment = assignment.data

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space align="start">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/my-tasks')} />
          <div>
            <Space wrap>
              <Typography.Title level={2} style={{ margin: 0 }}>{task.title}</Typography.Title>
              <PersonalTaskStatusTag status={currentAssignment.status} />
              <DeadlineStateTag task={task} status={currentAssignment.status} />
            </Space>
            <Typography.Text type="secondary">
              {task.project.team.name} · {task.project.name}
            </Typography.Text>
          </div>
        </Space>
      </Flex>

      <Card className="content-card">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="我的状态">
            <PersonalTaskStatusTag status={currentAssignment.status} />
          </Descriptions.Item>
          <Descriptions.Item label="优先级">
            <PersonalTaskPriorityTag priority={task.priority} />
          </Descriptions.Item>
          <Descriptions.Item label="所属小组">{task.project.team.name}</Descriptions.Item>
          <Descriptions.Item label="所属科目">{task.project.name}</Descriptions.Item>
          <Descriptions.Item label="开始时间">
            <CalendarOutlined /> {task.starts_at ? dayjs(task.starts_at).format('YYYY-MM-DD HH:mm') : '未设置'}
          </Descriptions.Item>
          <Descriptions.Item label="截止时间">
            <ClockCircleOutlined /> {task.due_at ? dayjs(task.due_at).format('YYYY-MM-DD HH:mm') : '未设置'}
          </Descriptions.Item>
          <Descriptions.Item label="附件模式">
            <PaperClipOutlined /> {task.attachment_mode === 'shared' ? '共享附件' : '独立附件'}
          </Descriptions.Item>
          <Descriptions.Item label="分配时间">
            {dayjs(currentAssignment.assigned_at).format('YYYY-MM-DD HH:mm')}
          </Descriptions.Item>
          <Descriptions.Item label="任务说明" span={2}>
            {task.description || '暂未填写任务说明'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="content-card" title="更新我的进度">
        <Flex vertical gap={16}>
          <Alert
            showIcon
            type="info"
            message="每位成员独立维护自己的状态"
            description="可选状态由后端状态机最终校验；不允许的流转会返回明确提示。"
          />
          <Form form={statusForm} layout="vertical" className="personal-task-status-form">
            <Form.Item name="status" label="目标状态" rules={[{ required: true }]}>
              <Select options={personalTaskStatusOptions} />
            </Form.Item>
            <Button
              type="primary"
              onClick={updateStatus}
              loading={statusMutation.isPending}
              block
            >
              保存状态
            </Button>
          </Form>
        </Flex>
      </Card>

      <Card className="content-card" title="进度时间">
        <Descriptions column={{ xs: 1, md: 3 }}>
          <Descriptions.Item label="分配">
            {dayjs(currentAssignment.assigned_at).format('YYYY-MM-DD HH:mm')}
          </Descriptions.Item>
          <Descriptions.Item label="开始">
            {currentAssignment.started_at
              ? dayjs(currentAssignment.started_at).format('YYYY-MM-DD HH:mm')
              : '尚未开始'}
          </Descriptions.Item>
          <Descriptions.Item label="完成">
            {currentAssignment.completed_at
              ? dayjs(currentAssignment.completed_at).format('YYYY-MM-DD HH:mm')
              : '尚未完成'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="content-card" title="任务文件">
        <FilePanel scope="task" ownerId={task.id} title="共享文件" />
      </Card>
    </Flex>
  )
}
