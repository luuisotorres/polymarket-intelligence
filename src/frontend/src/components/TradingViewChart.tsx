import { useEffect, useRef } from 'react'
import { BarChart3 } from 'lucide-react'
import { useMarketStore, Timeframe } from '../stores/marketStore'

declare global {
    interface Window {
        TradingView: {
            widget: new (config: Record<string, unknown>) => void
        }
    }
}

function getInterval(timeframe: Timeframe): string {
    switch (timeframe) {
        case '1H': return '60'
        case '4H': return '240'
        case '1D': return 'D'
        case '1W': return 'W'
        case '1M': return 'M'
        default: return 'D'
    }
}

export function TradingViewChart() {
    const containerRef = useRef<HTMLDivElement>(null)
    const { selectedMarket, selectedTimeframe } = useMarketStore()

    useEffect(() => {
        if (!containerRef.current || !selectedMarket) return

        // Clear previous widget
        containerRef.current.innerHTML = ''

        // Create a unique container ID
        const containerId = `tradingview_${selectedMarket.id.replace(/[^a-zA-Z0-9]/g, '_')}`
        const widgetContainer = document.createElement('div')
        widgetContainer.id = containerId
        widgetContainer.style.height = '100%'
        containerRef.current.appendChild(widgetContainer)

        // Check if TradingView is available
        if (typeof window.TradingView === 'undefined') {
            console.warn('TradingView script not loaded')
            return
        }

        // Initialize TradingView widget
        // Note: TradingView doesn't have direct Polymarket data
        // Using a placeholder symbol - in production you'd need a data feed
        try {
            new window.TradingView.widget({
                autosize: true,
                symbol: 'POLYMARKET:' + selectedMarket.slug.toUpperCase(),
                interval: getInterval(selectedTimeframe),
                timezone: 'Etc/UTC',
                theme: 'dark',
                style: '1',
                locale: 'en',
                toolbar_bg: '#0f172a',
                enable_publishing: false,
                hide_top_toolbar: false,
                hide_legend: true,
                save_image: false,
                container_id: containerId,
                backgroundColor: 'rgba(15, 23, 42, 0)',
                gridColor: 'rgba(51, 139, 255, 0.1)',
                studies: [],
                disabled_features: [
                    'header_symbol_search',
                    'header_compare',
                    'header_undo_redo',
                    'header_screenshot',
                    'header_saveload',
                    'left_toolbar',
                    'control_bar',
                    'timeframes_toolbar',
                    'edit_buttons_in_legend',
                    'context_menus',
                    'border_around_the_chart',
                ],
                enabled_features: [],
                overrides: {
                    'paneProperties.background': 'rgba(15, 23, 42, 0)',
                    'paneProperties.backgroundType': 'solid',
                    'scalesProperties.backgroundColor': 'rgba(15, 23, 42, 0)',
                    'mainSeriesProperties.candleStyle.upColor': '#22c55e',
                    'mainSeriesProperties.candleStyle.downColor': '#ef4444',
                    'mainSeriesProperties.candleStyle.borderUpColor': '#22c55e',
                    'mainSeriesProperties.candleStyle.borderDownColor': '#ef4444',
                    'mainSeriesProperties.candleStyle.wickUpColor': '#22c55e',
                    'mainSeriesProperties.candleStyle.wickDownColor': '#ef4444',
                },
            })
        } catch (error) {
            console.error('Failed to initialize TradingView widget:', error)
        }
    }, [selectedMarket, selectedTimeframe])

    if (!selectedMarket) {
        return (
            <div className="h-[400px] flex flex-col items-center justify-center text-surface-200">
                <BarChart3 className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm">Select a market to view the chart</p>
            </div>
        )
    }

    return (
        <div
            ref={containerRef}
            className="h-[400px] rounded-xl overflow-hidden bg-surface-900/30"
        >
            {/* Chart will be rendered here */}
            <div className="h-full flex items-center justify-center text-surface-200">
                <div className="text-center">
                    <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50 animate-pulse" />
                    <p className="text-sm">Loading chart...</p>
                    <p className="text-xs mt-1 opacity-60">
                        TradingView integration in progress
                    </p>
                </div>
            </div>
        </div>
    )
}
