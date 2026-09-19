import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ErrorState } from "./imp-ui/FeedbackStates";

type Props = { children: ReactNode };
type State = { error: Error | null };

/** Class boundary with no location remount — safe to wrap `Suspense`. */
export class ViewErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error("View render failed", error, info.componentStack);
    }
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          title="This view crashed while rendering."
          affects="Other product surfaces remain available. Retry this view or open another section from the menu."
          rawDetail={this.state.error.message}
          onRetry={() => this.setState({ error: null })}
        />
      );
    }
    return this.props.children;
  }
}

/** Catches render failures and resets when the route path changes. */
export function RouteErrorBoundary({ children }: Props) {
  const location = useLocation();
  return <ViewErrorBoundary key={location.pathname}>{children}</ViewErrorBoundary>;
}
