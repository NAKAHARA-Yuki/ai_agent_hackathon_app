# いざ旅 (Izatabi) - ドキュメント

このディレクトリには、いざ旅アプリケーションの詳細なドキュメントが含まれています。

## 📖 ドキュメント構成

### 📋 テスト関連 (`testing/`)
- **[TEST_SUMMARY.md](testing/TEST_SUMMARY.md)** - テストスイート実装の完了サマリー（163+ テストケース）
- **[test_mapping.md](testing/test_mapping.md)** - 包括的テスト設計書・テスト項目とコードの対応表

### 🔧 保守・メンテナンス (`maintenance/`)
- **[cleanup_report.md](maintenance/cleanup_report.md)** - 未使用ファイル整理レポート

### 📊 設計・仕様書
- **[AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md)** - ADK統合・マルチエージェントシステム詳細仕様
- **[async_plan_generation_analysis.md](async_plan_generation_analysis.md)** - 非同期旅行プラン生成 実装方法検討書
- **[async_plan_technical_specs.md](async_plan_technical_specs.md)** - 非同期旅行プラン生成 技術仕様書

### 🏗️ コンポーネント情報
コンポーネントの詳細情報は以下に記載されています：
- **[メイン README](../README.md)** - 全コンポーネントの概要（17個のビュー、11個のUIコンポーネント、7個のBlueprint）
- **agent/** - エージェント関連ドキュメント（`../agent/` 内に配置）
  - `agent/README.md` - ADKマルチエージェントサービスの詳細（Root Coordinator + 4サブエージェント）
  - `agent/AGENT_FIX_NOTES.md` - エージェント設定修正履歴（Tool Configuration、Circular Import修正）
- **server/** - バックエンド関連ドキュメント（`../server/` 内に配置）
  - `server/README_REFACTORING.md` - バックエンドリファクタリングサマリー（85.5%の複雑性削減）

## 🚀 クイックスタート

### 基本情報
- **[メイン README](../README.md)** - プロジェクト概要・セットアップ・使用方法
- **[開発者向け手順書](../.github/copilot-instructions.md)** - 効果的な開発方法・トラブルシューティング

### テスト実行
```bash
# フロントエンドテスト (Jest) - 81個のテストケース
cd client && npm test

# カバレッジ付きテスト実行
cd client && npm run test:coverage

# バックエンドテスト (pytest) - 82個のテストケース
cd server && pytest --cov=app

# 全テストスイート実行 (合計163+ テストケース)
# フロントエンド: apiClient (36), authStore (45)
# バックエンド: auth (20), health (14), quiz (18), 他多数
```

### ドキュメント更新
新しい機能を追加した場合：
1. 該当するドキュメントファイルを更新
2. テスト関連の変更があれば `testing/` ディレクトリ内のファイルを更新
3. メイン README.md の機能一覧を更新

## 📚 関連リソース

- **技術スタック**: Vue.js 3.4.21, Flask 3.0.3, Google ADK, Gemini 2.5 Pro
- **デプロイ先**: Google Cloud Run
- **データベース**: Google Firestore
- **CI/CD**: GitHub Actions
