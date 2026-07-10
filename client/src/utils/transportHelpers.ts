// Shared transport utility functions
const MODE_LABEL: Record<string, string> = {
  walking: '徒歩',
  transit: '公共交通',
  driving: '車',
  bus: 'バス',
  train: '電車',
  taxi: 'タクシー',
  bicycle: '自転車',
  cycling: '自転車',
  flight: '飛行機',
  boat: '船',
  ferry: 'フェリー'
};

export function transportLabel(mode?: string): string {
  const m = String(mode || '').toLowerCase();
  return MODE_LABEL[m] || '移動';
}

export function transportIcon(mode?: string): string {
  const m = String(mode || '').toLowerCase();
  switch (m) {
    case 'walking': return '🚶';
    case 'bus': return '🚌';
    case 'train': return '🚆';
    case 'transit': return '🚌';
    case 'driving': return '🚗';
    case 'taxi': return '🚕';
    case 'bicycle':
    case 'cycling': return '🚲';
    case 'flight': return '✈️';
    case 'boat':
    case 'ferry': return '⛴️';
    default: return '➡️';
  }
}

export function formatDuration(val?: number | string | null): string {
  if (val === null || val === undefined) return '';
  if (typeof val === 'number' && Number.isFinite(val)) return `${Math.round(val)}分`;
  if (typeof val === 'string') return val;
  return '';
}

export function formatDistance(km?: number | string | null): string {
  if (km === null || km === undefined) return '';
  const n = Number(km);
  if (!Number.isFinite(n)) return '';
  if (n === 0) return '0 km';
  return `${n.toFixed(1)} km`;
}
