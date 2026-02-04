import { useQuery } from '@tanstack/react-query'
import { Trophy, User } from 'lucide-react'
import { useMarketStore } from '../stores/marketStore'
import { getUserTags } from '../utils/userTags'

interface Holder {
    address: string
    name: string
    amount: number
    img?: string
    market_pnl: number
    market_roi: number
    global_pnl: number
    global_roi: number
    total_balance?: number
}

interface HoldersResponse {
    yes_holders: Holder[]
    no_holders: Holder[]
}

async function fetchHolders(marketId: string): Promise<HoldersResponse> {
    const response = await fetch(`/api/markets/${marketId}/holders`)
    if (!response.ok) {
        throw new Error('Failed to fetch holders')
    }
    return response.json()
}

function PnLBadge({ value, isPercent = false }: { value: number; isPercent?: boolean }) {
    const isPositive = value >= 0
    const formatted = isPercent
        ? `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
        : `${value > 0 ? '+' : ''}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`

    return (
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${isPositive
            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }`}>
            {formatted}
        </span>
    )
}

function HolderRow({ holder, rank }: { holder: Holder; rank: number }) {
    function formatAddress(address: string): string {
        if (!address) return 'Unknown'
        if (address.length < 10) return address
        return `${address.slice(0, 4)}...${address.slice(-4)}`
    }

    // Check if name is generic address or nickname
    const displayName = holder.name && holder.name !== "" ? holder.name : formatAddress(holder.address)

    const tags = getUserTags({
        global_pnl: holder.global_pnl,
        total_balance: holder.total_balance ?? null,
    })

    const tagClass = (tone: 'positive' | 'negative' | 'neutral') => {
        if (tone === 'positive') {
            return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
        }
        if (tone === 'negative') {
            return 'bg-red-500/10 text-red-300 border-red-500/20'
        }
        return 'bg-surface-700/30 text-surface-300 border-surface-600/30'
    }

    return (
        <div className="flex items-center justify-between py-3 border-b border-white/5 last:border-0 hover:bg-white/5 px-2 rounded-lg transition-colors group">
            <div className="flex items-center gap-3 min-w-0 flex-1">
                <span className={`text-xs font-mono w-4 shrink-0 ${rank <= 3 ? 'text-amber-400' : 'text-surface-400'}`}>
                    {rank}
                </span>
                <div className="flex items-center gap-2 min-w-0">
                    {holder.img ? (
                        <img src={holder.img} alt={displayName} className="w-5 h-5 rounded-full shrink-0" />
                    ) : (
                        <div className="w-5 h-5 rounded-full bg-surface-700 flex items-center justify-center shrink-0">
                            <User className="w-3 h-3 text-surface-400" />
                        </div>
                    )}
                    <div className="min-w-0">
                        <a
                            href={`https://polymarket.com/profile/${holder.address}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm text-surface-200 truncate hover:text-white transition-colors block"
                            title={holder.name}
                        >
                            {displayName}
                        </a>
                        {tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                                {tags.map((tag) => (
                                    <span
                                        key={`${tag.label}-${tag.display}`}
                                        className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${tagClass(tag.tone)}`}
                                    >
                                        {tag.label} {tag.display}
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="flex flex-col items-end gap-1 ml-4 shrink-0">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-surface-400">Position P&L:</span>
                    <PnLBadge value={holder.market_pnl} />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-surface-400">ROI:</span>
                    <PnLBadge value={holder.market_roi} isPercent />
                </div>
            </div>
        </div>
    )
}

export function TopHolders() {
    const { selectedMarket } = useMarketStore()
    const { data, isLoading } = useQuery({
        queryKey: ['holders', selectedMarket?.id],
        queryFn: () => fetchHolders(selectedMarket!.id),
        enabled: !!selectedMarket?.id,
        refetchInterval: 60000
    })

    if (!selectedMarket) return null

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1, 2].map((i) => (
                    <div key={i} className="animate-pulse space-y-2">
                        <div className="h-4 w-24 bg-surface-700 rounded mb-4" />
                        {[1, 2, 3, 4, 5].map((j) => (
                            <div key={j} className="h-8 bg-surface-800/50 rounded" />
                        ))}
                    </div>
                ))}
            </div>
        )
    }

    if (!data) return <div className="text-center text-surface-400 py-4">No holder data available</div>

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Yes Holders */}
            <div className="glass-light rounded-xl p-4 border border-emerald-500/20 bg-emerald-950/5">
                <div className="flex items-center gap-2 mb-4 pb-2 border-b border-emerald-500/10">
                    <Trophy className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider">Top YES Holders</h3>
                </div>
                <div className="max-h-[500px] overflow-y-auto custom-scrollbar pr-1">
                    {data.yes_holders.length > 0 ? (
                        data.yes_holders.map((holder, idx) => (
                            <HolderRow key={idx} holder={holder} rank={idx + 1} />
                        ))
                    ) : (
                        <p className="text-xs text-surface-400 text-center py-4">No holders found</p>
                    )}
                </div>
            </div>

            {/* No Holders */}
            <div className="glass-light rounded-xl p-4 border border-red-500/20 bg-red-950/5">
                <div className="flex items-center gap-2 mb-4 pb-2 border-b border-red-500/10">
                    <Trophy className="w-4 h-4 text-red-400" />
                    <h3 className="text-sm font-bold text-red-400 uppercase tracking-wider">Top NO Holders</h3>
                </div>
                <div className="max-h-[500px] overflow-y-auto custom-scrollbar pr-1">
                    {data.no_holders.length > 0 ? (
                        data.no_holders.map((holder, idx) => (
                            <HolderRow key={idx} holder={holder} rank={idx + 1} />
                        ))
                    ) : (
                        <p className="text-xs text-surface-400 text-center py-4">No holders found</p>
                    )}
                </div>
            </div>
        </div>
    )
}
