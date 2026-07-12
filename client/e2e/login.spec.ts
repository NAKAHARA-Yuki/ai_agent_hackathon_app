import { test, expect } from '@playwright/test';

test('signup and login e2e flow', async ({ page }) => {
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

  // テストごとに完全にユニークなユーザー名とパスワードを生成
  const uniqueId = `user_${Date.now()}`;
  const password = 'Password123!';

  // --- Step 1: 新規登録 (Signup) ---
  console.log('Navigating to signup page...');
  await page.goto('signup');
  await expect(page).toHaveTitle(/いざ旅/);

  console.log(`Registering unique user: ${uniqueId}`);
  await page.fill('input[placeholder*="山田 太郎"]', 'テストユーザー');
  await page.locator('input[placeholder*="gemini_user"]').fill(uniqueId);
  await page.fill('input[type="password"]', password);

  console.log('Submitting signup form...');
  await page.click('button[type="submit"]');

  console.log('Waiting for signup redirect...');
  // 登録完了後に /main または ホーム（/）にリダイレクトされるのを待つ
  await page.waitForURL(url => url.pathname.endsWith('/main') || url.pathname.endsWith('/izatabi/') || url.pathname.endsWith('/izatabi'), { timeout: 10000 });
  console.log(`Signup redirection successful, landed on: ${page.url()}`);

  // --- Step 2: ログアウト状態のシミュレートと再ログイン ---
  console.log('Clearing storage to test login explicitly...');
  await page.context().clearCookies();
  await page.evaluate(() => localStorage.clear());

  console.log('Navigating to login page...');
  await page.goto('login');

  console.log('Filling login credentials with the newly created user...');
  await page.fill('input[placeholder*="gemini_user"]', uniqueId);
  await page.fill('input[type="password"]', password);

  console.log('Submitting login form...');
  await page.click('button[type="submit"]');

  console.log('Waiting for login redirect...');
  // 診断未完了ユーザーの場合、ログイン後は '/' (すなわち /izatabi) にリダイレクトされるのが正常です
  await page.waitForURL(url => url.pathname.endsWith('/izatabi') || url.pathname.endsWith('/izatabi/'), { timeout: 15000 });
  
  const currentURL = page.url();
  console.log(`Final Page URL: ${currentURL}`);
  expect(currentURL).toMatch(/\/izatabi\/?$/);
});
