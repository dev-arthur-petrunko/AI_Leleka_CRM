import uk from './uk.json';

const dict: Record<string, string> = uk;

export function t(key: string): string {
  return dict[key] ?? key;
}
