import { useState } from 'react'
import SearchForm from './components/SearchForm.jsx'
import HealthDashboard from './components/HealthDashboard.jsx'
import styles from './App.module.css'

const STATUS = { IDLE: 'idle', LOADING: 'loading', SUCCESS: 'success', ERROR: 'error' }

export default function App() {
  const [insightsStatus, setInsightsStatus] = useState(STATUS.IDLE)
  const [insightsData, setInsightsData] = useState(null)
  const [insightsError, setInsightsError] = useState(null)
  const [lastSearch, setLastSearch] = useState(null)

  const [narrativeStatus, setNarrativeStatus] = useState(STATUS.IDLE)
  const [narrativeData, setNarrativeData] = useState(null)
  const [narrativeError, setNarrativeError] = useState(null)

  async function handleSearch({ subreddit, fromDate, toDate }) {
    setInsightsStatus(STATUS.LOADING)
    setInsightsData(null)
    setInsightsError(null)
    setNarrativeStatus(STATUS.IDLE)
    setNarrativeData(null)
    setNarrativeError(null)
    setLastSearch({ subreddit, fromDate, toDate })

    try {
      const params = new URLSearchParams({ subreddit, from: fromDate, to: toDate })
      const res = await fetch(`/api/insights/community-health?${params}`)
      let json
      try {
        json = await res.json()
      } catch {
        throw new Error(
          res.status === 504 || res.status === 502
            ? 'The request timed out. Reddit data collection can take a while for large date ranges — please try a shorter range or try again.'
            : `Server returned a non-JSON response (HTTP ${res.status})`
        )
      }
      if (!res.ok) throw new Error(json.detail ?? `HTTP ${res.status}`)
      setInsightsData(json)
      setInsightsStatus(STATUS.SUCCESS)
    } catch (err) {
      setInsightsError(err.message)
      setInsightsStatus(STATUS.ERROR)
    }
  }

  async function handleGetNarrative() {
    if (!lastSearch) return
    setNarrativeStatus(STATUS.LOADING)
    setNarrativeData(null)
    setNarrativeError(null)

    try {
      const res = await fetch('/api/narrative/community-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subreddit: lastSearch.subreddit,
          from: lastSearch.fromDate,
          to: lastSearch.toDate,
        }),
      })
      let json
      try {
        json = await res.json()
      } catch {
        throw new Error(
          res.status === 504 || res.status === 502
            ? 'The request timed out while generating the narrative — please try again.'
            : `Server returned a non-JSON response (HTTP ${res.status})`
        )
      }
      if (!res.ok) throw new Error(json.detail ?? `HTTP ${res.status}`)
      setNarrativeData(json)
      setNarrativeStatus(STATUS.SUCCESS)
    } catch (err) {
      setNarrativeError(err.message)
      setNarrativeStatus(STATUS.ERROR)
    }
  }

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.logo}>CommHealth</h1>
        <p className={styles.tagline}>Reddit community analytics</p>
      </header>

      <main className={styles.main}>
        <SearchForm onSearch={handleSearch} loading={insightsStatus === STATUS.LOADING} />

        {insightsStatus === STATUS.LOADING && (
          <div className={styles.notice}>
            <div className={styles.spinner} />
            <p>Fetching data from Reddit — first requests for a new range can take up to a minute.</p>
          </div>
        )}

        {insightsStatus === STATUS.ERROR && (
          <div className={styles.error}>
            <strong>Error:</strong> {insightsError}
          </div>
        )}

        {insightsStatus === STATUS.SUCCESS && insightsData && (
          <HealthDashboard
            data={insightsData}
            onGetNarrative={handleGetNarrative}
            narrativeStatus={narrativeStatus}
            narrativeData={narrativeData}
            narrativeError={narrativeError}
          />
        )}
      </main>
    </div>
  )
}
