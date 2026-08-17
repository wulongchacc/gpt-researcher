interface OutlineConfirmationToggleProps {
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

export default function OutlineConfirmationToggle({
  checked,
  disabled = false,
  onChange,
}: OutlineConfirmationToggleProps) {
  return (
    <label
      className={`flex items-center justify-between gap-4 py-2 ${
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      }`}
    >
      <span>
        <span className="block font-medium text-white">研究前确认提纲</span>
        <span className="block text-sm text-gray-400">
          先生成并编辑报告结构，确认后再开始研究
        </span>
      </span>
      <span className="relative h-6 w-11 shrink-0">
        <input
          type="checkbox"
          role="switch"
          aria-label="研究前确认提纲"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
        />
        <span className="absolute inset-0 rounded-full bg-gray-600 transition-colors peer-checked:bg-teal-500 peer-focus-visible:ring-2 peer-focus-visible:ring-teal-300 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-gray-900 peer-disabled:bg-gray-700" />
        <span className="absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform peer-checked:translate-x-5 peer-disabled:bg-gray-400" />
      </span>
    </label>
  );
}
