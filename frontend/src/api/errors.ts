interface ErrorBody {
  detail?: string | Array<{ msg?: string }>
}

export class ApiError extends Error {
  readonly status: number
  readonly body?: unknown

  constructor(
    message: string,
    status: number,
    body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export function getApiErrorMessage(error: unknown, fallback = '请求失败，请稍后重试') {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return fallback
}

export function createApiError(response: Response, body: unknown) {
  const errorBody = body as ErrorBody | undefined
  const detail = errorBody?.detail
  let message: string
  if (typeof detail === 'string') {
    message = detail
  } else if (Array.isArray(detail)) {
    message = detail.map((item) => item.msg).filter(Boolean).join('；')
  } else {
    message =
      {
        400: '请求内容无效，请检查后重试',
        401: '用户名或密码错误，或登录状态已失效',
        403: '没有执行此操作的权限',
        404: '请求的资源不存在',
        409: '该用户名或邮箱已被使用',
        422: '表单内容未通过验证',
      }[response.status] || response.statusText || '请求失败'
  }
  return new ApiError(message, response.status, body)
}
