import assert from "node:assert/strict";
import test from "node:test";

import {
  addOutlineSection,
  canConfirmOutline,
  moveOutlineSection,
  normalizeOutlineSections,
  removeOutlineSection,
  updateOutlineSection,
  validateOutlineSections,
} from "../components/outline/outlineEditor.ts";
import type { OutlineSection } from "../types/data.ts";

const sections: OutlineSection[] = [
  { id: "section-1", title: "行业背景", description: "背景说明" },
  { id: "section-2", title: "市场现状", description: "市场说明" },
  { id: "section-3", title: "未来趋势", description: "趋势说明" },
];

test("updateOutlineSection updates only the selected section", () => {
  const result = updateOutlineSection(sections, "section-2", {
    title: "竞争格局",
  });

  assert.notEqual(result, sections);
  assert.equal(result[0], sections[0]);
  assert.deepEqual(result[1], {
    id: "section-2",
    title: "竞争格局",
    description: "市场说明",
  });
});

test("addOutlineSection adds a blank section but never exceeds five", () => {
  const four = addOutlineSection(sections, () => "section-4");
  const five = addOutlineSection(four, () => "section-5");
  const stillFive = addOutlineSection(five, () => "section-6");

  assert.deepEqual(four[3], {
    id: "section-4",
    title: "",
    description: "",
  });
  assert.equal(stillFive.length, 5);
  assert.equal(stillFive, five);
});

test("removeOutlineSection never leaves fewer than three sections", () => {
  assert.equal(removeOutlineSection(sections, "section-2"), sections);

  const four = addOutlineSection(sections, () => "section-4");
  const result = removeOutlineSection(four, "section-2");
  assert.deepEqual(
    result.map((section) => section.id),
    ["section-1", "section-3", "section-4"],
  );
});

test("moveOutlineSection reorders sections and ignores boundaries", () => {
  assert.equal(moveOutlineSection(sections, 0, -1), sections);
  assert.equal(moveOutlineSection(sections, 2, 1), sections);

  const moved = moveOutlineSection(sections, 1, -1);
  assert.deepEqual(
    moved.map((section) => section.id),
    ["section-2", "section-1", "section-3"],
  );
});

test("validateOutlineSections rejects blank and duplicate titles", () => {
  assert.equal(validateOutlineSections(sections), null);
  assert.match(
    validateOutlineSections([
      sections[0],
      { ...sections[1], title: "  " },
      sections[2],
    ]) ?? "",
    /标题不能为空/,
  );
  assert.match(
    validateOutlineSections([
      sections[0],
      { ...sections[1], title: " 行业背景 " },
      sections[2],
    ]) ?? "",
    /标题不能重复/,
  );
});

test("canConfirmOutline disables confirmation for an invalid outline", () => {
  assert.equal(canConfirmOutline(sections), true);
  assert.equal(
    canConfirmOutline([
      sections[0],
      { ...sections[1], title: "  " },
      sections[2],
    ]),
    false,
  );
});

test("normalizeOutlineSections trims text without changing section ids", () => {
  const result = normalizeOutlineSections([
    { id: "section-1", title: " 行业背景 ", description: " 背景说明 " },
    sections[1],
    sections[2],
  ]);

  assert.deepEqual(result[0], {
    id: "section-1",
    title: "行业背景",
    description: "背景说明",
  });
});
