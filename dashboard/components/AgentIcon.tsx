/**
 * AgentIcon Component
 * 
 * Displays customizable SVG icons for agents with color themes
 */

interface AgentIconProps {
  icon?: string;
  color?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

// Icon library - clean vector icons
const ICONS = {
  robot: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  ),
  brain: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
    </svg>
  ),
  chip: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M15 2v2" />
      <path d="M15 20v2" />
      <path d="M2 15h2" />
      <path d="M2 9h2" />
      <path d="M20 15h2" />
      <path d="M20 9h2" />
      <path d="M9 2v2" />
      <path d="M9 20v2" />
    </svg>
  ),
  shield: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  lightning: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  eye: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
  gear: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v6m0 6v6m5.196-15.196l-4.242 4.242M7.757 16.243l-4.242 4.242M23 12h-6m-6 0H1m20.196-5.196l-4.242 4.242M7.757 7.757 3.515 3.515" />
    </svg>
  ),
  sparkles: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      <path d="M5 3v4" />
      <path d="M19 17v4" />
      <path d="M3 5h4" />
      <path d="M17 19h4" />
    </svg>
  ),
  target: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  ),
  diamond: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.7 10.3a2.41 2.41 0 0 0 0 3.41l7.59 7.59a2.41 2.41 0 0 0 3.41 0l7.59-7.59a2.41 2.41 0 0 0 0-3.41l-7.59-7.59a2.41 2.41 0 0 0-3.41 0Z" />
    </svg>
  ),
  globe: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  star: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  ),
};

// Color themes
const COLORS = {
  purple: {
    bg: 'bg-purple-50',
    text: 'text-purple-600',
    border: 'border-purple-100',
  },
  blue: {
    bg: 'bg-blue-50',
    text: 'text-blue-600',
    border: 'border-blue-100',
  },
  green: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-600',
    border: 'border-emerald-100',
  },
  red: {
    bg: 'bg-red-50',
    text: 'text-red-500',
    border: 'border-red-100',
  },
  yellow: {
    bg: 'bg-amber-50',
    text: 'text-amber-600',
    border: 'border-amber-100',
  },
  cyan: {
    bg: 'bg-cyan-50',
    text: 'text-cyan-600',
    border: 'border-cyan-100',
  },
  pink: {
    bg: 'bg-pink-50',
    text: 'text-pink-600',
    border: 'border-pink-100',
  },
  indigo: {
    bg: 'bg-indigo-50',
    text: 'text-indigo-600',
    border: 'border-indigo-100',
  },
};

// Size mappings
const SIZES = {
  sm: 'w-8 h-8',
  md: 'w-10 h-10',
  lg: 'w-12 h-12',
  xl: 'w-16 h-16',
};

const ICON_SIZES = {
  sm: 'w-4 h-4',
  md: 'w-5 h-5',
  lg: 'w-6 h-6',
  xl: 'w-8 h-8',
};

export default function AgentIcon({ 
  icon = 'robot', 
  color = 'purple', 
  size = 'md',
  className = ''
}: AgentIconProps) {
  const colorTheme = COLORS[color as keyof typeof COLORS] || COLORS.purple;
  const iconSvg = ICONS[icon as keyof typeof ICONS] || ICONS.robot;

  return (
    <div 
      className={`
        ${SIZES[size]} 
        ${colorTheme.bg} 
        ${colorTheme.text} 
        ${colorTheme.border}
        rounded-full 
        flex 
        items-center 
        justify-center 
        flex-shrink-0 
        border
        ${className}
      `}
    >
      <div className={ICON_SIZES[size]}>
        {iconSvg}
      </div>
    </div>
  );
}

// Export icon and color options for pickers
export const AVAILABLE_ICONS = Object.keys(ICONS);
export const AVAILABLE_COLORS = Object.keys(COLORS);

// Icon Picker Component
interface IconPickerProps {
  value: string;
  onChange: (icon: string) => void;
  color: string;
}

export function IconPicker({ value, onChange, color }: IconPickerProps) {
  return (
    <div className="grid grid-cols-4 gap-2">
      {AVAILABLE_ICONS.map((iconName) => (
        <button
          key={iconName}
          onClick={() => onChange(iconName)}
          className={`p-3 rounded-lg border-2 transition-all ${
            value === iconName
              ? 'border-accent-500 bg-accent-50'
              : 'border-surface-200 hover:border-surface-300 bg-white'
          }`}
        >
          <AgentIcon icon={iconName} color={color} size="sm" className="mx-auto" />
          <p className="text-xs text-ink-muted mt-1 capitalize">{iconName}</p>
        </button>
      ))}
    </div>
  );
}

// Color Picker Component
interface ColorPickerProps {
  value: string;
  onChange: (color: string) => void;
}

export function ColorPicker({ value, onChange }: ColorPickerProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {AVAILABLE_COLORS.map((colorName) => {
        const theme = COLORS[colorName as keyof typeof COLORS];
        return (
          <button
            key={colorName}
            onClick={() => onChange(colorName)}
            className={`
              w-10 h-10 rounded-full border-2 transition-all
              ${theme.bg} ${theme.border}
              ${value === colorName ? 'ring-2 ring-accent-500 ring-offset-2' : 'hover:scale-110'}
            `}
            title={colorName}
          >
            <span className={`block w-full h-full rounded-full ${theme.text}`}></span>
          </button>
        );
      })}
    </div>
  );
}
