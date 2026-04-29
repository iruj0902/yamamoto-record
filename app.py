import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

## ==========================================
# 1. ページ設定
# ==========================================
st.set_page_config(page_title="山本塾 計算ドリル", page_icon="✏️", layout="wide")

# ==========================================
# 2. データ操作関数 (Google Sheets)
# ==========================================
def init_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_master_data(_conn):
    """「マスタ」シートからドリル設定を読み込み、辞書形式に変換"""
    try:
        # マスタシートの読み込み
        master_df = _conn.read(worksheet="マスタ")
        # --- デバッグ用：読み込んだカラム名を画面に出す ---
        #st.write("現在アプリが見ているカラム名:", master_df.columns.tolist())
        # ----------------------------------------------
        # 必要なカラムがあるか確認
        required = ["単元", "レベル", "問題", "URL", "maru", "niju_maru"]
        for col in required:
            if col not in master_df.columns:
                st.error(f"マスタシートに '{col}' カラムが見つかりません。")
                return {}

        # 構造化: { 単元: { レベル: { 問題: {maru, niju_maru, pdf_q} } } }
        structured_data = {}
        for _, row in master_df.iterrows():
            unit = str(row["単元"])
            level = str(row["レベル"])
            prob = str(row["問題"])
            
            if unit not in structured_data:
                structured_data[unit] = {}
            if level not in structured_data[unit]:
                structured_data[unit][level] = {"problems": {}}
            
            # 各問題ごとのデータを格納
            structured_data[unit][level]["problems"][prob] = {
                "maru": row["maru"],
                "niju_maru": row["niju_maru"],
                "pdf_q": row["URL"]
            }
            # 一覧表示用にそのレベルの代表的な目標値を保持（便宜上、最初の問題の値を採用）
            if "maru" not in structured_data[unit][level]:
                structured_data[unit][level]["maru"] = row["maru"]
                structured_data[unit][level]["niju_maru"] = row["niju_maru"]
                
        return structured_data
    except Exception as e:
        st.error(f"マスタの読み込みに失敗しました: {e}")
        return {}


@st.cache_data(ttl=60)
def load_results_data(_conn):
    """「Sheet1」（記録用）から実績データを読み込み"""
    try:
        df = _conn.read(worksheet="Sheet1")
        expected_columns = ["日付", "単元", "レベル", "問題", "タイム", "間違えた数"]
        if df.empty or "日付" not in df.columns:
            return pd.DataFrame(columns=expected_columns)
        return df
    except Exception as e:
        return pd.DataFrame(columns=["日付", "単元", "レベル", "問題", "タイム", "間違えた数"])

def save_data(conn, df, entry):
    new_df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear()

# ==========================================
# 3. セッションステートの初期化
# ==========================================
def init_session_state(drill_data):
    if "current_screen" not in st.session_state:
        st.session_state.current_screen = "main"
    if "selected_unit" not in st.session_state:
        st.session_state.selected_unit = None
    if "selected_level" not in st.session_state:
        st.session_state.selected_level = None
    if "favorites" not in st.session_state:
        st.session_state.favorites = []
    
    if "selected_tab_unit" not in st.session_state:
        # マスタにデータがあれば最初の単元をデフォルトに
        st.session_state.selected_tab_unit = list(drill_data.keys())[0] if drill_data else "たし算"
        
    if "selected_problem" not in st.session_state:
        st.session_state.selected_problem = None
        
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None
    if 'elapsed_time' not in st.session_state:
        st.session_state.elapsed_time = 0.0
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False

# ==========================================
# 4. 共通UIパーツ（グラフ・遷移）
# ==========================================
def create_chart(df, unit, level, drill_data, is_mini=False):
    filtered_df = df[(df["単元"] == unit) & (df["レベル"] == level)].sort_values("日付").tail(10)
    if filtered_df.empty:
        return None
    
    filtered_df["間違えた数"] = pd.to_numeric(filtered_df["間違えた数"], errors='coerce').fillna(0)
    
    marker_colors = []
    for mistakes in filtered_df["間違えた数"]:
        if mistakes == 0: marker_colors.append("blue")
        elif mistakes == 1: marker_colors.append("orange")
        else: marker_colors.append("red")
    
    # マスタから目標タイムを取得
    targets = drill_data.get(unit, {}).get(level, {"maru": 100, "niju_maru": 80})
    max_y = max(filtered_df["タイム"].max(), targets["maru"])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=filtered_df["日付"], y=filtered_df["タイム"],
        mode='lines+markers',
        line=dict(color='lightgray', width=2),
        marker=dict(color=marker_colors, size=12 if is_mini else 16, line=dict(width=1, color='black')),
        name='タイム'
    ))
    
    fig.add_hline(y=targets["maru"], line_dash="dash", line_color="green", 
                  annotation_text="〇" if not is_mini else "", annotation_position="bottom right")
    fig.add_hline(y=targets["niju_maru"], line_dash="dash", line_color="blue", 
                  annotation_text="◎" if not is_mini else "", annotation_position="bottom right")
    
    fig.update_layout(
        dragmode=False,
        yaxis=dict(range=[0, max_y * 1.1], fixedrange=True),
        xaxis=dict(type='category', fixedrange=True),
        margin=dict(l=0, r=0, t=30 if not is_mini else 10, b=0),
        height=150 if is_mini else 400
    )
    return fig

def go_to_drill(unit, level):
    st.session_state.selected_unit = unit
    st.session_state.selected_level = level
    st.session_state.current_screen = "drill"
    st.session_state.selected_problem = None
    st.session_state.elapsed_time = 0.0
    st.session_state.is_running = False

def go_to_main():
    st.session_state.current_screen = "main"

def toggle_favorite(unit, level):
    fav = (unit, level)
    if fav in st.session_state.favorites:
        st.session_state.favorites.remove(fav)
    elif len(st.session_state.favorites) < 3:
        st.session_state.favorites.append(fav)

# ==========================================
# 5. 画面コンポーネント
# ==========================================
def display_main_screen(df, drill_data):
    st.title("📚 山本塾 計算ドリル")
    
    if st.button("🔄 マスタとデータを最新に更新"):
        st.cache_data.clear()
        st.rerun()

    # お気に入りセクション
    st.subheader("🌟 現在挑戦中のレベル")
    if st.session_state.favorites:
        cols = st.columns(3)
        for i, (f_unit, f_level) in enumerate(st.session_state.favorites):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"### {f_unit} : {f_level}")
                    fig = create_chart(df, f_unit, f_level, drill_data, is_mini=True)
                    if fig: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    st.button("🔥 挑戦する！", key=f"fav_{i}", type="primary", use_container_width=True, on_click=go_to_drill, args=(f_unit, f_level))
                    st.button("❌ はずす", key=f"rem_{i}", use_container_width=True, on_click=toggle_favorite, args=(f_unit, f_level))

    # 単元切り替えボタン
    st.divider()
    units = list(drill_data.keys())
    if units:
        btn_cols = st.columns(len(units))
        for i, u in enumerate(units):
            btn_type = "primary" if st.session_state.selected_tab_unit == u else "secondary"
            if btn_cols[i].button(u, key=f"tab_{u}", type=btn_type, use_container_width=True):
                st.session_state.selected_tab_unit = u
                st.rerun()

    current_unit = st.session_state.selected_tab_unit
    if current_unit in drill_data:
        for level, info in drill_data[current_unit].items():
            with st.container(border=True):
                col_left, col_right = st.columns([1, 1.2])
                filtered_df = df[(df["単元"] == current_unit) & (df["レベル"] == level)]
                
                with col_left:
                    st.markdown(f"### {level}")
                    st.markdown(f"**🎯 目標** 〇: {info['maru']}秒 / ◎: {info['niju_maru']}秒")
                    if not filtered_df.empty:
                        st.markdown(f"**🏆 最高:** {filtered_df['タイム'].min():.1f}s | **🔄 回数:** {len(filtered_df)}")
                    
                    b_col1, b_col2 = st.columns(2)
                    fav_txt = "⭐ 解除" if (current_unit, level) in st.session_state.favorites else "☆ 追加"
                    b_col1.button(fav_txt, key=f"fav_{current_unit}_{level}", on_click=toggle_favorite, args=(current_unit, level), use_container_width=True)
                    b_col2.button("▶️ 挑戦！", key=f"go_{current_unit}_{level}", type="primary", on_click=go_to_drill, args=(current_unit, level), use_container_width=True)
                
                with col_right:
                    fig = create_chart(df, current_unit, level, drill_data, is_mini=True)
                    if fig: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    else: st.info("記録なし")

def display_drill_screen(conn, df, drill_data):
    unit = st.session_state.selected_unit
    level = st.session_state.selected_level
    level_info = drill_data.get(unit, {}).get(level, {})
    
    st.button("⬅️ 一覧に戻る", on_click=go_to_main)
    st.title(f"🔥 {unit} {level} に挑戦！")
    
    # 目標表示
    col_t1, col_t2 = st.columns(2)
    col_t1.info(f"〇目標: {level_info.get('maru')}秒")
    col_t2.info(f"◎目標: {level_info.get('niju_maru')}秒")

    st.markdown("### 1️⃣ 問題を選ぶ")
    problems = list(level_info.get("problems", {}).keys())
    if not problems:
        st.error("問題データがありません。マスタを確認してください。")
        return

    p_cols = st.columns(len(problems))
    for i, p_key in enumerate(problems):
        btn_type = "primary" if st.session_state.selected_problem == p_key else "secondary"
        if p_cols[i].button(f"問題{p_key}", key=f"p_{p_key}", type=btn_type, use_container_width=True):
            st.session_state.selected_problem = p_key
            st.rerun()

    if st.session_state.selected_problem:
        p_key = st.session_state.selected_problem
        p_data = level_info["problems"][p_key]
        
        st.link_button(f"📄 問題{p_key} のプリントを開く", p_data["pdf_q"], use_container_width=True)
        
        st.divider()
        st.subheader("⏱️ 2️⃣ ストップウォッチ")
        
        c1, c2, c3 = st.columns(3)
        if c1.button("▶️ 開始", use_container_width=True):
            ph = st.empty()
            for i in [3, 2, 1]:
                ph.markdown(f"<h1 style='text-align:center; font-size:80px;'>{i}</h1>", unsafe_allow_html=True)
                time.sleep(1)
            ph.markdown("<h1 style='text-align:center; font-size:80px; color:red;'>GO!</h1>", unsafe_allow_html=True)
            time.sleep(0.5); ph.empty()
            st.session_state.start_time = time.time()
            st.session_state.is_running = True
            st.rerun()
            
        if c2.button("⏹️ 停止", use_container_width=True) and st.session_state.is_running:
            st.session_state.elapsed_time = time.time() - st.session_state.start_time
            st.session_state.is_running = False
            st.rerun()
            
        if c3.button("🔄 リセット", use_container_width=True):
            st.session_state.elapsed_time = 0; st.session_state.is_running = False; st.rerun()

        if st.session_state.is_running:
            st.warning("計測中... (スペースキーでも停止できます)")
            components.html("<script>window.parent.document.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();const b=[...window.parent.document.querySelectorAll('button')].find(x=>x.innerText.includes('停止'));if(b)b.click()}})</script>", height=0)

        if st.session_state.elapsed_time > 0 and not st.session_state.is_running:
            st.success(f"結果: {st.session_state.elapsed_time:.1f}秒")
            st.divider()
            st.subheader("📝 3️⃣ 記録の保存")
            ic1, ic2 = st.columns(2)
            it = ic1.number_input("タイム", value=float(round(st.session_state.elapsed_time, 1)), step=0.1)
            im = ic2.number_input("間違えた数", min_value=0, step=1)
            
            if st.button("💾 保存して一覧に戻る", type="primary", use_container_width=True):
                save_data(conn, df, {"日付": datetime.now().strftime("%Y-%m-%d"), "単元": unit, "レベル": level, "問題": p_key, "タイム": it, "間違えた数": im})
                go_to_main(); st.rerun()

    # 大きなグラフ
    st.divider()
    fig = create_chart(df, unit, level, drill_data)
    if fig: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# ==========================================
# 6. メイン
# ==========================================
def main():
    conn = init_connection()
    drill_data = load_master_data(conn)
    df = load_results_data(conn)
    
    if not drill_data:
        st.warning("スプレッドシートの「マスタ」シートにデータを入力してください。")
        return

    init_session_state(drill_data)
    
    if st.session_state.current_screen == "main":
        display_main_screen(df, drill_data)
    else:
        display_drill_screen(conn, df, drill_data)

if __name__ == "__main__":
    main()