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
  Card,
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
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { getApiErrorMessage } from '../api/errors'
import {
  useDeleteIndexedFile,
  useDownloadFile,
  useFileIndex,
} from '../features/files/hooks'
import type { FileIndexItem } from '../features/files/types'

interface TaskFileGroup {
  id: string
  title: string
  files: FileIndexItem[]
}

interface ProjectFileGroup {
  id: string
  name: string
  teamName: string
  sharedFiles: FileIndexItem[]
  tasks: TaskFileGroup[]
}

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

function groupFiles(files: FileIndexItem[]): ProjectFileGroup[] {
  const projects = new Map<
    string,
    ProjectFileGroup & { taskMap: Map<string, TaskFileGroup> }
  >()

  for (const file of files) {
    let project = projects.get(file.project.id)
    if (!project) {
      project = {
        id: file.project.id,
        name: file.project.name,
        teamName: file.team.name,
        sharedFiles: [],
        tasks: [],
        taskMap: new Map(),
      }
      projects.set(file.project.id, project)
    }
    if (!file.task) {
      project.sharedFiles.push(file)
      continue
    }
    let task = project.taskMap.get(file.task.id)
    if (!task) {
      task = { id: file.task.id, title: file.task.title, files: [] }
      project.taskMap.set(file.task.id, task)
      project.tasks.push(task)
    }
    task.files.push(file)
  }

  return Array.from(projects.values(), ({ taskMap: _, ...project }) => project)
}

function FileList({ files }: { files: FileIndexItem[] }) {
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
            title={<Typography.Text strong ellipsis={{ tooltip: file.original_name }}>{file.original_name}</Typography.Text>}
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

export function FilePoolPage() {
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    const timeout = window.setTimeout(() => setSearchQuery(searchInput.trim()), 350)
    return () => window.clearTimeout(timeout)
  }, [searchInput])

  const fileIndex = useFileIndex(searchQuery)
  const projects = useMemo(() => groupFiles(fileIndex.data ?? []), [fileIndex.data])

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="end" gap={16} wrap>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>文件池</Typography.Title>
          <Typography.Text type="secondary">集中查看你有权访问的科目文件和任务附件</Typography.Text>
        </div>
        <Typography.Text type="secondary">共 {fileIndex.data?.length ?? 0} 个文件</Typography.Text>
      </Flex>

      <Card className="content-card file-pool-search-card">
        <Input
          allowClear
          size="large"
          prefix={<SearchOutlined />}
          value={searchInput}
          placeholder="搜索文件名"
          aria-label="搜索文件名"
          onChange={(event) => setSearchInput(event.target.value)}
        />
      </Card>

      {fileIndex.isError ? (
        <Alert
          showIcon
          type="error"
          message="文件池加载失败"
          description={getApiErrorMessage(fileIndex.error)}
          action={<Button onClick={() => fileIndex.refetch()}>重试</Button>}
        />
      ) : fileIndex.isPending ? (
        <Card className="content-card"><Skeleton active paragraph={{ rows: 8 }} /></Card>
      ) : projects.length === 0 ? (
        <Card className="content-card">
          <Empty description={searchQuery ? '没有匹配的文件' : '暂时没有可访问的文件'} />
        </Card>
      ) : (
        <Collapse
          className="file-pool-projects"
          items={projects.map((project) => ({
            key: project.id,
            label: (
              <Flex align="center" justify="space-between" gap={12} className="file-pool-project-label">
                <Space size={10}>
                  <FolderOpenOutlined className="file-pool-project-icon" />
                  <Typography.Text strong>{project.name}</Typography.Text>
                </Space>
                <Space size={8}>
                  <Tag>{project.teamName}</Tag>
                  <Typography.Text type="secondary">
                    {project.sharedFiles.length + project.tasks.reduce((sum, task) => sum + task.files.length, 0)} 个
                  </Typography.Text>
                </Space>
              </Flex>
            ),
            children: (
              <Collapse
                className="file-pool-sections"
                ghost
                items={[
                  ...(project.sharedFiles.length
                    ? [{
                        key: `${project.id}-shared`,
                        label: `科目共享文件（${project.sharedFiles.length}）`,
                        children: <FileList files={project.sharedFiles} />,
                      }]
                    : []),
                  ...project.tasks.map((task) => ({
                    key: task.id,
                    label: `${task.title}（${task.files.length}）`,
                    children: <FileList files={task.files} />,
                  })),
                ]}
              />
            ),
          }))}
        />
      )}
    </Flex>
  )
}
