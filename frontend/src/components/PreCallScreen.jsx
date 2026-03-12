import { useState, useEffect } from "react";
import styles from "./PreCallScreen.module.css";

/**
 * PreCallScreen -- Lead selection + info preview + Start Call button.
 *
 * Fetches leads from GET /api/leads on mount and displays
 * a dropdown for selection, an info preview card, and a start button.
 *
 * @param {{ onSelectLead: Function, onStartCall: Function, selectedLead: object|null }} props
 */
export default function PreCallScreen({ onSelectLead, onStartCall, selectedLead }) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLeads = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/leads");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLeads(data);
    } catch (err) {
      setError("Failed to load leads");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const handleSelectChange = (e) => {
    const leadId = e.target.value;
    if (!leadId) {
      onSelectLead(null);
      return;
    }
    const lead = leads.find((l) => l.id === leadId);
    onSelectLead(lead || null);
  };

  return (
    <div className={styles.container}>
      {/* Sarah Avatar */}
      <div className={styles.avatar}>S</div>
      <div className={styles.name}>Sarah -- AI Sales Agent</div>

      {/* Lead Dropdown */}
      {loading && <div className={styles.loading}>Loading leads...</div>}
      {error && (
        <>
          <div className={styles.error}>{error}</div>
          <button className={styles.retryButton} onClick={fetchLeads}>
            Retry
          </button>
        </>
      )}
      {!loading && !error && (
        <select
          className={styles.select}
          value={selectedLead?.id || ""}
          onChange={handleSelectChange}
        >
          <option value="">Select a lead...</option>
          {leads.map((lead) => (
            <option key={lead.id} value={lead.id}>
              {lead.name} - {lead.phone} ({lead.call_outcome || "NEW"})
            </option>
          ))}
        </select>
      )}

      {/* Lead Info Preview Card */}
      {selectedLead && (
        <div className={styles.infoCard}>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>Name</span>
            <span className={styles.infoValue}>{selectedLead.name}</span>
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>Phone</span>
            <span className={styles.infoValue}>{selectedLead.phone}</span>
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>Email</span>
            <span className={styles.infoValue}>{selectedLead.email}</span>
          </div>
        </div>
      )}

      {/* Start Call Button */}
      <button
        className={styles.startButton}
        disabled={!selectedLead}
        onClick={onStartCall}
      >
        Start Call
      </button>
    </div>
  );
}
