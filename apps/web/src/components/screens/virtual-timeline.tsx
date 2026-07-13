"use client";

import { useState } from "react";

export type TimelineFixture = { id: string; author: string; body: string };

export function createTimelineFixtures(count: number): TimelineFixture[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `fixture-message-${index + 1}`,
    author: index % 5 === 0 ? "Agente BigHead" : "Operador",
    body: `Mensagem ${String(index + 1).padStart(4, "0")}`
  }));
}

export function VirtualTimeline({ items, height = 320, rowHeight = 52 }: { items: TimelineFixture[]; height?: number; rowHeight?: number }) {
  const [scrollTop, setScrollTop] = useState(0);
  const overscan = 4;
  const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleCount = Math.ceil(height / rowHeight) + overscan * 2;
  const last = Math.min(items.length, first + visibleCount);

  return (
    <div
      aria-label={`Timeline virtualizada com ${items.length} mensagens`}
      className="bh-virtual-timeline"
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      role="list"
      tabIndex={0}
      style={{ height, overflowY: "auto" }}
    >
      <div style={{ height: items.length * rowHeight, position: "relative" }}>
        {items.slice(first, last).map((item, offset) => (
          <div
            className="bh-chat-message"
            data-index={first + offset}
            key={item.id}
            role="listitem"
            style={{ height: rowHeight, left: 0, position: "absolute", right: 0, top: (first + offset) * rowHeight }}
          >
            <strong>{item.author}</strong>
            <span>{item.body}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
