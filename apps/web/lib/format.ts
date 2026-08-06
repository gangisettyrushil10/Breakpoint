/** Money arrives as integer cents from the simulation engine. */

export function money(cents: number, opts: { decimals?: boolean; sign?: boolean } = {}) {
  const { decimals = false, sign = false } = opts;
  const value = cents / 100;
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals ? 2 : 0,
    maximumFractionDigits: decimals ? 2 : 0,
  }).format(Math.abs(value));

  if (value < 0) return `−${formatted}`;
  if (sign && value > 0) return `+${formatted}`;
  return formatted;
}

/** Compact form for chart axes: $9.6k */
export function moneyCompact(cents: number) {
  const value = cents / 100;
  if (Math.abs(value) >= 1000) {
    return `$${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k`;
  }
  return `$${Math.round(value)}`;
}

export function months(value: number, decimals = 1) {
  return `${value.toFixed(decimals)} mo`;
}

export function percent(value: number, decimals = 0) {
  return `${(value * 100).toFixed(decimals)}%`;
}
