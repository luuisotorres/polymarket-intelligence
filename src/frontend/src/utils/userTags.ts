export type UserTagTone = 'positive' | 'negative' | 'neutral'

export interface UserTag {
    label: string
    tone: UserTagTone
    value: number
    display: string
}

const PNL_POS_TIERS = [
    { min: 5000, label: 'Profitable' },
    { min: 25000, label: 'High-Performing' },
    { min: 100000, label: 'Top Performer' },
    { min: 500000, label: 'Massive Winner' },
]

const PNL_NEG_TIERS = [
    { max: -5000, label: 'In the Red' },
    { max: -25000, label: 'Large Losses' },
    { max: -100000, label: 'Heavy Losses' },
    { max: -500000, label: 'Massive Losses' },
]

const BALANCE_TIERS = [
    { min: 25000, label: 'Solid Balance' },
    { min: 100000, label: 'Large Balance' },
    { min: 500000, label: 'Massive Balance' },
    { min: 2000000, label: 'Whale Balance' },
]

function formatUsdCompact(value: number): string {
    const abs = Math.abs(value)
    if (abs >= 1_000_000_000) {
        return `$${(abs / 1_000_000_000).toFixed(1)}B`
    }
    if (abs >= 1_000_000) {
        return `$${(abs / 1_000_000).toFixed(1)}M`
    }
    if (abs >= 1_000) {
        return `$${(abs / 1_000).toFixed(1)}K`
    }
    return `$${abs.toFixed(0)}`
}

function formatSignedUsd(value: number): string {
    const sign = value >= 0 ? '+' : '-'
    return `${sign}${formatUsdCompact(Math.abs(value))}`
}

function pickPositiveLabel(value: number) {
    let label: string | null = null
    for (const tier of PNL_POS_TIERS) {
        if (value >= tier.min) {
            label = tier.label
        }
    }
    return label
}

function pickNegativeLabel(value: number) {
    let label: string | null = null
    for (const tier of PNL_NEG_TIERS) {
        if (value <= tier.max) {
            label = tier.label
        }
    }
    return label
}

function pickBalanceLabel(value: number) {
    let label: string | null = null
    for (const tier of BALANCE_TIERS) {
        if (value >= tier.min) {
            label = tier.label
        }
    }
    return label
}

export function getUserTags(stats: {
    global_pnl?: number | null
    total_balance?: number | null
}): UserTag[] {
    const tags: UserTag[] = []

    if (typeof stats.global_pnl === 'number' && Number.isFinite(stats.global_pnl)) {
        if (stats.global_pnl >= 0) {
            const label = pickPositiveLabel(stats.global_pnl)
            if (label) {
                tags.push({
                    label: `${label}: Total PnL`,
                    tone: 'positive',
                    value: stats.global_pnl,
                    display: formatSignedUsd(stats.global_pnl),
                })
            }
        } else {
            const label = pickNegativeLabel(stats.global_pnl)
            if (label) {
                tags.push({
                    label: `${label}: Total PnL`,
                    tone: 'negative',
                    value: stats.global_pnl,
                    display: formatSignedUsd(stats.global_pnl),
                })
            }
        }
    }

    if (typeof stats.total_balance === 'number' && Number.isFinite(stats.total_balance)) {
        const label = pickBalanceLabel(stats.total_balance)
        if (label) {
            tags.push({
                label,
                tone: 'neutral',
                value: stats.total_balance,
                display: formatUsdCompact(stats.total_balance),
            })
        }
    }

    return tags
}
