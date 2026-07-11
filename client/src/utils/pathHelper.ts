/**
 * Tailscale serve の --set-path でパスプレフィックスが除去されるため、
 * クライアントサイドナビゲーション時に手動でプレフィックスを付与するユーティリティ。
 *
 * Next.js の basePath はサーバーサイドで完全なパスを期待するため使用できない。
 * 代わりにこのヘルパーを全てのルーター遷移で使用する。
 */

/** アプリケーションのベースパス（Tailscale serve のサブパス） */
export const APP_BASE_PATH = '/izatabi';

/**
 * アプリ内パスにベースパスを付与する
 * @param path - アプリ内の相対パス（例: '/login', '/plans/123'）
 * @returns ベースパス付きの完全パス（例: '/izatabi/login'）
 */
export function appPath(path: string): string {
  if (path.startsWith(APP_BASE_PATH)) return path;
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${APP_BASE_PATH}${normalizedPath}`;
}
