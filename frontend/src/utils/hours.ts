export function isPositiveHalfHour(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 && Number.isInteger(value * 2)
}
