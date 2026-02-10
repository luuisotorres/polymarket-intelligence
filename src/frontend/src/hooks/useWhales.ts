
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

export interface WhaleTrade {
    trade_id: string
    address: string
    name: string | null
    side: 'BUY' | 'SELL'
    outcome: string
    is_bullish: boolean
    size: number
    price: number
    volume: number
    timestamp: string
    global_pnl?: number
    global_roi?: number
    total_balance?: number
}

async function fetchWhaleTrades(
    marketId: string,
    minVolume: number,
    days: number,
    includeUserStats: boolean
): Promise<WhaleTrade[]> {
    const response = await fetch(
        `/api/markets/${marketId}/trades?min_volume=${minVolume}&days=${days}&include_user_stats=${includeUserStats}`
    )
    if (!response.ok) {
        throw new Error('Failed to fetch whale trades')
    }
    return response.json()
}

/**
 * Two-phase whale trades hook.
 *
 * Phase 1 — instant: fetches trades WITHOUT user stats (fast, ~200ms).
 * Phase 2 — background: fetches trades WITH user stats and merges them
 *           into the cache so the UI updates seamlessly.
 *
 * `staleTime` prevents re-fetching on tab switches for 2 minutes.
 */
export function useWhales(
    marketId: string | null,
    minVolume: number = 500,
    days: number = 7,
) {
    const queryClient = useQueryClient()

    // Phase 1: fast trades (no user stats)
    const result = useQuery({
        queryKey: ['whales', marketId, minVolume, days],
        queryFn: () => fetchWhaleTrades(marketId!, minVolume, days, false),
        enabled: !!marketId,
        staleTime: 2 * 60 * 1000,       // 2 min — no refetch on tab switch
        refetchInterval: 30_000,         // background poll every 30s
    })

    // Phase 2: enrich with user stats in the background
    useEffect(() => {
        if (!marketId || !result.data || result.data.length === 0) return

        // Small delay so the UI renders the fast list first
        const timer = setTimeout(async () => {
            try {
                const enriched = await fetchWhaleTrades(
                    marketId,
                    minVolume,
                    days,
                    true,
                )
                // Silently update the cache — React Query will re-render
                queryClient.setQueryData(
                    ['whales', marketId, minVolume, days],
                    enriched,
                )
            } catch {
                // Stats enrichment is non-critical — swallow silently
            }
        }, 100)

        return () => clearTimeout(timer)
        // Only re-run when the primary query key changes
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [marketId, minVolume, days, result.dataUpdatedAt])

    return result
}
