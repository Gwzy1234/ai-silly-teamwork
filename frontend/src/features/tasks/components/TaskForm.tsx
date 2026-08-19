import { DatePicker, Form, Input, Select } from 'antd'
import type { FormInstance } from 'antd'
import type { TeamMember } from '../../teams/types'
import { taskPriorityOptions } from '../constants'
import type { TaskFormValues } from '../forms'

const { TextArea } = Input

interface TaskFormProps {
  form: FormInstance<TaskFormValues>
  teamMembers?: TeamMember[]
  showOwner?: boolean
}

export function TaskForm({ form, teamMembers = [], showOwner = false }: TaskFormProps) {
  return (
    <Form
      form={form}
      layout="vertical"
      requiredMark={false}
      initialValues={{ priority: 'medium' }}
    >
      <Form.Item
        name="title"
        label="任务标题"
        rules={[{ required: true, message: '请输入任务标题' }, { max: 200 }]}
      >
        <Input placeholder="例如 完成展示文稿初稿" />
      </Form.Item>
      <Form.Item name="description" label="任务描述（可选）" rules={[{ max: 5000 }]}>
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
      {showOwner && (
        <Form.Item name="owner_user_id" label="负责人（可选）">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="默认由创建者担任负责人"
            options={teamMembers.map((member) => ({
              value: member.user_id,
              label: `${member.nickname || member.username} (@${member.username})`,
            }))}
          />
        </Form.Item>
      )}
    </Form>
  )
}
