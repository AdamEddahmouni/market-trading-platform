import type { QueryClient } from "@tanstack/react-query";

// Queries whose answers depend on a provider the operator can connect or configure.
const PROVIDER_BACKED = ["screener-setup", "screener-news", "screener-news-instrument", "main-screener", "screener-participants"];

export function refreshProviderQueries(queryClient: QueryClient) {
  void queryClient.invalidateQueries({
    predicate: (query) => {
      const head = query.queryKey[0];
      return typeof head === "string" && PROVIDER_BACKED.some((prefix) => head === prefix || head.startsWith(`${prefix}-`));
    },
  });
}
