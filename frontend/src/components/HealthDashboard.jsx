import AlertCard from './AlertCard.jsx'
import ContributorTable from './ContributorTable.jsx'
import NarrativePanel from './NarrativePanel.jsx'
import styles from './HealthDashboard.module.css'

function MetricCard({ label, value, unit, muted }) {
  return (
    <div className={styles.metricCard}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={`${styles.metricValue} ${muted ? styles.muted : ''}`}>
        {value ?? '—'}
        {unit && <span className={styles.metricUnit}>{unit}</span>}
      </span>
    </div>
  )
}

export default function HealthDashboard({ data, onGetNarrative, narrativeStatus, narrativeData, narrativeError }) {
  const computedAt = new Date(data.computed_at).toLocaleString()
  const narrativeLoading = narrativeStatus === 'loading'

  return (
    <div className={styles.dashboard}>
      <div className={styles.dashHeader}>
        <div>
          <h2 className={styles.subreddit}>r/{data.subreddit}</h2>
          <p className={styles.range}>{data.from_date} → {data.to_date}</p>
        </div>
        <p className={styles.computedAt}>Computed {computedAt}</p>
      </div>

      <section>
        <h3 className={styles.sectionTitle}>Volume</h3>
        <div className={styles.metricsGrid}>
          <MetricCard label="Total posts" value={data.total_posts.toLocaleString()} />
          <MetricCard label="Total comments" value={data.total_comments.toLocaleString()} />
          <MetricCard label="Unique contributors" value={data.unique_contributors.toLocaleString()} />
        </div>
      </section>

      <section>
        <h3 className={styles.sectionTitle}>Engagement</h3>
        <div className={styles.metricsGrid}>
          <MetricCard label="Avg comments / post" value={data.avg_comments_per_post} />
          <MetricCard
            label="Median response time"
            value={data.median_response_time_minutes ?? 'N/A'}
            unit={data.median_response_time_minutes != null ? ' min' : undefined}
            muted={data.median_response_time_minutes == null}
          />
          <MetricCard label="Engagement concentration" value={data.engagement_concentration_pct} unit="%" />
          <MetricCard label="Unanswered post rate" value={data.unanswered_post_rate_pct} unit="%" />
        </div>
      </section>

      {data.alerts.length > 0 && (
        <section>
          <h3 className={styles.sectionTitle}>Alerts</h3>
          <div className={styles.alertList}>
            {data.alerts.map((alert, i) => (
              <AlertCard key={i} alert={alert} />
            ))}
          </div>
        </section>
      )}

      {data.top_contributors.length > 0 && (
        <section>
          <h3 className={styles.sectionTitle}>Top contributors</h3>
          <ContributorTable contributors={data.top_contributors} />
        </section>
      )}

      <section className={styles.narrativeSection}>
        <div className={styles.narrativeDivider} />
        {narrativeStatus === 'idle' && (
          <button className={styles.narrativeButton} onClick={onGetNarrative}>
            Get community narrative
          </button>
        )}
        {narrativeLoading && (
          <div className={styles.narrativeLoading}>
            <div className={styles.spinner} />
            <p>Generating narrative…</p>
          </div>
        )}
        {narrativeStatus === 'error' && (
          <div className={styles.narrativeError}>
            <strong>Error:</strong> {narrativeError}
          </div>
        )}
        {narrativeStatus === 'success' && narrativeData && (
          <NarrativePanel data={narrativeData} />
        )}
      </section>
    </div>
  )
}
