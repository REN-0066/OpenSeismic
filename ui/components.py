import streamlit as st
import os
from typing import List, Dict, Any

def setup_page_config() -> None:
    st.set_page_config(
        page_title="OpenSeismic | 地震工程交流共享", 
        layout="centered", 
        initial_sidebar_state="collapsed"
    )

def init_session_state() -> None:
    if 'current_page' not in st.session_state: 
        st.session_state.current_page = 'HOME'

def inject_custom_css() -> None:
    st.markdown("""
    <style>
        .stApp { background-color: #F8FAFC; font-family: 'Inter', "PingFang SC", "Microsoft YaHei", sans-serif; }
        .hero-title { font-weight: 900; text-align: center; margin-top: 2rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px;}
        .hero-subtitle { text-align: center; color: #475569; font-size: 1.25rem; font-weight: 600; margin-bottom: 3.5rem; letter-spacing: 2px;}
        button[kind="primary"] { width: 100%; height: 110px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; color: #0f172a; font-size: 16px; font-weight: 700; transition: all 0.3s ease; white-space: pre-wrap; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        button[kind="primary"]:hover { border-color: #3b82f6; color: #1d4ed8; background: #ffffff; transform: translateY(-4px); box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.15); }
        button[kind="primary"][disabled] { background: #f1f5f9; color: #94a3b8; border: 1px dashed #cbd5e1; box-shadow: none; transform: none;}
        button[kind="secondary"] { height: auto !important; padding: 8px 24px; font-size: 14px; border-radius: 6px; background: #ffffff; border: 2px solid #3b82f6; color: #3b82f6; font-weight: 600; transition: all 0.3s ease; }
        button[kind="secondary"]:hover { background: #3b82f6; color: #ffffff; transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.2); }
        h3.chapter-title { border-left: 4px solid #1e3a8a; padding-left: 12px; margin-top: 2.5rem; margin-bottom: 1.2rem; color: #0f172a; font-weight: 800; font-size: 1.2rem; }
        .stNumberInput > div > div > input { border-radius: 6px; border: 1px solid #cbd5e1; }
        .block-container {
            max-width: 55% !important; 
            padding-top: 4rem;
            padding-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)    

def nav_to(page_id: str) -> None:
    st.session_state.current_page = page_id
    st.rerun()

def ui_back_button(target: str, label: str = "← 返回上级目录") -> None:
    if st.button(label): 
        nav_to(target)

def ui_card(): 
    return st.container(border=True)

def ui_button_grid(menu_items: List[Dict[str, Any]], cols_per_row: int = 3) -> None:
    for i in range(0, len(menu_items), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, item in zip(cols, menu_items[i : i + cols_per_row]):
            with col:
                is_disabled = item.get("disabled", False)
                if st.button(label=item["title"], type="primary", width="stretch", disabled=is_disabled, key=item["id"]):
                    if not is_disabled: 
                        nav_to(item["id"])

def ui_card_container() -> None:
    st.markdown("""<div style="background-color: white; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 20px; border: 1px solid #e2e8f0;">""", unsafe_allow_html=True)

def ui_card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)

def ui_file_download_card(title: str, file_path: str, description: str = "") -> None:
    ui_card_container()
    if not os.path.exists(file_path):
        st.error(f"❌ **物理文件缺失**：未能检测到服务器路径文件 `{file_path}`")
        ui_card_end()
        return
        
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    file_name = os.path.basename(file_path)
    
    col_text, col_btn = st.columns([3, 1])
    with col_text:
        st.markdown(f"<h4 style='margin: 0; padding-bottom: 5px; color: #0f172a;'>{title}</h4>", unsafe_allow_html=True)
        if description:
            st.markdown(f"<p style='margin: 0; color: #475569; font-size: 14px;'>{description}</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin: 8px 0 0 0; color: #94a3b8; font-size: 12px;'>📄 {file_name} &nbsp;|&nbsp; 📦 {file_size_mb:.2f} MB</p>", unsafe_allow_html=True)
        
    with col_btn:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        try:
            with open(file_path, "rb") as f: 
                file_bytes = f.read()
            st.download_button(
                label="立即下载", 
                data=file_bytes, 
                file_name=file_name, 
                mime="application/pdf", 
                type="secondary", 
                width="stretch", 
                key=f"dl_btn_{file_name}"
            )
        except Exception as e:
            st.error(f"读取失败: {str(e)}")
    ui_card_end()
