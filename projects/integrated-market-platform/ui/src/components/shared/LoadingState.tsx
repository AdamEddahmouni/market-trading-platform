type Props = {
  label?: string;
  className?: string;
};

export function LoadingState({ label = "Loading…", className }: Props) {
  return (
    <div className={className ? `app-loading ${className}` : "app-loading"} role="status">
      {label}
    </div>
  );
}
