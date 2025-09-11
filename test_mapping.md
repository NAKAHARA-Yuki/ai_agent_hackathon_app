# 旅行アプリ テスト設計書

本ドキュメントは、Vue.js フロントエンドおよび Flask バックエンドの包括的なテストスイートについて、テスト因子とテスト項目、対応するテストコードの関係を整理したものです。

## 目標

- **C1カバレッジ100%を達成**
- **すべての主要機能をテスト**
- **エラーハンドリングと境界値テスト**
- **モックとリアルAPI両対応**

---

## Frontend Testing (Vue.js + Jest)

### 1. API Client Service (`client/src/services/apiClient.js`)

#### テスト因子
- Mock/Real APIモード切り替え
- HTTP通信エラーハンドリング
- リトライ機能
- localStorage操作
- データ変換・バリデーション

#### テスト項目とテストコード

| テスト項目 | テスト因子 | テストコード | 期待結果 |
|-----------|-----------|-------------|----------|
| **エージェントチャット (agentChat)** |
| 正常なAPI呼び出し | 非Mockモード | `test_should_call_agent_chat_API_in_non_mock_mode` | 適切なHTTPリクエスト、正常レスポンス |
| Mockモード動作 | Mockモード | `test_should_return_mock_response_in_mock_mode` | モックデータ返却 |
| 401認証エラー | 認証失敗 | `test_should_handle_401_unauthorized_error` | 適切なエラーメッセージ |
| 503リトライ機能 | サービス停止 | `test_should_handle_503_service_unavailable_with_retry` | 自動リトライ実行 |
| 最大リトライ超過 | リトライ上限 | `test_should_fail_after_max_retries_on_503` | エラー発生 |
| **プラン管理 (Plans)** |
| プラン一覧取得 | API通信 | `test_should_list_plans_from_API` | プラン配列取得 |
| プラン作成 | データ送信 | `test_should_create_plan_via_API` | 新プラン作成成功 |
| プラン詳細取得 | ID指定 | `test_should_get_plan_detail_from_API` | 詳細データ取得 |
| プラン削除 | ID指定 | `test_should_delete_plan_via_API` | 削除成功 |
| アクティブプラン設定 | 状態管理 | `test_should_set_active_plan_via_API` | アクティブ状態更新 |
| **ローカルストレージ (localStorage)** |
| Mockデータ保存 | localStorage操作 | `test_should_handle_createPlan_in_mock_mode` | データ永続化 |
| データ取得エラー処理 | JSON解析失敗 | `test_should_handle_localStorage_parsing_errors_gracefully` | エラー時デフォルト値 |
| 容量不足エラー | 保存失敗 | `test_should_handle_localStorage_setItem_errors_gracefully` | 例外処理 |
| **Maps API** |
| キー取得 | API呼び出し | `test_should_get_maps_key_from_API` | 認証キー取得 |
| エラー時フォールバック | API失敗 | `test_should_return_empty_key_on_API_error` | 空キー返却 |
| **ネットワークエラー** |
| ネットワーク障害 | 通信失敗 | `test_should_handle_network_errors` | ネットワークエラー処理 |
| JSONパース失敗 | 不正データ | `test_should_handle_JSON_parse_errors` | パースエラー処理 |
| **ヘルパー関数** |
| UUID生成 | ID生成 | `test_should_generate_UUID_when_crypto_randomUUID_is_available` | 一意ID生成 |
| フォールバックID | crypto未対応 | `test_should_fallback_to_timestamp_based_ID` | タイムスタンプベースID |
| モック返信生成 | キーワード判定 | `test_should_generate_different_replies_for_different_keywords` | キーワード別レスポンス |

**カバレッジ対象:** 全関数、全分岐、エラーハンドリング、モック/リアル両対応

---

## Backend Testing (Flask + pytest)

### 1. 認証エンドポイント (`server/app.py` - Authentication)

#### テスト因子
- ユーザー登録・ログイン
- JWTトークン処理
- パスワードハッシュ化
- バリデーション
- Firestore/DevDB両対応

#### テスト項目とテストコード

| テスト項目 | テスト因子 | テストコード | 期待結果 |
|-----------|-----------|-------------|----------|
| **ユーザー登録 (signup)** |
| 正常登録 | 有効データ | `test_signup_success` | ユーザー作成、JWT返却 |
| 無効ユーザーID | 形式エラー | `test_signup_invalid_user_id` | バリデーションエラー |
| 短すぎるパスワード | 長さエラー | `test_signup_short_password` | パスワードエラー |
| 重複ユーザー | 既存ID | `test_signup_existing_user` | 重複エラー |
| 必須項目不足 | データ不足 | `test_signup_missing_fields` | 必須項目エラー |
| **ログイン (login)** |
| 正常ログイン | 有効認証情報 | `test_login_success` | JWT返却 |
| 無効認証情報 | 存在しないユーザー | `test_login_invalid_credentials` | 認証エラー |
| 間違いパスワード | パスワード不一致 | `test_login_wrong_password` | 認証エラー |
| 必須項目不足 | データ不足 | `test_login_missing_fields` | バリデーションエラー |
| **JWT認証 (/api/me)** |
| 有効認証 | 正当トークン | `test_me_endpoint_authenticated` | ユーザー情報返却 |
| 認証なし | トークンなし | `test_me_endpoint_unauthenticated` | 401エラー |
| 無効トークン | 不正トークン | `test_me_endpoint_invalid_token` | 401エラー |
| 期限切れトークン | 過期トークン | `test_me_endpoint_expired_token` | 401エラー |
| **JWT関連機能** |
| トークン生成 | JWT作成 | `test_jwt_token_validation` | 有効トークン生成 |
| TTL付きトークン | 期限指定 | `test_jwt_token_with_ttl` | 期限付きトークン |
| 認証デコレーター | 認証チェック | `test_require_auth_decorator` | 認証処理 |
| **データベース対応** |
| DevDBフォールバック | Firestore障害 | `test_auth_with_devdb_fallback` | DevDB利用 |

### 2. ヘルスチェックエンドポイント (`/api/health`)

#### テスト因子
- システム状態確認
- データベース接続状態
- 設定確認
- エラー処理

#### テスト項目とテストコード

| テスト項目 | テスト因子 | テストコード | 期待結果 |
|-----------|-----------|-------------|----------|
| 基本ヘルスチェック | システム状態 | `test_health_endpoint_basic` | 正常ステータス返却 |
| Firestore接続 | DB正常 | `test_health_endpoint_with_firestore` | firestore状態表示 |
| DevDBフォールバック | DB障害 | `test_health_endpoint_with_devdb_fallback` | devdb状態表示 |
| Gemini設定確認 | AI設定 | `test_health_endpoint_gemini_configuration` | 設定状態表示 |
| JWT設定確認 | 認証設定 | `test_health_endpoint_jwt_configuration` | JWT状態表示 |
| エージェントメトリクス | 統計情報 | `test_health_endpoint_agent_metrics` | メトリクス表示 |
| HTTPメソッド制限 | メソッド制御 | `test_health_endpoint_methods` | GET のみ許可 |
| 例外処理 | システムエラー | `test_health_endpoint_exception_handling` | エラー時500返却 |

### 3. クイズ・分析エンドポイント

#### テスト因子
- 質問データ取得
- AI分析処理
- 趣味マスター管理
- 同時リクエスト処理

#### テスト項目とテストコード

| テスト項目 | テスト因子 | テストコード | 期待結果 |
|-----------|-----------|-------------|----------|
| **質問取得 (/api/questions)** |
| 質問一覧取得 | データ取得 | `test_get_questions_endpoint` | 質問リスト返却 |
| 質問構造確認 | データ形式 | `test_get_questions_structure` | 適切な構造 |
| キャッシュ一貫性 | データ整合性 | `test_questions_endpoint_caching` | 同一レスポンス |
| **テキスト分析 (/api/analyze)** |
| 正常分析 | AI処理 | `test_analyze_text_endpoint` | 分析結果返却 |
| 必須項目不足 | バリデーション | `test_analyze_text_missing_fields` | バリデーションエラー |
| 空値処理 | 空データ | `test_analyze_text_empty_values` | 適切な処理 |
| 長文処理 | 大量データ | `test_analyze_text_long_input` | 長文対応 |
| AI API障害 | 外部API失敗 | `test_analyze_text_gemini_error` | エラー処理 |
| スコア範囲 | 値の正規化 | `test_analyze_text_score_range` | 1-5範囲内 |
| 多言語対応 | 日本語処理 | `test_analyze_text_with_japanese_text` | 日本語対応 |
| 同時処理 | 並行リクエスト | `test_analyze_text_concurrent_requests` | 並行処理対応 |
| **趣味マスター (/api/hobbies)** |
| 趣味一覧取得 | マスターデータ | `test_get_hobbies_master` | 趣味リスト返却 |
| データ構造確認 | 重み付き構造 | `test_hobbies_endpoint_structure` | 適切な重み値 |

---

## Integration Tests (統合テスト)

### テスト因子
- エンドツーエンド ユーザーフロー
- 外部サービス連携
- データフロー確認

### 主要統合テストシナリオ

| シナリオ | 対象コンポーネント | テスト項目 |
|---------|------------------|-----------|
| **ユーザー登録→ログイン→診断フロー** | Frontend + Backend | 完全なユーザージャーニー |
| **AIプラン生成フロー** | Frontend + Backend + Gemini API | AI機能統合 |
| **マップ連携フロー** | Frontend + Backend + Maps API | 地図機能統合 |
| **モックモード動作** | Frontend Mock Layer | オフライン対応 |

---

## Coverage Goals (カバレッジ目標)

### Frontend (Jest)
- **Statement Coverage:** 100%
- **Branch Coverage:** 100% 
- **Function Coverage:** 100%
- **Line Coverage:** 100%

### Backend (pytest)
- **Statement Coverage:** 100%
- **Branch Coverage:** 100%
- **Function Coverage:** 100%
- **Line Coverage:** 100%

### 除外対象
- 外部ライブラリ (`node_modules`, `site-packages`)
- エントリーポイント (`main.js`)
- 設定ファイル
- エージェントコンテナ (要件により除外)

---

## Test Execution (テスト実行)

### Frontend
```bash
# 全テスト実行
npm test

# カバレッジ付き実行
npm run test:coverage

# 特定テスト実行
npm test -- --testPathPattern=apiClient
```

### Backend
```bash
# 全テスト実行
pytest

# カバレッジ付き実行
pytest --cov=app --cov-report=html

# 特定テスト実行
pytest tests/unit/test_auth_endpoints.py
```

---

## Mock Strategy (モック戦略)

### Frontend
- **localStorage**: Jest mock で完全制御
- **fetch API**: 成功/失敗/タイムアウト パターン
- **crypto.randomUUID**: 予測可能なID生成

### Backend  
- **Firestore**: MagicMock で Firestore Client 模擬
- **Gemini AI**: レスポンス固定でAPI呼び出し模擬
- **Google Maps API**: requests.get 模擬
- **JWT**: 実際のライブラリで生成・検証

---

## Error Scenarios (エラーシナリオテスト)

### Network Errors
- Connection timeout
- DNS resolution failure
- HTTP 5xx errors
- Malformed JSON responses

### Authentication Errors  
- Expired tokens
- Invalid signatures
- Missing credentials
- Permission denied

### Data Validation Errors
- Invalid input formats
- Missing required fields
- Data type mismatches
- Constraint violations

### External Service Failures
- AI API rate limiting
- Maps API quota exceeded  
- Database connection lost
- Third-party service outages

---

## Performance Considerations (パフォーマンス考慮事項)

### Response Time Tests
- API endpoints < 100ms (mocked)
- Database queries optimization
- Large dataset handling

### Concurrency Tests
- Multiple simultaneous requests
- Race condition prevention
- Resource lock testing

### Memory Usage
- Memory leak detection
- Large file upload handling
- Cache management

---

本テスト設計により、旅行アプリの品質を保証し、本番環境での安定動作を確保します。全てのテストは自動化され、継続的インテグレーション (CI) パイプラインで実行されます。