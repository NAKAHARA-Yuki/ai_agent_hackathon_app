import os
from pathlib import Path
import time
import random
import re
import json
import requests
import logging
from time import monotonic
from flask import Flask, jsonify, send_from_directory, request, Response
from dotenv import load_dotenv
from google.cloud import firestore
import jwt
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash

# Ensure we load env from this directory (server/.env) even if CWD is repo root
_env_path = Path(__file__).resolve().parent / '.env'
try:
    load_dotenv(dotenv_path=str(_env_path))
except Exception:
    # fallback to default search if direct load fails
    load_dotenv()

app = Flask(__name__, static_folder='client/dist', static_url_path='/')

# Logging setup
LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT") or "%(asctime)s %(levelname)s %(name)s - %(message)s"
try:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)
except Exception:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# Whether to log request/response payloads (useful for debugging; be careful in prod)
# Forced to True as requested
LOG_PAYLOADS = True

SENSITIVE_KEYS = {"password", "pass", "token", "authorization", "api_key", "apikey", "secret", "jwt"}

def _snip_text(s: str, limit: int = 2000) -> str:
    try:
        if s is None:
            return "null"
        if len(s) <= limit:
            return s
        more = len(s) - limit
        return s[:limit] + f"...(+{more} chars)"
    except Exception:
        return str(s)[:limit]

def _sanitize(obj, depth: int = 0, max_depth: int = 5):
    if depth > max_depth:
        return "<max_depth>"
    try:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                key = str(k)
                if any(sk in key.lower() for sk in SENSITIVE_KEYS):
                    out[key] = "***"
                else:
                    out[key] = _sanitize(v, depth+1, max_depth)
            return out
        if isinstance(obj, list):
            return [_sanitize(v, depth+1, max_depth) for v in obj]
        if isinstance(obj, (int, float)):
            return obj
        if isinstance(obj, str):
            return obj
        return str(obj)
    except Exception:
        return str(obj)

def _snip_json(obj, limit: int = 2000) -> str:
    try:
        s = json.dumps(_sanitize(obj), ensure_ascii=False, default=str)
    except Exception:
        try:
            s = str(obj)
        except Exception:
            s = "<unserializable>"
    return _snip_text(s, limit)

@app.before_request
def _start_timer():
    try:
        request._start_time = monotonic()
    except Exception:
        request._start_time = None
    # attach a lightweight correlation id for tracing
    try:
        request._trace_id = f"{random.getrandbits(64):016x}"
    except Exception:
        request._trace_id = None

@app.after_request
def _log_request(resp: Response):
    try:
        dur_ms = None
        if getattr(request, "_start_time", None) is not None:
            dur_ms = (monotonic() - request._start_time) * 1000
        path = request.path
        if path.startswith("/api/"):
            tid = getattr(request, "_trace_id", None)
            if tid:
                resp.headers["X-Trace-Id"] = tid
            logger.info(f"HTTP {request.method} {path} -> {resp.status_code} {int(dur_ms or 0)}ms trace={tid}")
    except Exception:
        pass
    return resp

# Gemini APIキーの設定
api_key = os.getenv("GEMINI_API_KEY")
genai_configured = bool(api_key and api_key != "YOUR_API_KEY_HERE")

if not genai_configured:
    logger.warning("GEMINI_API_KEY is not set or is a placeholder. The AI analysis will use dummy data.")
else:
    # ここでは genai.configure は呼び出しません。
    # REST API を直接呼び出すため、SDKの設定は不要です。
    logger.info("Gemini API key is set. Using REST API for AI analysis.")

# Agent microservice config (ADK api_server)
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL")  # e.g., http://localhost:8080 or Cloud Run URL
AGENT_API_KEY = os.getenv("AGENT_API_KEY")  # optional simple auth header if you set one

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

# After ENV is known, apply dev fallback and compute configured flag
if not AGENT_BASE_URL and ENV.lower() == "development":
    AGENT_BASE_URL = "http://localhost:8080"
agent_configured = bool(AGENT_BASE_URL)
if agent_configured:
    logger.info(f"Agent base URL configured: {AGENT_BASE_URL}")

db = None
try:
    db = firestore.Client(project=FIRESTORE_PROJECT) if FIRESTORE_PROJECT else firestore.Client()
    logger.info("Firestore client initialized.")
except Exception as e:
    logger.warning(f"Firestore client init failed: {e}")
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

        def get(self, *args, **kwargs):
            node = self._resolve()
            data = node.get("__doc__")
            return _DevDocSnapshot(data)

        def set(self, data, *args, **kwargs):
            node = self._resolve()
            doc = deepcopy(data)
            # replace Firestore server timestamps if present
            for k, v in list(doc.items()):
                if v is getattr(firestore, "SERVER_TIMESTAMP", object()):
                    doc[k] = self._now_iso()
            node["__doc__"] = doc

        def update(self, data, *args, **kwargs):
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
    logger.info("DevDB initialized (in-memory). Firestore is not used in development mode.")

# 簡易ヘルスチェック
@app.route('/api/health', methods=['GET'])
def health():
    try:
        db_kind = 'unknown'
        if db is not None:
            db_kind = 'firestore'
            # DevDB クラス名で判断
            if type(db).__name__ == 'DevDB':
                db_kind = 'devdb'
        return jsonify({
            "status": "ok",
            "env": ENV,
            "db": db_kind,
            "gemini_configured": genai_configured,
            "jwt_configured": bool(JWT_SECRET)
        })
    except Exception as e:
        logger.exception("/api/health error")
        return jsonify({"status": "error", "message": str(e)}), 500

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


@app.get('/api/maps-key')
def get_maps_js_key():
    """Expose Google Maps JavaScript API key to the client.
    It is expected to be public on the frontend. Prefer VITE_GOOGLE_MAPS_API_KEY, fallback to GOOGLE_MAPS_API_KEY.
    """
    key = os.getenv('VITE_GOOGLE_MAPS_API_KEY') or os.getenv('GOOGLE_MAPS_API_KEY') or ''
    # avoid returning placeholder text
    if key == 'YOUR_API_KEY_HERE':
        key = ''
    return jsonify({ 'key': key })



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

# 趣味マスタ（likesOptions と同等のデータ）
HOBBIES_MASTER = [
    { "id": "onsen", "label": "温泉・サウナ", "emoji": "♨️", "weights": { "comfort": 0.6, "pace": -0.2 } },
    { "id": "relax", "label": "リラックス・スパ", "emoji": "🧖", "weights": { "comfort": 0.8, "activity": -0.4, "pace": -0.4 } },
    { "id": "art", "label": "アート・美術館", "emoji": "🖼️", "weights": { "culture": 0.7, "novelty": 0.1 } },
    { "id": "history", "label": "歴史・世界遺産", "emoji": "🏛️", "weights": { "culture": 0.8 } },
    { "id": "nature", "label": "自然・絶景", "emoji": "🏞️", "weights": { "nature": 0.8, "activity": 0.2 } },
    { "id": "gourmet", "label": "グルメ・食べ歩き", "emoji": "🍣", "weights": { "gourmet": 0.8, "comfort": 0.1 } },
    { "id": "citywalk", "label": "まち歩き", "emoji": "🚶", "weights": { "activity": 0.4, "culture": 0.2 } },
    { "id": "adventure", "label": "アドベンチャー", "emoji": "🧗", "weights": { "novelty": 0.6, "risk": 0.4, "activity": 0.6 } },
    { "id": "themepark", "label": "テーマパーク", "emoji": "🎢", "weights": { "comfort": 0.2, "pace": 0.2 } },
    { "id": "island", "label": "離島ステイ", "emoji": "🏝️", "weights": { "nature": 0.6, "novelty": 0.3, "comfort": 0.2 } },
    { "id": "snow", "label": "雪・ウィンター", "emoji": "❄️", "weights": { "activity": 0.4, "risk": 0.2, "comfort": -0.1 } },
    { "id": "festival", "label": "祭り・イベント", "emoji": "🎊", "weights": { "social": 0.6, "culture": 0.2 } },

    { "id": "pilgrimage", "label": "聖地巡礼（アニメ・ドラマ）", "emoji": "🎬", "weights": { "culture": 0.5, "novelty": 0.3, "planning": 0.2 } },
    { "id": "cafe", "label": "カフェめぐり", "emoji": "☕", "weights": { "gourmet": 0.6, "comfort": 0.2, "pace": -0.1 } },
    { "id": "coffee", "label": "コーヒー巡り", "emoji": "☕", "weights": { "gourmet": 0.5, "comfort": 0.2, "pace": -0.1 } },
    { "id": "sweets", "label": "スイーツ巡り", "emoji": "🍰", "weights": { "gourmet": 0.5, "comfort": 0.2 } },
    { "id": "bakery", "label": "ベーカリー巡り", "emoji": "🍞", "weights": { "gourmet": 0.4, "comfort": 0.2, "pace": -0.1 } },
    { "id": "ramen", "label": "ラーメン", "emoji": "🍜", "weights": { "gourmet": 0.5 } },
    { "id": "sushi_love", "label": "寿司巡り", "emoji": "🍣", "weights": { "gourmet": 0.5 } },
    { "id": "wagashi", "label": "和菓子", "emoji": "🍡", "weights": { "gourmet": 0.4, "culture": 0.2 } },
    { "id": "craftbeer", "label": "クラフトビール", "emoji": "🍺", "weights": { "gourmet": 0.4, "social": 0.3 } },
    { "id": "wine", "label": "ワイン", "emoji": "🍷", "weights": { "gourmet": 0.4, "comfort": 0.2 } },
    { "id": "sake", "label": "日本酒", "emoji": "🍶", "weights": { "gourmet": 0.4, "culture": 0.2 } },
    { "id": "vegan", "label": "ヴィーガン対応", "emoji": "🥦", "weights": { "gourmet": 0.2, "planning": 0.2, "comfort": 0.1 } },

    { "id": "shrines", "label": "神社仏閣", "emoji": "⛩️", "weights": { "culture": 0.6, "pace": -0.1 } },
    { "id": "goshuin", "label": "御朱印集め", "emoji": "📖", "weights": { "culture": 0.5, "planning": 0.2 } },
    { "id": "castles", "label": "城めぐり", "emoji": "🏯", "weights": { "culture": 0.6, "activity": 0.2 } },
    { "id": "hanabi", "label": "花火", "emoji": "🎆", "weights": { "social": 0.3, "culture": 0.2 } },
    { "id": "sakura", "label": "桜", "emoji": "🌸", "weights": { "nature": 0.4, "culture": 0.2 } },
    { "id": "momiji", "label": "紅葉", "emoji": "🍁", "weights": { "nature": 0.5, "activity": 0.1, "pace": -0.1 } },
    { "id": "waterfalls", "label": "滝めぐり", "emoji": "🏞️", "weights": { "nature": 0.6, "activity": 0.3, "risk": 0.1 } },
    { "id": "stargazing", "label": "星空観察", "emoji": "🌌", "weights": { "nature": 0.5, "pace": -0.2 } },
    { "id": "nightview", "label": "夜景・イルミ", "emoji": "🌃", "weights": { "culture": 0.2, "novelty": 0.1, "comfort": 0.1 } },
    { "id": "aquarium", "label": "水族館", "emoji": "🐠", "weights": { "culture": 0.2, "comfort": 0.2 } },
    { "id": "zoo", "label": "動物園・牧場", "emoji": "🦁", "weights": { "nature": 0.3, "social": 0.2 } },

    { "id": "kids", "label": "子連れに優しい", "emoji": "👨‍👩‍👧", "weights": { "comfort": 0.4, "risk": 0.2, "pace": -0.2 } },
    { "id": "pet", "label": "ペット同伴OK", "emoji": "🐶", "weights": { "comfort": 0.2, "planning": 0.2, "nature": 0.2 } },
    { "id": "couple", "label": "カップル向け", "emoji": "💑", "weights": { "comfort": 0.2, "gourmet": 0.2, "pace": -0.1 } },
    { "id": "girls", "label": "女子旅", "emoji": "👭", "weights": { "gourmet": 0.3, "culture": 0.2 } },
    { "id": "solo", "label": "ひとり旅", "emoji": "🧍", "weights": { "novelty": 0.2, "planning": 0.1, "comfort": -0.1 } },
    { "id": "photography", "label": "写真撮影", "emoji": "📸", "weights": { "nature": 0.3, "culture": 0.2, "planning": 0.1 } },
    { "id": "instaspot", "label": "映えスポット", "emoji": "✨", "weights": { "digital": 0.3, "novelty": 0.2, "culture": 0.1 } },

    { "id": "surf", "label": "サーフィン", "emoji": "🏄", "weights": { "activity": 0.7, "risk": 0.3, "nature": 0.3 } },
    { "id": "sup", "label": "SUP・カヤック", "emoji": "🛶", "weights": { "activity": 0.6, "nature": 0.3 } },
    { "id": "snorkel", "label": "シュノーケリング", "emoji": "🤿", "weights": { "activity": 0.6, "nature": 0.4 } },
    { "id": "ski", "label": "スキー・スノボ", "emoji": "🎿", "weights": { "activity": 0.7, "risk": 0.3, "nature": 0.3 } },
    { "id": "hike", "label": "ハイキング", "emoji": "🥾", "weights": { "activity": 0.5, "nature": 0.5 } },
    { "id": "climb", "label": "登山", "emoji": "⛰️", "weights": { "activity": 0.7, "risk": 0.3, "nature": 0.4 } },
    { "id": "trailrun", "label": "トレイルラン", "emoji": "🏃‍♂️", "weights": { "activity": 0.7, "risk": 0.2, "nature": 0.3 } },
    { "id": "cycle", "label": "サイクリング", "emoji": "🚴", "weights": { "activity": 0.5, "nature": 0.3 } },
    { "id": "drive", "label": "ドライブ", "emoji": "🚗", "weights": { "comfort": 0.2, "activity": 0.2 } },

    { "id": "rail", "label": "鉄道旅", "emoji": "🚆", "weights": { "culture": 0.2, "planning": 0.3, "comfort": 0.1 } },
    { "id": "scenic_train", "label": "絶景列車", "emoji": "🚞", "weights": { "nature": 0.3, "comfort": 0.2 } },
    { "id": "ferry", "label": "フェリー旅", "emoji": "⛴️", "weights": { "comfort": 0.2, "nature": 0.2 } },
    { "id": "cruise", "label": "クルーズ", "emoji": "🚢", "weights": { "comfort": 0.6, "pace": -0.2 } },

    { "id": "craft", "label": "伝統工芸体験", "emoji": "🎎", "weights": { "culture": 0.6, "novelty": 0.2, "activity": 0.1 } },
    { "id": "pottery", "label": "陶芸体験", "emoji": "🏺", "weights": { "culture": 0.5, "activity": 0.2 } },
    { "id": "kintsugi", "label": "金継ぎ", "emoji": "🪡", "weights": { "culture": 0.5, "planning": 0.2 } },
    { "id": "dyeing", "label": "染物体験", "emoji": "🧶", "weights": { "culture": 0.5 } },
    { "id": "sushi_making", "label": "寿司握り体験", "emoji": "🍣", "weights": { "gourmet": 0.4, "culture": 0.3, "activity": 0.1 } },
    { "id": "tea", "label": "茶道・抹茶体験", "emoji": "🍵", "weights": { "culture": 0.6, "pace": -0.2 } },
    { "id": "kimono", "label": "着物レンタル", "emoji": "👘", "weights": { "culture": 0.5, "digital": 0.1 } },
    { "id": "markets", "label": "朝市・市場", "emoji": "🧺", "weights": { "gourmet": 0.4, "culture": 0.2, "pace": 0.1 } },
    { "id": "outlet", "label": "アウトレット・ショッピング", "emoji": "🛍️", "weights": { "budget": 0.3, "comfort": 0.2 } },
    { "id": "thrift", "label": "古着・蚤の市", "emoji": "👗", "weights": { "budget": 0.2, "novelty": 0.2, "culture": 0.2 } },
    { "id": "tech", "label": "テック・ガジェット巡り", "emoji": "📱", "weights": { "digital": 0.6, "novelty": 0.2 } },
    { "id": "science_museum", "label": "科学館・博物館", "emoji": "🧪", "weights": { "culture": 0.5 } },
    { "id": "concept_cafe", "label": "コンセプトカフェ", "emoji": "🧋", "weights": { "social": 0.2, "culture": 0.2, "novelty": 0.2 } },

    { "id": "yoga", "label": "ヨガ・ウェルネス", "emoji": "🧘", "weights": { "comfort": 0.6, "activity": 0.2, "pace": -0.3 } },
]

@app.route('/api/hobbies', methods=['GET'])
def list_hobbies_master():
    """趣味マスタを返す。DBに未保存ならシードして返す。
    形式: { items: [ {id,label,emoji,weights}, ... ] }
    """
    try:
        meta_ref = db.collection('meta').document('hobbies_master')
        snap = meta_ref.get(timeout=5)
        if snap and snap.exists:
            data = snap.to_dict() or {}
            items = data.get('items')
            if isinstance(items, list) and items:
                return jsonify({"items": items})
        # seed
        to_save = { 'items': HOBBIES_MASTER, 'updated_at': firestore.SERVER_TIMESTAMP }
        meta_ref.set(to_save, timeout=5)
        return jsonify({"items": HOBBIES_MASTER})
    except Exception as e:
        logger.exception("/api/hobbies error")
        # フォールバック: 定数を返す
        return jsonify({"items": HOBBIES_MASTER})

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

def call_agent_plan(persona: dict, profile: dict | None = None, constraints: dict | None = None, timeout_sec: int = 30):
    """
    Agent サービスの /v1/plan を呼び出す。
    persona: { title: str, description: str, traitScores?: dict }
    """
    if not agent_configured:
        raise Exception("Agent base URL is not configured.")
    url = AGENT_BASE_URL.rstrip('/') + '/v1/plan'
    headers = { 'Content-Type': 'application/json' }
    if AGENT_API_KEY:
        headers['Authorization'] = f"Bearer {AGENT_API_KEY}"
    payload = {
        "persona": persona,
    }
    if profile:
        payload["profile"] = profile
    if constraints:
        payload["constraints"] = constraints
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        status = getattr(getattr(e, 'response', None), 'status_code', 'n/a')
        body = None
        try:
            body = e.response.text if getattr(e, 'response', None) is not None else None
        except Exception:
            body = None
        body_snip = (body[:500] + '…') if body and len(body) > 500 else (body or '')
        logging.getLogger('agent_bridge').error(f"/v1/plan failed: status={status} body={body_snip}")
        raise

def call_adk_agent_chat(app_name: str, user_id: str, session_id: str, message_text: str, timeout_sec: int = 60, base_url: str | None = None, ensure_session: bool = True):
    """ADK api_server に従った呼び出し手順でチャット実行。
    1) /list-apps で存在を確認（任意）
    2) /apps/{app_name}/users/{user_id}/sessions/{session_id} に空ボディPOSTでセッション作成
    3) /run に { app_name, user_id, session_id, new_message } をPOST
    戻り値: events配列（最終応答はevents内のmodelメッセージ）
    """
    if not (base_url or AGENT_BASE_URL):
        raise Exception("Agent base URL is not configured.")
    base = (base_url or AGENT_BASE_URL).rstrip('/')
    headers = { 'Content-Type': 'application/json' }
    if AGENT_API_KEY:
        headers['Authorization'] = f"Bearer {AGENT_API_KEY}"

    bridge_logger = logging.getLogger("agent_bridge")

    # 2) セッション作成（初回のみ／冪等）
    if ensure_session:
        sess_url = f"{base}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
        try:
            bridge_logger.info(f"Create session: POST {sess_url}")
            r = requests.post(sess_url, headers=headers, json={}, timeout=timeout_sec)
            text_snip = (r.text[:300] + '…') if (getattr(r, 'text', None) and len(r.text) > 300) else (r.text or '')
            already_exists = (r.status_code == 400 and isinstance(r.text, str) and 'session already exists' in r.text.lower())
            if 200 <= r.status_code < 300 or r.status_code == 409 or already_exists:
                if already_exists:
                    bridge_logger.info(f"Create session OK (already exists): {r.status_code} body={text_snip}")
                else:
                    bridge_logger.info(f"Create session OK: {r.status_code}")
            else:
                bridge_logger.error(f"Create session unexpected status: {r.status_code} body={text_snip}")
                r.raise_for_status()
        except Exception as e:
            bridge_logger.error(f"Create session failed: {e}")
            raise RuntimeError(f"Failed to create session: {e}")
    else:
        bridge_logger.info("Skip create session (already initialized on server side)")

    # 3) 実行
    run_url = f"{base}/run"
    payload = {
        "app_name": app_name,
        "user_id": user_id,
        "session_id": session_id,
        "new_message": { "role": "user", "parts": [{"text": message_text}] }
    }
    bridge_logger.info(f"Run agent: POST {run_url} app={app_name} user={user_id} session={session_id} msg_len={len(message_text)}")
    if LOG_PAYLOADS:
        try:
            bridge_logger.debug(f"Run payload: {_snip_json(payload)}")
        except Exception:
            pass
    t0 = monotonic()
    try:
        r2 = requests.post(run_url, headers=headers, json=payload, timeout=timeout_sec)
        r2.raise_for_status()
    except requests.RequestException as e:
        dt = (monotonic() - t0) * 1000
        status = getattr(getattr(e, 'response', None), 'status_code', 'n/a')
        body = None
        try:
            body = e.response.text if getattr(e, 'response', None) is not None else None
        except Exception:
            body = None
        body_snip = (body[:500] + '…') if body and len(body) > 500 else (body or '')
        bridge_logger.error(f"Run agent failed: status={status} {int(dt)}ms body={body_snip}")
        raise
    dt = (monotonic() - t0) * 1000
    j = r2.json()
    bridge_logger.info(f"Run agent OK: {r2.status_code} {int(dt)}ms events={len(j) if isinstance(j, list) else 'n/a'}")
    if LOG_PAYLOADS:
        try:
            bridge_logger.debug(f"Run response: {_snip_json(j)}")
        except Exception:
            pass
    return j

# ---- Session initialization tracking (first-message detection) ----
_primed_sessions = set()

def _session_key(user_id: str, session_id: str) -> str:
    return f"{user_id}::{session_id}"

def is_session_initialized(user_id: str, session_id: str) -> bool:
    key = _session_key(user_id, session_id)
    if key in _primed_sessions:
        return True
    try:
        if db is not None:
            doc = db.collection('agent_sessions').document(key).get(timeout=3)
            if getattr(doc, 'exists', False):
                d = doc.to_dict() or {}
                return bool(d.get('initialized'))
    except Exception:
        pass
    return False

def mark_session_initialized(user_id: str, session_id: str):
    key = _session_key(user_id, session_id)
    _primed_sessions.add(key)
    try:
        if db is not None:
            db.collection('agent_sessions').document(key).set({
                'initialized': True,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            })
    except Exception:
        pass

@app.post('/api/agent/chat')
def agent_chat():
    """チャットAPI。
    仕様: { message: string, user_id?: string, session_id?: string } -> { reply: string, places?: [{name, lat, lng, note?}] }
    - user_id: ADKの user_id に使用。未指定時は認証のsubまたは 'u_local' を使用。
    - session_id: ADKのセッションID。フロント(Vue)で生成したUUIDを必須で渡す。
    """
    try:
        data = request.get_json() or {}
        tid = getattr(request, '_trace_id', None)
        if LOG_PAYLOADS:
            logger.info(f"/api/agent/chat request body: {_snip_json(data)} trace={tid}")
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({"reply": "ご希望を教えてください（例: 温泉と美術館を楽しみたい）。"})

        # Agentサービスに委譲（ADK api_server 準拠）
        # 有効なADKベースURLを決定（環境設定 or ローカル自動検出）
        effective_base = AGENT_BASE_URL
        if not effective_base:
            try:
                probe = requests.get("http://localhost:8080/list-apps", timeout=1.5)
                if probe.ok:
                    effective_base = "http://localhost:8080"
                    logger.info("Detected local ADK at http://localhost:8080")
            except Exception:
                effective_base = None

        if effective_base:
            logger.info(f"/api/agent/chat delegating to ADK base={effective_base}")
            try:
                # リクエストで渡された user_id / session_id を採用
                req_user_id = (data.get('user_id') or '').strip() or None
                req_session_id = (data.get('session_id') or '').strip() or None
                if not req_session_id:
                    return jsonify({"error": "session_id is required"}), 400
                logger.info(f"/api/agent/chat start app=travel_planner user={req_user_id or 'auto'} session={req_session_id} msg_len={len(message)} trace={tid}")

                # 可能ならユーザー情報/ペルソナを付与して前置きコンテキストを作る
                claims = require_auth(request)
                user_info = None
                last_persona = None
                if claims and db is not None:
                    try:
                        udoc = db.collection('users').document(claims['sub']).get(timeout=3)
                        if udoc and udoc.exists:
                            u = udoc.to_dict() or {}
                            user_info = {
                                'id': claims['sub'],
                                'name': u.get('name'),
                                'profile': u.get('profile') or {}
                            }
                            last_id = u.get('last_persona_id')
                            if last_id:
                                pdoc = db.collection('users').document(claims['sub']).collection('personas').document(last_id).get(timeout=3)
                                if pdoc and pdoc.exists:
                                    pd = pdoc.to_dict() or {}
                                    last_persona = {
                                        'id': last_id,
                                        'profile': pd.get('profile'),
                                        'system_prompt': pd.get('system_prompt')
                                    }
                    except Exception:
                        pass

                # ADK呼び出し
                app_name = 'travel_planner'
                # user_id は優先的にリクエスト値を使用、なければ claims → 'u_local'
                user_id = req_user_id or (user_info.get('id') if isinstance(user_info, dict) and user_info.get('id') else 'u_local')
                session_id = req_session_id

                # 前置きユーザー情報の id をADKの user_id に合わせる
                if user_info is None:
                    user_info = { 'id': user_id }
                else:
                    try:
                        user_info['id'] = user_id
                    except Exception:
                        pass

                # 初回のみユーザー情報を前置、それ以降はプロンプトのみ
                initialized = is_session_initialized(user_id, session_id)
                if not initialized:
                    context = {
                        'user': user_info,
                        'persona': last_persona.get('profile') if isinstance(last_persona, dict) else None,
                        'persona_system_prompt': last_persona.get('system_prompt') if isinstance(last_persona, dict) else None,
                    }
                    message_to_send = (
                        "[ユーザー情報]\n" + json.dumps(context, ensure_ascii=False) +
                        "\n\n[ユーザーからの依頼]\n" + message
                    )
                    logger.info(f"/api/agent/chat using INIT message (include user info) user={user_id} session={session_id} trace={tid}")
                else:
                    message_to_send = message
                    logger.info(f"/api/agent/chat using CONTINUE message user={user_id} session={session_id} trace={tid}")

                events = call_adk_agent_chat(app_name, user_id, session_id, message_to_send, timeout_sec=60, base_url=effective_base, ensure_session=(not initialized))

                # eventsからreplyとplacesを抽出
                reply_text = None
                places = None
                if isinstance(events, list):
                    for ev in events:
                        if isinstance(ev, dict):
                            content = ev.get('content') or {}
                            parts = content.get('parts') if isinstance(content, dict) else None
                            if isinstance(parts, list):
                                for p in parts:
                                    t = p.get('text') if isinstance(p, dict) else None
                                    if t:
                                        reply_text = t
                # JSON末尾抽出（エージェント約束のフォーマット）
                if reply_text:
                    m = re.search(r'(\{\s*"places"\s*:\s*\[.*?\]\s*\})\s*$', reply_text, re.S)
                    if m:
                        try:
                            places_json = json.loads(m.group(1))
                            places = places_json.get('places')
                            # 本文からJSONを取り除く
                            reply_text = reply_text[:m.start()].rstrip()
                        except Exception:
                            pass
                logger.info(f"/api/agent/chat done user={user_id} session={session_id} reply_len={len(reply_text or '')} places={len(places or [])} trace={tid}")
                # 初回が成功したら初期化フラグを立てる
                try:
                    if not initialized:
                        mark_session_initialized(user_id, session_id)
                except Exception:
                    pass
                resp = { 'reply': reply_text or '提案を作成しました。', 'places': places }
                if LOG_PAYLOADS:
                    logger.info(f"/api/agent/chat response body: {_snip_json(resp)} trace={tid}")
                if tid:
                    resp['trace_id'] = tid
                return jsonify(resp)
            except Exception:
                logger.exception("Agent chat delegation failed")
        else:
            logger.warning("/api/agent/chat no ADK available (AGENT_BASE_URL not set and local ADK not detected); using fallback")

        # フォールバック: キーワードに応じて簡易候補地を返す
        reply = '次の候補を地図に表示しました。気になる場所はありますか？'
        candidates = []
        s = message
        if any(k in s for k in ['温泉','箱根','湯']):
            candidates.append({ 'name': '箱根温泉', 'lat': 35.232, 'lng': 139.106, 'note': '美術館と温泉巡り' })
        if any(k in s for k in ['美術','アート','直島']):
            candidates.append({ 'name': '直島 ベネッセハウス', 'lat': 34.459, 'lng': 134.009, 'note': '現代アート' })
        if any(k in s for k in ['自然','登山','屋久島']):
            candidates.append({ 'name': '屋久島 縄文杉', 'lat': 30.358, 'lng': 130.531, 'note': 'トレッキング' })
        if not candidates:
            candidates = [
                { 'name': '東京駅', 'lat': 35.681236, 'lng': 139.767125, 'note': '基準点' },
                { 'name': '京都駅', 'lat': 34.985849, 'lng': 135.758766, 'note': '観光拠点' },
            ]
        tid = getattr(request, '_trace_id', None)
        logger.info(f"/api/agent/chat fallback used candidates={len(candidates)} trace={tid}")
        resp = { 'reply': reply, 'places': candidates }
        if LOG_PAYLOADS:
            logger.info(f"/api/agent/chat response body (fallback): {_snip_json(resp)} trace={tid}")
        if tid:
            resp['trace_id'] = tid
        return jsonify(resp)
    except Exception as e:
        tid = getattr(request, '_trace_id', None)
        logger.exception("agent_chat error")
        resp = { 'reply': 'エラーが発生しました。時間をおいて再試行してください。' }
        if tid:
            resp['trace_id'] = tid
        return jsonify(resp)

@app.post('/api/geocode')
def geocode_places():
    """地名の配列を受け取って緯度経度に解決する。Google Geocoding APIキーはフロントのVITE_キーとは別管理のため、
    サーバー側で x-goog-api-key として GEMINI_API_KEY を使わず、環境変数 GOOGLE_MAPS_API_KEY があれば使用する。
    形式: { names: ["箱根温泉", ...] } -> { results: [{ name, lat, lng, formatted_address }] }
    """
    try:
        data = request.get_json() or {}
        names = data.get('names') or []
        if not isinstance(names, list) or not names:
            return jsonify({ 'results': [] })
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        results = []
        if not api_key:
            # APIキー未設定時は空で返す（フロントは名称のみで処理可能）
            return jsonify({ 'results': results })
        for nm in names[:20]:
            try:
                url = 'https://maps.googleapis.com/maps/api/geocode/json'
                params = { 'address': nm, 'key': api_key, 'language': 'ja' }
                r = requests.get(url, params=params, timeout=10)
                if r.ok:
                    j = r.json()
                    if j.get('results'):
                        g = j['results'][0]
                        loc = g['geometry']['location']
                        results.append({ 'name': nm, 'lat': loc['lat'], 'lng': loc['lng'], 'formatted_address': g.get('formatted_address') })
            except Exception:
                continue
        return jsonify({ 'results': results })
    except Exception as e:
        logger.exception("geocode error")
        return jsonify({ 'results': [] })

@app.get('/api/maps/static')
def static_map():
    """Return a Google Static Maps image for given markers.
    Query:
      size: e.g., 640x480 (default 640x480)
      markers: multiple allowed, format 'lat,lng|label:Name' or 'lat,lng'
      path: optional polyline path points (repeatable)
      zoom, center: optional; if omitted, Google fits markers
    """
    key = os.getenv('GOOGLE_MAPS_API_KEY') or os.getenv('VITE_GOOGLE_MAPS_API_KEY')
    if not key or key == 'YOUR_API_KEY_HERE':
        return jsonify({ 'error': 'maps_key_not_configured' }), 400
    size = request.args.get('size', '640x480')
    zoom = request.args.get('zoom')
    center = request.args.get('center')
    scale = request.args.get('scale', '2')
    fmt = request.args.get('format', 'png')
    # markers/path can be repeated
    markers = request.args.getlist('markers')
    paths = request.args.getlist('path')
    params = {
        'size': size,
        'scale': scale,
        'format': fmt,
        'key': key,
        'language': 'ja'
    }
    if zoom: params['zoom'] = zoom
    if center: params['center'] = center
    # Build query manually to allow repeated params
    base = 'https://maps.googleapis.com/maps/api/staticmap'
    # basic validation for size
    if 'x' not in size:
        params['size'] = '640x480'
    query_parts = [f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()]
    for m in markers[:50]:
        query_parts.append('markers=' + requests.utils.quote(m))
    for p in paths[:10]:
        query_parts.append('path=' + requests.utils.quote(p))
    url = base + '?' + '&'.join(query_parts)
    try:
        r = requests.get(url, timeout=15)
        if not r.ok:
            try:
                body_snip = (r.text[:500] + '…') if r.text and len(r.text) > 500 else (r.text or '')
            except Exception:
                body_snip = ''
            logger.warning(f"Static Maps upstream error: status={r.status_code} body={body_snip}")
            return jsonify({ 'error': 'upstream_error', 'status': r.status_code }), 502
        return Response(r.content, content_type=f'image/{fmt}')
    except Exception as e:
        logger.exception("Static Maps request_failed")
        return jsonify({ 'error': 'request_failed', 'message': str(e) }), 500

 

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
            logger.exception("Error generating explanation for non-free-text answer")
            # エラーが発生した場合は、汎用的な解説を返す
            return jsonify({"analyzed_score": base_score, "explanation": f"「{question_trait}」の観点から、あなたの選択は一貫したスタイルを示しています。"})

    if not genai_configured:
        logger.warning("Skipping Gemini API call due to missing configuration.")
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
        logger.exception("An error occurred during Gemini API call")
        score = random.randint(1, 4)
        explanation = f"AIの分析中にエラーが発生しました。ダミーデータ（スコア: {score}）を返します。"
        return jsonify({"analyzed_score": score, "explanation": explanation})

@app.route('/api/generate_plan', methods=['POST'])
def generate_plan():
    data = request.get_json()
    if not data or 'travel_type' not in data or 'description' not in data:
        return jsonify({"error": "Missing travel_type or description"}), 400

    # まず Agent サービスが設定されていれば委譲
    if agent_configured:
        try:
            persona = {
                "title": data['travel_type'],
                "description": data['description']
            }
            # 将来的にユーザープロフィールも付与可
            agent_result = call_agent_plan(persona=persona)
            # 期待形式 {"plans": [{title, description} ...]}
            if isinstance(agent_result, dict) and isinstance(agent_result.get('plans'), list):
                return jsonify(agent_result)
            else:
                logger.warning("Agent response shape unexpected; falling back to Gemini path")
        except Exception as e:
            logger.exception("Agent call failed, fallback to Gemini")

    if not genai_configured:
        logger.warning("Skipping Gemini API call for plan generation due to missing configuration.")
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
        logger.exception("An error occurred during plan generation")
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
    try:
        if doc_ref.get(timeout=5).exists:
            return jsonify({"error": "user_id already exists"}), 409
        user_doc = {
            'name': name,
            'user_id': user_id,
            'password_hash': generate_password_hash(password),
        'diagnosis_completed': False,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(user_doc, timeout=5)
    except Exception as e:
        logger.exception("Signup DB error")
        return jsonify({"error": "database unavailable"}), 503
    token = create_jwt(user_id)
    return jsonify({"token": token, "user": {"id": user_id, "name": name, "diagnosis_completed": False}})


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
    try:
        doc = users_ref.document(user_id).get(timeout=5)
    except Exception as e:
        logger.exception("Login DB error")
        return jsonify({"error": "database unavailable"}), 503
    if not doc.exists:
        return jsonify({"error": "invalid credentials"}), 401
    user = doc.to_dict()
    if not check_password_hash(user.get('password_hash', ''), password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_jwt(user_id)
    return jsonify({"token": token, "user": {"id": user_id, "name": user.get('name'), "diagnosis_completed": bool(user.get('diagnosis_completed'))}})


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

    # Collect user hobbies: prefer from request profile, else from user's saved profile
    user_hobbies = []
    try:
        hb = profile.get('hobbies')
        if isinstance(hb, list):
            user_hobbies = [str(x) for x in hb if str(x).strip()]
        elif isinstance(hb, str) and hb.strip():
            user_hobbies = [s.strip() for s in hb.split(',') if s.strip()]
        # Fallback to user's stored profile
        if not user_hobbies:
            udoc = db.collection('users').document(claims['sub']).get(timeout=5)
            if udoc and udoc.exists:
                up = (udoc.to_dict() or {}).get('profile') or {}
                hb2 = up.get('hobbies')
                if isinstance(hb2, list):
                    user_hobbies = [str(x) for x in hb2 if str(x).strip()]
    except Exception:
        pass

    # If system_prompt not provided, generate via Gemini
    if not system_prompt:
        if not genai_configured:
            system_prompt = (
                "あなたは旅行者の嗜好に基づき、国内旅行の提案と旅程調整を行うペルソナエージェントです。"
                "安全・予算・移動時間に配慮し、ユーザーのタイプ（{title}）の説明（{desc}）を尊重して提案します。"
                "ユーザーの趣味・関心も強く反映してください。以下の趣味参考: {hobbies}"
            ).format(title=profile.get('title'), desc=profile.get('description'), hobbies=json.dumps(user_hobbies, ensure_ascii=False))
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

                # ユーザーの趣味（旅行で重視するテーマや体験）
                {json.dumps(user_hobbies, ensure_ascii=False)}
                """
                api_response = call_gemini_api(prompt)
                system_prompt = api_response['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                logger.exception("Persona prompt generation error")
                system_prompt = (
                    "ユーザーの診断結果および趣味の傾向を尊重し、日本国内の旅行計画を丁寧に提案・調整すること。"
                )

    personas_ref = db.collection('users').document(claims['sub']).collection('personas')
    doc_ref = personas_ref.document()
    doc = {
        'profile': profile,
        'system_prompt': system_prompt,
        'created_at': firestore.SERVER_TIMESTAMP
    }
    try:
        doc_ref.set(doc, timeout=5)
    except Exception as e:
        logger.exception("Persona DB error")
        return jsonify({"error": "database unavailable"}), 503
    # mark user as diagnosis completed and track last persona id
    try:
        db.collection('users').document(claims['sub']).update({
            'diagnosis_completed': True,
            'last_persona_id': doc_ref.id,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, timeout=5)
    except Exception as e2:
        logger.exception("User update after persona error")
    return jsonify({"id": doc_ref.id, "profile": profile, "system_prompt": system_prompt})

# ==== Current user info ====
@app.route('/api/me', methods=['GET'])
def me():
    claims = require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    try:
        snap = db.collection('users').document(claims['sub']).get(timeout=5)
        if not snap.exists:
            return jsonify({"id": claims['sub'], "diagnosis_completed": False})
        u = snap.to_dict() or {}
        return jsonify({
            "id": claims['sub'],
            "name": u.get('name'),
            "diagnosis_completed": bool(u.get('diagnosis_completed')),
            "last_persona_id": u.get('last_persona_id')
        })
    except Exception as e:
        logger.exception("/api/me error")
        return jsonify({"id": claims['sub']}), 200

# ==== Latest persona ====
@app.route('/api/persona/latest', methods=['GET'])
def persona_latest():
    claims = require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    try:
        user_doc = db.collection('users').document(claims['sub']).get(timeout=5)
        last_id = None
        if user_doc and user_doc.exists:
            data = user_doc.to_dict() or {}
            last_id = data.get('last_persona_id')
        if last_id:
            pdoc = db.collection('users').document(claims['sub']).collection('personas').document(last_id).get(timeout=5)
            if pdoc.exists:
                pd = pdoc.to_dict() or {}
                return jsonify({"id": last_id, "profile": pd.get('profile'), "system_prompt": pd.get('system_prompt')})
        return jsonify({}), 404
    except Exception as e:
        logger.exception("/api/persona/latest error")
        return jsonify({}), 404

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path!= "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# ==== User profile (basic) ====
@app.route('/api/profile', methods=['GET', 'POST'])
def profile():
    claims = require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401
    user_id = claims['sub']
    user_ref = db.collection('users').document(user_id)
    if request.method == 'GET':
        try:
            snap = user_ref.get(timeout=5)
            profile = {}
            name = None
            if snap and snap.exists:
                data = snap.to_dict() or {}
                profile = data.get('profile') or {}
                name = data.get('name')
            return jsonify({
                "name": name,
                "profile": profile
            })
        except Exception as e:
            logger.exception("/api/profile GET error")
            return jsonify({"profile": {}}), 200
    else:
        # POST: upsert profile with validation
        payload = request.get_json() or {}
        prof = payload.get('profile') or {}
        sanitized = {}
        errors = []

        def as_str(x):
            try:
                return str(x).strip()
            except Exception:
                return ''

        def strip_ng(s: str):
            # remove control chars and angle brackets to avoid simple injection
            return re.sub(r'[\x00-\x1F<>]', '', s)

        # display_name
        if 'display_name' in prof:
            dn = strip_ng(as_str(prof.get('display_name')))
            if dn and len(dn) <= 50:
                sanitized['display_name'] = dn
            elif dn:
                errors.append('display_name must be <= 50 chars')

        # age
        if 'age' in prof:
            try:
                age = int(prof.get('age'))
                if 0 <= age <= 120:
                    sanitized['age'] = age
                else:
                    errors.append('age must be between 0 and 120')
            except Exception:
                errors.append('age must be an integer')

        # birthdate (YYYY-MM-DD)
        if 'birthdate' in prof:
            bd = as_str(prof.get('birthdate'))
            if bd:
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', bd):
                    sanitized['birthdate'] = bd
                else:
                    errors.append('invalid birthdate format')

        # gender
        if 'gender' in prof:
            g = as_str(prof.get('gender'))
            allowed_genders = {'', '男性', '女性', 'その他', '回答しない'}
            if g in allowed_genders:
                sanitized['gender'] = g
            else:
                errors.append('invalid gender')

        # hobbies
        if 'hobbies' in prof:
            hobbies = prof.get('hobbies')
            arr = []
            if isinstance(hobbies, list):
                arr = [strip_ng(as_str(h)) for h in hobbies]
            elif isinstance(hobbies, str):
                arr = [strip_ng(as_str(p)) for p in hobbies.split(',')]
            arr = [h for h in arr if h]
            # de-dup and length constraints
            seen = set()
            cleaned = []
            for h in arr:
                if h.lower() in seen:
                    continue
                seen.add(h.lower())
                if len(h) > 30:
                    errors.append('each hobby must be <= 30 chars')
                else:
                    cleaned.append(h)
            if len(cleaned) > 10:
                errors.append('max 10 hobbies')
                cleaned = cleaned[:10]
            if cleaned:
                sanitized['hobbies'] = cleaned

        # other optional fields with length limits
        limits = {'location': 100, 'budget': 100, 'notes': 500}
        for key, limit in limits.items():
            if key in prof:
                val = strip_ng(as_str(prof.get(key)))
                if len(val) > limit:
                    errors.append(f'{key} too long (>{limit})')
                elif val:
                    sanitized[key] = val

        if errors:
            return jsonify({"error": "; ".join(errors)}), 400
        try:
            # merge into existing profile
            snap = user_ref.get(timeout=5)
            base = {}
            if snap and snap.exists:
                data = snap.to_dict() or {}
                base = data.get('profile') or {}
            base.update(sanitized)
            user_ref.update({
                'profile': base,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, timeout=5)
        except Exception as e:
            # if update fails (e.g., doc missing), set instead
            try:
                user_ref.set({
                    'profile': sanitized,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True, timeout=5)
            except Exception as e2:
                logger.exception("/api/profile POST error")
                return jsonify({"error": "database unavailable"}), 503
        return jsonify({"profile": base if base else sanitized})

# ---- SPA history fallback (serve index.html for non-API routes) ----
# This allows reloading deep links like /planner or /result without 404.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa_fallback(path: str):
    # Do not intercept API routes
    if path.startswith('api/'):
        return jsonify({ 'error': 'not_found' }), 404
    try:
        # If the requested static asset exists, serve it
        static_root = app.static_folder or ''
        if path:
            full_path = os.path.join(static_root, path)
            if os.path.isfile(full_path):
                return app.send_static_file(path)
        # Otherwise serve the SPA entrypoint
        return app.send_static_file('index.html')
    except Exception:
        # As a last resort, return 404 to avoid masking real backend errors
        return jsonify({ 'error': 'not_found' }), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))



