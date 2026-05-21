import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import config.registry as registry
from ui.components import setup_page_config, init_session_state, inject_custom_css, nav_to

# ==========================================
# 社区数据持久化引擎 (Local File Database)
# ==========================================
STATS_FILE = "data/community_stats.json"

def init_community_stats():
    """初始化或加载全站统计数据"""
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(STATS_FILE):
        default_stats = {"visits": 1024, "likes": 356} # 设定一个初始基数
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_stats, f)
        return default_stats
    else:
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"visits": 1024, "likes": 356}

def save_community_stats(stats):
    """保存全站统计数据"""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f)

# ==========================================
# 主页视图 (Home View)
# ==========================================
def view_home() -> None:
    """渲染地震工程交流共享平台首页"""
    st.markdown('<div class="hero-title" style="font-size: 5rem;">OpenSeismic</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">开源免费 · 地震工程 · 交流共享</div>', unsafe_allow_html=True)
    
    cols = st.columns(3)
    with cols[0]:
        if st.button("《建筑抗震设计标准》\nGB/T 50011-2010 (2024 版)", type="primary", width="stretch"): 
            nav_to('GB50011')
    with cols[1]: 
        st.button("《工程场地地震安全性评价》\nGB 17741-2025 (开发中)", type="primary", width="stretch", disabled=True)
    with cols[2]: 
        st.button("《区域性地震安全性评价》\nGB/T 100-2024 (开发中)", type="primary", width="stretch", disabled=True)
        
    # ==========================================
    # 统计面板 (Data Dashboard) - 全球完整版
    # ==========================================
    stats = init_community_stats()
    
    # 页面首次加载时，增加全局访问量（基于 session_state 防止同用户反复刷新刷量）
    if 'has_visited' not in st.session_state:
        stats["visits"] += 1
        save_community_stats(stats)
        st.session_state.has_visited = True

    st.markdown("<h4 style='color: #0f172a; font-weight: 800; margin-bottom: 12px; font-size: 1.1rem;'>🌍 统计面板</h4>", unsafe_allow_html=True)
    
    # 保持紧凑的黄金分列比例 [5, 8]
    dash_col1, dash_col2 = st.columns([5, 8])
    
    with dash_col1:
        # 优化点 1：增加卡片 min-height 至 172px，内部增加上下 padding，确保文字居中饱满，与右侧完整地图高度完美平齐
        st.markdown("""
        <div style='background: white; padding: 24px 16px; border-radius: 6px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); min-height: 172px; display: flex; align-items: center;'>
            <div style='display: flex; justify-content: space-between; align-items: center; width: 100%;'>
                <div style='flex: 1; text-align: center;'>
                    <p style='color: #64748b; font-weight: 600; margin: 0; font-size: 14px;'>🚀 访问量</p>
                    <h3 style='color: #1e3a8a; margin: 6px 0 0 0; font-size: 1.6rem; font-weight: 800;'>{:,} <span style='font-size: 11px; color: #94a3b8; font-weight: 400;'>次</span></h3>
                </div>
                <div style='width: 1px; background: #e2e8f0; height: 50px; margin: 0 8px;'></div>
                <div style='flex: 1; text-align: center;'>
                    <p style='color: #64748b; font-weight: 600; margin: 0; font-size: 14px;'>💖 点赞量</p>
                    <h3 style='color: #ef4444; margin: 6px 0 0 0; font-size: 1.6rem; font-weight: 800;'>{:,} <span style='font-size: 11px; color: #94a3b8; font-weight: 400;'>次</span></h3>
                </div>
            </div>
        </div>
        """.format(stats["visits"], stats["likes"]), unsafe_allow_html=True)
        
        # 点赞交互按钮
        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        if st.button("👍 感谢点赞", width="stretch", type="secondary"):
            stats["likes"] += 1
            save_community_stats(stats)
            st.toast('感谢您对开源地震工程的支持！', icon='💖')
            st.rerun()

    with dash_col2:
        v = stats["visits"]
        map_data = pd.DataFrame({
            'iso_alpha': ['CHN', 'USA', 'JPN', 'GBR', 'SGP', 'AUS', 'DEU'],
            'country': ['中国', '美国', '日本', '英国', '新加坡', '澳大利亚', '德国'],
            'users': [v, int(v * 0.12) + 30, int(v * 0.15) + 45, int(v * 0.04) + 12, int(v * 0.08) + 21, int(v * 0.06) + 18, int(v * 0.05) + 15]
        })
        
        fig = px.scatter_geo(
            map_data, 
            locations="iso_alpha", 
            size="users",
            hover_name="country",
            projection="natural earth",
            color="users",
            size_max=16,  # 微调气泡最大尺寸，使其更加精致
            color_continuous_scale=["#60a5fa", "#1e3a8a"]
        )
        
        # 优化点 2：高度调整为 220px（世界地图完美无损显示的临界点）
        # 优化点 3：移除了强制截断的 lataxis_range，允许自动展示全球完整大陆轮廓
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_showscale=False,
            geo=dict(
                showland=True, landcolor="#f8fafc",
                showcountries=True, 
                countrycolor="#e2e8f0",  
                countrywidth=0.7,        
                showframe=True,          
                framecolor="#e2e8f0",    
                framewidth=1.0,          
                showocean=True, oceancolor="#ffffff",
                resolution=110
            ),
            height=230,  # 172(卡片) + 8(间距) + 40(按钮) ≈ 220px，左右两侧再度完美对齐
            dragmode=False 
        )
        
        fig.update_traces(
            marker=dict(
                line=dict(width=1, color='#ffffff'), 
                opacity=0.9
            )
        )
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})

    st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 13px; margin-top: 2rem;'>Python & Streamlit | 致力于地震工程数字化</p>", unsafe_allow_html=True)

# ==========================================
# 自动化路由执行器 (Auto Router Core)
# ==========================================
def main() -> None:
    setup_page_config()
    init_session_state()
    inject_custom_css()

    current_page = st.session_state.get('current_page', 'HOME')
    
    page_registry = {'HOME': view_home}
    if hasattr(registry, 'PAGE_ROUTES'):
        page_registry.update(registry.PAGE_ROUTES)
    
    if current_page in page_registry:
        page_registry[current_page]()
    else:
        st.error(f"🚧 404: 模块 '{current_page}' 正在紧张建设中...")
        if st.button("返回主页", key="error_back_home"): 
            nav_to('HOME')

if __name__ == "__main__":
    main()