import { clsx } from 'clsx'
import { useMarketStore, Timeframe } from '../stores/marketStore'

const timeframes: { value: Timeframe; label: string }[] = [
    { value: '24H', label: '24H' },
    { value: 'ALL', label: 'ALL' },
]

export function TimeframeSelector() {
    const { selectedTimeframe, setSelectedTimeframe } = useMarketStore()

    return (
        <div className="flex items-center gap-1 p-1 bg-surface-900/50 rounded-lg">
            {timeframes.map(({ value, label }) => (
                <button
                    key={value}
                    onClick={() => setSelectedTimeframe(value)}
                    className={clsx(
                        'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                        selectedTimeframe === value
                            ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/25'
                            : 'text-surface-200 hover:text-white hover:bg-white/5'
                    )}
                >
                    {label}
                </button>
            ))}
        </div>
    )
}
