import { useState } from 'react'
import styles from './SearchForm.module.css'

function defaultDates() {
  const to = new Date()
  to.setDate(to.getDate() - 1)
  const from = new Date(to)
  const fmt = d => d.toISOString().split('T')[0]
  return { from: fmt(from), to: fmt(to) }
}

export default function SearchForm({ onSearch, loading }) {
  const defaults = defaultDates()
  const [subreddit, setSubreddit] = useState('')
  const [fromDate, setFromDate] = useState(defaults.from)
  const [toDate, setToDate] = useState(defaults.to)

  function handleSubmit(e) {
    e.preventDefault()
    if (!subreddit.trim()) return
    onSearch({ subreddit: subreddit.trim(), fromDate, toDate })
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="subreddit">Subreddit</label>
        <div className={styles.inputWrapper}>
          <span className={styles.prefix}>r/</span>
          <input
            id="subreddit"
            className={styles.input}
            type="text"
            value={subreddit}
            onChange={e => setSubreddit(e.target.value)}
            placeholder="LocalLLaMA"
            required
            disabled={loading}
          />
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="from">From</label>
        <input
          id="from"
          className={styles.input}
          type="date"
          value={fromDate}
          onChange={e => setFromDate(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="to">To</label>
        <input
          id="to"
          className={styles.input}
          type="date"
          value={toDate}
          onChange={e => setToDate(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <button className={styles.button} type="submit" disabled={loading}>
        {loading ? 'Fetching…' : 'Analyze'}
      </button>

      <p className={styles.hint}>
        First fetch is slow: a single day on a large subreddit takes ~30–90s. Cached after that.
      </p>
    </form>
  )
}
