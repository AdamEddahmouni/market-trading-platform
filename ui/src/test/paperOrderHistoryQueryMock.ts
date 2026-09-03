import { vi } from "vitest";

export function createPaperOrderHistoryInfiniteQueryMock(orders: Record<string, unknown>[] = []) {
  return {
    data: {
      pages: [
        {
          orders,
          fills: [],
          next_cursor: null,
          total_count: orders.length,
          page_size: 25,
        },
      ],
    },
    isLoading: false,
    isError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  };
}
