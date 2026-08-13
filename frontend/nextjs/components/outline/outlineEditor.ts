import type { OutlineSection } from "../../types/data";

export const MIN_OUTLINE_SECTIONS = 3;
export const MAX_OUTLINE_SECTIONS = 5;

type EditableSectionFields = Pick<OutlineSection, "title" | "description">;

export const updateOutlineSection = (
  sections: OutlineSection[],
  sectionId: string,
  changes: Partial<EditableSectionFields>,
): OutlineSection[] =>
  sections.map((section) =>
    section.id === sectionId ? { ...section, ...changes } : section,
  );

export const addOutlineSection = (
  sections: OutlineSection[],
  createId: () => string,
): OutlineSection[] => {
  if (sections.length >= MAX_OUTLINE_SECTIONS) return sections;

  return [
    ...sections,
    { id: createId(), title: "", description: "" },
  ];
};

export const removeOutlineSection = (
  sections: OutlineSection[],
  sectionId: string,
): OutlineSection[] => {
  if (sections.length <= MIN_OUTLINE_SECTIONS) return sections;
  return sections.filter((section) => section.id !== sectionId);
};

export const moveOutlineSection = (
  sections: OutlineSection[],
  index: number,
  offset: -1 | 1,
): OutlineSection[] => {
  const destination = index + offset;
  if (index < 0 || index >= sections.length || destination < 0 || destination >= sections.length) {
    return sections;
  }

  const reordered = [...sections];
  [reordered[index], reordered[destination]] = [
    reordered[destination],
    reordered[index],
  ];
  return reordered;
};

export const validateOutlineSections = (
  sections: OutlineSection[],
): string | null => {
  if (
    sections.length < MIN_OUTLINE_SECTIONS ||
    sections.length > MAX_OUTLINE_SECTIONS
  ) {
    return `提纲需要包含 ${MIN_OUTLINE_SECTIONS}–${MAX_OUTLINE_SECTIONS} 个章节`;
  }

  const normalizedTitles = sections.map((section) => section.title.trim());
  const blankIndex = normalizedTitles.findIndex((title) => !title);
  if (blankIndex >= 0) {
    return `第 ${blankIndex + 1} 章标题不能为空`;
  }

  const uniqueTitles = new Set(normalizedTitles.map((title) => title.toLocaleLowerCase()));
  if (uniqueTitles.size !== normalizedTitles.length) {
    return "章节标题不能重复";
  }

  return null;
};

export const canConfirmOutline = (sections: OutlineSection[]): boolean =>
  validateOutlineSections(sections) === null;

export const normalizeOutlineSections = (
  sections: OutlineSection[],
): OutlineSection[] =>
  sections.map((section) => ({
    ...section,
    title: section.title.trim(),
    description: section.description.trim(),
  }));
