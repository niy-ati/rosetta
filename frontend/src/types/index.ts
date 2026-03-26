// Workflow and Phase Types
export type WorkflowPhase = 'Discovery' | 'Synthesis' | 'Aggression' | 'Validation' | 'Trust'
export type PhaseStatus = 'pending' | 'in-progress' | 'completed' | 'failed'
export type WorkflowStatus = 'processing' | 'completed' | 'failed'

export interface Workflow {
  workflowId: string
  artifactId: string
  artifactName: string
  status: WorkflowStatus
  currentPhase: WorkflowPhase
  phases: PhaseInfo[]
  createdAt: string
  updatedAt: string
  completedAt?: string
}

export interface PhaseInfo {
  name: WorkflowPhase
  status: PhaseStatus
  startedAt?: string
  completedAt?: string
  progress?: number
  error?: string
}

// Artifact Types
export type ArtifactType = 'COBOL' | 'FORTRAN' | 'BINARY'

export interface Artifact {
  artifactId: string
  name: string
  type: ArtifactType
  size: number
  uploadedAt: string
  uploadedBy: string
  workflowId?: string
  status: WorkflowStatus
  s3Key: string
  hash: string
}

// Test Result Types
export type TestStatus = 'pass' | 'fail'

export interface TestResult {
  testId: string
  workflowId: string
  vectorId: string
  status: TestStatus
  executionTimestamp: string
  legacyOutputHash: string
  modernOutputHash: string
  discrepancyReportKey?: string
}

export interface TestSummary {
  totalTests: number
  passedTests: number
  failedTests: number
  passRate: number
  executionTime: number
}

// Discrepancy Report Types
export interface DiscrepancyReport {
  reportId: string
  testId: string
  workflowId: string
  testVector: any
  legacyResult: ExecutionResult
  modernResult: ExecutionResult
  differences: DifferenceDetails
  generatedAt: string
}

export interface ExecutionResult {
  returnValue: string
  stdout: string
  stderr: string
  sideEffects: SideEffect[]
  executionDuration: number
}

export interface DifferenceDetails {
  returnValueDiff?: string
  stdoutDiff?: string
  stderrDiff?: string
  sideEffectDiffs?: string[]
}

export interface SideEffect {
  type: string
  operation: string
  data: string
}

// Certificate Types
export interface Certificate {
  certificateId: string
  workflowId: string
  artifactId: string
  testCount: number
  testResultsHash: string
  coveragePercentage: number
  generatedAt: string
  signature: string
  signingKeyId: string
  signingAlgorithm: string
  legacyArtifactMetadata: ArtifactMetadata
  modernImplementationMetadata: ArtifactMetadata
}

export interface ArtifactMetadata {
  identifier: string
  version: string
  hash: string
  s3Location: string
}

// Compliance Report Types
export interface ComplianceReport {
  reportId: string
  workflowId: string
  generatedAt: string
  testResults: TestResult[]
  certificate: Certificate
  auditLogs: AuditLog[]
  discrepancyReports: DiscrepancyReport[]
  status: 'generating' | 'completed' | 'failed'
}

export interface AuditLog {
  timestamp: string
  component: string
  action: string
  details: string
}

// System Health Types
export interface SystemHealth {
  lambdaMetrics: LambdaMetrics
  stepFunctionsMetrics: StepFunctionsMetrics
  s3Metrics: S3Metrics
  dynamoDBMetrics: DynamoDBMetrics
  timestamp: string
}

export interface LambdaMetrics {
  errorRate: number
  invocations: number
  duration: number
  throttles: number
}

export interface StepFunctionsMetrics {
  executionsStarted: number
  executionsSucceeded: number
  executionsFailed: number
  executionsTimedOut: number
}

export interface S3Metrics {
  totalBuckets: number
  totalObjects: number
  totalSize: number
  bucketUtilization: BucketUtilization[]
}

export interface BucketUtilization {
  bucketName: string
  objectCount: number
  sizeBytes: number
}

export interface DynamoDBMetrics {
  readCapacityUtilization: number
  writeCapacityUtilization: number
  itemCount: number
}

// Error Notification Types
export interface ErrorNotification {
  notificationId: string
  timestamp: string
  component: string
  errorMessage: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  workflowId?: string
  dismissed: boolean
}

// Dashboard Stats Types
export interface DashboardStats {
  totalArtifacts: number
  totalTests: number
  totalCertificates: number
  activeWorkflows: number
  recentCertificates: Certificate[]
  systemHealth: SystemHealth
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// Upload Types
export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}
