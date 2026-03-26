import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Download } from 'lucide-react'
import { getArtifact, downloadArtifact } from '../api'
import type { Artifact } from '../types'

export default function ArtifactDetail() {
  const { id } = useParams<{ id: string }>()
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (id) loadArtifact(id)
  }, [id])

  const loadArtifact = async (artifactId: string) => {
    try {
      const response = await getArtifact(artifactId)
      if (response.success && response.data) {
        setArtifact(response.data)
      }
    } catch (err) {
      console.error('Failed to load artifact:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!id) return
    try {
      const response = await downloadArtifact(id)
      if (response.success && response.data?.presignedUrl) {
        window.open(response.data.presignedUrl, '_blank')
      }
    } catch (err) {
      alert('Download failed')
    }
  }

  if (loading) {
    return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div></div>
  }

  if (!artifact) {
    return <div className="text-center py-12">Artifact not found</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link to="/artifacts" className="flex items-center text-gray-600 hover:text-gray-900">
          <ArrowLeft className="h-5 w-5 mr-2" />
          Back to Artifacts
        </Link>
        <button onClick={handleDownload} className="btn-primary">
          <Download className="h-5 w-5 mr-2" />
          Download
        </button>
      </div>

      <div className="card">
        <h2 className="text-2xl font-bold mb-6">{artifact.name}</h2>
        <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-gray-500">Artifact ID</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{artifact.artifactId}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Type</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{artifact.type}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Size</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{(artifact.size / 1024).toFixed(2)} KB</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Status</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{artifact.status}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Uploaded At</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{new Date(artifact.uploadedAt).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Uploaded By</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{artifact.uploadedBy}</dd>
          </div>
          {artifact.workflowId && (
            <div className="sm:col-span-2">
              <dt className="text-sm font-medium text-gray-500">Workflow</dt>
              <dd className="mt-1 text-sm">
                <Link to={`/workflows/${artifact.workflowId}`} className="text-primary-600 hover:text-primary-900">
                  {artifact.workflowId}
                </Link>
              </dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  )
}
