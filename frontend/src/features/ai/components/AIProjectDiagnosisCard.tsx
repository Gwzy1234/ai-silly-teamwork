import { RobotOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Empty, Flex, List, Skeleton, Typography } from 'antd'
import { ApiError } from '../../../api/errors'
import { useAnalyzeProjectRisk } from '../hooks'
import { RiskLevelTag } from '../presentation'
import type { RiskAnalysisResponse } from '../types'

interface AIProjectDiagnosisCardProps {
  projectId: string
  initialData?: RiskAnalysisResponse | null
}

function getAiRiskErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        return '登录状态失效，请重新登录'
      case 403:
        return '你没有访问该项目的权限'
      case 502:
        return 'AI服务暂时不可用，请稍后重试'
      default:
        return 'AI分析失败，请稍后重试'
    }
  }
  return 'AI分析失败，请稍后重试'
}

function RiskResult({ data }: { data: RiskAnalysisResponse }) {
  return (
    <Flex vertical gap={16}>
      <Flex align="center" gap={8} wrap>
        <Typography.Text strong>风险等级：</Typography.Text>
        <RiskLevelTag level={data.risk_level} />
      </Flex>
      <div>
        <Typography.Text strong>风险总结</Typography.Text>
        <Typography.Paragraph style={{ marginTop: 4, marginBottom: 0 }}>
          {data.summary}
        </Typography.Paragraph>
      </div>
      <div>
        <Typography.Text strong>风险原因</Typography.Text>
        <List
          size="small"
          dataSource={data.reasons}
          renderItem={(item) => <List.Item>{item}</List.Item>}
          locale={{ emptyText: '暂无风险原因' }}
        />
      </div>
      <div>
        <Typography.Text strong>优化建议</Typography.Text>
        <List
          size="small"
          dataSource={data.suggestions}
          renderItem={(item) => <List.Item>{item}</List.Item>}
          locale={{ emptyText: '暂无优化建议' }}
        />
      </div>
    </Flex>
  )
}

export function AIProjectDiagnosisCard({
  projectId,
  initialData = null,
}: AIProjectDiagnosisCardProps) {
  const mutation = useAnalyzeProjectRisk(projectId)
  const result = mutation.data ?? initialData

  return (
    <Card
      className="content-card"
      title="AI 项目诊断"
      extra={
        <Button
          type="primary"
          icon={<RobotOutlined />}
          loading={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          开始分析
        </Button>
      }
    >
      {mutation.isPending ? (
        <Skeleton active paragraph={{ rows: 5 }} />
      ) : mutation.isError ? (
        <Alert
          showIcon
          type="error"
          message="AI 项目诊断失败"
          description={getAiRiskErrorMessage(mutation.error)}
          action={
            <Button size="small" onClick={() => mutation.mutate()}>
              重试
            </Button>
          }
        />
      ) : result ? (
        <RiskResult data={result} />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="根据项目任务、截止日期和成员负载分析项目风险。"
        />
      )}
    </Card>
  )
}
