import styles from './ContributorTable.module.css'

export default function ContributorTable({ contributors }) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>#</th>
            <th className={styles.th}>Username</th>
            <th className={styles.th}>Comments</th>
            <th className={styles.th}>Posts</th>
            <th className={styles.th}>Total</th>
          </tr>
        </thead>
        <tbody>
          {contributors.map((c, i) => (
            <tr key={c.username} className={styles.row}>
              <td className={`${styles.td} ${styles.rank}`}>{i + 1}</td>
              <td className={`${styles.td} ${styles.username}`}>
                <a
                  href={`https://reddit.com/u/${c.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  u/{c.username}
                </a>
              </td>
              <td className={styles.td}>{c.comment_count.toLocaleString()}</td>
              <td className={styles.td}>{c.post_count.toLocaleString()}</td>
              <td className={`${styles.td} ${styles.total}`}>{c.total_contributions.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
