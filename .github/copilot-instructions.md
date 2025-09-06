# GitHub Copilot Instructions for Izatabi Project

このファイルは、GitHub Copilotがいざ旅（Izatabi）プロジェクトで効果的にコード生成・支援を行うためのガイドラインです。

## 🏗️ プロジェクト概要

**いざ旅**は、AIを活用した旅行診断・プランニングアプリケーションです。

### 主要コンポーネント
- **Frontend** (`client/`): Vue.js 3 + Composition API + Vite
- **Backend** (`server/`): Python Flask + Google Firestore
- **AI Agent** (`agent/`): Google ADK (Agent Development Kit) + Gemini API
- **MCP Service** (`mcp/`): Google Maps Platform Code Assist

## 📁 プロジェクト構造

```
├── client/                 # Vue.js フロントエンド
│   ├── src/
│   │   ├── components/     # 再利用可能コンポーネント
│   │   ├── views/         # ページレベルコンポーネント
│   │   ├── stores/        # Pinia状態管理
│   │   ├── services/      # API通信ロジック
│   │   └── router/        # Vue Router設定
├── server/                # Flask バックエンド
│   ├── app.py            # メインAPIサーバー
│   └── .env              # 環境変数（要作成）
├── agent/                # ADK AIエージェント
│   ├── agents/
│   │   └── travel_planner/ # 旅行プランナーエージェント
│   └── tools/            # カスタムツール
├── mcp/                  # Maps Code Assist MCP
└── .github/
    ├── workflows/        # CI/CDワークフロー
    └── copilot-instructions.md  # このファイル
```

## 🎯 開発原則・パターン

### 1. 環境・ブランチ戦略
- **dev**ブランチをデフォルトターゲットとする
- 本番環境は`main`、開発環境は`dev`ブランチ
- 新機能は`feature/*`、バグ修正は`fix/*`ブランチで開発

### 2. コーディング規約

#### Frontend (Vue.js)
```javascript
// ✅ 推奨: Composition API使用
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLoading = ref(false)

// computedは必要に応じて使用
const displayText = computed(() => {
  return isLoading.value ? '読み込み中...' : 'データ表示'
})
</script>

// ✅ 推奨: scoped CSS使用
<style scoped>
.component-class {
  /* スタイル定義 */
}
</style>
```

#### Backend (Python Flask)
```python
# ✅ 推奨: 型ヒント使用
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

@app.route('/api/endpoint', methods=['POST'])
def api_endpoint() -> Dict[str, Any]:
    """APIエンドポイントの説明"""
    try:
        data = request.get_json() or {}
        # 処理ロジック
        return jsonify({"status": "success"})
    except Exception as e:
        logger.exception("エラーメッセージ")
        return jsonify({"error": "エラー内容"}), 500
```

### 3. エラーハンドリング
- フロントエンド: try-catch + ユーザーフレンドリーなエラーメッセージ
- バックエンド: 適切なHTTPステータスコード + ログ出力
- データベース操作: timeout設定 + フォールバック処理

### 4. API設計

#### RESTful原則に従う
```
GET /api/plans           # プラン一覧取得
POST /api/plans          # プラン作成
GET /api/plans/:id       # プラン詳細取得
PUT /api/plans/:id       # プラン更新
DELETE /api/plans/:id    # プラン削除
```

#### レスポンス形式
```json
{
  "data": {...},
  "status": "success|error",
  "message": "メッセージ",
  "trace_id": "トレースID"
}
```

## 🔧 技術固有のガイドライン

### Vue.js開発
- **Pinia**を状態管理に使用
- **Vue Router**でルーティング
- **Composition API**を優先して使用
- コンポーネントは適切に分割（単一責任原則）

```javascript
// ✅ Store定義例
import { defineStore } from 'pinia'

export const useQuizStore = defineStore('quiz', () => {
  const questions = ref([])
  const currentIndex = ref(0)
  
  const fetchQuestions = async () => {
    try {
      // API呼び出し
    } catch (error) {
      console.error('Failed to fetch questions:', error)
    }
  }
  
  return { questions, currentIndex, fetchQuestions }
})
```

### Flask開発
- 認証はJWT使用
- Firestoreアクセスは適切なtimeout設定
- ログレベルを環境に応じて調整
- 環境変数での設定管理

```python
# ✅ Firestore操作例
@app.route('/api/data', methods=['GET'])
def get_data():
    claims = require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    
    try:
        doc_ref = db.collection('users').document(claims['sub'])
        doc = doc_ref.get(timeout=5)
        if doc.exists:
            return jsonify(doc.to_dict())
        return jsonify({}), 404
    except Exception as e:
        logger.exception("Database error")
        return jsonify({"error": "database_unavailable"}), 503
```

### ADK Agent開発
- `google.adk`パッケージを活用
- システムプロンプトは日本語で記述
- ツール利用時は適切なエラーハンドリング

```python
# ✅ Agent定義例
from google.adk.core import BaseAgent
from google.adk.tools import google_search

class TravelPlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="travel_planner",
            description="日本国内旅行のプランニングを支援するエージェント",
            model="gemini-2.5-flash"
        )
        self.add_tool(google_search)
```

## 🚨 重要な制約・注意事項

### セキュリティ
- **APIキーやシークレットは絶対にコードにハードコードしない**
- 環境変数で管理し、`.env`ファイルは`.gitignore`に含める
- JWTトークンの適切な有効期限設定
- CORS設定は環境に応じて適切に設定

### パフォーマンス
- Firestoreクエリは効率的に（適切なインデックス使用）
- フロントエンドのバンドルサイズを最適化
- 画像やマップの遅延読み込み実装

### ユーザビリティ
- エラーメッセージは日本語でユーザーフレンドリーに
- ローディング状態の適切な表示
- レスポンシブデザインの考慮

## 🔄 よくある開発タスク

### 新しいAPIエンドポイント追加
1. `server/app.py`にルート定義
2. 適切な認証チェック
3. バリデーション実装
4. エラーハンドリング
5. フロントエンドのサービス層にAPI呼び出し追加

### 新しいVueコンポーネント作成
1. `components/`または`views/`に配置
2. Composition API使用
3. Props定義にTypeScriptライクな型指定
4. 適切なemit定義
5. scoped CSS使用

### 新しいPiniaストア作成
1. `stores/`ディレクトリに配置
2. Composition API形式で定義
3. 非同期処理は適切にtry-catch
4. 状態の適切な初期化

## 🌐 外部サービス連携

### Google Maps API
- フロントエンド：`VITE_GOOGLE_MAPS_API_KEY`使用
- バックエンド：`GOOGLE_MAPS_API_KEY`使用（Geocoding, Static Maps）
- Advanced Marker使用時はMap ID必須

### Gemini API
- `GEMINI_API_KEY`環境変数で管理
- ADKエージェント経由でアクセス
- レスポンス形式の適切なパース

### Firestore
- プロジェクトIDとデータベース名を環境で分離
- 適切なセキュリティルール設定
- オフライン対応は現在未実装

## 📝 コメント・ドキュメント

### 関数・メソッドのコメント
```python
def analyze_travel_style(responses: List[Dict]) -> Dict[str, Any]:
    """旅行スタイルを分析し、ペルソナを生成する
    
    Args:
        responses: ユーザーの診断回答データ
        
    Returns:
        分析結果とペルソナ情報を含む辞書
        
    Raises:
        ValueError: 回答データが不正な場合
    """
```

### 複雑なロジックへのコメント
```javascript
// ユーザーの回答から旅行嗜好スコアを計算
// 各特性（新規性追求、計画性など）を1-4のスケールで評価
const calculateTraitScores = (answers) => {
  // 実装...
}
```

---

**重要**: このガイドラインに従って、一貫性のあるコードを生成し、プロジェクトの品質向上に貢献してください。