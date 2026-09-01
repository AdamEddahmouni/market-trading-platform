import { Link } from "react-router-dom";
import {
  WORKSPACE_LANE_REGISTRY,
  workspaceLanePath,
  type LaneRegistryEntry,
  type WorkspaceModuleId,
} from "./workspace-module-shared/laneRegistry";

export type { WorkspaceModuleId };

type Props = {
  instrumentId: string;
  active: WorkspaceModuleId;
  squeezeQuery?: string;
};

export function WorkspaceModuleNav({ instrumentId, active, squeezeQuery = "" }: Props) {
  const links = [...WORKSPACE_LANE_REGISTRY].sort((left, right) => left.navOrder - right.navOrder);
  return (
    <nav className="workspace-module-nav" aria-label="Workspace modules">
      {links.map((link: LaneRegistryEntry) => (
        <Link
          key={link.id}
          className={active === link.id ? "active" : undefined}
          to={workspaceLanePath(instrumentId, link.id, link.id === "squeeze" ? squeezeQuery : "")}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
