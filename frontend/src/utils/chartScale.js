/** chartScale.js — geometry for the dependency-free SVG charts. */

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

export function extent(seriesValues) {
  let min = Infinity
  let max = -Infinity
  for (const values of seriesValues) {
    for (const v of values) {
      if (isNum(v)) {
        if (v < min) min = v
        if (v > max) max = v
      }
    }
  }
  return min === Infinity ? null : [min, max]
}

/** Round axis ticks that bracket [min, max]. */
export function niceTicks(min, max, count = 4) {
  if (!isNum(min) || !isNum(max)) return []
  let lo = min
  let hi = max
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.05 || 1
    lo -= pad
    hi += pad
  }
  const rough = (hi - lo) / count
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const norm = rough / magnitude
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * magnitude
  const first = Math.floor(lo / step) * step
  const ticks = []
  for (let t = first; t < hi + step * 0.999; t += step) {
    ticks.push(Number(t.toFixed(10)))
  }
  return ticks
}

/** SVG path that breaks at null values instead of interpolating across them. */
export function linePath(points) {
  let d = ''
  let pen = false
  for (const p of points) {
    if (p === null) {
      pen = false
      continue
    }
    d += `${pen ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`
    pen = true
  }
  return d
}

/** Index of the slot under a pointer at `x`, for `n` evenly spaced slots. */
export function slotIndex(x, left, width, n) {
  if (n <= 1 || width <= 0) return 0
  const i = Math.round(((x - left) / width) * (n - 1))
  return Math.min(n - 1, Math.max(0, i))
}

/** Up to `count` evenly spread indexes including both ends. */
export function tickIndexes(n, count = 4) {
  if (n <= 0) return []
  if (n <= count) return Array.from({ length: n }, (_, i) => i)
  return Array.from({ length: count }, (_, i) => Math.round((i * (n - 1)) / (count - 1)))
}
