'use client';
import * as Select from '@radix-ui/react-select';
import { ChevronDown, Check } from 'lucide-react';
export function FilterSelect({
  label,
  value,
  items,
  onChange,
}: {
  label: string;
  value: string;
  items: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="filter">
      <span>{label}</span>
      <Select.Root value={value} onValueChange={onChange}>
        <Select.Trigger aria-label={label}>
          <Select.Value />
          <ChevronDown size={14} />
        </Select.Trigger>
        <Select.Portal>
          <Select.Content className="select-content" position="popper" sideOffset={8}>
            <Select.Viewport>
              {items.map((i) => (
                <Select.Item key={i.value} value={i.value} className="select-item">
                  <Select.ItemText>{i.label}</Select.ItemText>
                  <Select.ItemIndicator>
                    <Check size={12} />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </label>
  );
}
