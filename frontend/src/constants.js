// Display pool size (volume Top N). Backend score candidate pool is separate.
export const MAX_STOCKS = 600

// Mobile per-page card density options
export const MOBILE_DENSITY = {
  '2x2': { cols: 2, rows: 2 },
  '2x3': { cols: 2, rows: 3 },
  '3x3': { cols: 3, rows: 3 },
}
export const DEFAULT_MOBILE_DENSITY = '2x3'

// Tablet per-page card density options (769–1024 px)
export const TABLET_DENSITY = {
  '3x4': { cols: 3, rows: 4 },
  '4x4': { cols: 4, rows: 4 },
}
export const DEFAULT_TABLET_DENSITY = '3x4'
