import { Component } from "react";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app">
          <div className="error-screen">
            <div className="error-icon">!</div>
            <div className="error-title">Application error</div>
            <div className="error-message">{this.state.error?.message || "Unknown error"}</div>
            <div className="error-hint">
              Try refreshing the page. If the problem persists, check the browser console for details.
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
