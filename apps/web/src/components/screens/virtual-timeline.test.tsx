import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createTimelineFixtures, VirtualTimeline } from "./virtual-timeline";

describe("VirtualTimeline", () => {
  it("keeps a 5,000-message fixture timeline usable with a bounded DOM", () => {
    const items = createTimelineFixtures(5_000);
    render(<VirtualTimeline items={items} />);
    const timeline = screen.getByRole("list", { name: "Timeline virtualizada com 5000 mensagens" });
    expect(screen.getAllByRole("listitem").length).toBeLessThan(20);
    fireEvent.scroll(timeline, { target: { scrollTop: 4_999 * 52 } });
    expect(screen.getByText("Mensagem 5000")).toBeTruthy();
    expect(screen.getAllByRole("listitem").length).toBeLessThan(20);
  });
});
