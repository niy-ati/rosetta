import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TestTube, FileCode, CheckCircle, XCircle, Clock, TrendingUp, Code, Play } from 'lucide-react'
import { getTestExecutions } from '../api'
import { format } from 'date-fns'

interface TestExecution {
  executionId: string
  workflowId: string
  projectName: string
  company: string
  totalTests: number
  passedTests: number
  failedTests: number
  skippedTests: number
  duration: number
  executedAt: string
  testSuites: TestSuite[]
  codeFiles: CodeFile[]
}

interface TestSuite {
  name: string
  type: string
  tests: number
  passed: number
  failed: number
  coverage: number
}

interface CodeFile {
  path: string
  language: string
  lines: number
  covered: number
  coverage: number
}

export default function TestExecution() {
  const [executions, setExecutions] = useState<TestExecution[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedExecution, setSelectedExecution] = useState<TestExecution | null>(null)

  useEffect(() => {
    loadExecutions()
  }, [])

  const loadExecutions = async () => {
    try {
      const response = await getTestExecutions()
      if (response.success && response.data) {
        setExecutions(response.data)
        if (response.data.length > 0) {
          setSelectedExecution(response.data[0])
        }
      }
    } catch (err) {
      console.error('Failed to load test executions:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center">
          <TestTube className="h-8 w-8 text-indigo-500 mr-3" />
          Test Execution Dashboard
        </h1>
        <div className="text-sm text-gray-400">
          {executions.length} test executions tracked
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-6 md:grid-cols-4">
        <div className="card bg-gradient-to-br from-green-900/40 to-emerald-900/40 border-2 border-green-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-300">Total Tests Executed</p>
              <p className="text-3xl font-bold text-white mt-2">
                {executions.reduce((sum, e) => sum + e.totalTests, 0).toLocaleString()}
              </p>
            </div>
            <CheckCircle className="h-12 w-12 text-green-500" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-blue-900/40 to-indigo-900/40 border-2 border-blue-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-300">Pass Rate</p>
              <p className="text-3xl font-bold text-white mt-2">
                {((executions.reduce((sum, e) => sum + e.passedTests, 0) / 
                   executions.reduce((sum, e) => sum + e.totalTests, 0)) * 100).toFixed(1)}%
              </p>
            </div>
            <TrendingUp className="h-12 w-12 text-blue-500" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-purple-900/40 to-pink-900/40 border-2 border-purple-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-purple-300">Code Files Tested</p>
              <p className="text-3xl font-bold text-white mt-2">
                {executions.reduce((sum, e) => sum + e.codeFiles.length, 0)}
              </p>
            </div>
            <FileCode className="h-12 w-12 text-purple-500" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-orange-900/40 to-red-900/40 border-2 border-orange-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-orange-300">Avg Duration</p>
              <p className="text-3xl font-bold text-white mt-2">
                {Math.round(executions.reduce((sum, e) => sum + e.duration, 0) / executions.length / 60)}m
              </p>
            </div>
            <Clock className="h-12 w-12 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Execution List and Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Execution List */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-lg font-semibold text-white">Test Executions</h2>
          <div className="space-y-3 max-h-[800px] overflow-y-auto">
            {executions.map((execution) => (
              <button
                key={execution.executionId}
                onClick={() => setSelectedExecution(execution)}
                className={`w-full text-left card transition-all ${
                  selectedExecution?.executionId === execution.executionId
                    ? 'border-2 border-indigo-500 bg-indigo-900/30'
                    : 'hover:border-indigo-500/50'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h3 className="font-semibold text-white text-sm">{execution.projectName}</h3>
                    <p className="text-xs text-gray-400 mt-1">{execution.company}</p>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    (execution.passedTests / execution.totalTests) > 0.95
                      ? 'bg-green-900/50 text-green-300'
                      : 'bg-yellow-900/50 text-yellow-300'
                  }`}>
                    {((execution.passedTests / execution.totalTests) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>{execution.totalTests.toLocaleString()} tests</span>
                  <span>{format(new Date(execution.executedAt), 'MMM d')}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Execution Details */}
        {selectedExecution && (
          <div className="lg:col-span-2 space-y-6">
            {/* Header */}
            <div className="card bg-gradient-to-br from-indigo-900/40 to-purple-900/40 border-2 border-indigo-700/50">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold text-white">{selectedExecution.projectName}</h2>
                  <p className="text-gray-400 mt-1">{selectedExecution.company}</p>
                  <p className="text-sm text-gray-500 mt-2">
                    Executed: {format(new Date(selectedExecution.executedAt), 'MMM d, yyyy h:mm a')}
                  </p>
                </div>
                <Link
                  to={`/workflows/${selectedExecution.workflowId}`}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm transition-colors"
                >
                  View Workflow
                </Link>
              </div>

              <div className="grid grid-cols-4 gap-4">
                <div className="bg-gray-800/50 rounded-lg p-3">
                  <p className="text-xs text-gray-400">Total</p>
                  <p className="text-2xl font-bold text-white mt-1">{selectedExecution.totalTests.toLocaleString()}</p>
                </div>
                <div className="bg-green-900/30 rounded-lg p-3">
                  <p className="text-xs text-green-400">Passed</p>
                  <p className="text-2xl font-bold text-green-300 mt-1">{selectedExecution.passedTests.toLocaleString()}</p>
                </div>
                <div className="bg-red-900/30 rounded-lg p-3">
                  <p className="text-xs text-red-400">Failed</p>
                  <p className="text-2xl font-bold text-red-300 mt-1">{selectedExecution.failedTests.toLocaleString()}</p>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-3">
                  <p className="text-xs text-gray-400">Duration</p>
                  <p className="text-2xl font-bold text-white mt-1">{Math.round(selectedExecution.duration / 60)}m</p>
                </div>
              </div>
            </div>

            {/* Test Suites */}
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                <Play className="h-5 w-5 mr-2 text-indigo-500" />
                Test Suites
              </h3>
              <div className="space-y-3">
                {selectedExecution.testSuites.map((suite, idx) => (
                  <div key={idx} className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h4 className="font-semibold text-white">{suite.name}</h4>
                        <p className="text-sm text-gray-400 mt-1">{suite.type}</p>
                      </div>
                      <span className="px-3 py-1 bg-indigo-900/50 text-indigo-300 rounded-full text-sm font-semibold">
                        {suite.coverage}% coverage
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <p className="text-gray-400">Tests</p>
                        <p className="text-white font-semibold">{suite.tests}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Passed</p>
                        <p className="text-green-400 font-semibold">{suite.passed}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Failed</p>
                        <p className="text-red-400 font-semibold">{suite.failed}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Code Files */}
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                <Code className="h-5 w-5 mr-2 text-purple-500" />
                Code Files Tested
              </h3>
              <div className="space-y-2">
                {selectedExecution.codeFiles.map((file, idx) => (
                  <div key={idx} className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center flex-1">
                        <FileCode className="h-4 w-4 text-gray-400 mr-2" />
                        <span className="text-sm font-mono text-white">{file.path}</span>
                      </div>
                      <span className="px-2 py-1 bg-purple-900/50 text-purple-300 rounded text-xs font-semibold ml-2">
                        {file.language}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-400">{file.lines} lines • {file.covered} covered</span>
                      <span className={`font-semibold ${
                        file.coverage >= 90 ? 'text-green-400' :
                        file.coverage >= 75 ? 'text-yellow-400' :
                        'text-red-400'
                      }`}>
                        {file.coverage}% coverage
                      </span>
                    </div>
                    <div className="mt-2 w-full bg-gray-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          file.coverage >= 90 ? 'bg-green-500' :
                          file.coverage >= 75 ? 'bg-yellow-500' :
                          'bg-red-500'
                        }`}
                        style={{ width: `${file.coverage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
