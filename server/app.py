import os
import time
import random
import re
import json
import google.generativeai as genai
from flask import Flask, jsonify, send_from_directory, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='client/dist', static_url_path='/')

# Gemini APIキーの設定
api_key = os.getenv("GEMINI_API_KEY")
genai_configured = False
if api_key and api_key != "YOUR_API_KEY_HERE":
    try:
        genai.configure(api_key=api_key)
        genai_configured = True
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
else:
    print("WARNING: GEMINI_API_KEY is not set or is a placeholder. The AI analysis will use dummy data.")



# レポートに基づいた10個全ての質問データ
QUESTIONS = [
    {
        "id": 1,
        "trait": "新規性追求",
        "question": "あなたの理想の旅に最も近いのはどれですか？",
        "options": [
            {"text": "すべて手配済みの人気観光地への快適なパッケージツアー。", "score": 1},
            {"text": "有名な都市のホテルに滞在し、自分で名所を巡る旅。", "score": 2},
            {"text": "あまり知られていない地域へ自ら手配し、定番から外れた体験を目指す旅。", "score": 3},
            {"text": "観光インフラが未整備な地域へ赴き、現地の生活に完全に溶け込む旅。", "score": 4}
        ],
        "free_text_prompt": "最も「生きている」と感じた旅の思い出を教えてください。何が特別でしたか？"
    },
    {
        "id": 2,
        "trait": "旅程密度",
        "question": "旅行中の1日の過ごし方として、どちらを好みますか？",
        "options": [
            {"text": "1つの場所に腰を据え、何もしない贅沢を味わう。", "score": 1},
            {"text": "主な見どころをいくつか、ゆったりしたペースで巡る。", "score": 2},
            {"text": "効率的に計画を立て、多くのスポットや体験を組み合わせる。", "score": 3},
            {"text": "朝から晩まで、分刻みのスケジュールで活動的に動き回る。", "score": 4}
        ],
        "free_text_prompt": "理想的な旅行の1日を、朝起きてから寝るまでどのように過ごしたいですか？"
    },
    {
        "id": 3,
        "trait": "予算哲学",
        "question": "旅行の計画を立てる際、予算についてどのように考えますか？",
        "options": [
            {"text": "最も重要なのは価格。常に最もお得な選択肢を探す。", "score": 1},
            {"text": "予算内で最大限の価値を得られるよう、コストパフォーマンスを重視する。", "score": 2},
            {"text": "素晴らしい体験のためなら、多少予算を超えても構わない。", "score": 3},
            {"text": "予算は二の次。最高の体験を得るために必要な費用は惜しまない。", "score": 4}
        ],
        "free_text_prompt": "「これはお金をかけて良かった」と感じた旅行体験は何ですか？その理由も教えてください。"
    },
    {
        "id": 4,
        "trait": "社会的志向性",
        "question": "旅行先で、どのような人との関わり方を好みますか？",
        "options": [
            {"text": "できるだけ人と関わらず、一人の時間を静かに楽しみたい。", "score": 1},
            {"text": "同行者との時間を大切にし、グループ内での交流を深めたい。", "score": 2},
            {"text": "他の旅行者と情報交換したり、食事を共にしたりするのも楽しい。", "score": 3},
            {"text": "現地の人々と積極的に交流し、その土地の文化を肌で感じたい。", "score": 4}
        ],
        "free_text_prompt": "旅行先で誰かと交流して楽しかった経験があれば教えてください。"
    },
    {
        "id": 5,
        "trait": "主な興味関心",
        "question": "旅行の最大の目的となることが多いのは、次のうちどれですか？",
        "options": [
            {"text": "日常を忘れて心身ともにリラックスすること。", "score": 1},
            {"text": "その土地ならではの美味しい食事やお酒を堪能すること。", "score": 2},
            {"text": "美しい自然の風景や野生動物との出会いを楽しむこと。", "score": 3},
            {"text": "美術館や史跡を巡り、歴史や文化に触れること。", "score": 4}
        ],
        "free_text_prompt": "これまでの旅行で最も情熱を注いだテーマ（食、アート、自然など）と、その具体的なエピソードを教えてください。"
    },
    {
        "id": 6,
        "trait": "計画志向性",
        "question": "旅行の計画はどの程度立てますか？",
        "options": [
            {"text": "ほとんど計画せず、その場の気分や出会いを大切にする。", "score": 1},
            {"text": "大まかな行き先だけ決め、詳細は現地で決めることが多い。", "score": 2},
            {"text": "行きたい場所ややりたいことをリストアップし、大まかな日程を組む。", "score": 3},
            {"text": "交通機関やレストランまで予約し、詳細な旅程表を作成する。", "score": 4}
        ],
        "free_text_prompt": "計画通りに進まなかったけれど、結果的に最高の思い出になった経験はありますか？"
    },
    {
        "id": 7,
        "trait": "快適性水準",
        "question": "宿泊施設を選ぶ際に、最も重視する点は何ですか？",
        "options": [
            {"text": "価格と立地。寝るだけなので最低限の設備で十分。", "score": 1},
            {"text": "清潔で安全、かつ機能的であること。", "score": 2},
            {"text": "デザイン性が高く、快適なアメニティやサービスが揃っていること。", "score": 3},
            {"text": "スパや高級レストランなど、施設内で特別な体験ができること。", "score": 4}
        ],
        "free_text_prompt": "今までで最高のホテル体験と、その理由を教えてください。"
    },
    {
        "id": 8,
        "trait": "活動レベル",
        "question": "旅行中の身体活動について、あなたの好みはどれですか？",
        "options": [
            {"text": "ほとんど歩き回らず、乗り物や施設内でゆったり過ごしたい。", "score": 1},
            {"text": "のんびり散策したり、景色を楽しんだりする程度が心地よい。", "score": 2},
            {"text": "街歩きや軽いハイキングなど、積極的に体を動かしたい。", "score": 3},
            {"text": "登山やマリンスポーツなど、挑戦的なアクティビティを楽しみたい。", "score": 4}
        ],
        "free_text_prompt": "旅行先で体を動かして楽しかったアクティビティは何ですか？"
    },
    {
        "id": 9,
        "trait": "安全性の閾値",
        "question": "新しい旅行先を選ぶ際、安全性についてどの程度考慮しますか？",
        "options": [
            {"text": "あまり気にしない。多少のリスクは冒険の一部だと考える。", "score": 1},
            {"text": "一般的な観光地であれば、特に問題ないだろうと考える。", "score": 2},
            {"text": "事前に外務省の安全情報などを確認し、治安の良い地域を選ぶ。", "score": 3},
            {"text": "医療体制や衛生環境を含め、最高レベルの安全が確保されている場所を選ぶ。", "score": 4}
        ],
        "free_text_prompt": "旅行の準備で、安全のために特別に行っていることはありますか？"
    },
    {
        "id": 10,
        "trait": "デジタル統合度",
        "question": "旅行中にテクノロジーをどのように活用しますか？",
        "options": [
            {"text": "デジタルデトックスを好み、スマホやPCはほとんど使わない。", "score": 1},
            {"text": "地図アプリや翻訳アプリなど、必要最低限のツールのみ利用する。", "score": 2},
            {"text": "予約管理、情報収集、SNS投稿など、積極的にテクノロジーを活用する。", "score": 3},
            {"text": "最新のガジェットやアプリを駆使し、旅の全てを記録・最適化する。", "score": 4}
        ],
        "free_text_prompt": "あなたの旅行を劇的に便利にしたアプリやウェブサイトがあれば教えてください。"
    }
]

@app.route('/api/questions')
def get_questions():
    return jsonify(QUESTIONS)

@app.route('/api/analyze', methods=['POST'])
def analyze_text():
    """
    自由記述のテキストを受け取り、AIで分析してスコアを返すAPIエンドポイント。
    """
    data = request.get_json()
    text = data.get('text', '')
    question_trait = data.get('trait', '')
    question_text = data.get('question', '')

    if not text or not question_trait or not question_text:
        return jsonify({"analyzed_score": 0})

    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        以下の質問とユーザーの回答を分析し、ユーザーの旅行スタイルが特定の特性（新規性追求、計画性など）においてどの程度かを1から4の尺度で評価してください。
        あなたのタスクは、回答内容からユーザーの価値観や行動傾向を読み取り、最も適切と思われる単一の整数（1, 2, 3, 4のいずれか）を返すことです。
        評価の基準は質問の選択肢を参考にしてください。スコアが低いほど選択肢1に近く、高いほど選択肢4に近いことを意味します。
        回答はJSON形式で、"score"というキーに整数値を入れてください。

        ---
        ### 質問の特性
        {question_trait}

        ### 質問文
        {question_text}

        ### ユーザーの自由記述回答
        {text}
        ---

        分析と評価を行い、JSON形式でスコアのみを返してください。
        例: {{"score": 3}}
        """
        
        response = model.generate_content(prompt)
        
        # レスポンスからJSON部分を抽出
        match = re.search(r'\{.*\}', response.text)
        if match:
            result_json = match.group(0)
            score_data = json.loads(result_json)
            score = int(score_data.get("score", 0))
            # スコアが1-4の範囲に収まるように調整
            score = max(1, min(4, score))
        else:
            # JSONが見つからない場合、ダミーロジックにフォールバック
            score = random.randint(1, 4)

    except Exception as e:
        print(f"An error occurred during Gemini API call: {e}")
        # エラーが発生した場合、ダミーのスコアを返す
        score = random.randint(1, 4)

    return jsonify({"analyzed_score": score})


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path!= "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
