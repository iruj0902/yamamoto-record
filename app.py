import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. ページ設定とデータ定義
# ==========================================
st.set_page_config(page_title="山本塾 計算ドリル", page_icon="✏️", layout="wide")

# 単元とレベルの基本構成・目標タイム・PDFリンクの辞書を自動生成＆定義
# ※ URLはダミーです。実際のものに置き換えてください。
DRILL_DATA = {}
unit_configs = {
    "たし算": 11,
    "ひき算": 12,
    "かけ算": 8,
    "わり算": 10
}

for unit, max_lvl in unit_configs.items():
    DRILL_DATA[unit] = {}
    for i in range(1, max_lvl + 1):
        level_name = f"レベル{i}"
        # 例として、レベルが上がるごとに目標タイムが厳しくなるようなダミー値を設定
        maru_time = 100 - (i * 2)
        niju_maru_time = 80 - (i * 2)
        
        DRILL_DATA[unit][level_name] = {
            "maru": maru_time,
            "niju_maru": niju_maru_time,
            "pdf_q": f"https://example.com/{unit}_{level_name}_question.pdf", # 問題PDF
            "pdf_a": f"https://example.com/{unit}_{level_name}_answer.pdf"    # 解答PDF
        }

# ==========================================
# 2. セッションステートの初期化
# ==========================================
def init_session_state():
    if "current_screen" not in st.session_state:
        st.session_state.current_screen = "main" # "main" or "drill"
    if "selected_unit" not in st.session_state:
        st.session_state.selected_unit = None
    if "selected_level" not in st.session_state:
        st.session_state.selected_level = None
    if "favorites" not in st.session_state:
        st.session_state.favorites = [] # [(unit, level), ...] 最大3つ
    
    # タイマー用の状態
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None
    if 'elapsed_time' not in st.session_state:
        st.session_state.elapsed_time = 0.0
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False

init_session_state()

# ==========================================
# 3. 画面遷移・お気に入り操作のコールバック関数
# ==========================================
def go_to_drill(unit, level):
    st.session_state.selected_unit = unit
    st.session_state.selected_level = level
    st.session_state.current_screen = "drill"
    st.session_state.elapsed_time = 0.0
    st.session_state.start_time = None
    st.session_state.is_running = False

def go_to_main():
    st.session_state.current_screen = "main"
    st.session_state.selected_unit = None
    st.session_state.selected_level = None

def toggle_favorite(unit, level):
    fav = (unit, level)
    if fav in st.session_state.favorites:
        st.session_state.favorites.remove(fav)
    else:
        if len(st.session_state.favorites) >= 3:
            st.warning("お気に入りは最大3つまでです！")
        else:
            st.session_state.favorites.append(fav)

# ==========================================
# 4. データ操作関数 (Google Sheets)
# ==========================================
def init_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data(_conn):
    try:
        df = _conn.read(worksheet="Sheet1")
        if df.empty or "日付" not in df.columns:
            return pd.DataFrame(columns=["日付", "単元", "レベル", "タイム"])
        return df
    except Exception as e:
        st.error("データの読み込みに失敗しました。")
        return pd.DataFrame(columns=["日付", "単元", "レベル", "タイム"])

def save_data(conn, df, entry):
    new_df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear()

# ミニグラフ作成用関数
def create_mini_chart(df, unit, level):
    filtered_df = df[(df["単元"] == unit) & (df["レベル"] == level)].sort_values("日付").tail(10)
    if filtered_df.empty:
        return None
    
    fig = px.line(filtered_df, x="日付", y="タイム", markers=True)
    targets = DRILL_DATA[unit][level]
    
    fig.add_hline(y=targets["maru"], line_dash="dash", line_color="green")
    fig.add_hline(y=targets["niju_maru"], line_dash="dash", line_color="blue")
    
    # ミニグラフ用に余計な情報を隠す
    fig.update_layout(
        xaxis_title=None, yaxis_title=None,
        xaxis=dict(showticklabels=False, type='category'),
        margin=dict(l=0, r=0, t=10, b=0),
        height=150
    )
    return fig

# ==========================================
# 5. UIコンポーネント：メイン画面
# ==========================================
def display_main_screen(df):
    st.title("📚 山本塾 計算ドリル")
    
    # 最新データ読み込みボタン
    if st.button("🔄 データを最新に更新", use_container_width=False):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # ----- お気に入り（挑戦中）セクション -----
    st.subheader("🌟 現在挑戦中のレベル")
    if not st.session_state.favorites:
        st.info("下のリストから、挑戦したいレベルの「⭐」を押して追加しよう！")
    else:
        # 最大3つのカラムを作成
        cols = st.columns(3)
        for i, (f_unit, f_level) in enumerate(st.session_state.favorites):
            with cols[i]:
                st.markdown(f"### {f_unit} : {f_level}")
                
                # ミニグラフの表示
                fig = create_mini_chart(df, f_unit, f_level)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{f_unit}_{f_level}")
                else:
                    st.write("まだ記録がありません")
                
                # 挑戦ボタン
                st.button(
                    "🔥 挑戦する！", 
                    key=f"fav_btn_{f_unit}_{f_level}", 
                    type="primary", 
                    use_container_width=True,
                    on_click=go_to_drill,
                    args=(f_unit, f_level)
                )
                
                # お気に入り解除ボタン
                st.button(
                    "❌ はずす", 
                    key=f"rem_btn_{f_unit}_{f_level}", 
                    use_container_width=True,
                    on_click=toggle_favorite,
                    args=(f_unit, f_level)
                )

    st.markdown("---")

    # ----- 全レベル一覧（タブ形式） -----
    st.subheader("📖 ドリル一覧")
    tabs = st.tabs(list(unit_configs.keys()))
    
    for tab, unit in zip(tabs, unit_configs.keys()):
        with tab:
            for level, data in DRILL_DATA[unit].items():
                # iPadで見やすいようにカラム幅を調整
                col1, col2, col3, col4 = st.columns([3, 3, 2, 3])
                
                with col1:
                    st.markdown(f"**{level}**")
                with col2:
                    st.markdown(f"〇: {data['maru']}秒 / ◎: {data['niju_maru']}秒")
                with col3:
                    is_fav = (unit, level) in st.session_state.favorites
                    fav_icon = "⭐ 追加済み" if is_fav else "☆ 追加する"
                    st.button(
                        fav_icon, 
                        key=f"list_fav_{unit}_{level}", 
                        on_click=toggle_favorite, 
                        args=(unit, level),
                        use_container_width=True
                    )
                with col4:
                    st.button(
                        "▶️ 挑戦！", 
                        key=f"list_chal_{unit}_{level}", 
                        type="primary",
                        on_click=go_to_drill, 
                        args=(unit, level),
                        use_container_width=True
                    )
                st.divider()

# ==========================================
# 6. UIコンポーネント：ドリル実行画面
# ==========================================
def display_drill_screen(conn, df):
    unit = st.session_state.selected_unit
    level = st.session_state.selected_level
    data = DRILL_DATA[unit][level]
    
    # 戻るボタン
    st.button("⬅️ 一覧に戻る", on_click=go_to_main)
    
    st.title(f"🔥 {unit} {level} に挑戦！")
    
    col_tgt1, col_tgt2 = st.columns(2)
    col_tgt1.info(f"🎯 目標タイム 〇: {data['maru']} 秒")
    col_tgt2.info(f"🎯 目標タイム ◎: {data['niju_maru']} 秒")

    # 問題PDFを開く
    st.link_button("📄 問題プリントを開く (印刷・表示)", data["pdf_q"], use_container_width=True)
    
    st.markdown("---")

    # ----- タイマー機能 -----
    st.subheader("⏱️ ストップウォッチ")
    countdown_placeholder = st.empty()

    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1:
        if st.button("▶️ 開始", use_container_width=True, height=60): # heightはCSSハックが必要ですが、文字を大きくして対応可能
            # 3秒カウントダウン
            for i in range(3, 0, -1):
                countdown_placeholder.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{i}</h1>", unsafe_allow_html=True)
                time.sleep(1)
            countdown_placeholder.markdown("<h1 style='text-align: center; font-size: 80px; color: red;'>スタート！</h1>", unsafe_allow_html=True)
            time.sleep(0.5)
            countdown_placeholder.empty()
            
            st.session_state.start_time = time.time()
            st.session_state.is_running = True
            st.session_state.elapsed_time = 0.0
            st.rerun()

    with t_col2:
        if st.button("⏹️ 停止", use_container_width=True) and st.session_state.is_running:
            st.session_state.elapsed_time = time.time() - st.session_state.start_time
            st.session_state.is_running = False
            st.rerun()

    with t_col3:
        if st.button("🔄 リセット", use_container_width=True):
            st.session_state.start_time = None
            st.session_state.elapsed_time = 0.0
            st.session_state.is_running = False
            st.rerun()

    # 計測中の表示とスペースキー検知
    if st.session_state.is_running:
        st.warning("計測中... (画面上の「停止」を押すか、スペースキーを押してください)")
        components.html(
            """
            <script>
            const doc = window.parent.document;
            doc.addEventListener('keydown', function(e) {
                if (e.code === 'Space') {
                    e.preventDefault();
                    const buttons = Array.from(doc.querySelectorAll('button'));
                    const stopBtn = buttons.find(el => el.innerText.includes('停止'));
                    if (stopBtn) { stopBtn.click(); }
                }
            });
            </script>
            """, height=0
        )
    
    # ----- 計測完了後の処理（解答確認＆保存） -----
    if st.session_state.elapsed_time > 0 and not st.session_state.is_running:
        st.success(f"🎉 計測完了: {st.session_state.elapsed_time:.1f} 秒")
        
        st.markdown("---")
        st.subheader("📝 丸つけと記録")
        
        # 解答PDFを表示
        st.link_button("✅ 解答プリントを開く (丸つけ)", data["pdf_a"], use_container_width=True)
        
        # 記録の保存フォーム
        st.write("▼ タイムを確認して保存しよう！")
        input_time = st.number_input("タイム（秒）", min_value=0.0, step=0.1, value=float(round(st.session_state.elapsed_time, 1)), format="%.1f")
        
        if st.button("💾 記録を保存して戻る", type="primary", use_container_width=True):
            if input_time > 0:
                entry = {
                    "日付": datetime.now().strftime("%Y-%m-%d"),
                    "単元": unit,
                    "レベル": level,
                    "タイム": input_time
                }
                save_data(conn, df, entry)
                st.success("保存しました！")
                time.sleep(1) # 少しだけ成功メッセージを見せる
                go_to_main()  # メイン画面へ戻る
                st.rerun()

# ==========================================
# 7. メイン処理 (画面のルーティング)
# ==========================================
def main():
    conn = init_connection()
    df = load_data(conn)
    
    if st.session_state.current_screen == "main":
        display_main_screen(df)
    elif st.session_state.current_screen == "drill":
        display_drill_screen(conn, df)

if __name__ == "__main__":
    main()