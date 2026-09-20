import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    window.localStorage.clear();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      mode: "ollama", provider: "Ollama", model: "qwen2.5:7b-instruct", status: "ready", parallel_workers: 3,
      failover_provider: "Anthropic", failover_status: "configured",
    }), { status: 200, headers: { "Content-Type": "application/json" } })));
  });

  it("renders the product navigation and accessible uploader", () => {
    render(<App />);
    expect(screen.getByRole("link", { name: "MigrateFlow home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Drop CSV or Excel files/i })).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
    expect(screen.getByText(/Accepted: .csv and .xlsx/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Choose employee files")).toHaveAttribute("multiple");
  });

  it("shows an unmistakable empty live state", async () => {
    render(<App />);
    screen.getByRole("button", { name: /Analyze and map/ }).click();
    expect(await screen.findByText("No active migration")).toBeInTheDocument();
  });

  it("rejects an unsupported upload before calling the API", () => {
    render(<App />);
    const input = screen.getByLabelText("Choose employee files");
    fireEvent.change(input, { target: { files: [new File(["x"], "employees.exe")] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a CSV (.csv) or Excel (.xlsx) file");
    expect(screen.getByRole("button", { name: "Start autopilot migration" })).toBeDisabled();
  });

  it("offers clear autopilot and human-in-the-loop modes", () => {
    render(<App />);
    expect(screen.getByRole("radio", { name: /Autopilot/i })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /Human-in-the-loop/i }));
    expect(screen.getByRole("radio", { name: /Human-in-the-loop/i })).toBeChecked();
    expect(screen.getByRole("button", { name: "Start guided migration" })).toBeDisabled();
  });

  it("shows the active model provider and readiness", async () => {
    render(<App />);
    expect(await screen.findByText(/Ollama \/ qwen2.5:7b-instruct · 3 parallel workers · ready/i)).toBeInTheDocument();
  });

  it("shows the configured failover provider", async () => {
    render(<App />);
    expect(await screen.findByText(/failover: Anthropic configured/i)).toBeInTheDocument();
  });
});
