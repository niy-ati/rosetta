import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Award, Shield, CheckCircle, Download } from 'lucide-react'
import { getCertificates } from '../api'
import type { Certificate } from '../types'
import { format } from 'date-fns'

export default function Certificates() {
  const [certificates, setCertificates] = useState<Certificate[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadCertificates()
  }, [])

  const loadCertificates = async () => {
    try {
      const response = await getCertificates()
      if (response.success && response.data) {
        setCertificates(response.data.items)
      }
    } catch (err) {
      console.error('Failed to load certificates:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center">
          <Award className="h-8 w-8 text-yellow-500 mr-3" />
          Correctness Certificates
        </h1>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          {certificates.length} certificates issued
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : certificates.length > 0 ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {certificates.map((cert) => (
            <Link
              key={cert.certificateId}
              to={`/certificates/${cert.certificateId}`}
              className="card hover:shadow-2xl transition-all border-2 border-transparent hover:border-yellow-400 bg-gradient-to-br from-white to-yellow-50 dark:from-gray-800 dark:to-yellow-900/10"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                  <Shield className="h-8 w-8 text-yellow-600 dark:text-yellow-400" />
                </div>
                <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400 flex items-center">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Verified
                </span>
              </div>

              <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">
                Certificate #{cert.certificateId.split('-')[1]}
              </h3>

              <div className="space-y-2 mb-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Workflow:</span>
                  <span className="font-mono text-xs text-gray-900 dark:text-white">
                    {cert.workflowId.substring(0, 12)}...
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Tests Passed:</span>
                  <span className="font-bold text-green-600 dark:text-green-400">
                    {cert.testCount.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Coverage:</span>
                  <span className="font-bold text-blue-600 dark:text-blue-400">
                    {cert.coveragePercentage}%
                  </span>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <span>Issued {format(new Date(cert.generatedAt), 'MMM d, yyyy')}</span>
                  <Download className="h-4 w-4" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <Award className="mx-auto h-16 w-16 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No Certificates Yet
          </h3>
          <p className="text-gray-500 dark:text-gray-400">
            Certificates will appear here once workflows complete successfully
          </p>
        </div>
      )}
    </div>
  )
}
