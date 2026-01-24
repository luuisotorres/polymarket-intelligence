import { ExternalLink, Newspaper, RefreshCw, Clock } from 'lucide-react'
import { useNews, NewsArticle } from '../hooks/useNews'
import { useMarketStore } from '../stores/marketStore'

function formatTimeAgo(dateString: string | null | undefined): string {
    if (!dateString) return ''

    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
}

function NewsCard({ article }: { article: NewsArticle }) {
    return (
        <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-4 glass-light rounded-xl hover:bg-white/5 transition-all group animate-fade-in"
        >
            <div className="flex gap-4">
                {article.image_url ? (
                    <img
                        src={article.image_url}
                        alt=""
                        className="w-20 h-20 rounded-lg object-cover flex-shrink-0"
                    />
                ) : (
                    <div className="w-20 h-20 rounded-lg bg-gradient-to-br from-accent-500/20 to-primary-500/20 flex items-center justify-center flex-shrink-0">
                        <Newspaper className="w-8 h-8 text-accent-400/50" />
                    </div>
                )}
                <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-white line-clamp-2 group-hover:text-primary-400 transition-colors">
                        {article.title}
                    </h3>
                    {article.description && (
                        <p className="text-xs text-surface-200 line-clamp-2 mt-1">
                            {article.description}
                        </p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-surface-200/60">
                        {article.source && <span>{article.source}</span>}
                        {article.published_at && (
                            <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatTimeAgo(article.published_at)}
                            </span>
                        )}
                        <ExternalLink className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                </div>
            </div>
        </a>
    )
}

function NewsSkeleton() {
    return (
        <div className="p-4 glass-light rounded-xl animate-pulse">
            <div className="flex gap-4">
                <div className="w-20 h-20 rounded-lg skeleton" />
                <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 rounded skeleton" />
                    <div className="h-4 w-1/2 rounded skeleton" />
                    <div className="h-3 w-1/4 rounded skeleton mt-2" />
                </div>
            </div>
        </div>
    )
}

export function NewsFeed() {
    const { selectedMarket } = useMarketStore()
    const { data, isLoading, error, refetch, isFetching } = useNews(selectedMarket?.id ?? null)

    if (!selectedMarket) {
        return (
            <div className="text-center py-12 text-surface-200">
                <Newspaper className="w-10 h-10 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Select a market to see related news</p>
            </div>
        )
    }

    if (isLoading) {
        return (
            <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                    <NewsSkeleton key={i} />
                ))}
            </div>
        )
    }

    if (error) {
        return (
            <div className="text-center py-8 text-surface-200">
                <p className="text-sm">Failed to load news</p>
                <button
                    onClick={() => refetch()}
                    className="mt-2 text-xs text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                >
                    <RefreshCw className="w-3 h-3" />
                    Try again
                </button>
            </div>
        )
    }

    const articles = data?.articles ?? []

    return (
        <div>
            {/* Header with refresh indicator */}
            <div className="flex items-center justify-end mb-3">
                <button
                    onClick={() => refetch()}
                    disabled={isFetching}
                    className="text-xs text-surface-200/60 hover:text-white inline-flex items-center gap-1 transition-colors disabled:opacity-50"
                >
                    <RefreshCw className={`w-3 h-3 ${isFetching ? 'animate-spin' : ''}`} />
                    {isFetching ? 'Updating...' : 'Refresh'}
                </button>
            </div>

            {/* Articles */}
            {articles.length > 0 ? (
                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
                    {articles.map((article) => (
                        <NewsCard key={article.id} article={article} />
                    ))}
                </div>
            ) : (
                <div className="text-center py-8 text-surface-200">
                    <Newspaper className="w-10 h-10 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">No news articles found</p>
                    <p className="text-xs mt-1 opacity-60">Check back later for updates</p>
                </div>
            )}

            {/* Auto-refresh indicator */}
            <p className="text-xs text-surface-200/40 text-center mt-4">
                Auto-refreshes every 30 seconds
            </p>
        </div>
    )
}
