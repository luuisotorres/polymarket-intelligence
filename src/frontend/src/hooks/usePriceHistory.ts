import { useQuery } from '@tanstack/react-query'

interface PricePoint {
    timestamp: string
    yes_percentage: number
    no_percentage: number
    volume: number
}

interface PriceHistoryResponse {
    market_id: string
    history: PricePoint[]
    timeframe: string
}

const fetchPriceHistory = async (
    marketId: string,
    timeframe: string
): Promise<PriceHistoryResponse> => {
    const response = await fetch(
        `/api/markets/${encodeURIComponent(marketId)}/history?timeframe=${timeframe}`
    )
    if (!response.ok) {
        throw new Error('Failed to fetch price history')
    }
    const data = await response.json()

    // Compute no_percentage for each price point
    const historyWithNo: PricePoint[] = data.history.map((point: { timestamp: string; yes_percentage: number; volume: number }) => ({
        ...point,
        no_percentage: 100 - point.yes_percentage,
    }))

    return {
        ...data,
        history: historyWithNo,
    }
}

export const usePriceHistory = (marketId: string | null, timeframe: string) => {
    return useQuery({
        queryKey: ['priceHistory', marketId, timeframe],
        queryFn: () => fetchPriceHistory(marketId!, timeframe),
        enabled: !!marketId,
        refetchInterval: 60000, // Refetch every minute
        staleTime: 30000,
    })
}

export type { PricePoint, PriceHistoryResponse }

