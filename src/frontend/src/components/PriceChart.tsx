import { useEffect, useRef, useMemo, useCallback } from 'react'
import { createChart, AreaSeries, IChartApi, ISeriesApi, UTCTimestamp, ColorType } from 'lightweight-charts'
import { usePriceHistory } from '../hooks/usePriceHistory'
import { useMarketStore } from '../stores/marketStore'
import { Loader2, TrendingUp, TrendingDown } from 'lucide-react'

interface ChartDataPoint {
    time: UTCTimestamp
    value: number
}

export default function PriceChart() {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<'Area'> | null>(null)

    const { selectedMarket, selectedTimeframe } = useMarketStore()
    const { data, isLoading, error } = usePriceHistory(
        selectedMarket?.id || null,
        selectedTimeframe
    )

    const { chartData, priceChange } = useMemo(() => {
        if (!data?.history || data.history.length === 0) {
            return { chartData: null, priceChange: null }
        }

        const points: ChartDataPoint[] = data.history.map((p) => ({
            time: (new Date(p.timestamp).getTime() / 1000) as UTCTimestamp,
            value: p.yes_percentage,
        }))

        // Sort by time (required by lightweight-charts)
        points.sort((a, b) => a.time - b.time)

        const first = points[0].value
        const last = points[points.length - 1].value
        const change = last - first

        return {
            chartData: points,
            priceChange: {
                value: change,
                isPositive: change >= 0,
                current: last,
            },
        }
    }, [data])

    // Cleanup chart on unmount or when market changes
    const cleanupChart = useCallback(() => {
        if (seriesRef.current && chartRef.current) {
            try {
                chartRef.current.removeSeries(seriesRef.current)
            } catch {
                // Series may already be removed
            }
            seriesRef.current = null
        }
        if (chartRef.current) {
            chartRef.current.remove()
            chartRef.current = null
        }
    }, [])

    // Initialize and update chart when we have data
    useEffect(() => {
        if (!chartContainerRef.current || !chartData || chartData.length < 2) {
            return
        }

        // Cleanup previous chart if exists
        cleanupChart()

        const container = chartContainerRef.current
        const width = container.clientWidth || 800
        const height = 280

        // Create new chart
        const chart = createChart(container, {
            width,
            height,
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#9ca3af',
            },
            grid: {
                vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
            },
            rightPriceScale: {
                borderColor: 'rgba(255, 255, 255, 0.1)',
            },
            timeScale: {
                borderColor: 'rgba(255, 255, 255, 0.1)',
                timeVisible: true,
                secondsVisible: false,
            },
            crosshair: {
                vertLine: {
                    color: 'rgba(255, 255, 255, 0.3)',
                    width: 1,
                    style: 2,
                    labelBackgroundColor: '#1e293b',
                },
                horzLine: {
                    color: 'rgba(255, 255, 255, 0.3)',
                    width: 1,
                    style: 2,
                    labelBackgroundColor: '#1e293b',
                },
            },
            handleScroll: true,
            handleScale: true,
        })

        chartRef.current = chart

        // Add series with appropriate colors
        const isPositive = priceChange?.isPositive ?? true
        const lineColor = isPositive ? '#10b981' : '#ef4444'
        const topColor = isPositive ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'
        const bottomColor = isPositive ? 'rgba(16, 185, 129, 0.0)' : 'rgba(239, 68, 68, 0.0)'

        const areaSeries = chart.addSeries(AreaSeries, {
            lineColor,
            topColor,
            bottomColor,
            lineWidth: 2,
            priceFormat: {
                type: 'custom',
                formatter: (price: number) => `${price.toFixed(2)}%`,
            },
        })

        areaSeries.setData(chartData)
        seriesRef.current = areaSeries

        // Fit content to view all data
        chart.timeScale().fitContent()

        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                })
            }
        }

        window.addEventListener('resize', handleResize)

        return () => {
            window.removeEventListener('resize', handleResize)
            cleanupChart()
        }
    }, [chartData, priceChange?.isPositive, cleanupChart])

    if (!selectedMarket) {
        return (
            <div className="h-[400px] rounded-xl flex items-center justify-center bg-surface-900/50">
                <div className="text-center text-surface-300">
                    <TrendingUp className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>Select a market to view price history</p>
                </div>
            </div>
        )
    }

    if (isLoading) {
        return (
            <div className="h-[400px] rounded-xl flex items-center justify-center bg-surface-900/50">
                <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="h-[400px] rounded-xl flex items-center justify-center bg-surface-900/50">
                <p className="text-red-400">Failed to load price history</p>
            </div>
        )
    }

    // If we only have one data point or no history
    if (!chartData || chartData.length <= 1) {
        return (
            <div className="h-[400px] rounded-xl p-6 bg-surface-900/50">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">Price History</h3>
                    <span className="text-sm text-surface-300">Recording history...</span>
                </div>
                <div className="flex-1 flex items-center justify-center h-[300px]">
                    <div className="text-center">
                        <p className="text-5xl font-bold text-primary-400 mb-2">
                            {selectedMarket.yes_percentage.toFixed(2)}%
                        </p>
                        <p className="text-surface-300">Current "Yes" Probability</p>
                        <p className="text-sm text-surface-400 mt-4">
                            Price history will build up over time
                        </p>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="h-[400px] rounded-xl p-4 bg-surface-900/50">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-lg font-semibold text-white">Yes Price History</h3>
                    {priceChange && (
                        <div className="flex items-center gap-1 mt-1">
                            {priceChange.isPositive ? (
                                <TrendingUp className="w-4 h-4 text-green-400" />
                            ) : (
                                <TrendingDown className="w-4 h-4 text-red-400" />
                            )}
                            <span className={priceChange.isPositive ? 'text-green-400' : 'text-red-400'}>
                                {priceChange.isPositive ? '+' : ''}
                                {priceChange.value.toFixed(2)}%
                            </span>
                            <span className="text-surface-400 text-sm ml-1">({selectedTimeframe})</span>
                        </div>
                    )}
                </div>
                <div className="text-right">
                    <p className="text-2xl font-bold text-white">
                        {priceChange?.current.toFixed(2)}%
                    </p>
                    <p className="text-xs text-surface-400">Current</p>
                </div>
            </div>

            <div
                ref={chartContainerRef}
                className="w-full h-[300px]"
            />
        </div>
    )
}
