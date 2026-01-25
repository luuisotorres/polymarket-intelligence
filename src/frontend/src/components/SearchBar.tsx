import { useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useMarketStore } from '../stores/marketStore'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export function SearchBar() {
    const [query, setQuery] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const { setSelectedMarket } = useMarketStore()

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!query.trim()) return

        setIsLoading(true)
        setError(null)

        try {
            // Check if it's a full URL or just a slug
            let slug = query.trim()
            if (slug.includes('polymarket.com/event/')) {
                const parts = slug.split('/')
                slug = parts[parts.length - 1]
            }

            const response = await fetch(`${API_BASE}/api/markets/${slug}`)

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Market not found')
                }
                throw new Error('Failed to fetch market')
            }

            const market = await response.json()
            setSelectedMarket(market)
            setQuery('')

        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong')
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <form onSubmit={handleSearch} className="relative w-full max-w-md">
            <div className="relative">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search market by slug or URL..."
                    className="w-full bg-surface-800/50 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                    disabled={isLoading}
                />
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400">
                    {isLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin text-primary-400" />
                    ) : (
                        <Search className="w-4 h-4" />
                    )}
                </div>
            </div>
            {error && (
                <div className="absolute top-full mt-2 left-0 right-0 bg-red-500/10 border border-red-500/20 text-red-200 text-xs px-3 py-2 rounded-lg backdrop-blur-md">
                    {error}
                </div>
            )}
        </form>
    )
}
