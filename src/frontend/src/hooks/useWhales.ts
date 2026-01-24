
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
}

async function fetchWhaleTrades(marketId: string, minVolume: number): Promise<WhaleTrade[]> {
    const response = await fetch(`/api/markets/${marketId}/trades?min_volume=${minVolume}`)
    if (!response.ok) {
        throw new Error('Failed to fetch whale trades')
    }
    return response.json()
}

export function useWhales(marketId: string | null, minVolume: number = 500) {
    return useQuery({
        queryKey: ['whales', marketId, minVolume],
        queryFn: () => fetchWhaleTrades(marketId!, minVolume),
        enabled: !!marketId,
        refetchInterval: 30000, // Refresh every 30 seconds for live trades
    })
}
