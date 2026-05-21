import modules.gb50011 as gb50011

# ==========================================
# 规范主页菜单配置
# ==========================================
GB50011_MENUS = {
    "📑 基础与新规说明 (第1~3章)": [
        {"title": "规范原文与条文说明\n高清 PDF 下载", "id": "m_download"},
        {"title": "🔥 3.1.3 & 3.9.2 条 (2024版)\n抗震专篇与材料性能要求", "id": "m_material"},
    ],
    "🌍 场地、地基和基础 (第4章)": [
        {"title": "4.1.5 & 4.1.6 条\n等效剪切波速与场地类别", "id": "m_vse"},
        {"title": "4.2.3 & 4.2.4 条\n天然地基抗震承载力与底压", "id": "m_fae"},
        {"title": "4.3.3 条\n地基液化初步判别", "id": "m_liq_pre"},
        {"title": "4.3.4 & 4.3.5 条\n地基液化判别与液化指数", "id": "m_liq"},
        {"title": "4.4.3 条\n打入式挤土桩打桩后SPT估算", "id": "m_pile_spt"},
    ],
    "🏢 地震作用计算 (第5章)": [
        {"title": "5.1.5 条\n地震影响系数 α 与反应谱", "id": "m_alpha"},
        {"title": "5.2.1 条\n底部剪力法水平地震作用分配", "id": "m_base_shear"},
        {"title": "5.2.3 条\n振型组合 CQC 耦联系数 ρ", "id": "m_cqc"},
        {"title": "🚀 5.2.3 条 3款 (核心补全)\n双向地震扭转效应组合", "id": "m_bidirectional"},
        {"title": "5.2.5 条\n楼层最小地震剪力系数 λ", "id": "m_min_shear"},
        {"title": "5.2.7 条 (已修复)\n地基与结构动力相互作用折减", "id": "m_ssi"},
        {"title": "5.3.1 条\n高层建筑竖向地震作用估算", "id": "m_vertical_eq"},
    ],
    "🏗️ 抗震验算与构造 (第5~7章)": [
        {"title": "🔥 5.4.1 条 (2024版新规)\n地震作用效应基本组合 S", "id": "m_combo"},
        {"title": "5.4.2 条\n承载力抗震调整系数 γ_RE", "id": "m_gamma_re"},
        {"title": "5.5.1 & 5.5.5 条\n弹性与弹塑性层间位移角验算", "id": "m_drift"},
        {"title": "6.2.2 & 6.2.4 条\n框架能力设计(强柱弱梁/强剪)", "id": "m_capacity"},
        {"title": "🚀 6.2.5 & 6.2.8 条\n柱与抗震墙剪力放大设计", "id": "m_col_wall_shear"},
        {"title": "6.2.9 条\n截面抗震受剪承载力(剪压比)", "id": "m_shear_limit"},
        {"title": "🚀 附录 D (高频验算)\n梁柱节点核芯区受剪承载力", "id": "m_node_core"},
        {"title": "6.3.6 & 6.3.9 条\n框架柱轴压比与体积配箍率", "id": "m_col_details"},
        {"title": "6.4.5 条\n抗震墙约束边缘构件尺寸 lc", "id": "m_wall_edge"},
        {"title": "7.2.6 & 7.2.7 条\n纯无筋砌体沿阶梯形抗震受剪", "id": "m_masonry"},
        {"title": "🚀 7.2.7-3 条 (高频验算)\n含构造柱砌体墙段综合抗剪", "id": "m_masonry_col"}
    ]
}

# ==========================================
# 全局路由表 (映射页面 ID 到具体的渲染函数)
# ==========================================
PAGE_ROUTES = {
    'GB50011': gb50011.view_gb50011_menu,
    'm_download': gb50011.render_download,
    'm_material': gb50011.render_material,
    'm_vse': gb50011.render_vse,
    'm_fae': gb50011.render_fae,
    'm_liq_pre': gb50011.render_liq_pre,
    'm_liq': gb50011.render_liq,
    'm_pile_spt': gb50011.render_pile_spt,
    'm_alpha': gb50011.render_alpha,
    'm_base_shear': gb50011.render_base_shear,
    'm_cqc': gb50011.render_cqc,
    'm_bidirectional': gb50011.render_bidirectional_eq,
    'm_min_shear': gb50011.render_min_shear,
    'm_ssi': gb50011.render_ssi,
    'm_vertical_eq': gb50011.render_vertical_eq,
    'm_combo': gb50011.render_combo,
    'm_gamma_re': gb50011.render_gamma_re,
    'm_drift': gb50011.render_drift,
    'm_capacity': gb50011.render_capacity,
    'm_col_wall_shear': gb50011.render_col_wall_shear,
    'm_shear_limit': gb50011.render_shear_limit,
    'm_node_core': gb50011.render_node_core,
    'm_col_details': gb50011.render_col_details,
    'm_wall_edge': gb50011.render_wall_edge,
    'm_masonry': gb50011.render_masonry,
    'm_masonry_col': gb50011.render_masonry_col
}
