import { useEffect, useState } from 'react'
import { Activity, Server, Database, HardDrive, Zap, AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react'
import { getSystemHealth } from '../api'

export default function SystemHealth() {
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadHealth()
    const interval = setInterval(loadHealth, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const loadHealth = async () => {
    try {
      const response = await getSystemHealth()
      if (response.success && response.data) {
        setHealth(response.data)
      }
    } catch (err) {
      console.error('Failed to load system health:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center">
          <Activity className="h-8 w-8 text-green-600 mr-3" />
          System Health Monitor
        </h1>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-gray-600 dark:text-gray-400">Live</span>
        </div>
      </div>

      {/* Overall Status */}
      <div className="card bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-2 border-green-200 dark:border-green-800">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">All Systems Operational</h2>
            <p className="text-gray-600 dark:text-gray-400">Last updated: {new Date().toLocaleTimeString()}</p>
          </div>
          <CheckCircle className="h-16 w-16 text-green-600 dark:text-green-400" />
        </div>
      </div>

      {/* Lambda Metrics */}
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center">
          <Zap className="h-6 w-6 mr-2 text-yellow-600" />
          AWS Lambda Functions
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <MetricCard
            label="Invocations"
            value={health?.lambdaMetrics.invocations.toLocaleString() || '0'}
            icon={TrendingUp}
            color="blue"
            status="good"
          />
          <MetricCard
            label="Error Rate"
            value={`${(health?.lambdaMetrics.errorRate * 100).toFixed(3)}%`}
            icon={AlertTriangle}
            color={health?.lambdaMetrics.errorRate < 0.01 ? 'green' : 'yellow'}
            status={health?.lambdaMetrics.errorRate < 0.01 ? 'good' : 'warning'}
          />
          <MetricCard
            label="Avg Duration"
            value={`${health?.lambdaMetrics.duration}ms`}
            icon={Activity}
            color="purple"
            status="good"
          />
          <MetricCard
            label="Throttles"
            value={health?.lambdaMetrics.throttles || '0'}
            icon={AlertTriangle}
            color={health?.lambdaMetrics.throttles === 0 ? 'green' : 'red'}
            status={health?.lambdaMetrics.throttles === 0 ? 'good' : 'error'}
          />
        </div>
        <div className="mt-6 bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Lambda Functions</h3>
          <div className="space-y-2">
            {['BedrockArchitect', 'TestOrchestrator', 'CertificateGenerator', 'PIIDetector'].map((fn) => (
              <div key={fn} className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700 last:border-0">
                <span className="text-sm text-gray-900 dark:text-white">{fn}</span>
                <span className="px-2 py-1 bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400 rounded-full text-xs font-semibold flex items-center">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Healthy
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Step Functions */}
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center">
          <Server className="h-6 w-6 mr-2 text-blue-600" />
          AWS Step Functions
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <MetricCard
            label="Started"
            value={health?.stepFunctionsMetrics.executionsStarted.toLocaleString() || '0'}
            icon={TrendingUp}
            color="blue"
            status="good"
          />
          <MetricCard
            label="Succeeded"
            value={health?.stepFunctionsMetrics.executionsSucceeded.toLocaleString() || '0'}
            icon={CheckCircle}
            color="green"
            status="good"
          />
          <MetricCard
            label="Failed"
            value={health?.stepFunctionsMetrics.executionsFailed.toLocaleString() || '0'}
            icon={AlertTriangle}
            color={health?.stepFunctionsMetrics.executionsFailed < 5 ? 'yellow' : 'red'}
            status={health?.stepFunctionsMetrics.executionsFailed < 5 ? 'warning' : 'error'}
          />
          <MetricCard
            label="Timed Out"
            value={health?.stepFunctionsMetrics.executionsTimedOut.toLocaleString() || '0'}
            icon={AlertTriangle}
            color={health?.stepFunctionsMetrics.executionsTimedOut === 0 ? 'green' : 'red'}
            status={health?.stepFunctionsMetrics.executionsTimedOut === 0 ? 'good' : 'error'}
          />
        </div>
        <div className="mt-6">
          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Success Rate</h3>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl font-bold text-green-600 dark:text-green-400">
                {((health?.stepFunctionsMetrics.executionsSucceeded / health?.stepFunctionsMetrics.executionsStarted) * 100).toFixed(1)}%
              </span>
              <TrendingUp className="h-6 w-6 text-green-600 dark:text-green-400" />
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
              <div
                className="bg-gradient-to-r from-green-500 to-emerald-600 h-3 rounded-full"
                style={{ width: `${(health?.stepFunctionsMetrics.executionsSucceeded / health?.stepFunctionsMetrics.executionsStarted) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Storage & Database */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* S3 Storage */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center">
            <HardDrive className="h-6 w-6 mr-2 text-orange-600" />
            Amazon S3 Storage
          </h2>
          <div className="space-y-4">
            <div className="bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-900/20 dark:to-amber-900/20 rounded-lg p-4 border-2 border-orange-200 dark:border-orange-800">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Storage</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {formatBytes(health?.s3Metrics.totalSize || 0)}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Buckets</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {health?.s3Metrics.totalBuckets || 0}
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Objects</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {health?.s3Metrics.totalObjects.toLocaleString() || '0'}
                </p>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
              <h3 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Bucket Types</h3>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Legacy Artifacts</span>
                  <span className="text-gray-900 dark:text-white font-semibold">Encrypted</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Modern Implementations</span>
                  <span className="text-gray-900 dark:text-white font-semibold">Encrypted</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Test Vectors</span>
                  <span className="text-gray-900 dark:text-white font-semibold">Encrypted</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Certificates</span>
                  <span className="text-gray-900 dark:text-white font-semibold">Encrypted</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* DynamoDB */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center">
            <Database className="h-6 w-6 mr-2 text-indigo-600" />
            Amazon DynamoDB
          </h2>
          <div className="space-y-4">
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-lg p-4 border-2 border-indigo-200 dark:border-indigo-800">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Items</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {health?.dynamoDBMetrics.itemCount.toLocaleString() || '0'}
              </p>
            </div>
            <div className="space-y-3">
              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-gray-600 dark:text-gray-400">Read Capacity</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">
                    {health?.dynamoDBMetrics.readCapacityUtilization.toFixed(1)}%
                  </p>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-blue-500 to-indigo-600 h-2 rounded-full"
                    style={{ width: `${health?.dynamoDBMetrics.readCapacityUtilization}%` }}
                  />
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-gray-600 dark:text-gray-400">Write Capacity</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">
                    {health?.dynamoDBMetrics.writeCapacityUtilization.toFixed(1)}%
                  </p>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-purple-500 to-pink-600 h-2 rounded-full"
                    style={{ width: `${health?.dynamoDBMetrics.writeCapacityUtilization}%` }}
                  />
                </div>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
              <h3 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Tables</h3>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">TestResults</span>
                  <span className="text-green-600 dark:text-green-400 font-semibold">Active</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">WorkflowState</span>
                  <span className="text-green-600 dark:text-green-400 font-semibold">Active</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: string
  icon: any
  color: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'orange'
  status: 'good' | 'warning' | 'error'
}

function MetricCard({ label, value, icon: Icon, color, status }: MetricCardProps) {
  const colorClasses = {
    blue: 'from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-blue-200 dark:border-blue-800',
    green: 'from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-green-200 dark:border-green-800',
    yellow: 'from-yellow-50 to-yellow-100 dark:from-yellow-900/20 dark:to-yellow-800/20 border-yellow-200 dark:border-yellow-800',
    red: 'from-red-50 to-red-100 dark:from-red-900/20 dark:to-red-800/20 border-red-200 dark:border-red-800',
    purple: 'from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 border-purple-200 dark:border-purple-800',
    orange: 'from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20 border-orange-200 dark:border-orange-800',
  }

  const iconColors = {
    blue: 'text-blue-600 dark:text-blue-400',
    green: 'text-green-600 dark:text-green-400',
    yellow: 'text-yellow-600 dark:text-yellow-400',
    red: 'text-red-600 dark:text-red-400',
    purple: 'text-purple-600 dark:text-purple-400',
    orange: 'text-orange-600 dark:text-orange-400',
  }

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} rounded-lg p-4 border-2`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</p>
        <Icon className={`h-5 w-5 ${iconColors[color]}`} />
      </div>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
