import { App, Form, Modal } from 'antd'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../../../api/errors'
import type { TeamMember } from '../../teams/types'
import { toTaskCreate, type TaskFormValues } from '../forms'
import { useCreateTask } from '../hooks'
import { TaskForm } from './TaskForm'

interface CreateTaskModalProps {
  projectId: string
  teamMembers: TeamMember[]
  open: boolean
  onClose: () => void
}

export function CreateTaskModal({ projectId, teamMembers, open, onClose }: CreateTaskModalProps) {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [form] = Form.useForm<TaskFormValues>()
  const createMutation = useCreateTask(projectId)

  const close = () => {
    form.resetFields()
    onClose()
  }

  const submit = async () => {
    try {
      const task = await createMutation.mutateAsync(toTaskCreate(await form.validateFields()))
      message.success('任务已创建，Dashboard 截止数据已刷新')
      close()
      navigate(`/tasks/${task.id}`)
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Modal
      title="创建任务"
      open={open}
      width={620}
      onCancel={close}
      onOk={submit}
      confirmLoading={createMutation.isPending}
      okText="创建"
    >
      <TaskForm form={form} teamMembers={teamMembers} showOwner />
    </Modal>
  )
}
