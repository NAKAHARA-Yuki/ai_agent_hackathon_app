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