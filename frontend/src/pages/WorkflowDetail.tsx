import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, GitBranch, Clock, CheckCircle, XCircle, Loader, PlayCircle, Award } from 'lucide-react'
import { getWorkflow, getTestSummary } from '../api'
import type { Workflow } from '../types'
import { format } from 'date-fns'

export default function WorkflowDetail() {
  const { id } = useParams<{ id: string }>()
  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [testSummary, setTestSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (id) {
      loadWorkflow(id)
      loadTestSummary(id)
    }
  }, [id])

  const loadWorkflow = async (workflowId: string) => {
    try {
      const response = await getWorkflow(workflowId)
      if (response.success && response.data) {
        setWorkflow(response.data)
      }
    } catch (err) {
      console.error('Failed to load workflow:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadTestSummary = async (workflowId: string) => {
    try {
      const response = await getTestSummary(workflowId)
      if (response.success && response.data) {
        setTestSummary(response.data)
      }
    } catch (err) {
      console.error('Failed to load test summary:', err)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!workflow) {
    return (
      <div className="card text-center py-12">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">Workflow not found</h3>
      </div>
    )
  }

  const completedPhases = workflow.phases.filter(p => p.status === 'completed').length
  const progressPercentage = (completedPhases / workflow.phases.length) * 100

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link to="/workflows" className="flex items-center text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
          <ArrowLeft className="h-5 w-5 mr-2" />
          Back to Workflows
        </Link>
        <WorkflowStatusBadge status={workflow.status} />
      </div>

      {/* Workflow Overview */}
      <div className="card bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border-2 border-blue-200 dark:border-blue-800">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center">
            <div className="p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl mr-4">
              <GitBranch className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{workflow.artifactName}</h1>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Workflow ID: {workflow.workflowId}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Current Phase</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white mt-1">{workflow.currentPhase}</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Progress</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white mt-1">{progressPercentage.toFixed(0)}%</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Started</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white mt-1">
              {format(new Date(workflow.createdAt), 'MMM d, yyyy')}
            </p>
          </div>
        </div>
      </div>

      {/* Phase Timeline */}
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center">
          <PlayCircle className="h-6 w-6 mr-2 text-purple-600" />
          Modernization Pipeline
        </h2>
        <div className="space-y-6">
          {workflow.phases.map((phase, idx) => (
            <div key={idx} className="relative">
              {idx < workflow.phases.length - 1 && (
                <div className={`absolute left-6 top-12 w-0.5 h-full ${
                  phase.status === 'completed' ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'
                }`} />
              )}
              <div className="flex items-start">
                <div className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center ${
                  phase.status === 'completed' ? 'bg-green-500' :
                  phase.status === 'in-progress' ? 'bg-blue-500 animate-pulse' :
                  'bg-gray-300 dark:bg-gray-600'
                }`}>
                  {phase.status === 'completed' ? (
                    <CheckCircle className="h-6 w-6 text-white" />
                  ) : phase.status === 'in-progress' ? (
                    <Loader className="h-6 w-6 text-white animate-spin" />
                  ) : (
                    <div className="w-3 h-3 bg-white rounded-full" />
                  )}
                </div>
                <div className="ml-4 flex-1">
                  <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border-2 border-gray-200 dark:border-gray-700">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{phase.name}</h3>
                      <PhaseStatusBadge status={phase.status} />
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {getPhaseDescription(phase.name)}
                    </p>
                    {phase.status !== 'pending' && (
                      <div className="space-y-2">
                        {phase.startedAt && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Started: {format(new Date(phase.startedAt), 'MMM d, yyyy h:mm a')}
                          </p>
                        )}
                        {phase.completedAt && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Completed: {format(new Date(phase.completedAt), 'MMM d, yyyy h:mm a')}
                          </p>
                        )}
                        {phase.status === 'in-progress' && phase.progress !== undefined && (
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Progress</span>
                              <span className="text-xs font-semibold text-gray-900 dark:text-white">{phase.progress}%</span>
                            </div>
                            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                              <div
                                className="bg-gradient-to-r from-blue-500 to-purple-600 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${phase.progress}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Test Summary */}
      {testSummary && (
        <div className="card bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-2 border-green-200 dark:border-green-800">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center">
            <Award className="h-6 w-6 mr-2 text-green-600" />
            Test Execution Summary
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Total Tests</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                {testSummary.totalTests.toLocaleString()}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Passed</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">
                {testSummary.passedTests.toLocaleString()}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Failed</p>
              <p className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
                {testSummary.failedTests.toLocaleString()}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Pass Rate</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                {testSummary.passRate.toFixed(2)}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Artifact Link */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Related Artifact</h2>
        <Link
          to={`/artifacts/${workflow.artifactId}`}
          className="flex items-center justify-between p-4 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-purple-500 dark:hover:border-purple-500 transition-colors"
        >
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{workflow.artifactName}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Artifact ID: {workflow.artifactId}</p>
          </div>
          <ArrowLeft className="h-5 w-5 text-gray-400 transform rotate-180" />
        </Link>
      </div>
    </div>
  )
}

function WorkflowStatusBadge({ status }: { status: string }) {
  const config = {
    processing: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400', icon: Loader, label: 'Processing' },
    completed: { color: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400', icon: CheckCircle, label: 'Completed' },
    failed: { color: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400', icon: XCircle, label: 'Failed' },
  }

  const { color, icon: Icon, label } = config[status as keyof typeof config] || config.processing

  return (
    <span className={`px-4 py-2 inline-flex items-center text-sm font-semibold rounded-full ${color}`}>
      <Icon className="h-5 w-5 mr-2" />
      {label}
    </span>
  )
}

function PhaseStatusBadge({ status }: { status: string }) {
  const colors = {
    completed: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400',
    'in-progress': 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400',
    pending: 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400',
  }

  return (
    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${colors[status as keyof typeof colors] || colors.pending}`}>
      {status}
    </span>
  )
}

function getPhaseDescription(phaseName: string): string {
  const descriptions: Record<string, string> = {
    Discovery: 'Analyzing legacy code structure, identifying entry points, and extracting behavioral patterns using AWS Bedrock.',
    Synthesis: 'Generating modern CDK implementation based on discovered patterns and best practices.',
    Aggression: 'Creating comprehensive test vectors through property-based testing and fuzzing techniques.',
    Validation: 'Executing parallel tests comparing legacy and modern implementations for behavioral equivalence.',
    Trust: 'Generating cryptographically signed certificate of correctness with complete test results and coverage metrics.',
  }
  return descriptions[phaseName] || 'Processing phase...'
}
