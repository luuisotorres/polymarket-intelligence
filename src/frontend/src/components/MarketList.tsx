import { useMemo } from 'react'
import { Search, TrendingUp, TrendingDown, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useMarkets } from '../hooks/useMarkets'
import { useMarketStore, Market } from '../stores/marketStore'

function formatVolume(volume: number): string {
    if (volume >= 1_000_000) {
        return `$${(volume / 1_000_000).toFixed(1)}M`
    }
    if (volume >= 1_000) {
        return `$${(volume / 1_000).toFixed(1)}K`
    }
    return `$${volume.toFixed(0)}`
}

function MarketCard({ market, isSelected, onClick }: {
    market: Market
    isSelected: boolean
    onClick: () => void
}) {
    const yesPercent = market.yes_percentage

    return (
        <button
            onClick={onClick}
            className={clsx(
                'market-card w-full text-left p-3 rounded-xl transition-all',
                'glass-light hover:bg-white/5',
                isSelected && 'selected'
            )}
        >
            <div className="flex items-start gap-3">
                {market.image_url ? (
                    <img
                        src={market.image_url}
                        alt=""
                        className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
                    />
                ) : (
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500/30 to-accent-500/30 flex items-center justify-center flex-shrink-0">
                        <TrendingUp className="w-5 h-5 text-primary-400" />
                    </div>
                )}
                <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-white line-clamp-2 leading-tight">
                        {market.title}
                    </h3>
                    <div className="flex items-center gap-2 mt-2">
                        <span
                            className={clsx(
                                'text-xs font-semibold px-2 py-0.5 rounded-full',
                                yesPercent >= 50
                                    ? 'bg-accent-500/20 text-accent-400'
                                    : 'bg-red-500/20 text-red-400'
                            )}
                        >
                            {yesPercent.toFixed(2)}% Yes
                        </span>
                        <span className="text-xs text-surface-200">
                            {formatVolume(market.volume_7d)} vol
                        </span>
                    </div>
                </div>
            </div>
        </button>
    )
}

export function MarketList() {
    const { data, isLoading, error } = useMarkets()
    const { selectedMarket, setSelectedMarket, searchQuery, setSearchQuery } = useMarketStore()

    const filteredMarkets = useMemo(() => {
        if (!data?.markets) return []
        if (!searchQuery.trim()) return data.markets

        const query = searchQuery.toLowerCase()
        return data.markets.filter((m) =>
            m.title.toLowerCase().includes(query) ||
            m.slug.toLowerCase().includes(query)
        )
    }, [data?.markets, searchQuery])

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="text-center py-8">
                <TrendingDown className="w-8 h-8 text-red-400 mx-auto mb-2" />
                <p className="text-sm text-surface-200">Failed to load markets</p>
                <p className="text-xs text-surface-200/60 mt-1">Please try again later</p>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-[calc(100vh-220px)]">
            {/* Search */}
            <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-200" />
                <input
                    type="text"
                    placeholder="Search markets..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm bg-surface-900/50 border border-white/10 rounded-lg text-white placeholder-surface-200 focus:outline-none focus:border-primary-500/50 transition-colors"
                />
            </div>

            {/* Market List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {filteredMarkets.map((market) => (
                    <MarketCard
                        key={market.id}
                        market={market}
                        isSelected={selectedMarket?.id === market.id}
                        onClick={() => setSelectedMarket(market)}
                    />
                ))}
                {filteredMarkets.length === 0 && (
                    <p className="text-center text-sm text-surface-200 py-8">
                        No markets found
                    </p>
                )}
            </div>

            {/* Footer */}
            {data?.last_updated && (
                <p className="text-xs text-surface-200/60 mt-3 text-center">
                    Updated: {new Date(data.last_updated).toLocaleTimeString()}
                </p>
            )}
        </div>
    )
}
