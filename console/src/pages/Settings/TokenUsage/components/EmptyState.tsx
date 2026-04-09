import styles from "../index.module.less";

interface EmptyStateProps {
  message: string;
  icon?: string;
  className?: string;
}

export function EmptyState({ message, icon, className }: EmptyStateProps) {
  return (
    <div className={`${styles.emptyState} ${className ?? ""}`}>
      <span className={styles.emptyIcon}>{icon ?? "📊"}</span>
      <span>{message}</span>
    </div>
  );
}
