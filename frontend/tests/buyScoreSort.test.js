/**
 * Tests for the buy_score allStocks sorting logic used in HeatmapGrid.vue.
 * The logic is: merge sectors + scores, sort by score desc (null last), re-rank.
 */

import { describe, it, expect } from 'vitest'

function buyScoreSorted(sectors, scores, maxStocks = 480) {
  const flat = []
  for (const sector of sectors) {
    for (const s of sector.stocks ?? []) {
      const sc = scores[s.stock_id]
      flat.push({
        ...s,
        sector: sector.name,
        score: sc?.score ?? null,
        max_score: sc?.max_score ?? null,
      })
    }
  }
  flat.sort((a, b) => {
    if (a.score === null && b.score === null) return 0
    if (a.score === null) return 1
    if (b.score === null) return -1
    return b.score - a.score
  })
  return flat.slice(0, maxStocks).map((s, i) => ({ ...s, rank: i + 1 }))
}

const sectors = [
  {
    name: '半導體',
    stocks: [
      { stock_id: '2330', name: '台積電', rank: 1 },
      { stock_id: '2303', name: '聯電',   rank: 3 },
    ],
  },
  {
    name: '金融',
    stocks: [
      { stock_id: '2882', name: '國泰金', rank: 2 },
      { stock_id: '2891', name: '中信金', rank: 4 },
    ],
  },
]

describe('buyScoreSort — basic ordering', () => {
  it('sorts by score descending', () => {
    const scores = {
      '2330': { score: 20, max_score: 24 },
      '2303': { score: 10, max_score: 24 },
      '2882': { score: 18, max_score: 24 },
      '2891': { score: 15, max_score: 24 },
    }
    const result = buyScoreSorted(sectors, scores)
    expect(result.map(s => s.stock_id)).toEqual(['2330', '2882', '2891', '2303'])
  })

  it('assigns ranks starting from 1', () => {
    const scores = {
      '2330': { score: 20, max_score: 24 },
      '2303': { score: 10, max_score: 24 },
      '2882': { score: 18, max_score: 24 },
      '2891': { score: 15, max_score: 24 },
    }
    const result = buyScoreSorted(sectors, scores)
    expect(result[0].rank).toBe(1)
    expect(result[1].rank).toBe(2)
    expect(result[result.length - 1].rank).toBe(result.length)
  })

  it('puts null-score stocks last', () => {
    const scores = {
      '2330': { score: 20, max_score: 24 },
      // 2303 has no score
      '2882': { score: 5, max_score: 24 },
      // 2891 has no score
    }
    const result = buyScoreSorted(sectors, scores)
    expect(result[0].stock_id).toBe('2330')
    expect(result[1].stock_id).toBe('2882')
    const nullScores = result.filter(s => s.score === null)
    expect(nullScores.map(s => s.stock_id)).toEqual(
      expect.arrayContaining(['2303', '2891'])
    )
  })

  it('handles all stocks with null scores', () => {
    const result = buyScoreSorted(sectors, {})
    expect(result).toHaveLength(4)
    result.forEach(s => expect(s.score).toBeNull())
  })

  it('respects maxStocks cap', () => {
    const scores = { '2330': { score: 20, max_score: 24 } }
    const result = buyScoreSorted(sectors, scores, 2)
    expect(result).toHaveLength(2)
  })

  it('preserves sector name on each stock', () => {
    const scores = { '2330': { score: 20, max_score: 24 } }
    const result = buyScoreSorted(sectors, scores)
    const tsmc = result.find(s => s.stock_id === '2330')
    expect(tsmc.sector).toBe('半導體')
  })
})
