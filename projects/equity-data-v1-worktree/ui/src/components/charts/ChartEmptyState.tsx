type Props = {
  message: string;
};

export function ChartEmptyState({ message }: Props) {
  return (
    <div className="chart-empty" role="status">
      {message}
    </div>
  );
}
