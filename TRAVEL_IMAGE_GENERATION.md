# 旅行イメージ画像生成機能

## 概要

このプロジェクトに実装された旅行プラン画像生成機能は、Gemini 2.5 Flash Image API（"nano banana"とも呼ばれる）を使用して、旅行プランの内容から自動的に美しいイメージ画像を生成し、旅行プラン提案画面で表示する機能です。

## 機能詳細

### バックエンド実装

#### 1. 画像生成API統合
- **モデル**: `imagen-3.0-generate-001`
- **エンドポイント**: `https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:generateImage`
- **認証**: `x-goog-api-key` ヘッダーでGEMINI_API_KEYを使用

#### 2. 主要な新機能

**`call_gemini_image_api(prompt, model_name)`**
- Gemini Image API を直接呼び出し
- プロンプトから画像を生成
- セーフティ設定で不適切なコンテンツをブロック

**`generate_travel_image_prompt(travel_plan_text)`**
- 旅行プランのテキストから画像生成用のプロンプトを作成
- 日本の風景や文化的要素を含むプロフェッショナルな旅行写真風の指示
- アスペクト比 4:3 で Web 表示に最適化

**`generate_and_save_travel_image(travel_plan_text, plan_id)`**
- 旅行プランから画像を生成し、ローカルに保存
- ファイル名: `travel_plan_{plan_id}_{timestamp}.jpg`
- 保存先: `server/static/generated_images/`

**`create_development_placeholder_image(travel_plan_text, plan_id)`**
- 開発環境用：Pillowを使用した模擬画像生成
- プラン内容に基づいたカラー選択
- グラデーション効果とテキストオーバーレイ

#### 3. 統合ポイント

**`/api/agent/chat` エンドポイント修正**
```python
# plans 配列の各プランに対して画像を生成
for i, plan in enumerate(plans):
    if isinstance(plan, dict) and ('title' in plan or 'description' in plan):
        plan_text = f"{plan.get('title', '')} {plan.get('description', '')}".strip()
        if plan_text:
            plan_id = f"{req_session_id}_{i}_{int(time.time())}"
            image_url = generate_and_save_travel_image(plan_text, plan_id)
            if image_url:
                plan['image_url'] = image_url  # レスポンスに画像URLを追加
```

### フロントエンド実装

#### 1. SuggestionScreen.vue の修正
```javascript
const enrichedPlans = computed(() => props.plans.map((p, idx) => {
  let image
  
  // Check if the plan has a generated image
  if (p.image_url) {
    // Use the generated image from the server
    image = p.image_url.startsWith('http') ? p.image_url : `http://localhost:8080${p.image_url}`
  } else {
    // Fallback to Unsplash (original behavior)
    const key = encodeURIComponent(((p.title||'') + ' ' + keywords[idx % keywords.length]).trim())
    image = `https://source.unsplash.com/featured/400x300?${key}`
  }
  
  return { raw: p, id: p.id, image }
}))
```

#### 2. TravelPlanWizardView.vue の修正
```javascript
// プラン情報のマッピングに image_url を追加
mapped = resp.plans.slice(0,3).map((p,i)=>({
  // ... existing fields ...
  image_url: p.image_url || null,  // Add generated image URL
  // ... rest of mapping ...
}))
```

## セットアップと使用方法

### 1. 環境変数の設定

```bash
# server/.env ファイルに追加
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 2. 依存関係のインストール

```bash
cd server
pip install -r requirements.txt  # Pillow==11.3.0 が追加されました
```

### 3. 本番環境での使用

1. **Google Cloud Console** で Gemini API を有効化
2. **API キー** を取得し、適切な制限を設定
3. **環境変数** にAPI キーを設定
4. サーバーを再起動

### 4. 開発環境での使用

API キーが設定されていない場合、自動的に開発用の模擬画像が生成されます。

## テスト方法

### 1. 単体テスト
```bash
# テスト用エンドポイントで画像生成を確認
curl -X POST http://localhost:8080/api/test/travel_plans_with_images \
  -H "Content-Type: application/json" \
  -d '{"keyword": "京都の紅葉"}'
```

### 2. ビジュアルテスト
```
http://localhost:8080/static/test_images.html
```

### 3. 統合テスト
1. フロントエンドアプリケーションを起動
2. 旅行プラン作成ワークフローを実行
3. SuggestionScreen で生成された画像が表示されることを確認

## ファイル構造

```
server/
├── app.py                     # 画像生成機能を統合
├── requirements.txt           # Pillow を追加
├── static/
│   ├── generated_images/      # 生成された画像の保存先
│   └── test_images.html       # テスト用ページ
└── .env                       # GEMINI_API_KEY の設定

client/
├── src/
│   ├── components/
│   │   └── SuggestionScreen.vue    # 画像表示ロジックを修正
│   └── views/
│       └── TravelPlanWizardView.vue # image_url マッピングを追加
└── dist/                      # ビルド済みファイル
```

## エラーハンドリング

- **API キー未設定**: 開発用画像を自動生成
- **Pillow未インストール**: 外部プレースホルダーサービスにフォールバック
- **画像生成失敗**: Unsplash フォールバックを使用
- **ネットワークエラー**: ログに記録し、エラー画像を表示

## セキュリティ考慮事項

- 生成される画像にはセーフティフィルタを適用
- ファイル名にタイムスタンプを含めて衝突を回避
- 静的ファイル配信は適切なMIME タイプで実行

## パフォーマンス最適化

- 画像は一度生成されればローカルキャッシュを利用
- 非同期処理でUI のブロッキングを回避
- 開発環境では高速な模擬画像生成を使用

この機能により、旅行プラン提案画面がより視覚的に魅力的になり、ユーザーエクスペリエンスが大幅に向上します。