import { useQuery } from '@tanstack/react-query'
import { TrendingUp, TrendingDown, Minus, Activity, BarChart3, Zap, Target, Volume2 } from 'lucide-react'
import { useMarketStore } from '../stores/marketStore'

interface MarketSignal {
    name: string
    signal: 'bullish' | 'bearish' | 'neutral'
    strength: number
    description: string
    value: number | null
}

interface MarketStats {
    market_id: string
    current_price: number
    change_24h: number
    change_24h_percent: number
    change_7d: number
    change_7d_percent: number
    high_24h: number
    low_24h: number
    high_7d: number
    low_7d: number
    volume_24h: number
    volume_7d: number
    overall_signal: 'bullish' | 'bearish' | 'neutral'
    overall_strength: number
    signals: MarketSignal[]
}

async function fetchMarketStats(marketId: string): Promise<MarketStats> {
    const response = await fetch(`/api/markets/${marketId}/stats`)
    if (!response.ok) {
        throw new Error('Failed to fetch market stats')
    }
    return response.json()
}

function useMarketStats(marketId: string | null) {
    return useQuery({
        queryKey: ['marketStats', marketId],
        queryFn: () => fetchMarketStats(marketId!),
        enabled: !!marketId,
        refetchInterval: 60000,
    })
}

function formatCurrency(value: number): string {
    if (value >= 1000000) {
        return `$${(value / 1000000).toFixed(1)}M`
    }
    if (value >= 1000) {
        return `$${(value / 1000).toFixed(1)}K`
    }
    return `$${value.toFixed(0)}`
}

function SignalIcon({ signal }: { signal: 'bullish' | 'bearish' | 'neutral' }) {
    if (signal === 'bullish') {
        return <TrendingUp className="w-4 h-4 text-emerald-400" />
    }
    if (signal === 'bearish') {
        return <TrendingDown className="w-4 h-4 text-red-400" />
    }
    return <Minus className="w-4 h-4 text-surface-400" />
}

function StrengthBars({ strength, signal }: { strength: number; signal: string }) {
    const color = signal === 'bullish' ? 'bg-emerald-400' : signal === 'bearish' ? 'bg-red-400' : 'bg-surface-500'
    const bgColor = signal === 'bullish' ? 'bg-emerald-900/30' : signal === 'bearish' ? 'bg-red-900/30' : 'bg-surface-800'

    return (
        <div className="flex gap-0.5">
            {[1, 2, 3, 4, 5].map((level) => (
                <div
                    key={level}
                    className={`w-1.5 h-3 rounded-sm ${level <= strength ? color : bgColor}`}
                />
            ))}
        </div>
    )
}

function SignalCard({ signal }: { signal: MarketSignal }) {
    const iconMap: Record<string, React.ReactNode> = {
        '24h Momentum': <Zap className="w-4 h-4" />,
        '7d Trend': <TrendingUp className="w-4 h-4" />,
        'Range Position': <Target className="w-4 h-4" />,
        'Volume Surge': <Volume2 className="w-4 h-4" />,
        'Low Volume': <Volume2 className="w-4 h-4" />,
        'High Volatility': <Activity className="w-4 h-4" />,
        'Low Volatility': <Activity className="w-4 h-4" />,
    }

    const bgColor = signal.signal === 'bullish'
        ? 'bg-emerald-500/10 border-emerald-500/20'
        : signal.signal === 'bearish'
            ? 'bg-red-500/10 border-red-500/20'
            : 'bg-surface-800/50 border-surface-700/30'

    const textColor = signal.signal === 'bullish'
        ? 'text-emerald-400'
        : signal.signal === 'bearish'
            ? 'text-red-400'
            : 'text-surface-300'

    return (
        <div className={`p-3 rounded-xl border ${bgColor} transition-all hover:scale-[1.02]`}>
            <div className="flex items-center justify-between mb-2">
                <div className={`flex items-center gap-2 ${textColor}`}>
                    {iconMap[signal.name] || <Activity className="w-4 h-4" />}
                    <span className="text-sm font-medium">{signal.name}</span>
                </div>
                <StrengthBars strength={signal.strength} signal={signal.signal} />
            </div>
            <p className="text-xs text-surface-300">{signal.description}</p>
        </div>
    )
}

function StatCard({ label, value, change, isPercent = false }: {
    label: string
    value: string | number
    change?: number
    isPercent?: boolean
}) {
    return (
        <div className="bg-surface-800/50 rounded-xl p-3 border border-surface-700/30">
            <div className="text-[10px] text-surface-400 uppercase tracking-wide mb-1">{label}</div>
            <div className="text-lg font-bold text-white">{value}{isPercent ? '%' : ''}</div>
            {change !== undefined && (
                <div className={`text-xs font-medium flex items-center gap-1 mt-1 ${change > 0 ? 'text-emerald-400' : change < 0 ? 'text-red-400' : 'text-surface-400'
                    }`}>
                    {change > 0 ? <TrendingUp className="w-3 h-3" /> : change < 0 ? <TrendingDown className="w-3 h-3" /> : null}
                    {change > 0 ? '+' : ''}{change.toFixed(2)}%
                </div>
            )}
        </div>
    )
}

function PriceMovementSkeleton() {
    return (
        <div className="space-y-4 animate-pulse">
            <div className="h-24 skeleton rounded-xl" />
            <div className="grid grid-cols-2 gap-3">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-20 skeleton rounded-xl" />
                ))}
            </div>
            <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 skeleton rounded-xl" />
                ))}
            </div>
        </div>
    )
}

export function PriceMovement() {
    const { selectedMarket } = useMarketStore()
    const { data: stats, isLoading, error } = useMarketStats(selectedMarket?.id ?? null)

    if (!selectedMarket) {
        return (
            <div className="text-center py-12 text-surface-200">
                <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Select a market to see price movement</p>
            </div>
        )
    }

    if (isLoading) {
        return <PriceMovementSkeleton />
    }

    if (error || !stats) {
        return (
            <div className="text-center py-8 text-surface-200">
                <p className="text-sm">Failed to load market stats</p>
            </div>
        )
    }

    const overallBgColor = stats.overall_signal === 'bullish'
        ? 'bg-gradient-to-br from-emerald-500/20 to-emerald-600/5 border-emerald-500/30'
        : stats.overall_signal === 'bearish'
            ? 'bg-gradient-to-br from-red-500/20 to-red-600/5 border-red-500/30'
            : 'bg-gradient-to-br from-surface-700/30 to-surface-800/30 border-surface-600/30'

    const overallTextColor = stats.overall_signal === 'bullish'
        ? 'text-emerald-400'
        : stats.overall_signal === 'bearish'
            ? 'text-red-400'
            : 'text-surface-300'

    return (
        <div className="space-y-4">
            {/* Overall Signal Banner */}
            <div className={`p-4 rounded-2xl border ${overallBgColor}`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-xl ${stats.overall_signal === 'bullish' ? 'bg-emerald-500/20' :
                                stats.overall_signal === 'bearish' ? 'bg-red-500/20' : 'bg-surface-700/50'
                            }`}>
                            <SignalIcon signal={stats.overall_signal} />
                        </div>
                        <div>
                            <div className={`text-xl font-bold uppercase ${overallTextColor}`}>
                                {stats.overall_signal}
                            </div>
                            <div className="text-xs text-surface-400">Overall Market Sentiment</div>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-2xl font-bold text-white">{stats.current_price.toFixed(1)}%</div>
                        <div className={`text-sm font-medium ${stats.change_24h_percent > 0 ? 'text-emerald-400' :
                                stats.change_24h_percent < 0 ? 'text-red-400' : 'text-surface-400'
                            }`}>
                            {stats.change_24h_percent > 0 ? '+' : ''}{stats.change_24h_percent.toFixed(2)}% (24h)
                        </div>
                    </div>
                </div>
                <div className="mt-3 flex justify-center">
                    <StrengthBars strength={stats.overall_strength} signal={stats.overall_signal} />
                </div>
            </div>

            {/* Price Stats Grid */}
            <div className="grid grid-cols-2 gap-3">
                <StatCard
                    label="24h Change"
                    value={`${stats.change_24h > 0 ? '+' : ''}${stats.change_24h.toFixed(2)}`}
                    change={stats.change_24h_percent}
                    isPercent
                />
                <StatCard
                    label="7d Change"
                    value={`${stats.change_7d > 0 ? '+' : ''}${stats.change_7d.toFixed(2)}`}
                    change={stats.change_7d_percent}
                    isPercent
                />
                <StatCard
                    label="24h Range"
                    value={`${stats.low_24h.toFixed(1)} - ${stats.high_24h.toFixed(1)}%`}
                />
                <StatCard
                    label="7d Range"
                    value={`${stats.low_7d.toFixed(1)} - ${stats.high_7d.toFixed(1)}%`}
                />
            </div>

            {/* Volume Stats */}
            <div className="grid grid-cols-2 gap-3">
                <StatCard label="24h Volume" value={formatCurrency(stats.volume_24h)} />
                <StatCard label="7d Volume" value={formatCurrency(stats.volume_7d)} />
            </div>

            {/* Trading Signals */}
            <div>
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary-400" />
                    Trading Signals
                </h3>
                <div className="space-y-2">
                    {stats.signals.map((signal, index) => (
                        <SignalCard key={index} signal={signal} />
                    ))}
                </div>
            </div>
        </div>
    )
}
