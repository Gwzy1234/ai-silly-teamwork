import { Alert, App, DatePicker, Form, Input, Modal, Select } from 'antd'
import { getApiErrorMessage } from '../../../api/errors'
import { taskPriorityOptions } from '../../tasks/constants'
import type { TeamMember } from '../../teams/types'
import { toPersonalTaskCreate, type PersonalTaskFormValues } from '../forms'
import { useCreatePersonalTask } from '../hooks'

const { TextArea } = Input

interface PersonalTaskCreateModalProps {
  projectId: string
  teamMembers: TeamMember[]
  open: boolean
  onClose: () => void
  onCreated: (taskId: string) => void
}

export function PersonalTaskCreateModal({
  projectId,
  teamMembers,
  open,
  onClose,
  onCreated,
}: PersonalTaskCreateModalProps) {
  const { message } = App.useApp()
  const [form] = Form.useForm<PersonalTaskFormValues>()
  const createMutation = useCreatePersonalTask(projectId)

  const close = () => {
    if (createMutation.isPending) return
    form.resetFields()
    onClose()
  }

  const submit = async () => {
    try {
      const result = await createMutation.mutateAsync(
        toPersonalTaskCreate(await form.validateFields()),
      )
      message.success('个人任务发布成功')
      form.resetFields()
      onClose()
      onCreated(result.task.id)
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Modal
      title="发布个人任务"
      open={open}
      width={640}
      onCancel={close}
      onOk={submit}
      confirmLoading={createMutation.isPending}
      okText="发布任务"
      cancelButtonProps={{ disabled: createMutation.isPending }}
      maskClosable={!createMutation.isPending}
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{ priority: 'medium', assignee_user_ids: [] }}
      >
        <Form.Item
          name="title"
          label="任务标题"
          rules={[
            { required: true, message: '请输入任务标题' },
            { max: 200, message: '任务标题不能超过 200 个字符' },
          ]}
        >
          <Input placeholder="例如 完成实验报告" />
        </Form.Item>
        <Form.Item
          name="description"
          label="任务说明（可选）"
          rules={[{ max: 5000 }]}
        >
          <TextArea rows={4} maxLength={5000} showCount />
        </Form.Item>
        <Form.Item name="priority" label="优先级" rules={[{ required: true }]}>
          <Select options={taskPriorityOptions} />
        </Form.Item>
        <Form.Item name="starts_at" label="开始时间（可选）">
          <DatePicker showTime style={{ width: '100%' }} placeholder="选择开始时间" />
        </Form.Item>
        <Form.Item
          name="due_at"
          label="截止时间（可选）"
          dependencies={['starts_at']}
          rules={[
            ({ getFieldValue }) => ({
              validator(_, value) {
                const startsAt = getFieldValue('starts_at')
                return !value || !startsAt || !value.isBefore(startsAt)
                  ? Promise.resolve()
                  : Promise.reject(new Error('截止时间不能早于开始时间'))
              },
            }),
          ]}
        >
          <DatePicker showTime style={{ width: '100%' }} placeholder="选择截止时间" />
        </Form.Item>
        <Form.Item
          name="assignee_user_ids"
          label="分配成员"
          rules={[{ required: true, type: 'array', min: 1, message: '请至少选择一名成员' }]}
        >
          <Select
            mode="multiple"
            showSearch
            optionFilterProp="label"
            placeholder="选择需要独立完成任务的成员"
            maxTagCount="responsive"
            options={teamMembers.map((member) => ({
              value: member.user_id,
              label: `${member.nickname || member.username} (@${member.username})`,
            }))}
          />
        </Form.Item>
        <Alert
          showIcon
          type="info"
          message="附件模式：共享"
          description="V1.2 中所有被分配成员看到同一组任务附件，暂不支持个人独立附件。"
        />
      </Form>
    </Modal>
  )
}

