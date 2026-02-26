import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 設定値・定数
# ==========================================
# ページ設定（モバイル対応のためwideモード）
st.set_page_config(page_title="山本塾 タイム記録", page_icon="⏱️", layout="centered")

# 目標タイムの設定（適宜追加・変更してください）
TARGET_TIMES = {
    "たし算": {
        "4-1": {"maru": 80, "niju_maru": 50},
        "4-2": {"maru": 90, "niju_maru": 60},
    },
    "ひき算": {
        "4-1": {"maru": 85, "niju_maru": 55},
    }
}

# ==========================================
# 関数定義
# ==========================================

def init_connection():
    """スプレッドシートへの接続を初期化"""
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data(_conn):
    """データの読み込みとキャッシュ（_connでハッシュ化エラーを回避）"""
    try:
        df = _conn.read(worksheet="Sheet1")
        # データが空の場合の初期化
        if df.empty or "日付" not in df.columns:
            return pd.DataFrame(columns=["日付", "単元", "レベル", "タイム"])
        return df
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return pd.DataFrame(columns=["日付", "単元", "レベル", "タイム"])

def save_data(conn, df, entry):
    """新しい記録の追記処理"""
    # 既存のDataFrameに新しい辞書(entry)を結合
    new_df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear() # キャッシュをクリアして次回最新データを読み込む

def display_sidebar():
    """単元とレベルの選択UI (サイドバー)"""
    st.sidebar.title("📚 ドリルの設定")
    
    # 単元の選択
    unit = st.sidebar.selectbox("単元を選択", ["たし算", "ひき算", "かけ算", "わり算"])
    
    # 選択した単元に応じたレベルのリストを生成（例: 1-1から10-10など簡易的に生成）
    # ここでは例として簡易なリストを用意します
    levels = [f"{i}-{j}" for i in range(1, 11) for j in range(1, 3)]
    level = st.sidebar.selectbox("レベルを選択", levels, index=levels.index("4-1") if "4-1" in levels else 0)
    
    # 目標タイムの表示
    targets = TARGET_TIMES.get(unit, {}).get(level)
    if targets:
        st.sidebar.info(f"🎯 目標タイム\n\n〇 : {targets['maru']} 秒\n\n◎ : {targets['niju_maru']} 秒")
        
    return unit, level

def display_timer():
    """ストップウォッチ機能"""
    st.subheader("⏱️ ストップウォッチ")
    
    # セッションステートの初期化
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None
    if 'elapsed_time' not in st.session_state:
        st.session_state.elapsed_time = 0.0
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False

    # スマホでも押しやすいようにカラム幅を均等に
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶️ 開始", use_container_width=True):
            st.session_state.start_time = time.time()
            st.session_state.is_running = True
            st.session_state.elapsed_time = 0.0
            st.rerun()

    with col2:
        if st.button("⏹️ 停止", use_container_width=True) and st.session_state.is_running:
            st.session_state.elapsed_time = time.time() - st.session_state.start_time
            st.session_state.is_running = False
            st.rerun()

    with col3:
        if st.button("🔄 リセット", use_container_width=True):
            st.session_state.start_time = None
            st.session_state.elapsed_time = 0.0
            st.session_state.is_running = False
            st.rerun()

    # 状態の表示
    if st.session_state.is_running:
        st.warning("計測中... (終わったら停止を押してください)")
    elif st.session_state.elapsed_time > 0:
        st.success(f"計測完了: {st.session_state.elapsed_time:.1f} 秒")
        
    return st.session_state.elapsed_time

def display_charts(df, unit, level):
    """Plotlyを使用した時系列グラフの表示"""
    st.subheader(f"📊 {unit} レベル {level} の推移")
    
    # 選択された単元・レベルでフィルタリング
    filtered_df = df[(df["単元"] == unit) & (df["レベル"] == level)]
    
    if filtered_df.empty:
        st.info("このドリルはまだ記録がありません。最初の記録を付けましょう！")
        return
        
    # 日付でソートし、直近10回分を取得
    filtered_df = filtered_df.sort_values("日付").tail(10)
    
    # グラフの作成
    fig = px.line(
        filtered_df, 
        x="日付", 
        y="タイム", 
        markers=True, 
        title="直近10回のタイム推移（秒）"
    )
    
    # 目標値の破線を追加
    targets = TARGET_TIMES.get(unit, {}).get(level)
    if targets:
        # 〇タイム
        fig.add_hline(
            y=targets["maru"], 
            line_dash="dash", 
            line_color="green", 
            annotation_text="〇", 
            annotation_position="bottom right"
        )
        # ◎タイム
        fig.add_hline(
            y=targets["niju_maru"], 
            line_dash="dash", 
            line_color="blue", 
            annotation_text="◎", 
            annotation_position="bottom right"
        )
        
    # Y軸を0始まりにし、少し余裕を持たせる
    fig.update_layout(yaxis_rangemode='tozero')
    
    # スマホ対応でコンテナ幅いっぱいにする
    st.plotly_chart(fig, use_container_width=True)


# ==========================================
# メイン処理
# ==========================================
def main():
    st.title("山本塾 タイム記録")
    
    # 1. 接続とデータの読み込み
    conn = init_connection()
    df = load_data(conn)
    
    # 2. サイドバーの設定
    unit, level = display_sidebar()
    
    # 3. タイマーの表示と計測時間の取得
    elapsed_time = display_timer()
    
    st.divider()
    
    # 4. 記録の入力と保存
    st.subheader("📝 記録の保存")
    
    # タイマー計測値が自動で入力フォームのデフォルト値になります
    input_time = st.number_input(
        "タイム（秒）を入力", 
        min_value=0.0, 
        step=0.1, 
        value=float(round(elapsed_time, 1)),
        format="%.1f"
    )
    
    if st.button("💾 記録を保存", type="primary", use_container_width=True):
        if input_time > 0:
            entry = {
                "日付": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "単元": unit,
                "レベル": level,
                "タイム": input_time
            }
            save_data(conn, df, entry)
            st.success("記録を保存しました！グラフに反映します。")
            st.rerun() # リロードしてグラフを更新
        else:
            st.error("有効なタイムを入力してください。")
            
    st.divider()
    
    # 5. グラフの表示
    display_charts(df, unit, level)

if __name__ == "__main__":
    main()