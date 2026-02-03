import { useState } from 'react'
import {
    Activity,
    BarChart3,
    Layers,
    Loader2,
    Search,
    Sparkles,
    Target,
    TrendingDown,
    TrendingUp,
    Trophy,
    User,
    Wallet,
} from 'lucide-react'
import { useUserAnalytics, UserPosition } from '../hooks/useUserAnalytics'

function formatAddress(address?: string | null) {
    if (!address) return 'Unknown'
    if (address.length <= 12) return address
    return `${address.slice(0, 6)}...${address.slice(-4)}`
}

function formatCurrency(value: number, opts?: { minimumFractionDigits?: number; maximumFractionDigits?: number }) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: opts?.minimumFractionDigits ?? 0,
        maximumFractionDigits: opts?.maximumFractionDigits ?? 0,
    }).format(value)
}

function formatPercent(value: number, digits: number = 1) {
    const sign = value > 0 ? '+' : ''
    return `${sign}${value.toFixed(digits)}%`
}

function formatNumber(value: number) {
    return new Intl.NumberFormat('en-US', {
        maximumFractionDigits: 0,
    }).format(value)
}

function isWalletAddress(value?: string | null) {
    if (!value) return false
    return /^0x[a-fA-F0-9]{40}$/.test(value)
}

function metricTone(value: number) {
    return value >= 0 ? 'text-emerald-400' : 'text-red-400'
}

function MetricCard({
    icon: Icon,
    label,
    value,
    subtext,
    accentClass,
}: {
    icon: typeof Activity
    label: string
    value: string
    subtext?: string
    accentClass?: string
}) {
    return (
        <div className="glass-light rounded-xl p-4 border border-white/5">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs text-surface-400 uppercase tracking-wider">{label}</p>
                    <p className={`text-lg font-semibold mt-1 ${accentClass ?? 'text-white'}`}>{value}</p>
                </div>
                <div className="p-2 rounded-lg bg-surface-800/60">
                    <Icon className="w-4 h-4 text-surface-300" />
                </div>
            </div>
            {subtext && <p className="text-[11px] text-surface-400 mt-2">{subtext}</p>}
        </div>
    )
}

function PositionRow({ position }: { position: UserPosition }) {
    const marketLabel = position.title || position.slug || position.market_id || 'Unknown market'
    const pnlClass = metricTone(position.cash_pnl)

    return (
        <div className="grid grid-cols-12 gap-3 items-center py-3 px-2 rounded-lg hover:bg-white/5 transition-colors">
            <div className="col-span-12 md:col-span-5 min-w-0">
                <p className="text-sm text-white truncate" title={marketLabel}>
                    {marketLabel}
                </p>
                <div className="flex items-center gap-2 text-[11px] text-surface-400 mt-1">
                    <span className="uppercase">{position.outcome || 'N/A'}</span>
                    <span>•</span>
                    <span>{formatNumber(position.shares)} shares</span>
                </div>
            </div>
            <div className="col-span-6 md:col-span-2 text-xs text-surface-300">
                <span className="block">Avg</span>
                <span className="text-white">{formatCurrency(position.avg_price, { maximumFractionDigits: 3 })}</span>
            </div>
            <div className="col-span-6 md:col-span-2 text-xs text-surface-300">
                <span className="block">Value</span>
                <span className="text-white">{formatCurrency(position.current_value)}</span>
            </div>
            <div className="col-span-6 md:col-span-2 text-xs">
                <span className="block text-surface-300">P&L</span>
                <span className={`${pnlClass} font-semibold`}>{formatCurrency(position.cash_pnl)}</span>
            </div>
            <div className="col-span-6 md:col-span-1 text-xs">
                <span className="block text-surface-300">ROI</span>
                <span className={`${pnlClass} font-semibold`}>{formatPercent(position.percent_pnl, 1)}</span>
            </div>
        </div>
    )
}

function HighlightRow({ position, positive }: { position: UserPosition; positive: boolean }) {
    const marketLabel = position.title || position.slug || position.market_id || 'Unknown market'
    const tone = positive ? 'text-emerald-400' : 'text-red-400'
    const percentLabel = Number.isFinite(position.percent_pnl)
        ? `(${formatPercent(position.percent_pnl, 2)})`
        : ''

    return (
        <div className="flex items-center justify-between text-xs text-surface-200 py-2 border-b border-white/5 last:border-0">
            <div className="min-w-0">
                <p className="truncate text-white" title={marketLabel}>{marketLabel}</p>
                <p className="text-[11px] text-surface-400 mt-0.5">{position.outcome || 'N/A'} • {formatNumber(position.shares)} shares</p>
            </div>
            <div className={`font-semibold ${tone}`}>{formatCurrency(position.cash_pnl)} {percentLabel}</div>
        </div>
    )
}

export default function UserDashboard() {
    const [query, setQuery] = useState('')
    const [submittedQuery, setSubmittedQuery] = useState<string | null>(null)
    const [activePositionsTab, setActivePositionsTab] = useState<'open' | 'closed'>('open')

    const { data, isLoading, error, isFetching } = useUserAnalytics(submittedQuery)

    const handleSubmit = (event: React.FormEvent) => {
        event.preventDefault()
        const trimmed = query.trim()
        if (!trimmed) return
        setSubmittedQuery(trimmed)
    }

    const user = data?.user
    const metrics = data?.metrics
    const displayName = user?.display_name || user?.username || formatAddress(user?.address)
    const hasWallet = isWalletAddress(user?.address)

    const yesCount = metrics?.yes_positions ?? 0
    const noCount = metrics?.no_positions ?? 0
    const otherCount = metrics?.other_positions ?? 0
    const totalOutcomes = yesCount + noCount + otherCount

    const yesPercent = totalOutcomes > 0 ? (yesCount / totalOutcomes) * 100 : 0
    const noPercent = totalOutcomes > 0 ? (noCount / totalOutcomes) * 100 : 0
    const otherPercent = totalOutcomes > 0 ? (otherCount / totalOutcomes) * 100 : 0

    return (
        <div className="space-y-6">
            <section className="glass-card rounded-2xl p-4 lg:p-6">
                <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 rounded-xl bg-primary-500/20">
                        <Sparkles className="w-5 h-5 text-primary-300" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-white">User Intelligence</h2>
                        <p className="text-xs text-surface-300">Search by Polymarket username or wallet address</p>
                    </div>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col md:flex-row gap-3">
                    <div className="flex-1 relative">
                        <input
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            placeholder="e.g. vitalik or 0xabc..."
                            className="w-full bg-surface-900/60 border border-white/10 rounded-xl py-2.5 pl-11 pr-4 text-sm text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                        />
                        <Search className="w-4 h-4 text-surface-400 absolute left-4 top-1/2 -translate-y-1/2" />
                    </div>
                    <button
                        type="submit"
                        className="px-4 py-2.5 rounded-xl bg-primary-600 hover:bg-primary-500 text-sm font-semibold text-white transition-colors flex items-center justify-center gap-2"
                    >
                        {isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
                        Analyze
                    </button>
                </form>

                {error && (
                    <div className="mt-3 text-xs text-red-200 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                        {error.message}
                    </div>
                )}
            </section>

            {!submittedQuery && (
                <section className="glass-light rounded-2xl p-6 text-center border border-white/5">
                    <Wallet className="w-10 h-10 text-surface-400 mx-auto mb-3" />
                    <p className="text-sm text-surface-200">Start by searching a user to unlock their trading story.</p>
                    <p className="text-xs text-surface-500 mt-2">We surface PnL, open positions, closed markets, and hidden gems.</p>
                </section>
            )}

            {isLoading && submittedQuery && (
                <section className="glass-light rounded-2xl p-6 text-center border border-white/5">
                    <Loader2 className="w-6 h-6 text-primary-300 animate-spin mx-auto mb-2" />
                    <p className="text-sm text-surface-200">Crunching on-chain activity...</p>
                </section>
            )}

            {data && metrics && (
                <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 lg:gap-6">
                    <div className="xl:col-span-4 space-y-4">
                        <div className="glass-card rounded-2xl p-5 relative overflow-hidden">
                            <div className="absolute inset-0 bg-gradient-to-br from-primary-500/10 via-transparent to-emerald-500/10" />
                            <div className="relative flex items-center gap-3">
                                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500 to-emerald-400 flex items-center justify-center text-white font-semibold">
                                    <User className="w-6 h-6" />
                                </div>
                                <div className="min-w-0">
                                    <p className="text-white text-lg font-semibold truncate">{displayName}</p>
                                    <p className="text-xs text-surface-300 font-mono">{user?.address}</p>
                                </div>
                            </div>
                            <div className="relative mt-4 flex items-center justify-between text-xs text-surface-300">
                                <div className="flex items-center gap-2">
                                    <Wallet className="w-4 h-4" />
                                    <span>{formatAddress(user?.address)}</span>
                                </div>
                                {hasWallet ? (
                                    <a
                                        href={`https://polymarket.com/profile/${user?.address}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="text-primary-300 hover:text-primary-200 transition-colors"
                                    >
                                        View profile
                                    </a>
                                ) : (
                                    <span className="text-[11px] text-surface-400">Unresolved wallet</span>
                                )}
                            </div>
                        </div>

                        <div className="glass-light rounded-2xl p-4 border border-white/5">
                            <div className="flex items-center gap-2 mb-3">
                                <BarChart3 className="w-4 h-4 text-emerald-400" />
                                <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Outcome Bias</h3>
                            </div>
                            <div className="h-2 w-full rounded-full bg-surface-800 overflow-hidden flex">
                                <div className="bg-emerald-400" style={{ width: `${yesPercent}%` }} />
                                <div className="bg-red-400" style={{ width: `${noPercent}%` }} />
                                <div className="bg-surface-500" style={{ width: `${otherPercent}%` }} />
                            </div>
                            <div className="flex items-center justify-between text-[11px] text-surface-300 mt-2">
                                <span>Yes {yesCount}</span>
                                <span>No {noCount}</span>
                                <span>Other {otherCount}</span>
                            </div>
                        </div>

                        <div className="glass-light rounded-2xl p-4 border border-white/5">
                            <div className="flex items-center gap-2 mb-3">
                                <Activity className="w-4 h-4 text-primary-400" />
                                <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Activity Pulse</h3>
                            </div>
                            <div className="space-y-2 text-xs text-surface-200">
                                <div className="flex items-center justify-between">
                                    <span>Open positions</span>
                                    <span className="text-white font-semibold">{metrics.open_positions}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>Closed positions</span>
                                    <span className="text-white font-semibold">{metrics.closed_positions}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>Total markets</span>
                                    <span className="text-white font-semibold">{data.positions_total}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>Last activity</span>
                                    <span className="text-white font-semibold">
                                        {metrics.last_activity_at ? new Date(metrics.last_activity_at).toLocaleDateString() : 'N/A'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="xl:col-span-8 space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                            <MetricCard
                                icon={TrendingUp}
                                label="Total P&L"
                                value={formatCurrency(metrics.total_pnl)}
                                accentClass={metricTone(metrics.total_pnl)}
                                subtext={`Win rate ${formatPercent(metrics.win_rate, 1)}`}
                            />
                            <MetricCard
                                icon={Target}
                                label="ROI"
                                value={formatPercent(metrics.total_roi, 1)}
                                accentClass={metricTone(metrics.total_roi)}
                                subtext={`Realized ${formatPercent(metrics.realized_roi, 1)}`}
                            />
                            <MetricCard
                                icon={Layers}
                                label="Exposure"
                                value={formatCurrency(metrics.total_current_value)}
                                subtext={`Avg position ${formatCurrency(metrics.avg_position_size)}`}
                            />
                            <MetricCard
                                icon={Wallet}
                                label="Total Volume"
                                value={formatCurrency(metrics.total_initial_value)}
                                subtext={`Largest ${formatCurrency(metrics.largest_position_value)}`}
                            />
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="glass-light rounded-2xl p-4 border border-emerald-500/20">
                                <div className="flex items-center gap-2 mb-3">
                                    <Trophy className="w-4 h-4 text-emerald-400" />
                                    <h3 className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Biggest Wins</h3>
                                </div>
                                {data.biggest_wins.length > 0 ? (
                                    data.biggest_wins.slice(0, 5).map((position, index) => (
                                        <HighlightRow key={`${position.market_id}-${index}`} position={position} positive />
                                    ))
                                ) : (
                                    <p className="text-xs text-surface-400">No winning positions yet.</p>
                                )}
                            </div>

                            <div className="glass-light rounded-2xl p-4 border border-red-500/20">
                                <div className="flex items-center gap-2 mb-3">
                                    <TrendingDown className="w-4 h-4 text-red-400" />
                                    <h3 className="text-xs font-semibold text-red-300 uppercase tracking-wider">Biggest Losses</h3>
                                </div>
                                {data.biggest_losses.length > 0 ? (
                                    data.biggest_losses.slice(0, 5).map((position, index) => (
                                        <HighlightRow key={`${position.market_id}-${index}`} position={position} positive={false} />
                                    ))
                                ) : (
                                    <p className="text-xs text-surface-400">No losing positions yet.</p>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="xl:col-span-12 glass-card rounded-2xl p-4 lg:p-6">
                        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                            <div>
                                <h3 className="text-sm font-semibold text-white">Positions</h3>
                                <p className="text-xs text-surface-400">Open and closed markets tracked by this user.</p>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <button
                                    onClick={() => setActivePositionsTab('open')}
                                    className={`px-3 py-1 rounded-full border transition-colors ${activePositionsTab === 'open'
                                        ? 'bg-primary-500/20 border-primary-400 text-white'
                                        : 'border-white/10 text-surface-400 hover:text-white'
                                        }`}
                                >
                                    Open ({metrics.open_positions})
                                </button>
                                <button
                                    onClick={() => setActivePositionsTab('closed')}
                                    className={`px-3 py-1 rounded-full border transition-colors ${activePositionsTab === 'closed'
                                        ? 'bg-primary-500/20 border-primary-400 text-white'
                                        : 'border-white/10 text-surface-400 hover:text-white'
                                        }`}
                                >
                                    Closed ({metrics.closed_positions})
                                </button>
                            </div>
                        </div>

                        <div className="space-y-1">
                            {(activePositionsTab === 'open' ? data.open_positions : data.closed_positions).map((position, index) => (
                                <PositionRow key={`${position.market_id}-${index}`} position={position} />
                            ))}

                            {(activePositionsTab === 'open' ? data.open_positions : data.closed_positions).length === 0 && (
                                <p className="text-xs text-surface-400 text-center py-6">No positions to display.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
