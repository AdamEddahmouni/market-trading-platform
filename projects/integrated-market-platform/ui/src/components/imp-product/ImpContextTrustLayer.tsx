import { useState } from "react";
import type { ContextResponse } from "../../api/client";
import { ImpCapabilityStrip } from "./ImpCapabilityStrip";
import { ImpProviderMatrixDrawer } from "./ImpProviderMatrixDrawer";

type Props = {
  context: ContextResponse;
};

export function ImpContextTrustLayer({ context }: Props) {
  const [providerMatrixOpen, setProviderMatrixOpen] = useState(false);

  return (
    <>
      <ImpCapabilityStrip
        capabilityStates={context.capability_states}
        onOpenProviderMatrix={() => setProviderMatrixOpen(true)}
      />
      <ImpProviderMatrixDrawer
        open={providerMatrixOpen}
        onClose={() => setProviderMatrixOpen(false)}
        capabilityStates={context.capability_states}
      />
    </>
  );
}
