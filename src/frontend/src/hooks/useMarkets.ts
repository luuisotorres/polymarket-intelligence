import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import type { Market } from '../stores/marketStore'

interface MarketListResponse {
    markets: Market[]
    total: number
    last_updated: string | null
}

async function fetchMarkets(): Promise<MarketListResponse> {
    const response = await axios.get<MarketListResponse>('/api/markets/top50')
    return response.data
}

export function useMarkets() {
    return useQuery({
        queryKey: ['markets', 'top50'],
        queryFn: fetchMarkets,
        staleTime: 1000 * 60 * 5, // 5 minutes
        refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
    })
}

async function fetchMarket(marketId: string): Promise<Market> {
    const response = await axios.get<Market>(`/api/markets/${marketId}`)
    return response.data
}

export function useMarket(marketId: string | null) {
    return useQuery({
        queryKey: ['market', marketId],
        queryFn: () => fetchMarket(marketId!),
        enabled: !!marketId,
        staleTime: 1000 * 60 * 5,
    })
}
