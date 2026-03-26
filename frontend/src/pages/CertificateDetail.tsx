import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Shield, Award, Download, CheckCircle, FileText, Lock, Calendar } from 'lucide-react'
import { getCertificate, verifyCertificateSignature } from '../api'
import type { Certificate } from '../types'
import { format } from 'date-fns'

export default function CertificateDetail() {
  const { id } = useParams<{ id: string }>()
  const [certificate, setCertificate] = useState<Certificate | null>(null)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)
  const [verified, setVerified] = useState(false)

  useEffect(() => {
    if (id) loadCertificate(id)
  }, [id])

  const loadCertificate = async (certId: string) => {
    try {
      const response = await getCertificate(certId)
      if (response.success && response.data) {
        setCertificate(response.data)
      }
    } catch (err) {
      console.error('Failed to load certificate:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async () => {
    if (!id) return
    setVerifying(true)
    try {
      const response = await verifyCertificateSignature(id)
      if (response.success && response.data?.valid) {
        setVerified(true)
        setTimeout(() => setVerified(false), 3000)
      }
    } catch (err) {
      alert('Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  const handleDownload = () => {
    alert('Certificate download initiated')
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!certificate) {
    return (
      <div className="card text-center py-12">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">Certificate not found</h3>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link to="/certificates" className="flex items-center text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
          <ArrowLeft className="h-5 w-5 mr-2" />
          Back to Certificates
        </Link>
        <div className="flex space-x-3">
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="btn-secondary flex items-center"
          >
            {verifying ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-800 mr-2"></div>
                Verifying...
              </>
            ) : verified ? (
              <>
                <CheckCircle className="h-5 w-5 mr-2 text-green-600" />
                Verified!
              </>
            ) : (
              <>
                <Shield className="h-5 w-5 mr-2" />
                Verify Signature
              </>
            )}
          </button>
          <button onClick={handleDownload} className="btn-primary flex items-center">
            <Download className="h-5 w-5 mr-2" />
            Download Certificate
          </button>
        </div>
      </div>

      {/* Certificate Header */}
      <div className="card bg-gradient-to-br from-yellow-50 via-amber-50 to-orange-50 dark:from-yellow-900/20 dark:via-amber-900/20 dark:to-orange-900/20 border-4 border-yellow-400 dark:border-yellow-600">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center">
            <div className="p-4 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-xl mr-4 shadow-lg">
              <Award className="h-12 w-12 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Certificate of Correctness</h1>
              <p className="text-lg text-gray-700 dark:text-gray-300 mt-1">ID: {certificate.certificateId}</p>
            </div>
          </div>
          <div className="px-4 py-2 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center">
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 mr-2" />
            <span className="text-sm font-semibold text-green-800 dark:text-green-300">Verified</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-md">
            <p className="text-sm text-gray-600 dark:text-gray-400 flex items-center">
              <FileText className="h-4 w-4 mr-2" />
              Tests Executed
            </p>
            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
              {certificate.testCount.toLocaleString()}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-md">
            <p className="text-sm text-gray-600 dark:text-gray-400 flex items-center">
              <CheckCircle className="h-4 w-4 mr-2" />
              Coverage
            </p>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400 mt-2">
              {certificate.coveragePercentage}%
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-md">
            <p className="text-sm text-gray-600 dark:text-gray-400 flex items-center">
              <Calendar className="h-4 w-4 mr-2" />
              Issued
            </p>
            <p className="text-xl font-bold text-gray-900 dark:text-white mt-2">
              {format(new Date(certificate.generatedAt), 'MMM d, yyyy')}
            </p>
          </div>
        </div>
      </div>

      {/* Certificate Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Legacy Artifact */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <FileText className="h-6 w-6 mr-2 text-blue-600" />
            Legacy Artifact
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Identifier</span>
              <span className="text-sm font-mono text-gray-900 dark:text-white">
                {certificate.legacyArtifactMetadata.identifier}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Version</span>
              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                {certificate.legacyArtifactMetadata.version}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Hash</span>
              <span className="text-xs font-mono text-gray-900 dark:text-white">
                {certificate.legacyArtifactMetadata.hash}
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">S3 Location</span>
              <span className="text-xs font-mono text-gray-900 dark:text-white truncate max-w-xs">
                {certificate.legacyArtifactMetadata.s3Location}
              </span>
            </div>
          </div>
        </div>

        {/* Modern Implementation */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <FileText className="h-6 w-6 mr-2 text-green-600" />
            Modern Implementation
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Identifier</span>
              <span className="text-sm font-mono text-gray-900 dark:text-white">
                {certificate.modernImplementationMetadata.identifier}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Version</span>
              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                {certificate.modernImplementationMetadata.version}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Hash</span>
              <span className="text-xs font-mono text-gray-900 dark:text-white">
                {certificate.modernImplementationMetadata.hash}
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">S3 Location</span>
              <span className="text-xs font-mono text-gray-900 dark:text-white truncate max-w-xs">
                {certificate.modernImplementationMetadata.s3Location}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Cryptographic Details */}
      <div className="card bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 border-2 border-purple-200 dark:border-purple-800">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center">
          <Lock className="h-6 w-6 mr-2 text-purple-600" />
          Cryptographic Signature
        </h2>
        <div className="space-y-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Signature</p>
            <p className="text-xs font-mono text-gray-900 dark:text-white break-all bg-gray-100 dark:bg-gray-900 p-3 rounded">
              {certificate.signature}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Signing Key ID</p>
              <p className="text-sm font-mono text-gray-900 dark:text-white">{certificate.signingKeyId}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Algorithm</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">{certificate.signingAlgorithm}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Test Results Hash</p>
            <p className="text-xs font-mono text-gray-900 dark:text-white break-all bg-gray-100 dark:bg-gray-900 p-3 rounded">
              {certificate.testResultsHash}
            </p>
          </div>
        </div>
      </div>

      {/* Related Links */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Related Resources</h2>
        <div className="space-y-3">
          <Link
            to={`/workflows/${certificate.workflowId}`}
            className="flex items-center justify-between p-4 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-purple-500 dark:hover:border-purple-500 transition-colors"
          >
            <div>
              <p className="font-medium text-gray-900 dark:text-white">View Workflow</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Workflow ID: {certificate.workflowId}</p>
            </div>
            <ArrowLeft className="h-5 w-5 text-gray-400 transform rotate-180" />
          </Link>
          <Link
            to={`/artifacts/${certificate.artifactId}`}
            className="flex items-center justify-between p-4 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-purple-500 dark:hover:border-purple-500 transition-colors"
          >
            <div>
              <p className="font-medium text-gray-900 dark:text-white">View Artifact</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Artifact ID: {certificate.artifactId}</p>
            </div>
            <ArrowLeft className="h-5 w-5 text-gray-400 transform rotate-180" />
          </Link>
        </div>
      </div>
    </div>
  )
}
