type Props = {
  source: string;
  method?: string;
};

export function ChartProvenance({ source, method }: Props) {
  return (
    <p className="chart-provenance">
      Source: {source}
      {method ? ` · ${method}` : ""}
    </p>
  );
}
