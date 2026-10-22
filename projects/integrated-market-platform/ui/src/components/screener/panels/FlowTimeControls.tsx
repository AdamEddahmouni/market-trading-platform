import { type FlowRange, type FlowResolution } from "../../../api/screenerPanels";

export default function FlowTimeControls({ range, resolution, onRange, onResolution, crypto }: {
  range: FlowRange; resolution: FlowResolution; onRange: (range: FlowRange) => void;
  onResolution: (resolution: FlowResolution) => void; crypto: boolean;
}) {
  return <div className="screener-flow-controls">
    <div role="group" aria-label="Flow time range">
      <span>Range</span>{(["1m", "5m", "15m", "1h", "session"] as const).map(value =>
        <button key={value} type="button" aria-pressed={range === value} onClick={() => onRange(value)}>
          {value === "session" ? crypto ? "UTC day" : "Session" : value}</button>)}
    </div>
    <label>Resolution <select value={resolution} onChange={event => onResolution(event.target.value as FlowResolution)}>
      {(["auto", "1s", "5s", "15s", "1m", "5m"] as const).map(value => <option key={value} value={value}>{value === "auto" ? "Auto" : value}</option>)}
    </select></label>
  </div>;
}
