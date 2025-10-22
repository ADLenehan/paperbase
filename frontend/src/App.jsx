import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import BulkUpload from './pages/BulkUpload'
import BulkConfirmation from './pages/BulkConfirmation'
import DocumentsDashboard from './pages/DocumentsDashboard'
import NaturalLanguageQuery from './pages/NaturalLanguageQuery'
import Audit from './pages/Audit'
import Analytics from './pages/Analytics'
import SchemaEditor from './pages/SchemaEditor'
import Settings from './pages/Settings'
import Export from './pages/Export'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<BulkUpload />} />
        <Route path="confirm" element={<BulkConfirmation />} />
        <Route path="documents" element={<DocumentsDashboard />} />
        <Route path="query" element={<NaturalLanguageQuery />} />
        <Route path="audit" element={<Audit />} />
        <Route path="audit/document/:documentId" element={<Audit />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="export" element={<Export />} />
        <Route path="settings" element={<Settings />} />
        <Route path="schema/:schemaId" element={<SchemaEditor />} />
        {/* Legacy routes - redirect to Audit */}
        <Route path="verify" element={<Audit />} />
        <Route path="verify/:documentId" element={<Audit />} />
        <Route path="documents/:documentId" element={<Audit />} />
        <Route path="extractions/:extractionId" element={<Audit />} />
      </Route>
    </Routes>
  )
}

export default App
