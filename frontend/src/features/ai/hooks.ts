import { useMutation, useQuery } from '@tanstack/react-query'
import { analyzeProjectRisk, generateWeeklyReport, getAIHistory, suggestTasks } from './api'
import type { TaskSuggestionRequest } from './types'

export const aiHistoryQueryKeys = {
  project: (projectId: string) => ['projects', projectId, 'ai-history'] as const,
}

export function useAnalyzeProjectRisk(projectId: string) {
  return useMutation({
    mutationFn: () => analyzeProjectRisk(projectId),
  })
}

export function useTaskSuggestions(projectId: string) {
  return useMutation({
    mutationFn: (payload: TaskSuggestionRequest) => suggestTasks(projectId, payload),
  })
}

export function useWeeklyReport(projectId: string) {
  return useMutation({
    mutationFn: () => generateWeeklyReport(projectId),
  })
}

export function useAIHistory(projectId: string) {
  return useQuery({
    queryKey: aiHistoryQueryKeys.project(projectId),
    queryFn: () => getAIHistory(projectId),
    enabled: Boolean(projectId),
  })
}
