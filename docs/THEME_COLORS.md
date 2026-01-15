# Todo App Theme Colors

## Background Colors

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Primary Background (body) | `#f5f5f5` | `#1a1a1a` |
| Secondary Background (cards, inputs) | `white` | `#2d2d2d` |
| Tertiary Background (panels, controls) | `#f9f9f9` | `#242424` |
| Hover Background | `#F8F9FA` | `#3a3a3a` |

## Text Colors

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Primary Text | `#333` | `#e0e0e0` |
| Secondary Text | `#666` | `#b0b0b0` |
| Muted Text | `#999` | `#808080` |

## Border Colors

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Primary Border | `#ddd` | `#404040` |
| Secondary Border | `#e0e0e0` | `#353535` |
| Hover Border | `#B8C5D0` | `#505050` |

## Shadow Colors

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Standard Shadow | `rgba(0,0,0,0.1)` | `rgba(0,0,0,0.3)` |
| Hover Shadow | `rgba(0,0,0,0.05)` | `rgba(0,0,0,0.2)` |

## Code & Link Colors

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Code Background | `#f4f4f4` | `#1e1e1e` |
| Link Color | `#0066cc` | `#6db3f2` |

## Task State Colors

| State | Light Theme | Dark Theme |
|-------|-------------|------------|
| **Done Task Background** | `#e8f5e9` (light green) | `#1e3a1e` (dark green) |
| **Done Task Border** | `#4caf50` (green) | `#2e7d32` (darker green) |
| **Current Task Background** | `#fff9e6` (light yellow) | `#3a3420` (dark yellow) |
| **Current Task Border** | `#ff9800` (orange) | `#d68200` (darker orange) |

## Action Buttons

### Add Button (➕)

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Background | `#E6F4EA` | `#1e3a1e` |
| Text Color | `#1E7F43` | `#81c784` |
| Border | `#C3E6CB` | (implicit) |
| Hover Background | `#D1E7DD` | `#2e4a2e` |

### Set Current Button (▶️)

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Background | `#E3F2FD` | `#1a2a3a` |
| Text Color | `#1565C0` | `#64b5f6` |
| Border | `#90CAF9` | `#2a4a5a` |
| Hover Background | `#BBDEFB` | `#2a3a4a` |

### Focus Button (🎯)

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Background | `#FFF4E6` | `#3a2a1a` |
| Text Color | `#E65100` | `#ffb74d` |
| Border | `#FFCC80` | `#5a3a1a` |
| Hover Background | `#FFE0B2` | `#4a3a2a` |

### Delete Button (🗑️)

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Background | `#FDEAEA` | `#3a1a1a` |
| Text Color | `#B3261E` | `#ef5350` |
| Border | `#F5C2C7` | `#5a2a2a` |
| Hover Background | `#F8D7DA` | `#4a2a2a` |

## Workspace Buttons

### Standard Workspace Buttons (Switch, Rename)

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Background | `var(--bg-secondary)` (white) | `var(--bg-secondary)` (#2d2d2d) |
| Text Color | `var(--text-primary)` (#333) | `var(--text-primary)` (#e0e0e0) |
| Border | `var(--border-primary)` (#ddd) | `var(--border-primary)` (#404040) |
| Hover Background | `var(--bg-hover)` (#F8F9FA) | `var(--bg-hover)` (#3a3a3a) |

### Workspace Delete Button

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Background | `#ffebee` | `#3a1a1a` |
| Text Color | `#c62828` | `#ef5350` |
| Border | `#ffcdd2` | `#5a2a2a` |

## Theme Toggle Button

| Property | Light Theme | Dark Theme |
|----------|-------------|------------|
| Icon | 🌙 (moon) | ☀️ (sun) |
| Background | `var(--bg-tertiary)` (#f9f9f9) | `var(--bg-tertiary)` (#242424) |
| Border | `var(--border-primary)` (#ddd) | `var(--border-primary)` (#404040) |
| Hover Background | `var(--bg-hover)` (#F8F9FA) | `var(--bg-hover)` (#3a3a3a) |

## Outliner Panel

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Background | `var(--bg-tertiary)` (#f9f9f9) | `var(--bg-tertiary)` (#242424) |
| Border | `var(--border-primary)` (#ddd) | `var(--border-primary)` (#404040) |
| Shadow | `0 1px 3px var(--shadow)` | `0 1px 3px var(--shadow)` |
| Hover Item Background | `var(--bg-hover)` (#F8F9FA) | `var(--bg-hover)` (#3a3a3a) |
| Current Task Highlight | `var(--bg-current)` (#fff9e6) | `var(--bg-current)` (#3a3420) |

## Focus Mode Banner

| Element | Light Theme | Dark Theme |
|---------|-------------|------------|
| Background | `var(--bg-current)` (#fff9e6) | `var(--bg-current)` (#3a3420) |
| Border | `var(--border-current)` (#ff9800) | `var(--border-current)` (#d68200) |
| Exit Button Background | `var(--bg-secondary)` (white) | `var(--bg-secondary)` (#2d2d2d) |
| Exit Button Border | `var(--border-primary)` (#ddd) | `var(--border-primary)` (#404040) |

## Design Principles

### Light Theme
- Uses bright, airy colors with soft backgrounds
- High contrast between text (#333) and backgrounds (white)
- Pastel accent colors for different states and actions
- Subtle shadows with low opacity

### Dark Theme
- Uses dark, muted backgrounds to reduce eye strain
- Lower contrast between text (#e0e0e0) and backgrounds
- Deeper, saturated colors for accents
- Stronger shadows for depth perception
- All interactive elements maintain clear visual hierarchy

## Color Categories

1. **Greens**: Add/Create actions, Done states
2. **Blues**: Current task selection
3. **Oranges**: Focus mode, Current task borders
4. **Reds**: Delete/Destructive actions
5. **Grays**: Structural elements, disabled states
