import { JobResponse } from '../api/client'

const TARGET_LABELS: Record<string, string> = {
  ingest: '生成产物',
  fetch: '拉取论文',
  fetch_and_ingest: '拉取并生成',
  recommend_refresh: '刷新推荐',
  render_blog_html: '生成 HTML',
  markdown_publish: '公众号上传',
  wechat_prepare: '公众号预览',
  wechat_publish: '公众号发布'
}

export function jobTargetLabel(target: string): string {
  return TARGET_LABELS[target] ?? target
}

export function jobStatusLabel(status: JobResponse['status']): string {
  switch (status) {
    case 'pending':
      return '排队中'
    case 'running':
      return '进行中'
    case 'succeeded':
      return '已完成'
    case 'failed':
      return '失败'
    default:
      return status
  }
}

export function isActiveJob(job: JobResponse): boolean {
  return job.status === 'pending' || job.status === 'running'
}

export function summarizeActiveJobs(jobs: JobResponse[]): string {
  if (jobs.length === 0) return ''
  const first = jobs[0]
  const head = `${jobTargetLabel(first.target)} · ${first.slug}`
  if (jobs.length === 1) return head
  return `${head} 等 ${jobs.length} 个任务`
}
