import { DatePicker, Form, Input, Select } from 'antd'
import type { FormInstance } from 'antd'
import type { ProjectFormValues } from '../forms'
import type { TeamMember } from '../../teams/types'

const { TextArea } = Input

interface ProjectFormProps {
  form: FormInstance<ProjectFormValues>
  teamMembers?: TeamMember[]
  showOwner?: boolean
}

export function ProjectForm({ form, teamMembers = [], showOwner = false }: ProjectFormProps) {
  return (
    <Form form={form} layout="vertical" requiredMark={false}>
      <Form.Item
        name="name"
        label="科目名称"
        rules={[{ required: true, message: '请输入科目名称' }, { max: 160 }]}
      >
        <Input placeholder="例如 医学影像技术" />
      </Form.Item>
      <Form.Item name="description" label="科目描述（可选）" rules={[{ max: 5000 }]}>
        <TextArea rows={4} maxLength={5000} showCount />
      </Form.Item>
      <Form.Item name="starts_at" label="课程开始时间（可选）">
        <DatePicker showTime style={{ width: '100%' }} placeholder="选择课程开始时间" />
      </Form.Item>
      <Form.Item
        name="due_at"
        label="课程结束时间（可选）"
        dependencies={['starts_at']}
        rules={[
          ({ getFieldValue }) => ({
            validator(_, value) {
              const startsAt = getFieldValue('starts_at')
              return !value || !startsAt || !value.isBefore(startsAt)
                ? Promise.resolve()
                : Promise.reject(new Error('课程结束时间不能早于开始时间'))
            },
          }),
        ]}
      >
        <DatePicker showTime style={{ width: '100%' }} placeholder="选择课程结束时间" />
      </Form.Item>
      {showOwner && (
        <Form.Item name="owner_user_id" label="科目负责人（可选）">
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
