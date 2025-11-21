import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import DevModeBanner from './components/DevModeBanner'
import Landing from './pages/Landing'
import Login from './pages/Login'
import SignUp from './pages/SignUp'
import Layout from './components/Layout'
import BulkUpload from './pages/BulkUpload'
import BulkConfirmation from './pages/BulkConfirmation'
import DocumentsDashboard from './pages/DocumentsDashboard'
import DocumentDetail from './pages/DocumentDetail'
import NaturalLanguageQuery from './pages/NaturalLanguageQuery'
import ChatSearch from './pages/ChatSearch'
import Audit from './pages/Audit'
import SchemaEditor from './pages/SchemaEditor'
import Settings from './pages/Settings'

// Redirect component for legacy verify URLs
function VerifyRedirect() {
  const { documentId } = useParams()
  return <Navigate to={`/app/audit/document/${documentId}`} replace />
}

// Redirect component for legacy documents URLs
function DocumentRedirect() {
  const { documentId } = useParams()
  return <Navigate to={`/app/documents/${documentId}`} replace />
}

function App() {
  return (
    <AuthProvider>
      <DevModeBanner />
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />

        {/* Legacy redirects - old URLs to new app-prefixed URLs */}
        <Route
          path="/verify/:documentId"
          element={<VerifyRedirect />}
        />
        <Route path="/verify" element={<Navigate to="/app/audit" replace />} />
        <Route
          path="/documents/:documentId"
          element={<DocumentRedirect />}
        />
        <Route path="/documents" element={<Navigate to="/app/documents" replace />} />

        {/* Protected routes */}
        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<BulkUpload />} />
          <Route path="confirm" element={<BulkConfirmation />} />
          <Route path="documents" element={<DocumentsDashboard />} />
          <Route path="documents/:documentId" element={<DocumentDetail />} />
          <Route path="query" element={<ChatSearch />} />
          <Route path="audit" element={<Audit />} />
          <Route path="audit/document/:documentId" element={<Audit />} />
          <Route path="settings" element={<Settings />} />
          <Route path="schema/:schemaId" element={<SchemaEditor />} />
          {/* Legacy routes - redirect to Audit */}
          <Route path="verify" element={<Audit />} />
          <Route path="verify/:documentId" element={<Audit />} />
          <Route path="extractions/:extractionId" element={<Audit />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}

export default App
