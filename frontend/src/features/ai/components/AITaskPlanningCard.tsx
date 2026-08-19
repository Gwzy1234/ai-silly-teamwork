import { PlusOutlined } from '@ant-design/icons'
import {
  App,
  Button,
  Card,
  Checkbox,
  Empty,
  Flex,
  Input,
  InputNumber,
  List,
  Modal,
  Space,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { getApiErrorMessage, ApiError } from '../../../api/errors'
import { TaskPriorityTag } from '../../tasks/presentation'
import { useCreateTask } from '../../tasks/hooks'
import type { TeamMember } from '../../teams/types'
import { useTaskSuggestions } from '../hooks'
import type { TaskSuggestion } from '../types'

interface AITaskPlanningCardProps {
  projectId: string
  teamMembers: TeamMember[]
  initialSuggestions?: TaskSuggestion[] | null
}

function getAiTaskErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        return '登录状态失效，请重新登录'
      case 403:
        return '你没有访问该项目的权限'
      case 502:
        return 'AI服务暂时不可用，请稍后重试'
      default:
        return 'AI任务规划失败，请稍后重试'
    }
  }
  return 'AI任务规划失败，请稍后重试'
}

export function AITaskPlanningCard({
  projectId,
  teamMembers,
  initialSuggestions = null,
}: AITaskPlanningCardProps) {
  const { message } = App.useApp()
  const suggestionMutation = useTaskSuggestions(projectId)
  const createMutation = useCreateTask(projectId)
  const [modalOpen, setModalOpen] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [count, setCount] = useState(5)
  const [suggestions, setSuggestions] = useState<TaskSuggestion[]>([])
  const [selectedIndexes, setSelectedIndexes] = useState<number[]>([])

  useEffect(() => {
    if (initialSuggestions?.length && suggestions.length === 0) {
      setSuggestions(initialSuggestions)
    }
  }, [initialSuggestions, suggestions.length])

  const memberMap = useMemo(
    () => new Map(teamMembers.map((member) => [member.user_id, member])),
    [teamMembers],
  )

  const handleGenerate = async () => {
    if (!instruction.trim()) {
      message.warning('请输入任务规划需求')
      return
    }
    try {
      const result = await suggestionMutation.mutateAsync({
        instruction: instruction.trim(),
        count,
      })
      setSuggestions(result.suggestions)
      setSelectedIndexes([])
      setModalOpen(false)
    } catch (error) {
      message.error(getAiTaskErrorMessage(error))
    }
  }

  const handleCreateSelected = async () => {
    const selected = suggestions.filter((_, index) => selectedIndexes.includes(index))
    if (!selected.length) return
    try {
      for (const suggestion of selected) {
        await createMutation.mutateAsync({
          title: suggestion.title,
          description: suggestion.description || null,
          priority: suggestion.priority,
          starts_at: suggestion.starts_at || null,
          due_at: suggestion.due_at || null,
          owner_user_id: suggestion.recommended_owner_user_id || null,
        })
      }
      message.success(`已创建 ${selected.length} 个任务`)
      setSelectedIndexes([])
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  const ownerName = (suggestion: TaskSuggestion) => {
    if (!suggestion.recommended_owner_user_id) return '未指定'
    const member = memberMap.get(suggestion.recommended_owner_user_id)
    return member ? member.nickname || member.username : suggestion.recommended_owner_user_id
  }

  return (
    <Card
      className="content-card"
      title="AI 任务规划"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          AI任务规划
        </Button>
      }
    >
      {suggestions.length ? (
        <Flex vertical gap={16}>
          <List
            dataSource={suggestions}
            renderItem={(suggestion, index) => (
              <List.Item>
                <Flex vertical gap={8} style={{ width: '100%' }}>
                  <Flex align="center" gap={8} wrap>
                    <Checkbox
                      checked={selectedIndexes.includes(index)}
                      onChange={(event) => {
                        setSelectedIndexes((current) =>
                          event.target.checked
                            ? [...current, index]
                            : current.filter((item) => item !== index),
                        )
                      }}
                    />
                    <Typography.Text strong>{suggestion.title}</Typography.Text>
                    <TaskPriorityTag priority={suggestion.priority} />
                  </Flex>
                  {suggestion.description && (
                    <Typography.Text type="secondary">
                      {suggestion.description}
                    </Typography.Text>
                  )}
                  <Space size="large" wrap>
                    <Typography.Text>
                      推荐负责人：{ownerName(suggestion)}
                    </Typography.Text>
                    {suggestion.due_at && (
                      <Typography.Text>
                        截止日期：{dayjs(suggestion.due_at).format('YYYY-MM-DD HH:mm')}
                      </Typography.Text>
                    )}
                  </Space>
                  <Typography.Text type="secondary">
                    AI推荐原因：{suggestion.reason}
                  </Typography.Text>
                </Flex>
              </List.Item>
            )}
          />
          <Flex justify="flex-end">
            <Button
              type="primary"
              disabled={!selectedIndexes.length}
              loading={createMutation.isPending}
              onClick={handleCreateSelected}
            >
              创建选中任务
            </Button>
          </Flex>
        </Flex>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="点击“AI任务规划”，输入项目需求后生成任务建议。"
        />
      )}

      <Modal
        title="AI 任务规划"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleGenerate}
        confirmLoading={suggestionMutation.isPending}
        okText="生成建议"
      >
        <Flex vertical gap={16}>
          <div>
            <Typography.Text strong>规划需求</Typography.Text>
            <Input.TextArea
              rows={4}
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="例如：帮我规划一个医学影像课程项目"
            />
          </div>
          <div>
            <Typography.Text strong>建议任务数量</Typography.Text>
            <InputNumber
              min={1}
              max={10}
              value={count}
              onChange={(value) => setCount(value ?? 5)}
              style={{ width: 160 }}
            />
          </div>
        </Flex>
      </Modal>
    </Card>
  )
}
