import { test, expect } from '@playwright/test';

test('login test and diagnostic trace', async ({ page }) => {
  // ブラウザのコンソールログをリアルタイムで出力
  page.on('console', msg => {
    console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
  });

  // ネットワーク接続エラーをキャッチ
  page.on('requestfailed', request => {
    console.log(`[Browser Network Error] ${request.url()}: ${request.failure()?.errorText}`);
  });

  // APIリクエストのステータスとレスポンスボディをキャッチ
  page.on('response', response => {
    const url = response.url();
    if (url.includes('/api/')) {
      console.log(`[API Response] ${response.status()} ${url}`);
      response.text().then(text => {
        console.log(`[API Body] ${text}`);
      }).catch(() => {});
    }
  });

  console.log('Navigating to login page...');
  await page.goto('login');

  // タイトル等を確認して画面が存在することを確認
  await expect(page).toHaveTitle(/いざ旅/);
  
  console.log('Filling login credentials...');
  // ユーザーIDとパスワードの入力を試行
  await page.fill('input[placeholder*="ユーザーID"], input[placeholder*="user ID"], input[placeholder*="ID"]', 'gemini_user');
  await page.fill('input[type="password"]', 'password');

  console.log('Submitting login form...');
  await page.click('button[type="submit"]');

  console.log('Waiting for navigation...');
  // 遷移を待つため少し待機
  await page.waitForTimeout(5000);

  const currentURL = page.url();
  console.log(`Final Page URL: ${currentURL}`);
  
  // /main に遷移できたかをチェック
  expect(currentURL).toContain('/main');
});
