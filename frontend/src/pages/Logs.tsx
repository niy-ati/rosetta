import { useState, useEffect } from 'react'
import { Terminal, Search, Filter, AlertCircle, Info, CheckCircle, XCircle } from 'lucide-react'

interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success'
  service: string
  message: string
}

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [filter, setFilter] = useState<string>('')
  const [levelFilter, setLevelFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    // Generate mock logs
    const mockLogs: LogEntry[] = [
      { id: '1', timestamp: new Date().toISOString(), level: 'success', service: 'BedrockArchitect', message: 'CDK synthesis completed successfully for artifact-3' },
      { id: '2', timestamp: new Date(Date.now() - 60000).toISOString(), level: 'info', service: 'StepFunctions', message: 'Workflow workflow-5 entered Validation phase' },
      { id: '3', timestamp: new Date(Date.now() - 120000).toISOString(), level: 'info', service: 'TestOrchestrator', message: 'Started test execution for 150,000 test vectors' },
      { id: '4', timestamp: new Date(Date.now() - 180000).toISOString(), level: 'warning', service: 'PIIDetector', message: 'PII detected and redacted in artifact-2: 3 instances' },
      { id: '5', timestamp: new Date(Date.now() - 240000).toISOString(), level: 'success', service: 'CertificateGenerator', message: 'Certificate cert-3 generated with 500,000 passing tests' },
      { id: '6', timestamp: new Date(Date.now() - 300000).toISOString(), level: 'info', service: 'BedrockArchitect', message: 'Discovery phase completed for artifact-4' },
      { id: '7', timestamp: new Date(Date.now() - 360000).toISOString(), level: 'error', service: 'TestOrchestrator', message: 'Test execution failed: timeout after 3600s' },
      { id: '8', timestamp: new Date(Date.now() - 420000).toISOString(), level: 'info', service: 'S3Handler', message: 'Artifact artifact-5 uploaded successfully (45.2 KB)' },
      { id: '9', timestamp: new Date(Date.now() - 480000).toISOString(), level: 'success', service: 'StepFunctions', message: 'Workflow workflow-3 completed successfully' },
      { id: '10', timestamp: new Date(Date.now() - 540000).toISOString(), level: 'info', service: 'DynamoDB', message: 'Test results batch written: 10,000 records' },
      { id: '11', timestamp: new Date(Date.now() - 600000).toISOString(), level: 'warning', service: 'BedrockArchitect', message: 'Bedrock API throttling detected, retrying...' },
      { id: '12', timestamp: new Date(Date.now() - 660000).toISOString(), level: 'info', service: 'KMS', message: 'Certificate signing key rotated successfully' },
    ]
    setLogs(mockLogs)
  }, [])

  const filteredLogs = logs.filter(log => {
    const matchesSearch = log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         log.service.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesLevel = !levelFilter || log.level === levelFilter
    return matchesSearch && matchesLevel
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center">
          <Terminal className="h-8 w-8 text-green-600 mr-3" />
          System Logs
        </h1>
        <div className="flex items-center space-x-2">
          <span className="px-3 py-1 bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400 rounded-full text-sm font-semibold">
            Live
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search logs..."
                className="input pl-10"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
          <div className="sm:w-48">
            <select
              className="input"
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
            >
              <option value="">All Levels</option>
              <option value="info">Info</option>
              <option value="success">Success</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>
      </div>

      {/* Log Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="card bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-2 border-blue-200 dark:border-blue-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-300">Info</p>
              <p className="text-2xl font-bold text-blue-900 dark:text-blue-100 mt-1">
                {logs.filter(l => l.level === 'info').length}
              </p>
            </div>
            <Info className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-2 border-green-200 dark:border-green-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-800 dark:text-green-300">Success</p>
              <p className="text-2xl font-bold text-green-900 dark:text-green-100 mt-1">
                {logs.filter(l => l.level === 'success').length}
              </p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-yellow-50 to-yellow-100 dark:from-yellow-900/20 dark:to-yellow-800/20 border-2 border-yellow-200 dark:border-yellow-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-300">Warning</p>
              <p className="text-2xl font-bold text-yellow-900 dark:text-yellow-100 mt-1">
                {logs.filter(l => l.level === 'warning').length}
              </p>
            </div>
            <AlertCircle className="h-8 w-8 text-yellow-600 dark:text-yellow-400" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-red-50 to-red-100 dark:from-red-900/20 dark:to-red-800/20 border-2 border-red-200 dark:border-red-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-red-800 dark:text-red-300">Error</p>
              <p className="text-2xl font-bold text-red-900 dark:text-red-100 mt-1">
                {logs.filter(l => l.level === 'error').length}
              </p>
            </div>
            <XCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
          </div>
        </div>
      </div>

      {/* Logs Display */}
      <div className="card bg-gray-900 dark:bg-black p-4 font-mono text-sm">
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {filteredLogs.map((log) => (
            <div key={log.id} className="flex items-start space-x-3 py-2 border-b border-gray-800 last:border-0">
              <LogLevelIcon level={log.level} />
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-1">
                  <span className="text-gray-400 text-xs">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getServiceColor(log.service)}`}>
                    {log.service}
                  </span>
                </div>
                <p className={getLogColor(log.level)}>{log.message}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function LogLevelIcon({ level }: { level: string }) {
  const icons = {
    info: <Info className="h-5 w-5 text-blue-400" />,
    success: <CheckCircle className="h-5 w-5 text-green-400" />,
    warning: <AlertCircle className="h-5 w-5 text-yellow-400" />,
    error: <XCircle className="h-5 w-5 text-red-400" />,
  }
  return icons[level as keyof typeof icons] || icons.info
}

function getLogColor(level: string) {
  const colors = {
    info: 'text-blue-300',
    success: 'text-green-300',
    warning: 'text-yellow-300',
    error: 'text-red-300',
  }
  return colors[level as keyof typeof colors] || colors.info
}

function getServiceColor(service: string) {
  const colors: Record<string, string> = {
    BedrockArchitect: 'bg-purple-900/50 text-purple-300',
    StepFunctions: 'bg-blue-900/50 text-blue-300',
    TestOrchestrator: 'bg-green-900/50 text-green-300',
    PIIDetector: 'bg-yellow-900/50 text-yellow-300',
    CertificateGenerator: 'bg-pink-900/50 text-pink-300',
    S3Handler: 'bg-orange-900/50 text-orange-300',
    DynamoDB: 'bg-indigo-900/50 text-indigo-300',
    KMS: 'bg-red-900/50 text-red-300',
  }
  return colors[service] || 'bg-gray-800 text-gray-300'
}
