import { Component, type ReactNode, type ErrorInfo } from "react";
import { Alert, Button, Stack, Text } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches descendant render errors and renders a configurable fallback with
 * a retry callback. MUST NOT expose stack traces or internal details.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    const err =
      error instanceof Error
        ? error
        : new Error("An unexpected error occurred");
    return { error: err };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // Error telemetry hook — do not log sensitive error details to console in production
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    const { children, fallback } = this.props;

    if (error) {
      if (fallback) return fallback(error, this.handleReset);
      return (
        <Stack p="md" align="center">
          <Alert
            icon={<IconAlertTriangle size={16} />}
            title="Something went wrong"
            color="red"
            variant="light"
          >
            <Text size="sm">An error occurred while loading this content.</Text>
          </Alert>
          <Button variant="light" size="xs" onClick={this.handleReset}>
            Try again
          </Button>
        </Stack>
      );
    }

    return children;
  }
}
