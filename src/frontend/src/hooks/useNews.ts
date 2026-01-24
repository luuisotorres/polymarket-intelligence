import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

export interface NewsArticle {
    id: number
    market_id: string
    title: string
    description?: string | null
    url: string
    source?: string | null
    author?: string | null
    image_url?: string | null
    published_at?: string | null
    sentiment_score?: number | null
}

interface NewsListResponse {
    articles: NewsArticle[]
    total: number
    market_id: string
}

async function fetchNews(marketId: string, limit: number = 20): Promise<NewsListResponse> {
    const response = await axios.get<NewsListResponse>(`/api/news/${marketId}`, {
        params: { limit },
    })
    return response.data
}

export function useNews(marketId: string | null, limit: number = 20) {
    return useQuery({
        queryKey: ['news', marketId, limit],
        queryFn: () => fetchNews(marketId!, limit),
        enabled: !!marketId,
        staleTime: 1000 * 30, // 30 seconds
        refetchInterval: 1000 * 30, // Auto-refresh every 30 seconds
    })
}
