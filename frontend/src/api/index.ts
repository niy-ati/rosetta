import { apiClient } from './client'
import type {
  ApiResponse,
  PaginatedResponse,
  DashboardStats,
  Artifact,
  Workflow,
  TestResult,
  TestSummary,
  DiscrepancyReport,
  Certificate,
  ComplianceReport,
  SystemHealth,
  ErrorNotification,
} from '../types'

// Dashboard API
export const getDashboardStats = () =>
  apiClient.get<ApiResponse<DashboardStats>>('/dashboard/stats')

// Artifacts API
export const getArtifacts = (page = 1, pageSize = 50, status?: string) =>
  apiClient.get<ApiResponse<PaginatedResponse<Artifact>>>('/artifacts', {
    params: { page, pageSize, status },
  })

export const getArtifact = (id: string) =>
  apiClient.get<ApiResponse<Artifact>>(`/artifacts/${id}`)

export const uploadArtifact = (file: File, onProgress?: (progress: number) => void) =>
  apiClient.upload<ApiResponse<{ artifactId: string; workflowId: string }>>(
    '/artifacts/upload',
    file,
    onProgress
  )

export const downloadArtifact = (id: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/artifacts/${id}/download`)

// Workflows API
export const getWorkflows = (page = 1, pageSize = 50, status?: string) =>
  apiClient.get<ApiResponse<PaginatedResponse<Workflow>>>('/workflows', {
    params: { page, pageSize, status },
  })

export const getWorkflow = (id: string) =>
  apiClient.get<ApiResponse<Workflow>>(`/workflows/${id}`)

export const searchWorkflows = (query: string) =>
  apiClient.get<ApiResponse<Workflow[]>>('/workflows/search', {
    params: { q: query },
  })

// Test Results API
export const getTestResults = (workflowId: string, page = 1, pageSize = 100, status?: string) =>
  apiClient.get<ApiResponse<PaginatedResponse<TestResult>>>(`/workflows/${workflowId}/tests`, {
    params: { page, pageSize, status },
  })

export const getTestSummary = (workflowId: string) =>
  apiClient.get<ApiResponse<TestSummary>>(`/workflows/${workflowId}/tests/summary`)

export const getDiscrepancyReport = (testId: string) =>
  apiClient.get<ApiResponse<DiscrepancyReport>>(`/tests/${testId}/discrepancy`)

export const downloadTestResults = (workflowId: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/workflows/${workflowId}/tests/download`)

// Certificates API
export const getCertificates = (page = 1, pageSize = 50) =>
  apiClient.get<ApiResponse<PaginatedResponse<Certificate>>>('/certificates', {
    params: { page, pageSize },
  })

export const getCertificate = (id: string) =>
  apiClient.get<ApiResponse<Certificate>>(`/certificates/${id}`)

export const verifyCertificateSignature = (id: string) =>
  apiClient.post<ApiResponse<{ valid: boolean; keyId: string }>>(`/certificates/${id}/verify`)

export const downloadCertificate = (id: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/certificates/${id}/download`)

// Compliance API
export const getComplianceReports = (page = 1, pageSize = 50) =>
  apiClient.get<ApiResponse<PaginatedResponse<ComplianceReport>>>('/compliance/reports', {
    params: { page, pageSize },
  })

export const generateComplianceReport = (workflowId: string) =>
  apiClient.post<ApiResponse<{ reportId: string }>>('/compliance/reports', { workflowId })

export const getComplianceReport = (id: string) =>
  apiClient.get<ApiResponse<ComplianceReport>>(`/compliance/reports/${id}`)

export const downloadComplianceReport = (id: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/compliance/reports/${id}/download`)

// System Health API
export const getSystemHealth = () =>
  apiClient.get<ApiResponse<SystemHealth>>('/system/health')

export const getErrorNotifications = (dismissed = false) =>
  apiClient.get<ApiResponse<ErrorNotification[]>>('/system/notifications', {
    params: { dismissed },
  })

export const dismissNotification = (id: string) =>
  apiClient.post<ApiResponse<void>>(`/system/notifications/${id}/dismiss`)

// Logs API
export const getCloudWatchLogs = (
  logGroup: string,
  startTime?: string,
  endTime?: string,
  filterPattern?: string
) =>
  apiClient.get<ApiResponse<any>>('/logs', {
    params: { logGroup, startTime, endTime, filterPattern },
  })

// Downloads API
export const downloadLogicMap = (workflowId: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/workflows/${workflowId}/logic-map/download`)

export const downloadModernImplementation = (workflowId: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/workflows/${workflowId}/modern-impl/download`)

export const downloadEarsRequirements = (workflowId: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/workflows/${workflowId}/ears/download`)

export const downloadCdkInfrastructure = (workflowId: string) =>
  apiClient.get<ApiResponse<{ presignedUrl: string }>>(`/workflows/${workflowId}/cdk/download`)
