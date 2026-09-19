import { lazy } from "react";
import type { RadarPageProps, RadarTab } from "./radar/RadarPage";
import type { Mode } from "./mode-session/types";

const RadarPage = lazy(() =>
  import("./radar/RadarPage").then((module) => ({ default: module.RadarPage })),
);

type Props = Omit<RadarPageProps, "mode" | "tab"> & {
  mode: Mode;
  tab?: RadarTab;
};

export function ModeRadarRoute({ mode, tab = "opportunities", ...actions }: Props) {
  return <RadarPage mode={mode} tab={tab} {...actions} />;
}
