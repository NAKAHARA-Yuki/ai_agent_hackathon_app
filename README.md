# ai_agent_hackathon_app

## Google Maps の有効化（JS マップ／Advanced Marker）

- Maps JavaScript API を有効化し、HTTP リファラ制限を設定した API キーを用意してください。
	- 参考: Google Cloud Console > APIs & Services > Credentials
	- 参考: APIs & Services > Library で「Maps JavaScript API」を有効化
- フロントエンドの環境変数を設定（Vite）。`client/.env.example` をコピーして `.env.local` を作成し、値を入れます。

必要な変数:

- VITE_GOOGLE_MAPS_API_KEY: フロントから読み込む公開キー
- VITE_GOOGLE_MAPS_MAP_ID: （任意）マップスタイルの Map ID。Advanced Marker を使う場合に推奨
- VITE_ENABLE_ADVANCED_MARKER: （任意）true で Advanced Marker を有効化（Map ID 設定時のみ有効）

バックエンドは `/api/maps-key` でキー・mapId・advanced を返します。MapPanel はこれらを使って JS マップを初期化し、Advanced Marker が有効かつ mapId が指定されている場合のみ高機能ピンを使用します。

注意:

- ルート表示はキー不要の埋め込みを既定で使用します（InvalidKeyMapError 時でも表示可能）。
- Advanced Marker を使う場合は、Map ID を設定し、VITE_ENABLE_ADVANCED_MARKER=true にしてください。

## GitHub Actions / Secrets 方針（全環境共通）

main=本番, dev=開発 で Cloud Run へデプロイしますが、Secrets は全て共通 ( *_DEV を使わない ) としています。分離はサービス名 suffix (-dev) と `APP_ENV` で行います。

### 採用理由
- 初期フェーズで運用コストを最小化（Secrets 二重管理を避ける）
- ローテーション対象が単一セットになり人的エラー低減
- 監査・権限設定が一元化

### リスクと軽減策
- 開発環境から同一 GCP プロジェクト操作: dev 用 Cloud Run サービス名に -dev suffix を必須化
- 誤操作で本番サービス上書き: workflow 内で本番サービス名を参照しない（`*-dev` 固定）
- 署名/鍵漏えいインパクト拡大: 必要になった時点で *_DEV 移行できるよう README に再分離手順を記載（下記）

### 再分離したくなった場合の手順
1. GitHub Secrets に *_DEV 変数を追加（例: GEMINI_API_KEY_DEV）
2. `deploy-cloud-run-dev.yml` を編集し `${{ secrets.GEMINI_API_KEY }}` を `${{ secrets.GEMINI_API_KEY_DEV }}` へ置換
3. 同様に必要な鍵 (JWT_SECRET, GOOGLE_MAPS_API_KEY など) を差し替え
4. PR & merge 後 dev ブランチへ push しデプロイ確認

### 追加検討 (任意)
- Firestore コレクション名を `plans_dev` などに切り替える環境分岐（`APP_ENV` 判定）
- 本番と開発でモデルバージョンを変更したい場合: dev workflow に `GEMINI_MODEL=...` を別途設定

