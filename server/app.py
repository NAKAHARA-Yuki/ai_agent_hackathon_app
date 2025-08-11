import os
import time
import random
import re
import json
import requests
from flask import Flask, jsonify, send_from_directory, request
from dotenv import load_dotenv
from google.cloud import firestore
import jwt
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__, static_folder='client/dist', static_url_path='/')

# Gemini APIキーの設定
api_key = os.getenv("GEMINI_API_KEY")
genai_configured = bool(api_key and api_key != "YOUR_API_KEY_HERE")

if not genai_configured:
    print("WARNING: GEMINI_API_KEY is not set or is a placeholder. The AI analysis will use dummy data.")
else:
    # ここでは genai.configure は呼び出しません。
    # REST API を直接呼び出すため、SDKの設定は不要です。
    print("Gemini API key is set. Using REST API for AI analysis.")

# Auth / DB config
FIRESTORE_PROJECT = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")

# JWT Secret 強化: 本番では未設定を許可しない
ENV = os.getenv("FLASK_ENV") or os.getenv("ENV") or "production"
_jwt_from_env = os.getenv("JWT_SECRET")
if ENV.lower() == "development":
    JWT_SECRET = _jwt_from_env or "dev-secret-change-me"
else:
    if not _jwt_from_env or _jwt_from_env == "dev-secret-change-me":
        raise RuntimeError("JWT_SECRET environment variable must be set in production.")
    JWT_SECRET = _jwt_from_env

JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "2880"))  # 48h

db = None
try:
    db = firestore.Client(project=FIRESTORE_PROJECT) if FIRESTORE_PROJECT else firestore.Client()
    print("Firestore client initialized.")
except Exception as e:
    print(f"WARNING: Firestore client init failed: {e}")
    db = None

# Development fallback: in-memory DB when Firestore is unavailable
if db is None and (os.getenv("FLASK_ENV", "").lower() == "development" or os.getenv("ENV", "").lower() == "development"):
    import uuid
    from copy import deepcopy

    class _DevDocSnapshot:
        def __init__(self, data):
            self._data = deepcopy(data) if data is not None else None

        @property
        def exists(self):
            return self._data is not None

        def to_dict(self):
            return deepcopy(self._data) if self._data is not None else None

    class _DevDocumentRef:
        def __init__(self, store, path):
            self._store = store
            self._path = path  # tuple of segments
            self.id = path[-1] if path else None

        def _now_iso(self):
            return datetime.utcnow().isoformat() + "Z"

        def _resolve(self):
            cur = self._store
            for seg in self._path:
                cur = cur.setdefault(seg, {})
            return cur

        def get(self):
            node = self._resolve()
            data = node.get("__doc__")
            return _DevDocSnapshot(data)

        def set(self, data):
            node = self._resolve()
            doc = deepcopy(data)
            # replace Firestore server timestamps if present
            for k, v in list(doc.items()):
                if v is getattr(firestore, "SERVER_TIMESTAMP", object()):
                    doc[k] = self._now_iso()
            node["__doc__"] = doc

        def update(self, data):
            node = self._resolve()
            base = node.get("__doc__", {})
            for k, v in data.items():
                base[k] = v
            node["__doc__"] = base

        def collection(self, name):
            return _DevCollectionRef(self._store, self._path + (name,))

    class _DevCollectionRef:
        def __init__(self, store, path):
            self._store = store
            self._path = path  # tuple of segments

        def document(self, doc_id=None):
            if not doc_id:
                doc_id = uuid.uuid4().hex
            # ensure collection container exists
            cur = self._store
            for seg in self._path:
                cur = cur.setdefault(seg, {})
            # create doc node
            cur.setdefault(doc_id, {})
            return _DevDocumentRef(self._store, self._path + (doc_id,))

    class DevDB:
        def __init__(self):
            self._store = {}

        def collection(self, name):
            return _DevCollectionRef(self._store, (name,))

    db = DevDB()
    print("DevDB initialized (in-memory). Firestore is not used in development mode.")

def create_jwt(user_id: str):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MIN)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def require_auth(req):
    authz = req.headers.get("Authorization", "")
    if authz.startswith("Bearer "):
        token = authz.split(" ", 1)[1]
        return verify_jwt(token)
    return None



# レポートに基づいた10個全ての質問データ
QUESTIONS = [
    {
        "id": 1,
        "trait": "新規性追求",
        "trait_description": "新しい、未知の体験をどれだけ好むかを示します。スコアが高いほど、冒険的で型にはまらない旅を求める傾向があります。",
        "question": "あなたの理想の旅に最も近いのはどれですか？",
        "options": [
            {"text": "すべて手配済みの人気観光地への快適なパッケージツアー。", "score": 1},
            {"text": "有名な都市のホテルに滞在し、自分で名所を巡る旅。", "score": 2},
            {"text": "あまり知られていない地域へ自ら手配し、定番から外れた体験を目指す旅。", "score": 3},
            {"text": "観光インフラが未整備な地域へ赴き、現地の生活に完全に溶け込む旅。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "最も「生きている」と感じた旅の思い出を教えてください。何が特別でしたか？",
        "free_text_placeholder": "例：誰もいない早朝のビーチで、水平線から昇る朝日を独り占めした時。"
    },
    {
        "id": 2,
        "trait": "旅程密度",
        "trait_description": "旅行中にどれだけ多くの活動を詰め込みたいかを示します。スコアが高いほど、多くの体験を効率的にこなすことを好む傾向があります。",
        "question": "旅行中の1日の過ごし方として、どちらを好みますか？",
        "options": [
            {"text": "1つの場所に腰を据え、何もしない贅沢を味わう。", "score": 1},
            {"text": "主な見どころをいくつか、ゆったりしたペースで巡る。", "score": 2},
            {"text": "効率的に計画を立て、多くのスポットや体験を組み合わせる。", "score": 3},
            {"text": "朝から晩まで、分刻みのスケジュールで活動的に動き回る。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "理想的な旅行の1日を、朝起きてから寝るまでどのように過ごしたいですか？",
        "free_text_placeholder": "例：朝はカフェでゆっくり過ごし、午後は美術館へ。夜は地元の人気レストランでディナー。"
    },
    {
        "id": 3,
        "trait": "予算哲学",
        "trait_description": "旅行におけるお金の使い方に関する考え方を示します。スコアが高いほど、価格よりも体験の質を重視する傾向があります。",
        "question": "旅行の計画を立てる際、予算についてどのように考えますか？",
        "options": [
            {"text": "最も重要なのは価格。常に最もお得な選択肢を探す。", "score": 1},
            {"text": "予算内で最大限の価値を得られるよう、コストパフォーマンスを重視する。", "score": 2},
            {"text": "素晴らしい体験のためなら、多少予算を超えても構わない。", "score": 3},
            {"text": "予算は二の次。最高の体験を得るために必要な費用は惜しまない。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "「これはお金をかけて良かった」と感じた旅行体験は何ですか？その理由も教えてください。",
        "free_text_placeholder": "例：少し高かったけど、熱気球から見た朝焼けの景色は一生の思い出になった。"
    },
    {
        "id": 4,
        "trait": "社会的志向性",
        "trait_description": "旅行中に他人とどの程度関わりたいかを示します。スコアが高いほど、現地の人や他の旅行者との交流を積極的に求める傾向があります。",
        "question": "旅行先で、どのような人との関わり方を好みますか？",
        "options": [
            {"text": "できるだけ人と関わらず、一人の時間を静かに楽しみたい。", "score": 1},
            {"text": "同行者との時間を大切にし、グループ内での交流を深めたい。", "score": 2},
            {"text": "他の旅行者と情報交換したり、食事を共にしたりするのも楽しい。", "score": 3},
            {"text": "現地の人々と積極的に交流し、その土地の文化を肌で感じたい。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "旅行先で誰かと交流して楽しかった経験があれば教えてください。",
        "free_text_placeholder": "例：ゲストハウスで出会った旅行者と意気投合し、一緒に観光したこと。"
    },
    {
        "id": 5,
        "trait": "主な興味関心",
        "trait_description": "旅行の主な目的が何であるかを示します。スコアはリラックス(1)→食事(2)→自然(3)→文化(4)という軸で評価されますが、グラフでは総合的な興味の方向性として解釈されます。",
        "question": "旅行の最大の目的となることが多いのは、次のうちどれですか？",
        "options": [
            {"text": "日常を忘れて心身ともにリラックスすること。", "score": 1},
            {"text": "その土地ならではの美味しい食事やお酒を堪能すること。", "score": 2},
            {"text": "美しい自然の風景や野生動物との出会いを楽しむこと。", "score": 3},
            {"text": "美術館や史跡を巡り、歴史や文化に触れること。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "これまでの旅行で最も情熱を注いだテーマ（食、アート、自然など）と、その具体的なエピソードを教えてください。",
        "free_text_placeholder": "例：ラーメンが好きで、旅行先では必ず地元の人気店を3軒以上はしごします。"
    },
    {
        "id": 6,
        "trait": "計画志向性",
        "trait_description": "旅行をどの程度詳細に計画するかを示します。スコアが高いほど、事前の計画を重視し、スケジュール通りに行動することを好む傾向があります。",
        "question": "旅行の計画はどの程度立てますか？",
        "options": [
            {"text": "ほとんど計画せず、その場の気分や出会いを大切にする。", "score": 1},
            {"text": "大まかな行き先だけ決め、詳細は現地で決めることが多い。", "score": 2},
            {"text": "行きたい場所ややりたいことをリストアップし、大まかな日程を組む。", "score": 3},
            {"text": "交通機関やレストランまで予約し、詳細な旅程表を作成する。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "計画通りに進まなかったけれど、結果的に最高の思い出になった経験はありますか？",
        "free_text_placeholder": "例：乗る予定のバスを逃したが、そのおかげで素敵なカフェを見つけられた。"
    },
    {
        "id": 7,
        "trait": "快適性水準",
        "trait_description": "宿泊施設や移動手段にどれだけの快適さを求めるかを示します。スコアが高いほど、快適さや豪華さを重視する傾向があります。",
        "question": "宿泊施設を選ぶ際に、最も重視する点は何ですか？",
        "options": [
            {"text": "価格と立地。寝るだけなので最低限の設備で十分。", "score": 1},
            {"text": "清潔で安全、かつ機能的であること。", "score": 2},
            {"text": "デザイン性が高く、快適なアメニティやサービスが揃っていること。", "score": 3},
            {"text": "スパや高級レストランなど、施設内で特別な体験ができること。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "今までで最高のホテル体験と、その理由を教えてください。",
        "free_text_placeholder": "例：部屋の窓から見える景色が素晴らしく、朝食も美味しかったホテル。"
    },
    {
        "id": 8,
        "trait": "活動レベル",
        "trait_description": "旅行中にどれだけ身体を動かすことを好むかを示します。スコアが高いほど、ハイキングやスポーツなどのアクティブな活動を求める傾向があります。",
        "question": "旅行中の身体活動について、あなたの好みはどれですか？",
        "options": [
            {"text": "ほとんど歩き回らず、乗り物や施設内でゆったり過ごしたい。", "score": 1},
            {"text": "のんびり散策したり、景色を楽しんだりする程度が心地よい。", "score": 2},
            {"text": "街歩きや軽いハイキングなど、積極的に体を動かしたい。", "score": 3},
            {"text": "登山やマリンスポーツなど、挑戦的なアクティビティを楽しみたい。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "旅行先で体を動かして楽しかったアクティビティは何ですか？",
        "free_text_placeholder": "例：初めて挑戦したカヤックで、川の上からの景色を楽しんだこと。"
    },
    {
        "id": 9,
        "trait": "安全性の閾値",
        "trait_description": "旅行先の安全性やリスクをどの程度重視するかを示します。スコアが高いほど、安全性を最優先し、リスクを避ける傾向があります。",
        "question": "新しい旅行先を選ぶ際、安全性についてどの程度考慮しますか？",
        "options": [
            {"text": "あまり気にしない。多少のリスクは冒険の一部だと考える。", "score": 1},
            {"text": "一般的な観光地であれば、特に問題ないだろうと考える。", "score": 2},
            {"text": "事前に外務省の安全情報などを確認し、治安の良い地域を選ぶ。", "score": 3},
            {"text": "医療体制や衛生環境を含め、最高レベルの安全が確保されている場所を選ぶ。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "旅行の準備で、安全のために特別に行っていることはありますか？",
        "free_text_placeholder": "例：海外旅行では、スリ対策のために体の前にかけるバッグを使っている。"
    },
    {
        "id": 10,
        "trait": "デジタル統合度",
        "trait_description": "旅行中にスマートフォンやアプリなどのテクノロジーをどの程度活用するかを示します。スコアが高いほど、テクノロジーを駆使して旅を効率化・記録することを好む傾向があります。",
        "question": "旅行中にテクノロジーをどのように活用しますか？",
        "options": [
            {"text": "デジタルデトックスを好み、スマホやPCはほとんど使わない。", "score": 1},
            {"text": "地図アプリや翻訳アプリなど、必要最低限のツールのみ利用する。", "score": 2},
            {"text": "予約管理、情報収集、SNS投稿など、積極的にテクノロジーを活用する。", "score": 3},
            {"text": "最新のガジェットやアプリを駆使し、旅の全てを記録・最適化する。", "score": 4},
            {"text": "上記のどれでもない（自由記述）", "score": 0}
        ],
        "free_text_prompt": "あなたの旅行を劇的に便利にしたアプリやウェブサイトがあれば教えてください。",
        "free_text_placeholder": "例：Google Mapsのオフライン機能のおかげで、電波がない場所でも迷わなかった。"
    }
]

@app.route('/api/questions')
def get_questions():
    return jsonify(QUESTIONS)

def call_gemini_api(prompt, model_name='gemini-2.5-flash'):
    """
    Gemini APIをRESTで呼び出す共通関数。
    """
    if not genai_configured:
        raise Exception("GEMINI_API_KEY is not configured.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': api_key
    }
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status() # HTTPエラーがあれば例外を発生させる
    
    # APIからのレスポンスを直接JSONとしてパース
    return response.json()

@app.route('/api/analyze', methods=['POST'])
def analyze_text():
    """
    自由記述のテキストを受け取り、AIで分析してスコアと解説を返すAPIエンドポイント。
    """
    data = request.get_json()
    text = data.get('text', '')
    question_trait = data.get('trait', '')
    question_text = data.get('question', '')

    # 自由記述がない場合でも、選択式回答に基づいて基本的な解説を生成する
    if not text:
        base_score = data.get('base_score', 0)
        options = next((q['options'] for q in QUESTIONS if q['id'] == data.get('question_id')), [])
        selected_option_text = next((opt['text'] for opt in options if opt['score'] == base_score), "未選択")

        # AIに解説生成を依頼
        try:
            prompt = f"""
            あなたは、ユーザーの旅行スタイルを分析する専門家です。
            以下の質問とユーザーが選択した回答に基づいて、なぜその選択が特定の旅行スタイルを示すのかを簡潔に（50文字程度で）解説してください。

            ### 質問の特性
            {question_trait}

            ### 質問文
            {question_text}

            ### ユーザーが選択した回答
            「{selected_option_text}」

            ### 解説の生成例
            「計画性よりも、その場の出会いや発見を大切にする冒険家タイプですね。」

            ---
            あなたの解説：
            """
            api_response = call_gemini_api(prompt)
            # APIレスポンスのテキスト部分を抽出
            explanation = api_response['candidates'][0]['content']['parts'][0]['text'].strip()
            return jsonify({"analyzed_score": base_score, "explanation": explanation})

        except Exception as e:
            print(f"Error generating explanation for non-free-text answer: {e}")
            # エラーが発生した場合は、汎用的な解説を返す
            return jsonify({"analyzed_score": base_score, "explanation": f"「{question_trait}」の観点から、あなたの選択は一貫したスタイルを示しています。"})

    if not genai_configured:
        print("Skipping Gemini API call due to missing configuration.")
        time.sleep(1)
        dummy_score = random.randint(1, 4)
        dummy_explanation = f"これは「{question_trait}」に関するダミーの解説です。スコアは{dummy_score}と評価されました。"
        return jsonify({"analyzed_score": dummy_score, "explanation": dummy_explanation})


    try:
        prompt = f"""
        あなたは、ユーザーの旅行スタイルを分析する専門家です。
        以下の質問とユーザーの自由記述回答を分析し、2つのタスクを実行してください。

        1.  **スコアリング**: ユーザーの旅行スタイルが特定の特性においてどの程度かを1から4の尺度で評価してください。
            -   評価の基準は質問の選択肢を参考にしてください。スコアが低いほど選択肢1に近く、高いほど選択肢4に近いことを意味します。
            -   例えば、「1: 依存型」〜「4: 冒険型」のような尺度です。

        2.  **解説の生成**: なぜそのスコアになったのか、ユーザーの回答のどの部分からそう判断したのかを、簡潔に（50文字程度で）説明してください。

        ---
        ### 質問の特性
        {question_trait}

        ### 質問文
        {question_text}

        ### ユーザーの自由記述回答
        {text}
        ---

        分析と評価を行い、必ず以下のJSON形式で結果を返してください。
        {{
          "analyzed_score": <1から4の整数スコア>,
          "explanation": "<評価の根拠となる簡潔な解説>"
        }}
        """
        
        api_response = call_gemini_api(prompt)
        
        # レスポンスからコンテンツを抽出
        content_text = api_response['candidates'][0]['content']['parts'][0]['text']
        result_data = json.loads(content_text)
        
        score = int(result_data.get("analyzed_score", 0))
        score = max(1, min(4, score))
        
        explanation = result_data.get("explanation", "解説を生成できませんでした。")

        return jsonify({"analyzed_score": score, "explanation": explanation})

    except Exception as e:
        print(f"An error occurred during Gemini API call: {e}")
        score = random.randint(1, 4)
        explanation = f"AIの分析中にエラーが発生しました。ダミーデータ（スコア: {score}）を返します。"
        return jsonify({"analyzed_score": score, "explanation": explanation})

@app.route('/api/generate_plan', methods=['POST'])
def generate_plan():
    data = request.get_json()
    if not data or 'travel_type' not in data or 'description' not in data:
        return jsonify({"error": "Missing travel_type or description"}), 400

    if not genai_configured:
        print("Skipping Gemini API call for plan generation due to missing configuration.")
        # ダミーのプランを返す
        dummy_plans = {
            "plans": [
                {"title": "設定エラー", "description": "APIキーが設定されていないため、AIプランを生成できません。"},
                {"title": "管理者向け", "description": "server/.env ファイルに有効な GEMINI_API_KEY を設定してください。"}
            ]
        }
        return jsonify(dummy_plans)

    try:
        travel_type = data['travel_type']
        description = data['description']

        prompt = f"""
        あなたは日本の旅行プランを提案する専門家です。
        以下の旅行者タイプ診断の結果に基づいて、その人に合った日本の国内旅行プランを3つ提案してください。

        # 診断結果
        ## 旅行タイプ
        {travel_type}

        ## タイプの説明
        {description}

        # 指示
        1.  提案は必ず日本の国内旅行に限定してください。
        2.  多様な地域のプランを提案してください（例：北海道、本州、九州・沖縄など）。
        3.  各プランには「タイトル」と「簡単な説明」を含めてください。
        4.  出力は必ず以下のJSON形式に従ってください。
            {{
              "plans": [
                {{
                  "title": "<プラン1のタイトル>",
                  "description": "<プラン1の簡単な説明>"
                }},
                {{
                  "title": "<プラン2のタイトル>",
                  "description": "<プラン2の簡単な説明>"
                }},
                {{
                  "title": "<プラン3のタイトル>",
                  "description": "<プラン3の簡単な説明>"
                }}
              ]
            }}
        """

        api_response = call_gemini_api(prompt)
        
        # レスポンスからコンテンツを抽出
        content_text = api_response['candidates'][0]['content']['parts'][0]['text']
        plan_result = json.loads(content_text)

        return jsonify(plan_result)

    except Exception as e:
        print(f"An error occurred during plan generation: {e}")
        return jsonify({"error": "Failed to generate travel plans with AI", "details": str(e)}), 500


# ==== Auth endpoints (Firestore) ====
USER_ID_REGEX = r'[a-z0-9_-]{3,30}'
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    if db is None:
        return jsonify({"error": "Database not configured"}), 500
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    user_id = (data.get('user_id') or '').strip().lower()
    password = data.get('password') or ''
    # Validate
    if not name or not user_id or not password:
        return jsonify({"error": "missing fields"}), 400
    # user_id: 3-30 chars, lowercase letters, numbers, _-
    if not re.fullmatch(USER_ID_REGEX, user_id):
        return jsonify({"error": "invalid user_id"}), 400
    if len(password) < 8:
        return jsonify({"error": "weak password"}), 400
    users_ref = db.collection('users')
    # Use user_id as document id to enforce uniqueness
    doc_ref = users_ref.document(user_id)
    if doc_ref.get().exists:
        return jsonify({"error": "user_id already exists"}), 409
    user_doc = {
        'name': name,
        'user_id': user_id,
        'password_hash': generate_password_hash(password),
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    doc_ref.set(user_doc)
    token = create_jwt(user_id)
    return jsonify({"token": token, "user": {"id": user_id, "name": name}})


@app.route('/api/auth/login', methods=['POST'])
def login():
    if db is None:
        return jsonify({"error": "Database not configured"}), 500
    data = request.get_json() or {}
    user_id = (data.get('user_id') or '').strip().lower()
    password = data.get('password') or ''
    if not user_id or not password:
        return jsonify({"error": "missing fields"}), 400
    if not re.fullmatch(USER_ID_REGEX, user_id):
        return jsonify({"error": "invalid user_id"}), 400
    users_ref = db.collection('users')
    doc = users_ref.document(user_id).get()
    if not doc.exists:
        return jsonify({"error": "invalid credentials"}), 401
    user = doc.to_dict()
    if not check_password_hash(user.get('password_hash', ''), password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_jwt(user_id)
    return jsonify({"token": token, "user": {"id": user_id, "name": user.get('name')}})


# ==== Persona generation and storage ====
@app.route('/api/persona', methods=['POST'])
def create_persona():
    if db is None:
        return jsonify({"error": "Database not configured"}), 500
    claims = require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json() or {}
    # Expect: { profile: {traitScores.., title, description}, system_prompt?: string }
    profile = data.get('profile') or {}
    system_prompt = data.get('system_prompt')

    # If system_prompt not provided, generate via Gemini
    if not system_prompt:
        if not genai_configured:
            system_prompt = (
                "あなたは旅行者の嗜好に基づき、国内旅行の提案と旅程調整を行うペルソナエージェントです。"
                "安全・予算・移動時間に配慮し、ユーザーのタイプ（{title}）の説明（{desc}）を尊重して提案します。"
            ).format(title=profile.get('title'), desc=profile.get('description'))
        else:
            try:
                prompt = f"""
                あなたは旅行者専用のペルソナエージェントのシステムプロンプトを作成します。
                以下の診断結果（タイプ名と説明、特性スコア）を読み、エージェントが守るべき原則・口調・判断基準・制約を日本語で明確に列挙してください。
                出力は純テキストのみ（箇条書き可）。

                # タイプ
                {profile.get('title')}

                # 説明
                {profile.get('description')}

                # 特性スコア
                {json.dumps(profile.get('traitScores', {}), ensure_ascii=False)}
                """
                api_response = call_gemini_api(prompt)
                system_prompt = api_response['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                print(f"Persona prompt generation error: {e}")
                system_prompt = (
                    "ユーザーの診断結果に沿って、日本国内の旅行計画を丁寧に提案・調整すること。"
                )

    personas_ref = db.collection('users').document(claims['sub']).collection('personas')
    doc_ref = personas_ref.document()
    doc = {
        'profile': profile,
        'system_prompt': system_prompt,
        'created_at': firestore.SERVER_TIMESTAMP
    }
    doc_ref.set(doc)
    return jsonify({"id": doc_ref.id, "profile": profile, "system_prompt": system_prompt})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path!= "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))



