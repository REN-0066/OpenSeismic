import streamlit as st
import requests  # 新增：用于调用云端数据库 API
import os
import pandas as pd
import plotly.express as px
import config.registry as registry
from ui.components import setup_page_config, init_session_state, inject_custom_css, nav_to

# ==========================================
# 社区数据持久化引擎 (Cloud Redis Database)
# ==========================================
def get_redis_headers():
    # 从 Streamlit Secrets 中安全读取 Token
    return {"Authorization": f"Bearer {st.secrets['UPSTASH_REDIS_REST_TOKEN']}"}

def get_redis_url():
    return st.secrets["UPSTASH_REDIS_REST_URL"]

def init_community_stats():
    """初始化或加载全站统计数据（从云端获取）"""
    # 如果在本地测试且没有配置 secrets，提供安全的回退机制
    if "UPSTASH_REDIS_REST_URL" not in st.secrets:
        return {"visits": 1024, "likes": 356}
        
    url = get_redis_url()
    headers = get_redis_headers()
    
    # 获取当前的 visits 和 likes
    try:
        visits_res = requests.get(f"{url}/get/visits", headers=headers).json().get("result")
        likes_res = requests.get(f"{url}/get/likes", headers=headers).json().get("result")
        
        # 如果是全新的数据库，设置你在代码里期望的初始基数
        if visits_res is None:
            requests.get(f"{url}/set/visits/1024", headers=headers)
            visits_res = 1024
        if likes_res is None:
            requests.get(f"{url}/set/likes/356", headers=headers)
            likes_res = 356
            
        return {"visits": int(visits_res), "likes": int(likes_res)}
    except Exception as e:
        # 网络异常时返回默认值，防止页面崩溃
        return {"visits": 1024, "likes": 356}

def increment_stat(stat_key):
    """云端原子递增统计项，并返回最新值"""
    if "UPSTASH_REDIS_REST_URL" not in st.secrets:
        return 0
        
    url = get_redis_url()
    headers = get_redis_headers()
    
    # Redis 的 INCR 命令完美解决多用户同时点击造成的并发冲突
    try:
        res = requests.get(f"{url}/incr/{stat_key}", headers=headers).json()
        return int(res.get("result", 0))
    except Exception:
        return 0

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
    # ==========================================
    # 终极网络调试探针（查完错后可删除）
    # ==========================================
    if "UPSTASH_REDIS_REST_URL" in st.secrets:
        try:
            raw_url = st.secrets["UPSTASH_REDIS_REST_URL"]
            safe_url = raw_url.rstrip('/') # 自动砍掉网址结尾多余的斜杠
            headers = {"Authorization": f"Bearer {st.secrets['UPSTASH_REDIS_REST_TOKEN']}"}
            
            st.info(f"正在尝试连接数据库... 目标网址: {safe_url}")
            test_res = requests.get(f"{safe_url}/get/visits", headers=headers)
            
            if test_res.status_code == 200:
                st.success(f"🎉 数据库连接完全成功！返回数据: {test_res.text}")
            else:
                st.error(f"🚨 数据库连接失败！状态码: {test_res.status_code}")
                st.error(f"数据库给出的具体拒绝理由: {test_res.text}")
        except Exception as e:
            st.error(f"💥 网络请求崩溃，详细错误: {str(e)}")
    # ==========================================
    
    # 页面首次加载时，触发云端递增访问量
    if 'has_visited' not in st.session_state:
        new_visits = increment_stat("visits")
        if new_visits > 0:
            stats["visits"] = new_visits
        st.session_state.has_visited = True

    st.markdown("<h4 style='color: #0f172a; font-weight: 800; margin-bottom: 12px; font-size: 1.1rem;'>🌍 统计面板</h4>", unsafe_allow_html=True)
    
    dash_col1, dash_col2 = st.columns([5, 8])
    
    with dash_col1:
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
            # 触发云端递增点赞量
            new_likes = increment_stat("likes")
            if new_likes > 0:
                stats["likes"] = new_likes
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
            size_max=16, 
            color_continuous_scale=["#60a5fa", "#1e3a8a"]
        )
        
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_showscale=False,
            geo=dict(
                showland=True, landcolor="#f8fafc",
                showcountries=True, countrycolor="#e2e8f0",  
                countrywidth=0.7, showframe=True,          
                framecolor="#e2e8f0", framewidth=1.0,          
                showocean=True, oceancolor="#ffffff",
                resolution=110
            ),
            height=230,
            dragmode=False 
        )
        
        fig.update_traces(marker=dict(line=dict(width=1, color='#ffffff'), opacity=0.9))
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})

    st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 13px; margin-top: 2rem;'>Python & Streamlit | 致力于地震工程数字化</p>", unsafe_allow_html=True)

# ==========================================
# 页面初始化与执行逻辑
# ==========================================
if __name__ == "__main__":
    setup_page_config()
    init_session_state()
    inject_custom_css()
    
    # 核心修改：动态路由分发器 (Router)
    current = st.session_state.current_page
    
    if current == 'HOME':
        # 如果状态是 HOME，则渲染主页
        view_home()
    elif current in registry.PAGE_ROUTES:
        # 如果状态在注册表里，就从字典里取出对应的渲染函数并执行 ()
        registry.PAGE_ROUTES[current]()
    else:
        # 异常兜底
        st.error("⚠️ 页面走丢了...")
        if st.button("返回首页"):
            nav_to('HOME')
