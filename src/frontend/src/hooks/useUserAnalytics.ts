import { useQuery } from '@tanstack/react-query'

export interface UserProfile {
    address: string
    username?: string | null
    display_name?: string | null
    profile_image?: string | null
    resolved: boolean
}

export interface UserPosition {
    market_id?: string | null
    title?: string | null
    slug?: string | null
    outcome?: string | null
    shares: number
    avg_price: number
    current_value: number
    initial_value: number
    total_bought: number
    cash_pnl: number
    percent_pnl: number
    status?: string | null
    last_updated?: string | null
    is_open: boolean
}

export interface UserMetrics {
    total_pnl: number
    total_roi: number
    realized_pnl: number
    realized_roi: number
    realized_cost_basis: number
    volume_traded: number
    unrealized_pnl: number
    total_initial_value: number
    total_current_value: number
    open_positions: number
    closed_positions: number
    win_rate: number
    avg_roi: number
    avg_position_size: number
    largest_position_value: number
    best_position_pnl: number
    worst_position_pnl: number
    yes_positions: number
    no_positions: number
    other_positions: number
    last_activity_at?: string | null
}

export interface UserAnalyticsResponse {
    user: UserProfile
    metrics: UserMetrics
    open_positions: UserPosition[]
    closed_positions: UserPosition[]
    biggest_wins: UserPosition[]
    biggest_losses: UserPosition[]
    positions_total: number
}

async function fetchUserAnalytics(query: string): Promise<UserAnalyticsResponse> {
    const response = await fetch(`/api/users/analytics?query=${encodeURIComponent(query)}`)
    if (!response.ok) {
        const message = response.status === 404 ? 'User not found' : 'Failed to fetch user analytics'
        throw new Error(message)
    }
    return response.json()
}

export function useUserAnalytics(query: string | null) {
    return useQuery({
        queryKey: ['user-analytics', query],
        queryFn: () => fetchUserAnalytics(query!),
        enabled: !!query,
        refetchInterval: 60000,
    })
}
