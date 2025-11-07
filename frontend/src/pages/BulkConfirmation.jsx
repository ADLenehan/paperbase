import { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

/**
 * Legacy BulkConfirmation page - now redirects to Audit in table mode
 *
 * This page has been replaced by Audit.jsx with mode=table for consistency.
 * We keep this as a thin redirect wrapper to maintain URL compatibility.
 *
 * Flow:
 * - User lands on /confirm?schema_id=123
 * - Automatically redirects to /audit?template_id=123&mode=table
 * - Audit.jsx renders AuditTableView component
 * - All verification flows consolidated in one place
 */
export default function BulkConfirmation() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const schemaId = searchParams.get('schema_id');

  useEffect(() => {
    // Redirect to Audit page in table mode
    if (schemaId) {
      navigate(`/audit?template_id=${schemaId}&mode=table`, { replace: true });
    } else {
      // No schema ID - redirect to documents dashboard
      navigate('/documents', { replace: true });
    }
  }, [schemaId, navigate]);

  // Show loading state while redirecting
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-gray-500">Redirecting...</div>
    </div>
  );
}
