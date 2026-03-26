import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileCode, GitBranch, Award, Activity, TrendingUp, AlertCircle } from 'lucide-react'
import { getDashboardStats } from '../api'
import type { DashboardStats } from '../types'
import { format } from 'date-fns'

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStats()
    const interval = setInterval(loadStats, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const loadStats = async () => {
    try {
      const response = await getDashboardStats()
      if (response.success && response.data) {
        setStats(response.data)
        setError(null)
      }
    } catch (err) {
      setError('Failed to load dashboard stats')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4">
        <div className="flex">
          <AlertCircle className="h-5 w-5 text-red-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-200">{error}</h3>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Artifacts"
          value={stats?.totalArtifacts || 0}
          icon={FileCode}
          color="blue"
          link="/artifacts"
        />
        <StatCard
          title="Active Workflows"
          value={stats?.activeWorkflows || 0}
          icon={GitBranch}
          color="purple"
          link="/workflows"
        />
        <StatCard
          title="Tests Executed"
          value={stats?.totalTests.toLocaleString() || 0}
          icon={TrendingUp}
          color="green"
        />
        <StatCard
          title="Certificates Issued"
          value={stats?.totalCertificates || 0}
          icon={Award}
          color="yellow"
          link="/certificates"
        />
      </div>

      {/* System Health */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <Activity className="mr-2 h-5 w-5" />
            System Health
          </h3>
          <Link to="/system" className="text-sm text-primary-600 hover:text-primary-700">
            View Details →
          </Link>
        </div>
        {stats?.systemHealth && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <HealthMetric
              label="Lambda Error Rate"
              value={`${(stats.systemHealth.lambdaMetrics.errorRate * 100).toFixed(2)}%`}
              status={stats.systemHealth.lambdaMetrics.errorRate < 0.01 ? 'good' : 'warning'}
            />
            <HealthMetric
              label="Step Functions Success"
              value={`${stats.systemHealth.stepFunctionsMetrics.executionsSucceeded}`}
              status="good"
            />
            <HealthMetric
              label="S3 Storage"
              value={formatBytes(stats.systemHealth.s3Metrics.totalSize)}
              status="good"
            />
            <HealthMetric
              label="DynamoDB Items"
              value={stats.systemHealth.dynamoDBMetrics.itemCount.toLocaleString()}
              status="good"
            />
          </div>
        )}
      </div>

      {/* Recent Certificates */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <Award className="mr-2 h-5 w-5" />
            Recent Certificates
          </h3>
          <Link to="/certificates" className="text-sm text-primary-600 hover:text-primary-700">
            View All →
          </Link>
        </div>
        {stats?.recentCertificates && stats.recentCertificates.length > 0 ? (
          <div className="space-y-3">
            {stats.recentCertificates.map((cert) => (
              <Link
                key={cert.certificateId}
                to={`/certificates/${cert.certificateId}`}
                className="block p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary-500 dark:hover:border-primary-500 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      Workflow: {cert.workflowId.substring(0, 8)}...
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {cert.testCount.toLocaleString()} tests • {cert.coveragePercentage}% coverage
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {format(new Date(cert.generatedAt), 'MMM d, yyyy')}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {format(new Date(cert.generatedAt), 'h:mm a')}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-center py-8">
            No certificates generated yet
          </p>
        )}
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: number | string
  icon: any
  color: 'blue' | 'purple' | 'green' | 'yellow'
  link?: string
}

function StatCard({ title, value, icon: Icon, color, link }: StatCardProps) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400',
    purple: 'bg-purple-100 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400',
    green: 'bg-green-100 text-green-600 dark:bg-green-900/20 dark:text-green-400',
    yellow: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/20 dark:text-yellow-400',
  }

  const content = (
    <>
      <div className={`inline-flex rounded-lg p-3 ${colorClasses[color]}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div className="mt-4">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
        <p className="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">{value}</p>
      </div>
    </>
  )

  if (link) {
    return (
      <Link to={link} className="card hover:shadow-lg transition-shadow">
        {content}
      </Link>
    )
  }

  return <div className="card">{content}</div>
}

interface HealthMetricProps {
  label: string
  value: string
  status: 'good' | 'warning' | 'error'
}

function HealthMetric({ label, value, status }: HealthMetricProps) {
  const statusColors = {
    good: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400',
    warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400',
    error: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400',
  }

  return (
    <div className="flex flex-col">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className={`mt-1 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[status]}`}>
        {value}
      </span>
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
