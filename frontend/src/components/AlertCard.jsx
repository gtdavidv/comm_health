import styles from './AlertCard.module.css'

export default function AlertCard({ alert }) {
  const isCritical = alert.severity === 'critical'
  return (
    <div className={`${styles.card} ${isCritical ? styles.critical : styles.warning}`}>
      <div className={styles.top}>
        <span className={styles.badge}>{alert.severity}</span>
        <span className={styles.code}>{alert.code}</span>
      </div>
      <p className={styles.message}>{alert.message}</p>
    </div>
  )
}
