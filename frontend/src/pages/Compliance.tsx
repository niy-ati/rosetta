import { useState } from 'react'
import { FileText, Download, Calendar, CheckCircle, AlertTriangle } from 'lucide-react'

export default function Compliance() {
  const [generating, setGenerating] = useState(false)

  const mockReports = [
    {
      id: 'report-001',
      name: 'Q1 2026 Compliance Report',
      date: '2026-03-01',
      status: 'completed',
      artifacts: 15,
      certificates: 12,
      passRate: 98.5
    },
    {
      id: 'report-002',
      name: 'February 2026 Audit',
      date: '2026-02-15',
      status: 'completed',
      artifacts: 8,
      certificates: 7,
      passRate: 99.2
    },
    {
      id: 'report-003',
      name: 'January 2026 Summary',
      date: '2026-01-31',
      status: 'completed',
      artifacts: 12,
      certificates: 10,
      passRate: 97.8
    }
  ]

  const handleGenerate = () => {
    setGenerating(true)
    setTimeout(() => {
      setGenerating(false)
      alert('Compliance report generated successfully!')
    }, 2000)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center">
          <FileText className="h-8 w-8 text-purple-600 mr-3" />
          Compliance Reports
        </h1>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-primary flex items-center"
        >
          {generating ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Generating...
            </>
          ) : (
            <>
              <FileText className="h-5 w-5 mr-2" />
              Generate New Report
            </>
          )}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="card bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-2 border-green-200 dark:border-green-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-800 dark:text-green-300">Total Reports</p>
              <p className="text-3xl font-bold text-green-900 dark:text-green-100 mt-2">{mockReports.length}</p>
            </div>
            <CheckCircle className="h-12 w-12 text-green-600 dark:text-green-400" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-2 border-blue-200 dark:border-blue-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-300">Avg Pass Rate</p>
              <p className="text-3xl font-bold text-blue-900 dark:text-blue-100 mt-2">
                {(mockReports.reduce((sum, r) => sum + r.passRate, 0) / mockReports.length).toFixed(1)}%
              </p>
            </div>
            <AlertTriangle className="h-12 w-12 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 border-2 border-purple-200 dark:border-purple-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-purple-800 dark:text-purple-300">Total Artifacts</p>
              <p className="text-3xl font-bold text-purple-900 dark:text-purple-100 mt-2">
                {mockReports.reduce((sum, r) => sum + r.artifacts, 0)}
              </p>
            </div>
            <FileText className="h-12 w-12 text-purple-600 dark:text-purple-400" />
          </div>
        </div>
      </div>

      {/* Reports List */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Generated Reports</h2>
        <div className="space-y-4">
          {mockReports.map((report) => (
            <div
              key={report.id}
              className="flex items-center justify-between p-4 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-purple-500 dark:hover:border-purple-500 transition-colors bg-gradient-to-r from-white to-purple-50 dark:from-gray-800 dark:to-purple-900/10"
            >
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                  <FileText className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{report.name}</h3>
                  <div className="flex items-center space-x-4 mt-1 text-sm text-gray-500 dark:text-gray-400">
                    <span className="flex items-center">
                      <Calendar className="h-4 w-4 mr-1" />
                      {new Date(report.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                    <span>{report.artifacts} artifacts</span>
                    <span>{report.certificates} certificates</span>
                    <span className="font-semibold text-green-600 dark:text-green-400">
                      {report.passRate}% pass rate
                    </span>
                  </div>
                </div>
              </div>
              <button className="flex items-center px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors">
                <Download className="h-4 w-4 mr-2" />
                Download
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
