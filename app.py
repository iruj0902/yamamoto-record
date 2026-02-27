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

# 単元とレベルの基本構成・目標タイム・PDFリンクの辞書
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
        st.session_state.current_screen = "main"
    if "selected_unit" not in st.session_state:
        st.session_state.selected_unit = None
    if "selected_level" not in st.session_state:
        st.session_state.selected_level = None
    if "favorites" not in st.session_state:
        st.session_state.favorites = []
    
    # ドリル一覧の単元選択用ステート
    if "selected_tab_unit" not in st.session_state:
        st.session_state.selected_tab_unit = "たし算"
        
    # タイマー用の状態
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None
    if 'elapsed_time' not in st.session_state:
        st.session_state.elapsed_time = 0.0
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False

init_session_state()

# ==========================================
# 3. 画面遷移・操作のコールバック関数
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

def set_tab_unit(unit):
    st.session_state.selected_tab_unit = unit

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

# グラフ作成用関数（大・小兼用、ロック機能付き）
def create_chart(df, unit, level, is_mini=False):
    filtered_df = df[(df["単元"] == unit) & (df["レベル"] == level)].sort_values("日付").tail(10)
    if filtered_df.empty:
        return None
    
    fig = px.line(filtered_df, x="日付", y="タイム", markers=True)
    targets = DRILL_DATA[unit][level]
    
    # Y軸の最大値を計算（記録の最大値と〇タイムの大きい方）
    max_y = filtered_df["タイム"].max()
    max_y = max(max_y, targets["maru"])
    
    # 目標ライン
    fig.add_hline(y=targets["maru"], line_dash="dash", line_color="green", 
                  annotation_text="〇" if not is_mini else "", annotation_position="bottom right")
    fig.add_hline(y=targets["niju_maru"], line_dash="dash", line_color="blue", 
                  annotation_text="◎" if not is_mini else "", annotation_position="bottom right")
    
    # グラフのロックとレイアウト設定
    layout_args = dict(
        dragmode=False, # ズームやパンを無効化
        yaxis=dict(range=[0, max_y * 1.1], fixedrange=True),
        xaxis=dict(type='category', fixedrange=True),
        margin=dict(l=0, r=0, t=30 if not is_mini else 10, b=0)
    )
    
    if is_mini:
        layout_args.update(dict(
            xaxis_title=None, yaxis_title=None,
            xaxis=dict(showticklabels=False, type='category', fixedrange=True),
            height=120
        ))
    else:
        layout_args.update(dict(
            title="直近10回のタイム推移（秒）",
            height=350
        ))
        
    fig.update_layout(**layout_args)
    return fig

# ==========================================
# 5. UIコンポーネント：メイン画面
# ==========================================
def display_main_screen(df):
    st.title("📚 山本塾 計算ドリル")
    
    if st.button("🔄 データを最新に更新", use_container_width=False):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # ----- お気に入り（挑戦中）セクション -----
    st.subheader("🌟 現在挑戦中のレベル")
    if not st.session_state.favorites:
        st.info("下のリストから、挑戦したいレベルの「⭐」を押して追加しよう！")
    else:
        cols = st.columns(3)
        for i, (f_unit, f_level) in enumerate(st.session_state.favorites):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"### {f_unit} : {f_level}")
                    
                    fig = create_chart(df, f_unit, f_level, is_mini=True)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key=f"fav_chart_{f_unit}_{f_level}")
                    else:
                        st.write("まだ記録がありません")
                    
                    st.button("🔥 挑戦する！", key=f"fav_btn_{f_unit}_{f_level}", type="primary", use_container_width=True, on_click=go_to_drill, args=(f_unit, f_level))
                    st.button("❌ はずす", key=f"rem_btn_{f_unit}_{f_level}", use_container_width=True, on_click=toggle_favorite, args=(f_unit, f_level))

    st.markdown("---")

    # ----- 全レベル一覧 -----
    st.subheader("📖 ドリル一覧")
    
    # 大きなボタンで単元を切り替え
    units = list(unit_configs.keys())
    btn_cols = st.columns(len(units))
    for i, u in enumerate(units):
        with btn_cols[i]:
            # 選択中のボタンは色を変える
            btn_type = "primary" if st.session_state.selected_tab_unit == u else "secondary"
            st.button(u, key=f"tab_{u}", type=btn_type, use_container_width=True, on_click=set_tab_unit, args=(u,))
    
    current_unit = st.session_state.selected_tab_unit
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 選択された単元のレベルを一覧表示
    for level, data in DRILL_DATA[current_unit].items():
        with st.container(border=True):
            # データの集計（最高記録、最終日、回数）
            filtered_df = df[(df["単元"] == current_unit) & (df["レベル"] == level)]
            if not filtered_df.empty:
                best_time = f"{filtered_df['タイム'].min():.1f} 秒"
                last_date = filtered_df["日付"].max()
                try_count = f"{len(filtered_df)} 回"
            else:
                best_time = "-"
                last_date = "-"
                try_count = "0 回"
            
            # ヘッダーと目標・記録情報
            st.markdown(f"### {level}")
            info_col1, info_col2 = st.columns([1, 1.5])
            info_col1.markdown(f"**🎯 目標** 〇: {data['maru']}秒 / ◎: {data['niju_maru']}秒")
            info_col2.markdown(f"**🏆 最高:** {best_time} ｜ **📅 最終:** {last_date} ｜ **🔄 回数:** {try_count}")
            
            # ミニグラフ
            fig = create_chart(df, current_unit, level, is_mini=True)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key=f"list_chart_{current_unit}_{level}")
            else:
                st.info("まだ記録がありません")
            
            # アクションボタン
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                is_fav = (current_unit, level) in st.session_state.favorites
                fav_icon = "⭐ お気に入り解除" if is_fav else "☆ お気に入りに追加"
                st.button(fav_icon, key=f"list_fav_{current_unit}_{level}", on_click=toggle_favorite, args=(current_unit, level), use_container_width=True)
            with btn_col2:
                st.button("▶️ 挑戦！", key=f"list_chal_{current_unit}_{level}", type="primary", on_click=go_to_drill, args=(current_unit, level), use_container_width=True)

# ==========================================
# 6. UIコンポーネント：ドリル実行画面
# ==========================================
def display_drill_screen(conn, df):
    unit = st.session_state.selected_unit
    level = st.session_state.selected_level
    data = DRILL_DATA[unit][level]
    
    st.button("⬅️ 一覧に戻る", on_click=go_to_main)
    
    st.title(f"🔥 {unit} {level} に挑戦！")
    
    col_tgt1, col_tgt2 = st.columns(2)
    col_tgt1.info(f"🎯 目標タイム 〇: {data['maru']} 秒")
    col_tgt2.info(f"🎯 目標タイム ◎: {data['niju_maru']} 秒")

    st.link_button("📄 問題プリントを開く (印刷・表示)", data["pdf_q"], use_container_width=True)
    
    st.markdown("---")

    # ----- タイマー機能 -----
    st.subheader("⏱️ ストップウォッチ")
    countdown_placeholder = st.empty()

    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1:
        if st.button("▶️ 開始", use_container_width=True):
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
        
        st.link_button("✅ 解答プリントを開く (丸つけ)", data["pdf_a"], use_container_width=True)
        
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
                time.sleep(1)
                go_to_main()
                st.rerun()
                
    # ----- 挑戦画面の大きなグラフ表示 -----
    st.markdown("---")
    st.subheader("📊 これまでの推移")
    fig = create_chart(df, unit, level, is_mini=False)
    if fig:
        # ツールバー（メニュー）を非表示にして表示
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key=f"drill_chart_{unit}_{level}")
    else:
        st.info("まだ記録がありません。最初の記録を作りましょう！")

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