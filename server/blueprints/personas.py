"""Persona and profile management blueprint"""
import json
import os
import re
import logging
from flask import Blueprint, request, jsonify
from google.cloud import firestore

from utils.auth import claims_or_dev, require_auth
from utils.ai_processing import call_gemini_api, genai_configured

logger = logging.getLogger(__name__)

personas_bp = Blueprint('personas', __name__)


@personas_bp.route('/api/persona', methods=['POST'])
def create_persona():
    """Create a new persona based on personality assessment results"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
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


@personas_bp.route('/api/persona/latest', methods=['GET'])
def persona_latest():
    """Get the latest persona for the current user"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    claims = claims_or_dev()
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
                profile = pd.get('profile')
                if profile and profile.get('title'):  # Validate profile has required fields
                    return jsonify({"id": last_id, "profile": profile, "system_prompt": pd.get('system_prompt')})
                else:
                    logger.warning(f"Persona {last_id} exists but has invalid profile data: {profile}")
        
        # No valid persona found
        return jsonify({"error": "no_persona_found", "message": "診断結果が見つかりません。性格診断を完了してください。"}), 404
    except Exception as e:
        logger.exception("/api/persona/latest error")
        return jsonify({"error": "server_error", "message": "ペルソナデータの取得中にエラーが発生しました。"}), 500


@personas_bp.route('/api/profile', methods=['GET', 'POST'])
def profile():
    """User profile management"""
    from flask import current_app
    db = getattr(current_app, 'db', None)
    
    claims = claims_or_dev()
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