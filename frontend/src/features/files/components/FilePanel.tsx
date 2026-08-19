import {
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FileZipOutlined,
  InboxOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App,
  Button,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Space,
  Typography,
  Upload,
} from 'antd'
import type { UploadProps } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { getApiErrorMessage } from '../../../api/errors'
import { useCurrentUser } from '../../auth/hooks'
import {
  useCollaborationFiles,
  useDeleteFile,
  useDownloadFile,
  useUpdateFileMetadata,
  useUploadFile,
} from '../hooks'
import type { CollaborationFile, FileScope } from '../types'

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function fileIcon(file: CollaborationFile): ReactNode {
  const contentType = file.content_type.toLowerCase()
  const extension = file.original_name.split('.').pop()?.toLowerCase()

  if (contentType.includes('pdf') || extension === 'pdf') return <FilePdfOutlined />
  if (contentType.startsWith('image/')) return <FileImageOutlined />
  if (contentType.includes('word') || ['doc', 'docx'].includes(extension || '')) {
    return <FileWordOutlined />
  }
  if (contentType.includes('sheet') || ['xls', 'xlsx', 'csv'].includes(extension || '')) {
    return <FileExcelOutlined />
  }
  if (contentType.includes('presentation') || ['ppt', 'pptx'].includes(extension || '')) {
    return <FilePptOutlined />
  }
  if (contentType.includes('zip') || ['zip', 'rar', '7z', 'tar', 'gz'].includes(extension || '')) {
    return <FileZipOutlined />
  }
  if (contentType.startsWith('text/')) return <FileTextOutlined />
  return <FileOutlined />
}

interface FilePanelProps {
  scope: Extract<FileScope, 'task'>
  ownerId: string
  title?: string
}

export function FilePanel({ scope, ownerId, title = '文件' }: FilePanelProps) {
  const { message } = App.useApp()
  const currentUser = useCurrentUser()
  const files = useCollaborationFiles(scope, ownerId)
  const uploadMutation = useUploadFile(scope, ownerId)
  const updateMutation = useUpdateFileMetadata(scope, ownerId)
  const deleteMutation = useDeleteFile(scope, ownerId)
  const downloadMutation = useDownloadFile()
  const [editingFile, setEditingFile] = useState<CollaborationFile | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [renameForm] = Form.useForm<{ original_name: string }>()

  useEffect(() => {
    const timeout = window.setTimeout(() => setSearchQuery(searchInput.trim().toLowerCase()), 350)
    return () => window.clearTimeout(timeout)
  }, [searchInput])

  const visibleFiles = useMemo(() => {
    const sortedFiles = [...(files.data ?? [])].sort(
      (left, right) => dayjs(right.created_at).valueOf() - dayjs(left.created_at).valueOf(),
    )
    if (!searchQuery) return sortedFiles
    return sortedFiles.filter((file) => file.original_name.toLowerCase().includes(searchQuery))
  }, [files.data, searchQuery])

  const uploaderName = (file: CollaborationFile) => {
    if (!file.uploaded_by_id) return '已注销用户'
    if (file.uploaded_by_id === currentUser.data?.id) {
      return currentUser.data.nickname || currentUser.data.username
    }
    return `用户 ${file.uploaded_by_id.slice(0, 8)}`
  }

  const runAction = async (action: () => Promise<unknown>, success: string) => {
    try {
      await action()
      message.success(success)
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  const upload: UploadProps['customRequest'] = async ({ file, onSuccess, onError }) => {
    if (!(file instanceof File)) return
    try {
      const result = await uploadMutation.mutateAsync(file)
      onSuccess?.(result)
      message.success(`${file.name} 上传成功`)
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('文件上传失败'))
      message.error(getApiErrorMessage(error, '文件上传失败'))
    }
  }

  const openRename = (file: CollaborationFile) => {
    setEditingFile(file)
    renameForm.setFieldValue('original_name', file.original_name)
  }

  const submitRename = async () => {
    if (!editingFile) return
    try {
      const values = await renameForm.validateFields()
      await updateMutation.mutateAsync({
        fileId: editingFile.id,
        originalName: values.original_name.trim(),
      })
      message.success('文件名已更新')
      setEditingFile(null)
      renameForm.resetFields()
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Flex vertical gap={18}>
      <Upload.Dragger
        multiple
        showUploadList={false}
        customRequest={upload}
        disabled={uploadMutation.isPending}
      >
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
        <p className="ant-upload-hint">文件访问和操作权限由后端统一校验</p>
      </Upload.Dragger>

      <Flex justify="space-between" align="center" gap={12} wrap>
        <Typography.Title level={5} style={{ margin: 0 }}>{title}</Typography.Title>
        <Typography.Text type="secondary">
          {searchQuery ? `找到 ${visibleFiles.length} 个，共 ${files.data?.length ?? 0} 个` : `共 ${files.data?.length ?? 0} 个`}
        </Typography.Text>
      </Flex>

      <Input
        allowClear
        size="large"
        className="task-file-search"
        prefix={<SearchOutlined />}
        value={searchInput}
        placeholder="搜索当前任务附件"
        aria-label="搜索当前任务附件"
        onChange={(event) => setSearchInput(event.target.value)}
      />

      {files.isError ? (
        <Alert
          showIcon
          type="error"
          message="文件列表加载失败"
          action={<Button onClick={() => files.refetch()}>重试</Button>}
        />
      ) : visibleFiles.length ? (
        <List
          className="task-file-list"
          loading={files.isPending}
          dataSource={visibleFiles}
          renderItem={(file) => (
            <List.Item
              className="task-file-list-item"
              actions={[
                <Button
                  key="download"
                  type="link"
                  icon={<DownloadOutlined />}
                  loading={downloadMutation.isPending && downloadMutation.variables?.fileId === file.id}
                  onClick={() => void runAction(
                    () => downloadMutation.mutateAsync({ fileId: file.id, originalName: file.original_name }),
                    '文件已开始下载',
                  )}
                >
                  下载
                </Button>,
                ...(file.permissions.can_modify
                  ? [
                      <Button
                        key="rename"
                        type="link"
                        icon={<EditOutlined />}
                        onClick={() => openRename(file)}
                      >
                        重命名
                      </Button>,
                    ]
                  : []),
                ...(file.permissions.can_delete
                  ? [
                      <Popconfirm
                        key="delete"
                        title="确认删除该文件？"
                        description="删除后无法恢复。"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => runAction(
                          () => deleteMutation.mutateAsync(file.id),
                          '文件已删除',
                        )}
                      >
                        <Button
                          danger
                          type="link"
                          icon={<DeleteOutlined />}
                          loading={deleteMutation.isPending && deleteMutation.variables === file.id}
                        >
                          删除
                        </Button>
                      </Popconfirm>,
                    ]
                  : []),
              ]}
            >
              <List.Item.Meta
                avatar={<span className="task-file-icon">{fileIcon(file)}</span>}
                title={
                  <Typography.Text strong ellipsis={{ tooltip: file.original_name }}>
                    {file.original_name}
                  </Typography.Text>
                }
                description={
                  <Space className="task-file-meta" size={[12, 4]} wrap>
                    <span>{formatFileSize(file.size_bytes)}</span>
                    <span>上传者：{uploaderName(file)}</span>
                    <span>{dayjs(file.created_at).format('YYYY-MM-DD HH:mm')}</span>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      ) : files.isPending ? null : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={searchQuery ? '没有匹配的任务附件' : '暂未上传文件'}
        />
      )}

      <Modal
        title="修改文件名"
        open={Boolean(editingFile)}
        onCancel={() => setEditingFile(null)}
        onOk={submitRename}
        confirmLoading={updateMutation.isPending}
        okText="保存"
      >
        <Form form={renameForm} layout="vertical">
          <Form.Item
            name="original_name"
            label="文件名"
            rules={[
              { required: true, whitespace: true, message: '请输入文件名' },
              { max: 255, message: '文件名不能超过 255 个字符' },
            ]}
          >
            <Input maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </Flex>
  )
}
