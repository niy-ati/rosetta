import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitBranch, Clock, CheckCircle, XCircle, Loader } from 'lucide-react'
import { getWorkflows } from '../api'
import type { Workflow } from '../types'
import { format } from 'date-fns'

export default function Workflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')

  useEffect(() => {
    loadWorkflows()
  }, [statusFilter])

  const loadWorkflows = async () => {
    try {
      const response = await getWorkflows(1, 50, statusFilter)
      if (response.success && response.data) {
        setWorkflows(response.data.items)
      }
    } catch (err) {
      console.error('Failed to load workflows:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Modernization Workflows</h1>
        <select
          className="input w-48"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Status</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <div className="grid gap-6">
          {workflows.map((workflow) => (
            <Link
              key={workflow.workflowId}
              to={`/workflows/${workflow.workflowId}`}
              className="card hover:shadow-xl transition-shadow border-2 border-transparent hover:border-primary-500"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center">
                  <GitBranch className="h-6 w-6 text-primary-600 mr-3" />
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {workflow.artifactName}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Workflow ID: {workflow.workflowId}
                    </p>
                  </div>
                </div>
                <WorkflowStatusBadge status={workflow.status} />
              </div>

              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Current Phase: {workflow.currentPhase}
                  </span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {workflow.phases.filter(p => p.status === 'completed').length} / {workflow.phases.length} Complete
                  </span>
                </div>
                <div className="flex gap-2">
                  {workflow.phases.map((phase, idx) => (
                    <div key={idx} className="flex-1">
                      <div className={`h-2 rounded-full ${
                        phase.status === 'completed' ? 'bg-green-500' :
                        phase.status === 'in-progress' ? 'bg-blue-500 animate-pulse' :
                        'bg-gray-300 dark:bg-gray-600'
                      }`} />
                      <p className="text-xs text-center mt-1 text-gray-600 dark:text-gray-400">
                        {phase.name}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                <div className="flex items-center">
                  <Clock className="h-4 w-4 mr-1" />
                  Started {format(new Date(workflow.createdAt), 'MMM d, yyyy h:mm a')}
                </div>
                {workflow.completedAt && (
                  <div className="flex items-center text-green-600 dark:text-green-400">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Completed
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
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
    <span className={`px-3 py-1 inline-flex items-center text-sm font-semibold rounded-full ${color}`}>
      <Icon className="h-4 w-4 mr-1" />
      {label}
    </span>
  )
}
