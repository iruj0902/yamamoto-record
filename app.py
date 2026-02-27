import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
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
        
        # 問題①〜④用のPDFリンク（ダミー）を生成
        pdf_q_dict = {
            "①": f"https://example.com/{unit}_{level_name}_q1.pdf",
            "②": f"https://example.com/{unit}_{level_name}_q2.pdf",
            "③": f"https://example.com/{unit}_{level_name}_q3.pdf",
            "④": f"https://example.com/{unit}_{level_name}_q4.pdf",
        }
        pdf_a_dict = {
            "①": f"https://example.com/{unit}_{level_name}_a1.pdf",
            "②": f"https://example.com/{unit}_{level_name}_a2.pdf",
            "③": f"https://example.com/{unit}_{level_name}_a3.pdf",
            "④": f"https://example.com/{unit}_{level_name}_a4.pdf",
        }
        
        DRILL_DATA[unit][level_name] = {
            "maru": maru_time,
            "niju_maru": niju_maru_time,
            "pdf_q": pdf_q_dict,
            "pdf_a": pdf_a_dict
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
    
    if "selected_tab_unit" not in st.session_state:
        st.session_state.selected_tab_unit = "たし算"
        
    # ドリル画面での「問題」選択用
    if "selected_problem" not in st.session_state:
        st.session_state.selected_problem = None
        
    # タイマー用
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
    # 初期化
    st.session_state.selected_problem = None
    st.session_state.elapsed_time = 0.0
    st.session_state.start_time = None
    st.session_state.is_running = False

def go_to_main():
    st.session_state.current_screen = "main"
    st.session_state.selected_unit = None
    st.session_state.selected_level = None
    st.session_state.selected_problem = None

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

def set_problem(p):
    st.session_state.selected_problem = p

# ==========================================
# 4. データ操作関数 (Google Sheets)
# ==========================================
def init_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data(_conn):
    try:
        df = _conn.read(worksheet="Sheet1")
        # カラム構成を最新版に更新
        expected_columns = ["日付", "単元", "レベル", "問題", "タイム", "間違えた数"]
        if df.empty or "日付" not in df.columns:
            return pd.DataFrame(columns=expected_columns)
        return df
    except Exception as e:
        st.error("データの読み込みに失敗しました。")
        return pd.DataFrame(columns=["日付", "単元", "レベル", "問題", "タイム", "間違えた数"])

def save_data(conn, df, entry):
    new_df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear()

# グラフ作成用関数 (間違え数に応じた色変更対応)
def create_chart(df, unit, level, is_mini=False):
    filtered_df = df[(df["単元"] == unit) & (df["レベル"] == level)].sort_values("日付").tail(10)
    if filtered_df.empty:
        return None
    
    # 間違えた数を数値化（空欄などは0として扱う）
    filtered_df["間違えた数"] = pd.to_numeric(filtered_df["間違えた数"], errors='coerce').fillna(0)
    
    # ドットの色のリストを作成
    marker_colors = []
    for mistakes in filtered_df["間違えた数"]:
        if mistakes == 0:
            marker_colors.append("blue")
        elif mistakes == 1:
            marker_colors.append("orange")
        else:
            marker_colors.append("red")
    
    targets = DRILL_DATA[unit][level]
    max_y = max(filtered_df["タイム"].max(), targets["maru"])
    
    # Plotly Graph Objectsでグラフを構築
    fig = go.Figure()
    
    # 折れ線とマーカーを追加
    marker_size = 12 if is_mini else 16 # ドットの大きさを少し大きく
    fig.add_trace(go.Scatter(
        x=filtered_df["日付"],
        y=filtered_df["タイム"],
        mode='lines+markers',
        line=dict(color='lightgray', width=2), # 線の色はグレーで固定
        marker=dict(color=marker_colors, size=marker_size, line=dict(width=1, color='black')),
        name='タイム'
    ))
    
    # 目標ライン
    fig.add_hline(y=targets["maru"], line_dash="dash", line_color="green", 
                  annotation_text="〇" if not is_mini else "", annotation_position="bottom right")
    fig.add_hline(y=targets["niju_maru"], line_dash="dash", line_color="blue", 
                  annotation_text="◎" if not is_mini else "", annotation_position="bottom right")
    
    # グラフのロックとレイアウト設定
    layout_args = dict(
        dragmode=False,
        yaxis=dict(range=[0, max_y * 1.1], fixedrange=True),
        xaxis=dict(type='category', fixedrange=True),
        margin=dict(l=0, r=0, t=30 if not is_mini else 10, b=0)
    )
    
    if is_mini:
        layout_args.update(dict(
            xaxis_title=None, yaxis_title=None,
            xaxis=dict(showticklabels=False, type='category', fixedrange=True),
            height=150 # ミニグラフの高さを少し確保
        ))
    else:
        layout_args.update(dict(
            title="直近10回のタイム推移（青: 満点, オレンジ: 1ミス, 赤: 2ミス以上）",
            height=400
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
    
    units = list(unit_configs.keys())
    btn_cols = st.columns(len(units))
    for i, u in enumerate(units):
        with btn_cols[i]:
            btn_type = "primary" if st.session_state.selected_tab_unit == u else "secondary"
            st.button(u, key=f"tab_{u}", type=btn_type, use_container_width=True, on_click=set_tab_unit, args=(u,))
    
    current_unit = st.session_state.selected_tab_unit
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 選択された単元のレベルを一覧表示
    for level, data in DRILL_DATA[current_unit].items():
        with st.container(border=True):
            # --- 左右に分割（左: 情報とボタン, 右: グラフ） ---
            col_left, col_right = st.columns([1, 1.2]) # 右側のグラフの幅を少し広めに
            
            # データの集計
            filtered_df = df[(df["単元"] == current_unit) & (df["レベル"] == level)]
            if not filtered_df.empty:
                best_time = f"{filtered_df['タイム'].min():.1f} 秒"
                last_date = filtered_df["日付"].max()
                try_count = f"{len(filtered_df)} 回"
            else:
                best_time = "-"
                last_date = "-"
                try_count = "0 回"
            
            # 左側：文字情報とボタン
            with col_left:
                st.markdown(f"### {level}")
                st.markdown(f"**🎯 目標** 〇: {data['maru']}秒 / ◎: {data['niju_maru']}秒")
                st.markdown(f"**🏆 最高:** {best_time}  \n**📅 最終:** {last_date}  \n**🔄 回数:** {try_count}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    is_fav = (current_unit, level) in st.session_state.favorites
                    fav_icon = "⭐ 解除" if is_fav else "☆ 追加"
                    st.button(fav_icon, key=f"list_fav_{current_unit}_{level}", on_click=toggle_favorite, args=(current_unit, level), use_container_width=True)
                with btn_col2:
                    st.button("▶️ 挑戦！", key=f"list_chal_{current_unit}_{level}", type="primary", on_click=go_to_drill, args=(current_unit, level), use_container_width=True)
            
            # 右側：グラフ
            with col_right:
                fig = create_chart(df, current_unit, level, is_mini=True)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key=f"list_chart_{current_unit}_{level}")
                else:
                    # グラフがない場合は余白を埋めるために少し改行
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.info("まだ記録がありません")

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

    st.markdown("---")
    
    # ----- 挑戦する問題（①〜④）の選択 -----
    st.markdown("### 1️⃣ どの問題に挑戦する？")
    p_cols = st.columns(4)
    problems = ["①", "②", "③", "④"]
    
    for i, p in enumerate(problems):
        with p_cols[i]:
            btn_type = "primary" if st.session_state.selected_problem == p else "secondary"
            st.button(f"問題{p} に挑戦", key=f"prob_{p}", type=btn_type, use_container_width=True, on_click=set_problem, args=(p,))

    if not st.session_state.selected_problem:
        st.warning("👆 上のボタンから、挑戦する問題（①〜④）を選んでね！")
        return # 問題が選ばれるまではこれ以降のUIを表示しない
        
    p = st.session_state.selected_problem
    
    # 選択された問題のPDFリンクを表示
    st.link_button(f"📄 問題{p} のプリントを開く (印刷・表示)", data["pdf_q"][p], use_container_width=True)
    
    st.markdown("---")

    # ----- タイマー機能 -----
    st.subheader(f"⏱️ 2️⃣ ストップウォッチ (問題{p})")
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
        st.subheader("📝 3️⃣ 丸つけと記録")
        
        # 選択された問題の解答PDF
        st.link_button(f"✅ 解答プリントを開く (問題{p}の丸つけ)", data["pdf_a"][p], use_container_width=True)
        
        st.write("▼ タイムと間違えた数を確認して保存しよう！")
        
        # タイムと間違え数の入力フォームを並べる
        in_col1, in_col2 = st.columns(2)
        with in_col1:
            input_time = st.number_input("タイム（秒）", min_value=0.0, step=0.1, value=float(round(st.session_state.elapsed_time, 1)), format="%.1f")
        with in_col2:
            input_mistakes = st.number_input("間違えた数", min_value=0, step=1, value=0)
        
        if st.button("💾 記録を保存して戻る", type="primary", use_container_width=True):
            if input_time > 0:
                entry = {
                    "日付": datetime.now().strftime("%Y-%m-%d"),
                    "単元": unit,
                    "レベル": level,
                    "問題": p,         # 新規追加列
                    "タイム": input_time,
                    "間違えた数": input_mistakes # 新規追加列
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