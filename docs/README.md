# いざ旅 (Izatabi) - ドキュメント

このディレクトリには、いざ旅アプリケーションの詳細なドキュメントが含まれています。

## 📖 ドキュメント構成

### 📋 テスト関連 (`testing/`)
- **[TEST_SUMMARY.md](testing/TEST_SUMMARY.md)** - テストスイート実装の完了サマリー
- **[test_mapping.md](testing/test_mapping.md)** - 包括的テスト設計書・テスト項目とコードの対応表

### 🔧 保守・メンテナンス (`maintenance/`)
- **[cleanup_report.md](maintenance/cleanup_report.md)** - 未使用ファイル整理レポート

### 🏗️ コンポーネント情報
コンポーネントの詳細情報は以下に記載されています：
- **[メイン README](../README.md)** - 全コンポーネントの概要（15個のビュー、10個のUIコンポーネント）
- **agent/** - エージェント関連ドキュメント（`../agent/` 内に配置）
  - `agent/README.md` - ADKエージェントサービスの詳細
  - `agent/AGENT_FIX_NOTES.md` - エージェント設定修正履歴
  - `agent/tools/README.md` - エージェントツール説明

## 🚀 クイックスタート

### 基本情報
- **[メイン README](../README.md)** - プロジェクト概要・セットアップ・使用方法
- **[開発者向け手順書](../.github/copilot-instructions.md)** - 効果的な開発方法・トラブルシューティング

### テスト実行
```bash
# フロントエンドテスト (Jest)
cd client && npm test

# バックエンドテスト (pytest) 
cd server && pytest --cov=app
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

---

**最終更新**: 2025年9月15日