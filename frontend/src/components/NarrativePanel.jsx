import styles from './NarrativePanel.module.css'

export default function NarrativePanel({ data }) {
  const confidencePct = Math.round(data.confidence * 100)

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.communityType}>{data.community_type}</span>
        <span className={styles.confidence} title="Model confidence based on data volume">
          {confidencePct}% confidence
        </span>
      </div>

      <p className={styles.narrative}>{data.narrative}</p>

      {data.evidence.length > 0 && (
        <div className={styles.evidence}>
          <p className={styles.evidenceLabel}>Grounded in</p>
          <ul className={styles.evidenceList}>
            {data.evidence.map((item, i) => (
              <li key={i} className={styles.evidenceItem}>
                <span className={styles.evidenceMetric}>{item.metric}</span>
                <span className={styles.evidenceValue}>{item.value}</span>
                <span className={styles.evidenceInterpretation}>{item.interpretation}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
