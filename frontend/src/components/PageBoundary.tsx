import { Component, type ReactNode } from "react";
export class PageBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <section className="panel">
          <h1>Unable to display this page</h1>
          <p role="alert">
            The API returned unexpected data. Check the backend and reload the
            page.
          </p>
          <button onClick={() => window.location.reload()}>Reload page</button>
        </section>
      );
    return this.props.children;
  }
}
