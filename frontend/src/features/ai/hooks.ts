import { useMutation } from '@tanstack/react-query'
import { analyzeProjectRisk } from './api'

export function useAnalyzeProjectRisk(projectId: string) {
  return useMutation({
    mutationFn: () => analyzeProjectRisk(projectId),
  })
}
