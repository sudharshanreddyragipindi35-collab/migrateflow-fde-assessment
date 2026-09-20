import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IntegrationAudit } from "../src/pages/IntegrationAudit";
import { api } from "../src/api/client";

vi.mock("../src/api/client", () => ({ api: { pushes: vi.fn(), retry: vi.fn(), rollback: vi.fn() } }));
const failed = { target_write_id: "target-1", source_record_id: "1", status: "RETRYABLE_FAILURE", retry_count: 0 };

describe("migration results", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  it("shows actionable failures and refreshes after retry", async () => {
    vi.mocked(api.pushes).mockResolvedValue([failed]);
    vi.mocked(api.retry).mockResolvedValue([{ ...failed, status: "SUCCESS", retry_count: 1 }]);
    render(<IntegrationAudit batchId="batch-1" />);
    expect(await screen.findByText("Temporary failure")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry failed records" }));
    expect(await screen.findByText("All approved records were sent successfully.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry failed records" })).toBeDisabled();
  });
  it("shows errors instead of silently reporting success", async () => {
    vi.mocked(api.pushes).mockResolvedValue([failed]);
    vi.mocked(api.retry).mockRejectedValue(new Error("Destination unavailable"));
    render(<IntegrationAudit batchId="batch-1" />);
    await screen.findByText("Temporary failure");
    fireEvent.click(screen.getByRole("button", { name: "Retry failed records" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Destination unavailable");
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry failed records" })).toBeEnabled());
  });
  it("does not allow retries after records have been undone", async () => {
    vi.mocked(api.pushes).mockResolvedValue([failed, { ...failed, target_write_id: "target-2", status: "ROLLED_BACK" }]);
    render(<IntegrationAudit batchId="batch-1" />);
    await screen.findByText("Undone");
    expect(screen.getByRole("button", { name: "Retry failed records" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Undo sent records" })).toBeDisabled();
  });
});
