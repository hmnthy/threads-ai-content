"use client";

import { useId, useMemo, useRef, useState } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { topicOfUnit, TYPE, UnitText } from "@/components/AppBlock";
import type { PickableUnit } from "@/components/UnitVsChannel";
import { formatPostDateTimeParis } from "@/lib/dates";
import { count, pct, RATE_INFO, type RateKey } from "@/lib/landing";

// So khớp không dấu, không hoa/thường: người đọc không gõ tiếng Việt vẫn tìm được "kinh nghiem" → "kinh nghiệm"
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

// Ô chọn content unit — combobox WAI-ARIA 1.2 (ô gõ + danh sách bật ra): gõ để lọc theo dòng đầu hoặc tên topic tiếng
// Anh, ↑/↓ đi qua danh sách, Enter chọn, Esc đóng (A1/A2: dùng được bằng bàn phím, trình đọc màn hình nghe được dòng
// đang trỏ qua aria-activedescendant). Mỗi dòng: tên topic tiếng Anh TRÊN chữ gốc (B2, `UnitText`) + rate · views · ngày
export function UnitPicker({
  units,
  value,
  onChange,
  rate,
  topicOf,
  topicCount,
}: {
  units: PickableUnit[];
  value: string;
  onChange: (id: string) => void;
  rate: RateKey; // tỉ lệ khối đang so — mỗi dòng hiện đúng tỉ lệ đó (code-reviewer 2026-11-02)
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  // -1 = chưa trỏ dòng nào (vừa gõ / vừa mở): phím ↓ đầu tiên tới dòng 1, Enter chọn dòng 1
  const [active, setActive] = useState(-1);
  const listRef = useRef<HTMLUListElement>(null);
  const baseId = useId();
  const listId = `${baseId}-list`;

  const shown = useMemo(() => {
    const needle = fold(query.trim());
    if (!needle) return units;
    return units.filter((unit) => {
      const topic = topicOfUnit(topicOf, unit.id);
      return fold(`${unit.text} ${typeof topic === "string" ? topic : ""}`).includes(needle);
    });
  }, [units, query, topicOf]);

  const choose = (id: string) => {
    onChange(id);
    setOpen(false);
    setQuery("");
    setActive(-1);
  };
  const move = (next: number) => {
    const index = Math.max(0, Math.min(shown.length - 1, next));
    setActive(index);
    listRef.current?.querySelector<HTMLElement>(`[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" });
  };

  const optionId = (index: number) => `${baseId}-option-${index}`;
  const expanded = open && shown.length > 0;

  return (
    <div className="relative flex flex-col gap-1.5">
      <label htmlFor={`${baseId}-input`} className={TYPE.label}>
        Content unit to compare ({count(units.length)} with recorded views, newest first)
      </label>
      {/* Vòng focus 2px amber trên khung (A2): input tắt outline riêng để không vẽ 2 vòng lồng nhau */}
      <div className="flex min-h-[44px] items-center gap-2 rounded-full border border-border-hairline bg-bg-card px-4 focus-within:border-amber-600 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-amber-600">
        <MagnifyingGlass size={16} aria-hidden="true" className="shrink-0 text-text-muted" />
        <input
          id={`${baseId}-input`}
          type="text"
          role="combobox"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={expanded && active >= 0 ? optionId(active) : undefined}
          autoComplete="off"
          spellCheck={false}
          placeholder="Search first line or topic"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          // Sau khi chọn bằng chuột, focus vẫn ở ô → bấm lại không có onFocus; click mở lại danh sách (code-reviewer)
          onClick={() => setOpen(true)}
          // Đóng sau khi click chọn kịp chạy (mousedown trên dòng chặn blur bằng preventDefault)
          onBlur={() => setOpen(false)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setOpen(true);
              move(active + 1);
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              move(active - 1);
            } else if (event.key === "Enter" && expanded) {
              event.preventDefault();
              choose(shown[Math.max(active, 0)].id);
            } else if (event.key === "Escape" || event.key === "Tab") {
              // Tab: đóng trước khi focus rời ô, để danh sách bị ẩn không kéo focus về <body> (WCAG 2.4.3)
              setOpen(false);
              setActive(-1);
            }
          }}
          className={`min-w-0 flex-1 bg-transparent py-2 ${TYPE.body} text-text-primary outline-none placeholder:text-text-muted`}
        />
      </div>
      {open && shown.length === 0 ? (
        <p className={`m-0 ${TYPE.note}`} role="status">
          No content unit matches “{query.trim()}”. Try a word from an English topic name.
        </p>
      ) : null}
      {/* tabIndex -1: Edge coi danh sách cuộn được là chỗ nhận Tab — focus phải ở lại ô gõ (aria-activedescendant).
          mousedown trên cả danh sách (kể cả thanh cuộn) không làm ô gõ mất focus */}
      <ul
        ref={listRef}
        id={listId}
        role="listbox"
        tabIndex={-1}
        aria-label="Content units with recorded views"
        hidden={!expanded}
        onMouseDown={(event) => event.preventDefault()}
        className="absolute inset-x-0 top-full z-20 m-0 mt-1 max-h-[360px] list-none overflow-y-auto rounded-xl border border-border-hairline bg-bg-card p-1 shadow-[0_8px_24px_rgba(17,24,39,0.12)]"
      >
        {shown.map((unit, index) => (
          <li
            key={unit.id}
            id={optionId(index)}
            data-index={index}
            role="option"
            // APG combobox: aria-selected = dòng đang trỏ; bài đang được so ghi bằng chữ "· selected"
            aria-selected={index === active}
            onMouseEnter={() => setActive(index)}
            onClick={() => choose(unit.id)}
            // Dòng đang trỏ: nền amber nhạt + vạch trái 3px amber — không chỉ dựa vào màu nền (A2)
            className={`flex cursor-pointer flex-col gap-1 rounded-lg border-l-[3px] px-3 py-2.5 ${
              index === active ? "border-amber-600 bg-amber-soft" : "border-transparent"
            }`}
          >
            <UnitText text={unit.text} topic={topicOfUnit(topicOf, unit.id)} topicCount={topicCount} size="cell" />
            <span className={`${TYPE.mono} text-text-secondary`}>
              {pct(unit.rates[rate], RATE_INFO[rate].digits)} {RATE_INFO[rate].label.toLowerCase()} · {count(unit.views)} views
              {unit.timestamp ? ` · ${formatPostDateTimeParis(unit.timestamp)} Paris time` : ""}
              {unit.id === value ? " · selected" : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
