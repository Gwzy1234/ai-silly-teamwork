import {
  DeleteOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FileZipOutlined,
  FolderOpenOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App,
  Button,
  Collapse,
  Empty,
  Flex,
  Input,
  List,
  Popconfirm,
  Skeleton,
  Space,
  Tag,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState, type ReactNode } from 'react'
import { getApiErrorMessage } from '../../../api/errors'
import { useDeleteIndexedFile, useDownloadFile, useProjectFileIndex } from '../hooks'
import type { FileIndexItem } from '../types'

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function fileIcon(file: FileIndexItem): ReactNode {
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

function ProjectFileList({ files }: { files: FileIndexItem[] }) {
  const { message } = App.useApp()
  const download = useDownloadFile()
  const deleteMutation = useDeleteIndexedFile()

  const downloadFile = async (file: FileIndexItem) => {
    try {
      await download.mutateAsync({ fileId: file.id, originalName: file.original_name })
      message.success('文件已开始下载')
    } catch (error) {
      message.error(getApiErrorMessage(error, '文件下载失败'))
    }
  }

  const deleteFile = async (file: FileIndexItem) => {
    try {
      await deleteMutation.mutateAsync(file.id)
      message.success('文件已删除')
    } catch (error) {
      message.error(getApiErrorMessage(error, '文件删除失败'))
    }
  }

  return (
    <List
      className="file-pool-list"
      dataSource={files}
      renderItem={(file) => (
        <List.Item
          className="file-pool-list-item"
          actions={[
            <Button
              key="download"
              type="text"
              className="file-pool-download"
              icon={<DownloadOutlined />}
              loading={download.isPending && download.variables?.fileId === file.id}
              onClick={() => void downloadFile(file)}
            >
              下载
            </Button>,
            ...(file.permissions.can_delete
              ? [
                  <Popconfirm
                    key="delete"
                    title="确认删除该文件？"
                    description="删除后无法恢复。"
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => deleteFile(file)}
                  >
                    <Button
                      danger
                      type="text"
                      className="file-pool-delete"
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
            avatar={<span className="file-pool-file-icon">{fileIcon(file)}</span>}
            title={
              <Typography.Text strong ellipsis={{ tooltip: file.original_name }}>
                {file.original_name}
              </Typography.Text>
            }
            description={
              <Flex vertical gap={6}>
                <Space size={[8, 4]} wrap>
                  <span>{formatFileSize(file.size_bytes)}</span>
                  <span>{file.uploader?.nickname || file.uploader?.username || '已注销用户'}</span>
                  <span>{dayjs(file.uploaded_at).format('YYYY-MM-DD HH:mm')}</span>
                </Space>
                <Space size={[6, 4]} wrap>
                  <Tag>{file.team.name}</Tag>
                  <Tag color="blue">{file.project.name}</Tag>
                  {file.task && <Tag color="purple">{file.task.title}</Tag>}
                </Space>
              </Flex>
            }
          />
        </List.Item>
      )}
    />
  )
}

export function ProjectFileIndexPanel({ projectId }: { projectId: string }) {
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    const timeout = window.setTimeout(() => setSearchQuery(searchInput.trim()), 350)
    return () => window.clearTimeout(timeout)
  }, [searchInput])

  const fileIndex = useProjectFileIndex(projectId, searchQuery)
  const totalFiles = fileIndex.data
    ? fileIndex.data.shared_files.length
      + fileIndex.data.tasks.reduce((sum, group) => sum + group.files.length, 0)
    : 0

  return (
    <Flex vertical gap={18} className="project-file-index">
      <Flex justify="space-between" align="center" gap={12} wrap>
        <Typography.Title level={5} style={{ margin: 0 }}>科目文件</Typography.Title>
        <Typography.Text type="secondary">共 {totalFiles} 个文件</Typography.Text>
      </Flex>

      <Input
        allowClear
        size="large"
        prefix={<SearchOutlined />}
        value={searchInput}
        placeholder="搜索当前科目文件"
        aria-label="搜索当前科目文件"
        onChange={(event) => setSearchInput(event.target.value)}
      />

      {fileIndex.isError ? (
        <Alert
          showIcon
          type="error"
          message="科目文件加载失败"
          description={getApiErrorMessage(fileIndex.error)}
          action={<Button onClick={() => fileIndex.refetch()}>重试</Button>}
        />
      ) : fileIndex.isPending ? (
        <Skeleton active paragraph={{ rows: 6 }} />
      ) : totalFiles === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={searchQuery ? '没有匹配的文件' : '该科目暂时没有文件'}
        />
      ) : (
        <Collapse
          className="project-file-index-sections file-pool-sections"
          items={[
            ...(fileIndex.data?.shared_files.length
              ? [{
                  key: 'shared-files',
                  label: (
                    <Space>
                      <FolderOpenOutlined />
                      <span>科目共享文件（{fileIndex.data.shared_files.length}）</span>
                    </Space>
                  ),
                  children: <ProjectFileList files={fileIndex.data.shared_files} />,
                }]
              : []),
            ...(fileIndex.data?.tasks.map((group) => ({
              key: group.task.id,
              label: `${group.task.title}（${group.files.length}）`,
              children: <ProjectFileList files={group.files} />,
            })) ?? []),
          ]}
        />
      )}
    </Flex>
  )
}
