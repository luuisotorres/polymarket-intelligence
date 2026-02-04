
import { useQuery } from '@tanstack/react-query'

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

export function useWhales(
    marketId: string | null,
    minVolume: number = 500,
    days: number = 7,
    includeUserStats: boolean = true
) {
    return useQuery({
        queryKey: ['whales', marketId, minVolume, days, includeUserStats],
        queryFn: () => fetchWhaleTrades(marketId!, minVolume, days, includeUserStats),
        enabled: !!marketId,
        refetchInterval: 30000, // Refresh every 30 seconds for live trades
    })
}
