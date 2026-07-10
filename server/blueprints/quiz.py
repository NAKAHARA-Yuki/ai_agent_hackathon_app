"""Quiz and personality assessment blueprint"""
import json
import random
import time
import logging
from flask import Blueprint, request, jsonify
from utils.firestore_dummy import firestore

from utils.ai_processing import call_gemini_api, genai_configured
from utils.auth import claims_or_dev

logger = logging.getLogger(__name__)

quiz_bp = Blueprint('quiz', __name__)

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
    {"id": "onsen", "label": "温泉・サウナ", "emoji": "♨️", "weights": {"comfort": 0.6, "pace": -0.2}},
    {"id": "relax", "label": "リラックス・スパ", "emoji": "🧖", "weights": {"comfort": 0.8, "activity": -0.4, "pace": -0.4}},
    {"id": "art", "label": "アート・美術館", "emoji": "🖼️", "weights": {"culture": 0.7, "novelty": 0.1}},
    {"id": "history", "label": "歴史・世界遺産", "emoji": "🏛️", "weights": {"culture": 0.8}},
    {"id": "nature", "label": "自然・絶景", "emoji": "🏞️", "weights": {"nature": 0.8, "activity": 0.2}},
    {"id": "gourmet", "label": "グルメ・食べ歩き", "emoji": "🍣", "weights": {"gourmet": 0.8, "comfort": 0.1}},
    {"id": "citywalk", "label": "まち歩き", "emoji": "🚶", "weights": {"activity": 0.4, "culture": 0.2}},
    {"id": "adventure", "label": "アドベンチャー", "emoji": "🧗", "weights": {"novelty": 0.6, "risk": 0.4, "activity": 0.6}},
    {"id": "themepark", "label": "テーマパーク", "emoji": "🎢", "weights": {"comfort": 0.2, "pace": 0.2}},
    {"id": "island", "label": "離島ステイ", "emoji": "🏝️", "weights": {"nature": 0.6, "novelty": 0.3, "comfort": 0.2}},
    {"id": "snow", "label": "雪・ウィンター", "emoji": "❄️", "weights": {"activity": 0.4, "risk": 0.2, "comfort": -0.1}},
    {"id": "festival", "label": "祭り・イベント", "emoji": "🎊", "weights": {"social": 0.6, "culture": 0.2}},
    {"id": "pilgrimage", "label": "聖地巡礼（アニメ・ドラマ）", "emoji": "🎬", "weights": {"culture": 0.5, "novelty": 0.3, "planning": 0.2}},
    {"id": "cafe", "label": "カフェめぐり", "emoji": "☕", "weights": {"gourmet": 0.6, "comfort": 0.2, "pace": -0.1}},
    {"id": "coffee", "label": "コーヒー巡り", "emoji": "☕", "weights": {"gourmet": 0.5, "comfort": 0.2, "pace": -0.1}},
    {"id": "sweets", "label": "スイーツ巡り", "emoji": "🍰", "weights": {"gourmet": 0.5, "comfort": 0.2}},
    {"id": "bakery", "label": "ベーカリー巡り", "emoji": "🍞", "weights": {"gourmet": 0.4, "comfort": 0.2, "pace": -0.1}},
    {"id": "ramen", "label": "ラーメン", "emoji": "🍜", "weights": {"gourmet": 0.5}},
    {"id": "sushi_love", "label": "寿司巡り", "emoji": "🍣", "weights": {"gourmet": 0.5}},
    {"id": "wagashi", "label": "和菓子", "emoji": "🍡", "weights": {"gourmet": 0.4, "culture": 0.2}},
    {"id": "craftbeer", "label": "クラフトビール", "emoji": "🍺", "weights": {"gourmet": 0.4, "social": 0.3}},
    {"id": "wine", "label": "ワイン", "emoji": "🍷", "weights": {"gourmet": 0.4, "comfort": 0.2}},
    {"id": "sake", "label": "日本酒", "emoji": "🍶", "weights": {"gourmet": 0.4, "culture": 0.2}},
    {"id": "vegan", "label": "ヴィーガン対応", "emoji": "🥦", "weights": {"gourmet": 0.2, "planning": 0.2, "comfort": 0.1}},
    {"id": "shrines", "label": "神社仏閣", "emoji": "⛩️", "weights": {"culture": 0.6, "pace": -0.1}},
    {"id": "goshuin", "label": "御朱印集め", "emoji": "📖", "weights": {"culture": 0.5, "planning": 0.2}},
    {"id": "castles", "label": "城めぐり", "emoji": "🏯", "weights": {"culture": 0.6, "activity": 0.2}},
    {"id": "hanabi", "label": "花火", "emoji": "🎆", "weights": {"social": 0.3, "culture": 0.2}},
    {"id": "sakura", "label": "桜", "emoji": "🌸", "weights": {"nature": 0.4, "culture": 0.2}},
    {"id": "momiji", "label": "紅葉", "emoji": "🍁", "weights": {"nature": 0.5, "activity": 0.1, "pace": -0.1}},
    {"id": "waterfalls", "label": "滝めぐり", "emoji": "🏞️", "weights": {"nature": 0.6, "activity": 0.3, "risk": 0.1}},
    {"id": "stargazing", "label": "星空観察", "emoji": "🌌", "weights": {"nature": 0.5, "pace": -0.2}},
    {"id": "nightview", "label": "夜景・イルミ", "emoji": "🌃", "weights": {"culture": 0.2, "novelty": 0.1, "comfort": 0.1}},
    {"id": "aquarium", "label": "水族館", "emoji": "🐠", "weights": {"culture": 0.2, "comfort": 0.2}},
    {"id": "zoo", "label": "動物園・牧場", "emoji": "🦁", "weights": {"nature": 0.3, "social": 0.2}},
    {"id": "kids", "label": "子連れに優しい", "emoji": "👨‍👩‍👧", "weights": {"comfort": 0.4, "risk": 0.2, "pace": -0.2}},
    {"id": "pet", "label": "ペット同伴OK", "emoji": "🐶", "weights": {"comfort": 0.2, "planning": 0.2, "nature": 0.2}},
    {"id": "couple", "label": "カップル向け", "emoji": "💑", "weights": {"comfort": 0.2, "gourmet": 0.2, "pace": -0.1}},
    {"id": "girls", "label": "女子旅", "emoji": "👭", "weights": {"gourmet": 0.3, "culture": 0.2}},
    {"id": "solo", "label": "ひとり旅", "emoji": "🧍", "weights": {"novelty": 0.2, "planning": 0.1, "comfort": -0.1}},
    {"id": "photography", "label": "写真撮影", "emoji": "📸", "weights": {"nature": 0.3, "culture": 0.2, "planning": 0.1}},
    {"id": "instaspot", "label": "映えスポット", "emoji": "✨", "weights": {"digital": 0.3, "novelty": 0.2, "culture": 0.1}},
    {"id": "surf", "label": "サーフィン", "emoji": "🏄", "weights": {"activity": 0.7, "risk": 0.3, "nature": 0.3}},
    {"id": "sup", "label": "SUP・カヤック", "emoji": "🛶", "weights": {"activity": 0.6, "nature": 0.3}},
    {"id": "snorkel", "label": "シュノーケリング", "emoji": "🤿", "weights": {"activity": 0.6, "nature": 0.4}},
    {"id": "ski", "label": "スキー・スノボ", "emoji": "🎿", "weights": {"activity": 0.7, "risk": 0.3, "nature": 0.3}},
    {"id": "hike", "label": "ハイキング", "emoji": "🥾", "weights": {"activity": 0.5, "nature": 0.5}},
    {"id": "climb", "label": "登山", "emoji": "⛰️", "weights": {"activity": 0.7, "risk": 0.3, "nature": 0.4}},
    {"id": "trailrun", "label": "トレイルラン", "emoji": "🏃‍♂️", "weights": {"activity": 0.7, "risk": 0.2, "nature": 0.3}},
    {"id": "cycle", "label": "サイクリング", "emoji": "🚴", "weights": {"activity": 0.5, "nature": 0.3}},
    {"id": "drive", "label": "ドライブ", "emoji": "🚗", "weights": {"comfort": 0.2, "activity": 0.2}},
    {"id": "rail", "label": "鉄道旅", "emoji": "🚆", "weights": {"culture": 0.2, "planning": 0.3, "comfort": 0.1}},
    {"id": "scenic_train", "label": "絶景列車", "emoji": "🚞", "weights": {"nature": 0.3, "comfort": 0.2}},
    {"id": "ferry", "label": "フェリー旅", "emoji": "⛴️", "weights": {"comfort": 0.2, "nature": 0.2}},
    {"id": "cruise", "label": "クルーズ", "emoji": "🚢", "weights": {"comfort": 0.6, "pace": -0.2}},
    {"id": "craft", "label": "伝統工芸体験", "emoji": "🎎", "weights": {"culture": 0.6, "novelty": 0.2, "activity": 0.1}},
    {"id": "pottery", "label": "陶芸体験", "emoji": "🏺", "weights": {"culture": 0.5, "activity": 0.2}},
    {"id": "kintsugi", "label": "金継ぎ", "emoji": "🪡", "weights": {"culture": 0.5, "planning": 0.2}},
    {"id": "dyeing", "label": "染物体験", "emoji": "🧶", "weights": {"culture": 0.5}},
    {"id": "sushi_making", "label": "寿司握り体験", "emoji": "🍣", "weights": {"gourmet": 0.4, "culture": 0.3, "activity": 0.1}},
    {"id": "tea", "label": "茶道・抹茶体験", "emoji": "🍵", "weights": {"culture": 0.6, "pace": -0.2}},
    {"id": "kimono", "label": "着物レンタル", "emoji": "👘", "weights": {"culture": 0.5, "digital": 0.1}},
    {"id": "markets", "label": "朝市・市場", "emoji": "🧺", "weights": {"gourmet": 0.4, "culture": 0.2, "pace": 0.1}},
    {"id": "outlet", "label": "アウトレット・ショッピング", "emoji": "🛍️", "weights": {"budget": 0.3, "comfort": 0.2}},
    {"id": "thrift", "label": "古着・蚤の市", "emoji": "👗", "weights": {"budget": 0.2, "novelty": 0.2, "culture": 0.2}},
    {"id": "tech", "label": "テック・ガジェット巡り", "emoji": "📱", "weights": {"digital": 0.6, "novelty": 0.2}},
    {"id": "science_museum", "label": "科学館・博物館", "emoji": "🧪", "weights": {"culture": 0.5}},
    {"id": "concept_cafe", "label": "コンセプトカフェ", "emoji": "🧋", "weights": {"social": 0.2, "culture": 0.2, "novelty": 0.2}},
    {"id": "yoga", "label": "ヨガ・ウェルネス", "emoji": "🧘", "weights": {"comfort": 0.6, "activity": 0.2, "pace": -0.3}},
]


@quiz_bp.route('/api/hobbies', methods=['GET'])
def list_hobbies_master():
    """趣味マスタを返す。DBに未保存ならシードして返す。
    形式: { items: [ {id,label,emoji,weights}, ... ] }
    """
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    try:
        meta_ref = db.collection('meta').document('hobbies_master')
        snap = meta_ref.get(timeout=5)
        if snap and snap.exists:
            data = snap.to_dict() or {}
            items = data.get('items')
            if isinstance(items, list) and items:
                return jsonify({"items": items})
        # seed
        to_save = {'items': HOBBIES_MASTER, 'updated_at': firestore.SERVER_TIMESTAMP}
        meta_ref.set(to_save, timeout=5)
        return jsonify({"items": HOBBIES_MASTER})
    except Exception as e:
        logger.exception("/api/hobbies error")
        # フォールバック: 定数を返す
        return jsonify({"items": HOBBIES_MASTER})


@quiz_bp.route('/api/questions')
def get_questions():
    """Get all personality assessment questions"""
    return jsonify(QUESTIONS)


@quiz_bp.route('/api/analyze', methods=['POST'])
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