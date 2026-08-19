import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type { RiskAnalysisResponse } from './types'

export async function analyzeProjectRisk(projectId: string): Promise<RiskAnalysisResponse> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/ai/risk-analysis',
    { params: { path: { project_id: projectId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}
