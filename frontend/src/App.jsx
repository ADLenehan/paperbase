import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import BulkUpload from './pages/BulkUpload'
import BulkConfirmation from './pages/BulkConfirmation'
import DocumentsDashboard from './pages/DocumentsDashboard'
import DocumentDetail from './pages/DocumentDetail'
import NaturalLanguageQuery from './pages/NaturalLanguageQuery'
import ChatSearch from './pages/ChatSearch'
import Audit from './pages/Audit'
import SchemaEditor from './pages/SchemaEditor'
import Settings from './pages/Settings'

function App() {
  return (
    <Routes>
      {/* Landing page - standalone, outside Layout */}
      <Route path="/" element={<LandingPage />} />

      {/* App routes - inside Layout */}
      <Route path="/" element={<Layout />}>
        <Route path="upload" element={<BulkUpload />} />
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
  )
}

export default App
