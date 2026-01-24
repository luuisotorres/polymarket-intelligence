import { useState } from 'react'
import { Wallet, RefreshCw, Clock, ExternalLink, TrendingUp, TrendingDown, ArrowUpCircle, ArrowDownCircle } from 'lucide-react'
import { useWhales, WhaleTrade } from '../hooks/useWhales'
import { useMarketStore } from '../stores/marketStore'

function formatAddress(address: string): string {
    if (!address) return 'Unknown'
    if (address.length < 10) return address
    return `${address.slice(0, 6)}...${address.slice(-4)}`
}

function formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value)
}

function formatTimeAgo(dateString: string): string {
    if (!dateString) return ''

    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
}

function WhaleTradeCard({ trade, rank }: { trade: WhaleTrade; rank: number }) {
    const isBuy = trade.side === 'BUY'
    const displayName = trade.name || formatAddress(trade.address)

    return (
        <div className="p-4 glass-light rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
                {/* Rank */}
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-surface-800 flex items-center justify-center text-xs font-bold text-surface-400">
                    #{rank}
                </div>

                {/* Bullish/Bearish indicator */}
                <div className={`flex-shrink-0 p-1.5 rounded-lg ${trade.is_bullish ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
                    {trade.is_bullish ? (
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                    ) : (
                        <TrendingDown className="w-4 h-4 text-red-400" />
                    )}
                </div>

                {/* Trade info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 flex-wrap">
                            <a
                                href={`https://polymarket.com/profile/${trade.address}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm font-medium text-white group-hover:text-primary-400 transition-colors font-mono truncate max-w-[120px]"
                            >
                                {displayName}
                            </a>

                            {/* BUY/SELL badge */}
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${isBuy
                                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                : 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                                }`}>
                                {trade.side}
                            </span>

                            {/* Outcome badge */}
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${trade.outcome.toLowerCase() === 'yes' || trade.outcome.toLowerCase() === 'up'
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : 'bg-red-500/20 text-red-400 border border-red-500/30'
                                }`}>
                                {trade.outcome}
                            </span>

                            {/* Sentiment badge */}
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded flex items-center gap-0.5 ${trade.is_bullish
                                ? 'bg-emerald-500/10 text-emerald-400'
                                : 'bg-red-500/10 text-red-400'
                                }`}>
                                {trade.is_bullish ? (
                                    <>
                                        <ArrowUpCircle className="w-3 h-3" />
                                        BULLISH
                                    </>
                                ) : (
                                    <>
                                        <ArrowDownCircle className="w-3 h-3" />
                                        BEARISH
                                    </>
                                )}
                            </span>
                        </div>

                        {/* Volume */}
                        <span className={`text-sm font-bold ml-2 ${trade.is_bullish ? 'text-emerald-400' : 'text-red-400'}`}>
                            {formatCurrency(trade.volume)}
                        </span>
                    </div>

                    <div className="flex items-center justify-between mt-1.5 text-xs text-surface-200/60">
                        <div className="flex items-center gap-2">
                            <span>{trade.size.toLocaleString()} shares</span>
                            <span>•</span>
                            <span>@{(trade.price * 100).toFixed(0)}¢</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTimeAgo(trade.timestamp)}
                        </div>
                    </div>
                </div>

                {/* External link */}
                <a
                    href={`https://polymarket.com/profile/${trade.address}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 rounded-lg hover:bg-white/10 text-surface-400 hover:text-white transition-colors flex-shrink-0"
                >
                    <ExternalLink className="w-4 h-4" />
                </a>
            </div>
        </div>
    )
}

function WhaleSkeleton() {
    return (
        <div className="p-4 glass-light rounded-xl animate-pulse">
            <div className="flex items-center gap-4">
                <div className="w-7 h-7 rounded-full skeleton" />
                <div className="w-8 h-8 rounded-lg skeleton" />
                <div className="flex-1 space-y-2">
                    <div className="flex justify-between">
                        <div className="h-4 w-32 rounded skeleton" />
                        <div className="h-4 w-16 rounded skeleton" />
                    </div>
                    <div className="flex justify-between">
                        <div className="h-3 w-24 rounded skeleton" />
                        <div className="h-3 w-12 rounded skeleton" />
                    </div>
                </div>
            </div>
        </div>
    )
}

const VOLUME_THRESHOLDS = [100, 250, 500, 1000, 5000]

export function WhaleList() {
    const { selectedMarket } = useMarketStore()
    const [minVolume, setMinVolume] = useState(100)
    const [sentimentFilter, setSentimentFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH'>('ALL')

    const { data: trades, isLoading, error, refetch, isFetching } = useWhales(selectedMarket?.id ?? null, minVolume)

    const filteredTrades = trades?.filter((trade: WhaleTrade) => {
        if (sentimentFilter === 'ALL') return true
        if (sentimentFilter === 'BULLISH') return trade.is_bullish
        if (sentimentFilter === 'BEARISH') return !trade.is_bullish
        return true
    })

    if (!selectedMarket) {
        return (
            <div className="text-center py-12 text-surface-200">
                <Wallet className="w-10 h-10 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Select a market to see whale trades</p>
            </div>
        )
    }

    if (isLoading) {
        return (
            <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                    <WhaleSkeleton key={i} />
                ))}
            </div>
        )
    }

    if (error) {
        return (
            <div className="text-center py-8 text-surface-200">
                <p className="text-sm">Failed to load trade data</p>
                <button
                    onClick={() => refetch()}
                    className="mt-2 text-xs text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                >
                    <RefreshCw className="w-3 h-3" />
                    Try again
                </button>
            </div>
        )
    }

    return (
        <div>
            {/* Controls */}
            <div className="flex flex-col gap-3 mb-4 px-1">
                {/* Threshold selector */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-200/60 whitespace-nowrap">Min Order:</span>
                    <div className="flex bg-surface-800/50 rounded-lg p-0.5 flex-wrap">
                        {VOLUME_THRESHOLDS.map((threshold) => (
                            <button
                                key={threshold}
                                onClick={() => setMinVolume(threshold)}
                                className={`px-2 py-1 text-[10px] font-medium rounded-md transition-all ${minVolume === threshold
                                    ? 'bg-primary-500/20 text-primary-400 shadow-sm'
                                    : 'text-surface-400 hover:text-surface-200'
                                    }`}
                            >
                                ${threshold >= 1000 ? `${threshold / 1000}k` : threshold}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Sentiment filter + refresh */}
                <div className="flex items-center justify-between">
                    <div className="flex bg-surface-800/50 rounded-lg p-0.5">
                        <button
                            onClick={() => setSentimentFilter('ALL')}
                            className={`px-2 py-1 text-[10px] font-medium rounded-md transition-all ${sentimentFilter === 'ALL'
                                ? 'bg-primary-500/20 text-primary-400 shadow-sm'
                                : 'text-surface-400 hover:text-surface-200'
                                }`}
                        >
                            All
                        </button>
                        <button
                            onClick={() => setSentimentFilter('BULLISH')}
                            className={`px-2 py-1 text-[10px] font-medium rounded-md transition-all flex items-center gap-1 ${sentimentFilter === 'BULLISH'
                                ? 'bg-emerald-500/20 text-emerald-400 shadow-sm'
                                : 'text-surface-400 hover:text-surface-200'
                                }`}
                        >
                            <TrendingUp className="w-3 h-3" />
                            Bullish
                        </button>
                        <button
                            onClick={() => setSentimentFilter('BEARISH')}
                            className={`px-2 py-1 text-[10px] font-medium rounded-md transition-all flex items-center gap-1 ${sentimentFilter === 'BEARISH'
                                ? 'bg-red-500/20 text-red-400 shadow-sm'
                                : 'text-surface-400 hover:text-surface-200'
                                }`}
                        >
                            <TrendingDown className="w-3 h-3" />
                            Bearish
                        </button>
                    </div>

                    <button
                        onClick={() => refetch()}
                        disabled={isFetching}
                        className="text-xs text-surface-200/60 hover:text-white inline-flex items-center gap-1 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-3 h-3 ${isFetching ? 'animate-spin' : ''}`} />
                        <span className="hidden sm:inline">{isFetching ? 'Updating...' : 'Refresh'}</span>
                    </button>
                </div>
            </div>

            {/* Trades List */}
            {!filteredTrades || filteredTrades.length === 0 ? (
                <div className="text-center py-8 text-surface-200">
                    <Wallet className="w-10 h-10 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">No large trades found</p>
                    <p className="text-xs mt-1 opacity-60">Try lowering the minimum order threshold</p>
                </div>
            ) : (
                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
                    {filteredTrades.map((trade: WhaleTrade, index: number) => (
                        <WhaleTradeCard key={`${trade.trade_id}-${index}`} trade={trade} rank={index + 1} />
                    ))}
                </div>
            )}
        </div>
    )
}
