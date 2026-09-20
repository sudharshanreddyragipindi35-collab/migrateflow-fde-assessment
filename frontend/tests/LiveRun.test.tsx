import { describe, expect, it } from "vitest";
import { friendlyWorkflowMessage } from "../src/utils/workflow";

describe("LiveRun error guidance", () => {
  it("turns incomplete model output into safe recovery guidance", () => {
    const message = friendlyWorkflowMessage("Model batch response did not cover every source column");
    expect(message).toContain("No data was changed");
    expect(message).toContain("retry once");
  });
});
