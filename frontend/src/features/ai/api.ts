import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  AIHistoryResponse,
  RiskAnalysisResponse,
  TaskSuggestionRequest,
  TaskSuggestionResponse,
  WeeklyReportRequest,
  WeeklyReportResponse,
} from './types'

export async function analyzeProjectRisk(projectId: string): Promise<RiskAnalysisResponse> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/ai/risk-analysis',
    { params: { path: { project_id: projectId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function suggestTasks(
  projectId: string,
  payload: TaskSuggestionRequest,
): Promise<TaskSuggestionResponse> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/ai/task-suggestions',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function generateWeeklyReport(
  projectId: string,
  payload: WeeklyReportRequest = {},
): Promise<WeeklyReportResponse> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/ai/weekly-report',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function getAIHistory(projectId: string): Promise<AIHistoryResponse> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/projects/{project_id}/ai/history',
    { params: { path: { project_id: projectId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}
