export interface OutlineRequestGate {
  begin: () => number | null;
  finish: (requestId: number) => boolean;
  cancel: () => void;
  isActive: () => boolean;
}

export const createOutlineRequestGate = (): OutlineRequestGate => {
  let sequence = 0;
  let activeRequestId: number | null = null;

  return {
    begin: () => {
      if (activeRequestId !== null) return null;
      sequence += 1;
      activeRequestId = sequence;
      return activeRequestId;
    },
    finish: (requestId) => {
      if (activeRequestId !== requestId) return false;
      activeRequestId = null;
      return true;
    },
    cancel: () => {
      sequence += 1;
      activeRequestId = null;
    },
    isActive: () => activeRequestId !== null,
  };
};
