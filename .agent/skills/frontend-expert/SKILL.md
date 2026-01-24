---
name: frontend-expert
description: "Frontend development expert specializing in React 18+ with Vite, TypeScript, Tailwind CSS, React Query (for API data fetching), Zustand (for UI state management), and TradingView Advanced Charts Widget integration. Use when reviewing, debugging, or fixing frontend code issues including: (1) React component architecture problems, (2) TypeScript type errors, (3) Tailwind CSS styling issues, (4) React Query caching/fetching problems, (5) Zustand state management bugs, (6) TradingView widget integration issues, (7) Build/bundling errors with Vite."
---

# Frontend Expert

Expert reviewer for modern React frontend applications built with Vite, TypeScript, Tailwind CSS, React Query, Zustand, and TradingView widgets.

## Review Process

1. **Identify the scope** - Determine which files/components need review
2. **Check architecture** - Verify component structure follows best practices
3. **Validate types** - Ensure TypeScript types are correct and complete
4. **Review state management** - Check React Query and Zustand usage patterns
5. **Inspect styling** - Verify Tailwind CSS implementation
6. **Test integrations** - Validate TradingView widget configuration

---

## React 18+ Best Practices

### Component Architecture

```tsx
// Prefer function components with explicit typing
interface Props {
  marketId: string;
  onSelect: (id: string) => void;
}

export function MarketCard({ marketId, onSelect }: Props) {
  // Hooks at top level
  const { data, isLoading } = useMarketData(marketId);
  
  // Early returns for loading/error states
  if (isLoading) return <Skeleton />;
  
  return (
    <div onClick={() => onSelect(marketId)}>
      {/* Component JSX */}
    </div>
  );
}
```

### Common Issues to Fix

| Issue | Solution |
|-------|----------|
| Missing `key` prop in lists | Add unique `key` from data ID, not array index |
| useEffect with missing deps | Include all referenced values in dependency array |
| Inline functions in props | Memoize with `useCallback` when passed to memoized children |
| Complex state in useState | Split into multiple states or use `useReducer` |
| Prop drilling > 2 levels | Consider Zustand store or React Context |

---

## TypeScript Patterns

### Strict Type Definitions

```typescript
// Prefer interfaces for object shapes
interface Market {
  id: string;
  question: string;
  outcomes: Outcome[];
  volume: number;
  liquidity: number;
}

// Use unions for constrained values
type OrderSide = 'buy' | 'sell';
type MarketStatus = 'open' | 'closed' | 'resolved';

// Generic components with constraints
interface ListProps<T extends { id: string }> {
  items: T[];
  renderItem: (item: T) => React.ReactNode;
}
```

### Fix Common Type Errors

```typescript
// ❌ Avoid `any` - loses type safety
const handleData = (data: any) => { ... }

// ✅ Use proper types or generics
const handleData = <T extends Record<string, unknown>>(data: T) => { ... }

// ❌ Non-null assertion without checks
const value = data!.property;

// ✅ Proper null handling
const value = data?.property ?? defaultValue;
```

---

## Tailwind CSS Guidelines

### Responsive Design Pattern

```tsx
// Mobile-first with breakpoint modifiers
<div className="
  flex flex-col gap-4
  md:flex-row md:gap-6
  lg:gap-8
">

// Dark mode support
<div className="
  bg-white text-gray-900
  dark:bg-gray-900 dark:text-white
">
```

### Component Styling Patterns

```tsx
// Use clsx/cn for conditional classes
import { cn } from '@/lib/utils';

interface ButtonProps {
  variant: 'primary' | 'secondary';
  disabled?: boolean;
}

function Button({ variant, disabled, children }: ButtonProps) {
  return (
    <button
      className={cn(
        'px-4 py-2 rounded-lg font-medium transition-colors',
        variant === 'primary' && 'bg-blue-600 text-white hover:bg-blue-700',
        variant === 'secondary' && 'bg-gray-200 text-gray-900 hover:bg-gray-300',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
```

---

## React Query (TanStack Query) v5

### Query Pattern

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Query keys as const arrays for consistency
const marketKeys = {
  all: ['markets'] as const,
  detail: (id: string) => [...marketKeys.all, id] as const,
  orderbook: (id: string) => [...marketKeys.detail(id), 'orderbook'] as const,
};

// Custom hook with proper typing
function useMarket(marketId: string) {
  return useQuery({
    queryKey: marketKeys.detail(marketId),
    queryFn: () => fetchMarket(marketId),
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
  });
}
```

### Mutation Pattern

```typescript
function usePlaceOrder() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (order: OrderPayload) => placeOrder(order),
    onSuccess: (_, variables) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ 
        queryKey: marketKeys.orderbook(variables.marketId) 
      });
    },
    onError: (error) => {
      toast.error(`Order failed: ${error.message}`);
    },
  });
}
```

### Common Issues to Fix

| Issue | Solution |
|-------|----------|
| Stale data after mutation | Call `invalidateQueries` with correct query key |
| Infinite refetching | Check `refetchInterval` config, ensure stable query keys |
| Memory leaks | Enable `gcTime`, remove unused queries |
| Race conditions | Use `useQuery` with `enabled` flag, not manual fetching |

---

## Zustand State Management

### Store Pattern

```typescript
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface UIState {
  // State
  sidebarOpen: boolean;
  selectedMarketId: string | null;
  theme: 'light' | 'dark';
  
  // Actions
  toggleSidebar: () => void;
  selectMarket: (id: string) => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        sidebarOpen: true,
        selectedMarketId: null,
        theme: 'dark',
        
        toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
        selectMarket: (id) => set({ selectedMarketId: id }),
        setTheme: (theme) => set({ theme }),
      }),
      { name: 'ui-store' }
    )
  )
);
```

### Selector Pattern for Performance

```typescript
// ❌ Selecting entire store causes unnecessary re-renders
const { sidebarOpen, theme } = useUIStore();

// ✅ Use selectors for specific slices
const sidebarOpen = useUIStore((s) => s.sidebarOpen);
const theme = useUIStore((s) => s.theme);

// ✅ Memoized derived selectors
import { shallow } from 'zustand/shallow';

const { sidebarOpen, theme } = useUIStore(
  (s) => ({ sidebarOpen: s.sidebarOpen, theme: s.theme }),
  shallow
);
```

### When to Use Zustand vs React Query

| Use Case | Tool |
|----------|------|
| Server state (API data) | React Query |
| Client-only UI state | Zustand |
| User preferences | Zustand with `persist` |
| Form state | React Hook Form or local state |
| Authentication state | Zustand (synced with API) |

---

## TradingView Advanced Charts Widget

### Basic Integration

```tsx
import { useEffect, useRef } from 'react';

interface TradingViewWidgetProps {
  symbol: string;
  theme?: 'light' | 'dark';
  interval?: string;
}

export function TradingViewWidget({ 
  symbol, 
  theme = 'dark',
  interval = 'D' 
}: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      new (window as any).TradingView.widget({
        container_id: containerRef.current!.id,
        symbol: symbol,
        interval: interval,
        theme: theme,
        style: '1',
        locale: 'en',
        toolbar_bg: '#f1f3f6',
        enable_publishing: false,
        allow_symbol_change: true,
        autosize: true,
      });
    };

    containerRef.current.appendChild(script);

    return () => {
      // Cleanup widget on unmount
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [symbol, theme, interval]);

  return (
    <div 
      id={`tradingview_${symbol.replace('/', '_')}`}
      ref={containerRef} 
      className="h-[500px] w-full"
    />
  );
}
```

### Advanced Widget Configuration

```typescript
// Widget options for Polymarket-style charts
const polymarketChartConfig = {
  // Chart appearance
  theme: 'dark',
  style: '3', // Area chart
  
  // Hide unnecessary UI
  hide_top_toolbar: false,
  hide_side_toolbar: true,
  hide_legend: false,
  
  // Customization
  backgroundColor: 'rgba(0, 0, 0, 0)',
  gridColor: 'rgba(255, 255, 255, 0.1)',
  
  // Disable features not needed
  enable_publishing: false,
  withdateranges: true,
  save_image: false,
  
  // Study configuration
  studies: [
    'Volume@tv-basicstudies',
  ],
};
```

### Common Widget Issues

| Issue | Solution |
|-------|----------|
| Widget not loading | Ensure script loads before creating widget instance |
| Multiple widgets conflict | Use unique `container_id` per widget instance |
| Memory leaks | Clean up widget in useEffect return function |
| Symbol not found | Verify symbol format matches TradingView naming |
| Resize issues | Use `autosize: true` and ensure parent has defined dimensions |

---

## Vite Build Configuration

### Common vite.config.ts Setup

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@lib': path.resolve(__dirname, './src/lib'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
```

### Fix Common Build Errors

| Error | Solution |
|-------|----------|
| Module not found | Check path aliases in `vite.config.ts` and `tsconfig.json` |
| Type errors blocking build | Fix types or use `// @ts-ignore` sparingly |
| Large bundle size | Code split with `React.lazy()`, analyze with `vite-bundle-analyzer` |
| CSS not loading | Verify Tailwind config and PostCSS setup |

---

## Review Checklist

Before completing a frontend review, verify:

- [ ] No TypeScript errors (`npm run type-check`)
- [ ] ESLint passes (`npm run lint`)
- [ ] Build succeeds (`npm run build`)
- [ ] React Query has proper query keys and cache config
- [ ] Zustand selectors used for performance
- [ ] TradingView widgets clean up properly
- [ ] Responsive design works on mobile/tablet/desktop
- [ ] Dark mode styling is consistent
- [ ] Loading and error states handled in all data components
