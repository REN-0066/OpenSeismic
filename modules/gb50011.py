import streamlit as st
import numpy as np
import pandas as pd
import math
import plotly.graph_objects as go
from typing import Tuple
from ui.components import ui_back_button, ui_card, ui_button_grid, nav_to, ui_file_download_card
# import config.registry as registry

# ==========================================
# 核心数学计算引擎 (Pure Math Model)
# ==========================================
class SeismicMath:
    @staticmethod
    def calc_vse(d_cover: float, df: pd.DataFrame) -> Tuple[bool, float, float, float, str]:
        """计算等效剪切波速并判定场地类别"""
        d0 = min(d_cover, 20.0)
        t = 0.0
        current = 0.0
        for _, row in df.iterrows():
            try:
                di = float(row.get('层厚(m)', 0))
                vsi = float(row.get('波速(m/s)', 0))
            except (ValueError, TypeError, KeyError):
                continue
            if pd.isna(di) or pd.isna(vsi) or di <= 0 or vsi <= 0: 
                continue
            if current + di <= d0:
                t += di / vsi
                current += di
            else:
                t += (d0 - current) / vsi
                current = d0
                break
        vse = d0 / t if t > 0 else 0.0
        
        # 严格执行规范标准的场地判定矩阵
        if vse > 800: site = "I0 类"
        elif 500 < vse <= 800: site = "I1 类"
        elif 250 < vse <= 500: site = "I1 类" if d_cover < 5 else "II 类"
        elif 150 < vse <= 250: site = "I1 类" if d_cover < 3 else ("II 类" if d_cover <= 50 else "III 类")
        else: site = "I1 类" if d_cover < 3 else ("II 类" if d_cover <= 15 else ("III 类" if d_cover <= 80 else "IV 类"))
        return (current >= d0 - 1e-4), d0, t, vse, site

    @staticmethod
    def calc_fae_pressure(zeta_a: float, fa: float, n: float, m: float, a: float, b: float) -> Tuple[float, float, float]:
        """计算基础抗震承载力及偏心基底压力"""
        fae = zeta_a * fa
        area = a * b
        w = (b * a ** 2) / 6 if a > 0 else 1.0 
        p_avg = n / area if area > 0 else 0
        p_max = p_avg + m / w if w > 0 else p_avg
        return fae, p_avg, p_max

    @staticmethod
    def calc_liq_pre(du: float, dw: float, d0: float, db: float) -> Tuple[bool, str]:
        """地基液化初步判别哨兵"""
        db_calc = max(db, 2.0)
        c1 = du > d0 + db_calc - 2.0
        c2 = dw > d0 + db_calc - 3.0
        c3 = du + dw > 1.5 * d0 + 2 * db_calc - 4.5
        ok = c1 or c2 or c3
        msg = "满足" if ok else "不满足"
        return ok, f"条件1: {c1} | 条件2: {c2} | 条件3: {c3} -> 综合判别：{msg}不液化条件"

    @staticmethod
    def calc_liq(acc: str, grp: str, dw: float, df_spt: pd.DataFrame) -> Tuple[float, str]:
        """标准贯入击数精确计算液化指数及等级评估"""
        n0_map = {'0.10g': 7, '0.15g': 10, '0.20g': 12, '0.30g': 16, '0.40g': 19}
        beta_map = {'第一组': 0.80, '第二组': 0.95, '第三组': 1.05}
        n0 = n0_map.get(acc, 10)
        beta = beta_map.get(grp, 1.0)
        ile = 0.0
        for _, row in df_spt.iterrows():
            try:
                ds = float(row.get('深度(m)', 0))
                ni = float(row.get('实测Ni', 0))
                rhoc = float(row.get('黏粒(%)', 3))
                di = float(row.get('厚度(m)', 0))
                is_sand = bool(row.get('纯砂不折减', False))
            except (ValueError, TypeError, KeyError):
                continue
            if pd.isna(ds) or ds <= 0 or di <= 0: 
                continue
            rhoc_calc = 3.0 if is_sand else max(3.0, rhoc)
            ncr = n0 * beta * (math.log(0.6 * ds + 1.5) - 0.1 * dw) * math.sqrt(3 / rhoc_calc)
            ncr = max(0.0, ncr)
            wi = 10.0 if ds <= 5.0 else (10.0 * (20.0 - ds) / 15.0 if ds <= 20.0 else 0.0)
            if ni < ncr: 
                ile += (1.0 - ni / ncr) * di * wi
        level = "不液化" if ile == 0 else ("轻微液化" if ile <= 6 else ("中等液化" if ile <= 18 else "严重液化"))
        return ile, level

    @staticmethod
    def calc_pile_spt(np_val: float, rho: float) -> float:
        return np_val + 100 * rho * (1 - math.exp(-0.3 * np_val))

    @staticmethod
    def calc_alpha(amax: float, tg: float, zeta: float) -> Tuple[float, float, float]:
        """计算反应谱地震影响系数边界曲线族参数"""
        gamma = 0.9 + (0.05 - zeta) / (0.3 + 6 * zeta) 
        eta2 = max(0.55, 1.0 + (0.05 - zeta) / (0.08 + 1.6 * zeta))
        eta1 = max(0.0, 0.02 + (0.05 - zeta) / (4 + 32 * zeta))
        return gamma, eta1, eta2

    @staticmethod
    def calc_base_shear(alpha1: float, tg: float, t1: float, df: pd.DataFrame) -> Tuple[float, float, float, pd.DataFrame]:
        """经典底部剪力法多层剪力推进矩阵模型"""
        df_calc = df.copy()
        df_calc['重力(kN)'] = pd.to_numeric(df_calc.get('重力(kN)', 0), errors='coerce').fillna(0)
        df_calc['层高(m)'] = pd.to_numeric(df_calc.get('层高(m)', 0), errors='coerce').fillna(0)
        g_total = df_calc['重力(kN)'].sum()
        g_eq = 0.85 * g_total if len(df_calc) > 1 else g_total 
        dn = 0.0
        if t1 > 1.4 * tg:
            if tg <= 0.35: dn = 0.08 * t1 + 0.07
            elif tg <= 0.55: dn = 0.08 * t1 + 0.01
            else: dn = 0.08 * t1 - 0.02
        dn = max(0.0, dn)
        fek = alpha1 * g_eq
        dfn = dn * fek
        df_calc['计算标高Hi(m)'] = df_calc['层高(m)'].cumsum()
        df_calc['Gi*Hi'] = df_calc['重力(kN)'] * df_calc['计算标高Hi(m)']
        sum_gh = df_calc['Gi*Hi'].sum()
        fi_list = []
        for i in range(len(df_calc)):
            fi = (df_calc['Gi*Hi'].iloc[i] / sum_gh) * fek * (1 - dn) if sum_gh > 0 else 0
            if i == len(df_calc) - 1: 
                fi += dfn  
            fi_list.append(round(fi, 2))
        df_calc['水平地震力Fi(kN)'] = fi_list
        df_calc['楼层剪力Vi(kN)'] = df_calc['水平地震力Fi(kN)'].iloc[::-1].cumsum().iloc[::-1]
        return fek, dfn, g_eq, df_calc

    @staticmethod
    def calc_cqc_rho(lam_t: float, zeta: float) -> float:
        numerator = 8 * (zeta ** 2) * (1 + lam_t) * (lam_t ** 1.5)
        denominator = (1 - lam_t ** 2) ** 2 + 8 * (zeta ** 2) * lam_t * (1 + lam_t)
        return numerator / denominator if denominator != 0 else 1.0

    @staticmethod
    def calc_min_shear(intensity: str, t1: float, is_torsion: bool) -> float:
        vals = {'6度':(0.008, 0.006), '7度(0.10g)':(0.016, 0.012), '7度(0.15g)':(0.024, 0.018), 
                '8度(0.20g)':(0.032, 0.024), '8度(0.30g)':(0.048, 0.036), '9度':(0.064, 0.048)}
        v1, v2 = vals.get(intensity, (0.016, 0.012))
        v2 = v1 if is_torsion else v2
        if t1 <= 3.5: return v1
        if t1 >= 5.0: return v2
        return v1 - (v1 - v2) * (t1 - 3.5) / 1.5

    @staticmethod
    def calc_ssi(t1: float, acc: str, site: str) -> Tuple[float, float]:
        if site not in ["III类", "IV类"] or acc not in ["8度", "9度"]: 
            return 0.0, 1.0
        dt_map = {"8度": {"III类": 0.08, "IV类": 0.20}, "9度": {"III类": 0.10, "IV类": 0.25}}
        dt = dt_map[acc][site]
        return dt, (t1 / (t1 + dt)) ** 0.9 if dt > 0 else 1.0

    @staticmethod
    def calc_vertical_eq(amax: float, geq: float, is_cantilever: bool, intensity: str) -> Tuple[float, float]:
        if is_cantilever:
            coeff = 0.10 if intensity == '8度(0.20g)' else (0.15 if intensity == '8度(0.30g)' else 0.20)
            return coeff, coeff * geq
        else:
            av_max = 0.65 * amax
            return av_max, av_max * geq

    @staticmethod
    def calc_combo_2024(sg: float, seh: float, sev: float, sw: float, ctype: int, is_fav: bool, has_wind: bool) -> Tuple[float, float, float, float]:
        gg = 1.0 if is_fav else 1.3
        gw = 1.5
        pw = 0.2 if has_wind else 0.0
        gh, gv = [(1.4, 0.0), (0.0, 1.4), (1.4, 0.5), (0.5, 1.4)][ctype]
        s = gg * sg + gh * seh + gv * sev + pw * gw * sw
        return s, gg, gh, gv

    @staticmethod
    def calc_drift(stype: str, h: float, due: float, dup: float) -> Tuple[float, float, float, float]:
        e_map = {"框架": 550, "框架-抗震墙/核心筒": 800, "抗震墙/筒体": 1000, "框支层": 1000, "钢结构": 250}
        p_map = {"框架": 50, "框架-抗震墙/核心筒": 100, "抗震墙/筒体": 120, "框支层": 100, "钢结构": 50}
        limit_e = 1.0 / e_map.get(stype, 550)
        limit_p = 1.0 / p_map.get(stype, 50)
        te = due / h if h > 0 else 0
        tp = dup / h if h > 0 else 0
        return te, limit_e, tp, limit_p

    @staticmethod
    def calc_capacity(grade: int, ftype: str, mbl: float, mbr: float, ln: float, vgb: float) -> Tuple[float, float]:
        ec = {1: 1.7, 2: 1.5, 3: 1.3, 4: 1.2}.get(grade, 1.2) if ftype == "框架结构" else {1: 1.4, 2: 1.2, 3: 1.1, 4: 1.1}.get(grade, 1.1)
        evb = {1: 1.3, 2: 1.2, 3: 1.1, 4: 1.0}.get(grade, 1.0)
        return ec * (mbl + mbr), (evb * (mbl + mbr) / ln + vgb) if ln > 0 else 0

    @staticmethod
    def calc_shear_limit(fc: float, b: float, h0: float, lam: float, is_short: bool) -> float:
        fc_calc = max(fc, 16.7) 
        coeff = 0.15 if is_short or lam <= 2.5 else 0.20
        return coeff * fc_calc * b * h0 / 0.85 / 1000 

    @staticmethod
    def calc_col_limits(stype: str, lvl: int, short: bool, hoop: bool, core: bool, lv: float, fc: float, fyv: float) -> Tuple[float, float]:
        lims = {"框架结构": [0.65, 0.75, 0.85, 0.90], "框剪/筒体": [0.75, 0.85, 0.90, 0.95], "部分框支": [0.60, 0.70, 0.0, 0.0]}
        base = lims.get(stype, [0.0]*4)[lvl - 1]
        if base > 0:
            if short: base -= 0.05
            if hoop and core: base += 0.15
            elif hoop: base += 0.10
            elif core: base += 0.05
        rho_v = lv * max(fc, 16.7) / fyv * 100 if fyv > 0 else 0
        return min(base, 1.05), rho_v

    @staticmethod
    def calc_wall_edge(hw: float, ax_ratio: float, level_type: str) -> float:
        if level_type == "一级(9度)": return 0.25 * hw if ax_ratio <= 0.3 else 0.20 * hw
        elif level_type == "一级(7、8度)": return 0.20 * hw if ax_ratio <= 0.3 else 0.15 * hw
        else: return 0.20 * hw if ax_ratio <= 0.4 else 0.15 * hw

    @staticmethod
    def calc_masonry_v(fv: float, sig: float, is_brick: bool, area: float, gamma_re: float) -> Tuple[float, float, float]:
        rat = sig / fv if fv > 0 else 0
        xp = [0.0, 1.0, 3.0, 5.0, 7.0, 10.0, 12.0, 16.0]
        yp = [0.80, 0.99, 1.25, 1.47, 1.65, 1.90, 2.05, 2.05] if is_brick else [1.00, 1.23, 1.69, 2.15, 2.57, 3.02, 3.32, 3.92]
        zn = float(np.interp(rat, xp, yp))
        return zn, zn * fv, (zn * fv * area / gamma_re / 1000 if gamma_re > 0 else 0)


# ==========================================
# 视图层 (View Controllers)
# ==========================================
def view_gb50011_menu() -> None:
    import config.registry as registry  # 新增：把引入挪到函数里面！
    
    if st.button("← 返回首页"): 
        nav_to('HOME')
    st.markdown('<div class="hero-title" style="font-size: 2rem; margin-top: 1rem;">GB/T 50011-2010 (2024 版) 计算模块</div>', unsafe_allow_html=True)
    for chapter, modules in registry.GB50011_MENUS.items():
        st.markdown(f"<h3 class='chapter-title'>{chapter}</h3>", unsafe_allow_html=True)
        ui_button_grid(modules, cols_per_row=3)

def render_download() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">⬇️ 规范文档查阅与下载</h2>', unsafe_allow_html=True)
    st.info("💡 **2024 年版局部修订提示**：本次修订提高了部分构件混凝土强度下限，并全面提升了**地震组合的荷载分项系数**。")
    ui_file_download_card(
        title="📖 建筑抗震设计标准 (2024版局部修订)",
        file_path="data/建筑抗震设计标准 (2024).pdf",
        description="包含最新局部修订条文，适用于 2024 年以后的最新项目抗震计算。"
    )
    ui_file_download_card(
        title="📝 建筑抗震设计规范 (2016版完整正文)",
        file_path="data/建筑抗震设计规范 (2016).pdf",
        description="GB 50011-2010 (2016年修订) 完整正文与条文说明原件。"
    )

def render_material() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">🔥 3.1.3 & 3.9.2 条 抗震专篇与材料要求 (2024新规)</h2>', unsafe_allow_html=True)
    with ui_card():
        st.error("🚨 **2024版重大修订（强条）**：\n\n框支梁、框支柱及抗震等级一、二级的框架梁、柱、节点核芯区，混凝土强度不应低于 **C30**；构造柱、芯柱、圈梁不应低于 **C25** (原为C20)。")
        st.success("✅ **抗震钢筋要求 (带E钢筋)**：\n1. 实测抗拉强度 / 实测屈服强度 ≥ 1.25\n2. 实测屈服 / 标准屈服 ≤ 1.30\n3. 最大拉力总伸长率 ≥ 9%")

def render_vse() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.1.5 & 4.1.6 等效剪切波速与场地类别精算书</h2>', unsafe_allow_html=True)
    
    if 'df_vse' not in st.session_state: 
        st.session_state.df_vse = pd.DataFrame({"层厚(m)": [2.5, 6.0, 10.0], "波速(m/s)": [140.0, 220.0, 310.0]})
    
    with ui_card():
        d_cov = st.number_input("场地覆盖层厚度 (m)", value=15.0, min_value=0.1, step=1.0)
        st.caption("📋 勘察孔分层岩土测试点数据输入（双击单元格可修改，自动根据 20m 上限截断）")
        edf = st.data_editor(st.session_state.df_vse, num_rows="dynamic", width="stretch", key="vse_editor")
        st.session_state.df_vse = edf
    
    ok, d0, t, vse, site = SeismicMath.calc_vse(d_cov, edf)
    
    st.markdown("### 🧮 数字化工程计算书")
    c1, c2 = st.columns(2)
    c1.latex(r"t = \sum_{i=1}^{n} \frac{d_i}{v_{si}} = " + f"{t:.4f} \\text{{ s}}")
    c2.latex(r"v_{se} = \frac{d_0}{t} = \frac{" + f"{d0:.2f}" + r"}{" + f"{t:.4f}" + r"} = " + f"{vse:.2f} \\text{{ m/s}}")
    
    if not ok: 
        st.warning(f"⚠️ 当前累计填写层厚不足限值(当前: {d0:.2f}m)，系统已按实际总土层计算，建议补全深部数据。")
    
    st.markdown(f"""<div style="background-color: #f8fafc; border-left: 5px solid #3b82f6; padding: 15px; margin: 15px 0;">
        <span style='color: #1e3a8a; font-weight: 800; font-size: 1.2rem;'>🎯 建筑勘察场地类别判定： {site}</span> (等效剪切波速计为 {vse:.1f} m/s)
    </div>""", unsafe_allow_html=True)

    st.markdown("#### 📊 场地地质剖面波速层序可视化")
    fig = go.Figure()
    for idx, row in edf.iterrows():
        try:
            h = float(row.get('层厚(m)', 0))
            v = float(row.get('波速(m/s)', 0))
        except (ValueError, TypeError):
            continue
        if h > 0 and v > 0:
            fig.add_trace(go.Bar(
                name=f"第{idx+1}层 ({v:.0f}m/s)", x=[v], y=[h], orientation='h',
                marker=dict(color='#60a5fa', line=dict(color='#1e3a8a', width=1)),
                hovertemplate=f"层厚: {h}m<br>波速: {v}m/s<extra></extra>"
            ))
    fig.add_vline(x=vse, line_dash="dashdot", line_color="#ef4444", line_width=2.5, annotation_text=f"等效波速 {vse:.1f} m/s")
    
    # 核心修正：autorange="reversed" 完美控制Y轴深度的地层翻转表达
    fig.update_layout(barmode='stack', yaxis=dict(autorange="reversed", title="深度标高 (m)"), xaxis=dict(title="剪切波速 Vs (m/s)", side="top"), height=320, margin=dict(l=40, r=40, t=40, b=40), plot_bgcolor='white')
    st.plotly_chart(fig, width="stretch")

def render_fae() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.2.3 & 4.2.4 天然地基抗震承载力与偏心底压验算</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        za = c1.selectbox("调整系数 ζa (查表4.2.3)", [1.5, 1.3, 1.1, 1.0])
        fa = c2.number_input("深宽修正后地基承载力 $f_a$ (kPa)", value=200.0, step=10.0)
        c3, c4, c5, c6 = st.columns(4)
        n = c3.number_input("轴力 N (kN)", value=3000.0)
        m = c4.number_input("弯矩 M (kN·m)", value=600.0)
        a = c5.number_input("底长 a (m)", value=4.0, min_value=0.1)
        b = c6.number_input("底宽 b (m)", value=4.0, min_value=0.1)
    
    fae, p_avg, p_max = SeismicMath.calc_fae_pressure(za, fa, n, m, a, b)
    op1 = r'\le' if p_avg <= fae else '>'
    op2 = r'\le' if p_max <= 1.2 * fae else '>'
    
    st.markdown("#### 🧮 验算过程及结论")
    st.latex(rf"f_{{aE}} = \zeta_a f_a = {za} \times {fa} = {fae:.1f} \text{{ kPa}}")
    st.latex(rf"p_{{avg}} = \frac{{N}}{{A}} = {p_avg:.1f} \text{{ kPa}} \quad {op1} \quad f_{{aE}} \text{{ ({fae:.1f} kPa)}}")
    st.latex(rf"p_{{max}} = p_{{avg}} + \frac{{M}}{{W}} = {p_max:.1f} \text{{ kPa}} \quad {op2} \quad 1.2f_{{aE}} \text{{ ({1.2*fae:.1f} kPa)}}")

    c_a, c_b = st.columns(2)
    if p_avg <= fae: 
        c_a.success(f"**平均压应力** $p = {p_avg:.1f}$ kPa ✅ 满足规范")
    else: 
        c_a.error(f"**平均压应力** $p = {p_avg:.1f}$ kPa ❌ 超过限值")
        
    if p_max <= 1.2*fae: 
        c_b.success(f"**边缘最大应力** $p_{{max}} = {p_max:.1f}$ kPa ✅ 满足规范")
    else: 
        c_b.error(f"**边缘最大应力** $p_{{max}} = {p_max:.1f}$ kPa ❌ 超过限值")

def render_liq_pre() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.3.3 地基液化初步判别</h2>', unsafe_allow_html=True)
    with ui_card():
        st.info("提示：规范要求基础埋深 $d_b$ 小于 2m 时按 2m 计算，系统已内置该截断规则。")
        c1, c2, c3, c4 = st.columns(4)
        du = c1.number_input("上覆非液化土厚 $d_u$ (m)", value=4.0)
        dw = c2.number_input("地下水位 $d_w$ (m)", value=2.0)
        d0 = c3.number_input("液化特征深度 $d_0$ (m)", value=7.0)
        db = c4.number_input("基础埋置深度 $d_b$ (m)", value=1.5)
        
    ok, msg = SeismicMath.calc_liq_pre(du, dw, d0, db)
    db_act = max(db, 2.0)
    
    st.markdown("#### 🧮 初步判别公式校核（满足其一即可）")
    st.latex(rf"1) \quad d_u > d_0 + d_b - 2 \Longrightarrow {du} > {d0} + {db_act} - 2 = {d0+db_act-2:.1f}")
    st.latex(rf"2) \quad d_w > d_0 + d_b - 3 \Longrightarrow {dw} > {d0} + {db_act} - 3 = {d0+db_act-3:.1f}")
    st.latex(rf"3) \quad d_u + d_w > 1.5d_0 + 2d_b - 4.5 \Longrightarrow {du+dw:.1f} > {1.5*d0 + 2*db_act - 4.5:.1f}")
    
    if ok: 
        st.success(f"✅ {msg}")
    else: 
        st.error(f"❌ {msg}")

def render_liq() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.3.4 & 4.3.5 地基液化判别与指数精算</h2>', unsafe_allow_html=True)
    if 'df_spt' not in st.session_state: 
        st.session_state.df_spt = pd.DataFrame({"深度(m)": [3.0, 7.0], "实测Ni": [6.0, 12.0], "厚度(m)": [4.0, 5.0], "黏粒(%)": [12.0, 5.0], "纯砂不折减": [False, True]})
        
    with ui_card():
        c1, c2, c3 = st.columns(3)
        acc = c1.selectbox("设计基本加速度", ['0.10g', '0.15g', '0.20g', '0.30g', '0.40g'], index=1)
        grp = c2.selectbox("设计地震分组", ['第一组', '第二组', '第三组'])
        dw = c3.number_input("地下水位深度 $d_w$ (m)", value=2.0)
        st.caption("钻孔 SPT 数据录入：")
        edf = st.data_editor(st.session_state.df_spt, num_rows="dynamic", width="stretch", key="spt_editor")
        st.session_state.df_spt = edf
    
    ile, level = SeismicMath.calc_liq(acc, grp, dw, edf)
    st.markdown("#### 🧮 积分累加总液化指数")
    st.latex(r"I_{lE} = \sum_{i=1}^{n} \left( 1 - \frac{N_i}{N_{cri}} \right) d_i W_i = " + f"{ile:.3f}")
    
    if ile > 0: 
        st.error(f"判定结论：综合地基液化指数 **$I_{{lE}} = {ile:.3f}$** ，属于 **【{level}】** 场地。")
    else: 
        st.success(f"判定结论：综合地基液化指数 **$I_{{lE}} = {ile:.3f}$** ，该场地 **【安全不液化】**。")

def render_pile_spt() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.4.3 打入式挤土桩打桩后 SPT 估算</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        np_val = c1.number_input("打桩前的标贯击数 $N_p$", value=10.0)
        rho = c2.number_input("挤土预制桩的面积置换率 $ρ$", value=0.03, step=0.01, format="%.3f")
        
    st.markdown("#### 🧮 估算公式")
    st.latex(r"N_1 = N_p + 100 \rho (1 - e^{-0.3 N_p})")
    st.success(f"### 估算打桩后的标贯击数 $N_1 = {SeismicMath.calc_pile_spt(np_val, rho):.1f}$")

def render_alpha() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.1.5 地震影响系数 α 与反应谱</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2, c3 = st.columns(3)
        amax = c1.number_input("最大影响系数 $α_{max}$", value=0.16)
        tg = c2.number_input("特征周期 $T_g$ (s)", value=0.35, min_value=0.05)
        zeta = c3.number_input("结构阻尼比 $ζ$", value=0.05, min_value=0.0, max_value=0.9)
    g, e1, e2 = SeismicMath.calc_alpha(amax, tg, zeta)
    
    st.markdown("#### 🧮 曲线参数计算")
    st.latex(r"\gamma = 0.9 + \frac{0.05-\zeta}{0.3+6\zeta} = " + f"{g:.3f}")
    st.latex(r"\eta_1 = 0.02 + \frac{0.05-\zeta}{4+32\zeta} = " + f"{e1:.3f}")
    st.latex(r"\eta_2 = 1 + \frac{0.05-\zeta}{0.08+1.6\zeta} = " + f"{e2:.3f}")
    
    t_vals = np.arange(0, 7.0, 0.01)
    a_vals = [amax if t<0.1 else (amax if t<tg else ((tg/t)**g * e2 * amax if t<5*tg else max(0, (e2*0.2**g - e1*(t-5*tg))*amax))) for t in t_vals]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t_vals, y=a_vals, mode='lines', name=r'影响系数 α', line=dict(color='#1e3a8a', width=3)))
    
    # 0.1s：放在线的【左上方】，并向左微推 5 像素防遮挡
    fig.add_vline(
        x=0.1, line_dash="dot", line_color="gray", 
        annotation_text="0.1s", 
        annotation_position="bottom right",
        annotation_yshift=20,
        annotation_xshift=5
    )
    
    # Tg：放在线的【右上方】
    fig.add_vline(
        x=tg, line_dash="dash", line_color="#ef4444", 
        annotation_text=f"Tg={tg}s", 
        annotation_position="top right",
        annotation_xshift=5
    )
    
    # 5Tg：放在线的【右下方】，避免和顶部的 Tg 挤在一起
    if 5*tg <= 6.0: 
        fig.add_vline(
            x=5*tg, line_dash="dashdot", line_color="#10b981", 
            annotation_text=f"5Tg={5*tg:.2f}s", 
            annotation_position="bottom right",
            annotation_yshift=20, # 向上提 20 像素，避免贴住 X 轴边缘
            annotation_xshift=5
        )
        
    fig.update_layout(title="结构地震影响系数曲线 (GB/T 50011)", xaxis_title="自振周期 T (s)", yaxis_title="地震影响系数 α", plot_bgcolor='white', hovermode="x unified")
    st.plotly_chart(fig, width="stretch")

def render_base_shear() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.2.1 底部剪力法侧推分配模型</h2>', unsafe_allow_html=True)
    if 'df_fl' not in st.session_state: 
        st.session_state.df_fl = pd.DataFrame({"楼层": ["1层", "2层", "3层"], "层高(m)": [4.0, 3.2, 3.2], "重力(kN)": [3000, 2500, 2000]})
        
    with ui_card():
        c1, c2, c3 = st.columns(3)
        alpha1 = c1.number_input("基本周期影响系数 $α_1$", value=0.12)
        t1 = c2.number_input("结构基本周期 $T_1$ (s)", value=0.80)
        tg = c3.number_input("特征周期 $T_g$ (s)", value=0.35)
        st.caption("层重力荷载输入（按楼层自下而上填写）：")
        edf = st.data_editor(st.session_state.df_fl, num_rows="dynamic", width="stretch", key="base_shear_editor")
        st.session_state.df_fl = edf
    
    fek, dfn, geq, df_res = SeismicMath.calc_base_shear(alpha1, tg, t1, edf)
    
    st.markdown("#### 🧮 计算总指标")
    c_a, c_b, c_c = st.columns(3)
    c_a.metric(label="等效总重力 Geq", value=f"{geq:.1f} kN")
    c_b.metric(label="底部总水平剪力 FEk", value=f"{fek:.1f} kN")
    c_c.metric(label="顶层附加剪力 ΔFn", value=f"{dfn:.1f} kN")
    
    st.markdown("#### 📊 楼层地震剪力与水平推力包络图")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_res['水平地震力Fi(kN)'], y=df_res['计算标高Hi(m)'], mode='lines+markers', name='楼层水平力 Fi', line=dict(color='#ef4444', width=3)))
    fig.add_trace(go.Scatter(x=df_res['楼层剪力Vi(kN)'], y=df_res['计算标高Hi(m)'], mode='lines+markers', name='层间剪力 Vi', line=dict(color='#3b82f6', width=3, shape='hv')))
    fig.update_layout(xaxis_title="受力大小 (kN)", yaxis_title="楼层标高 (m)", height=380, hovermode="y unified", plot_bgcolor='#f8fafc')
    st.plotly_chart(fig, width="stretch")
    
    st.dataframe(df_res.style.format({"计算标高Hi(m)": "{:.2f}", "水平地震力Fi(kN)": "{:.2f}", "楼层剪力Vi(kN)": "{:.2f}"}).background_gradient(subset=['楼层剪力Vi(kN)'], cmap='YlGnBu'), width="stretch", hide_index=True)

def render_cqc() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.2.3 振型组合 CQC 耦联系数 ρ</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        lam_t = c1.number_input("振型周期比 $λ_T = T_k / T_j$", value=0.85, step=0.05)
        zeta = c2.number_input("阻尼比 $ζ$", value=0.05)
    st.latex(r"\rho_{jk} = \frac{8\zeta^2(1+\lambda_T)\lambda_T^{1.5}}{(1-\lambda_T^2)^2 + 8\zeta^2\lambda_T(1+\lambda_T)}")
    st.success(f"### 🎯 耦联系数 $\\rho_{{jk}} = {SeismicMath.calc_cqc_rho(lam_t, zeta):.4f}$")

def render_min_shear() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.2.5 楼层最小地震剪力系数 λ (剪重比)</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        acc = c1.selectbox("设防烈度", ['6度', '7度(0.10g)', '7度(0.15g)', '8度(0.20g)', '8度(0.30g)', '9度'], index=3)
        t1 = c2.number_input("结构基本周期 $T_1$ (s)", value=4.0)
        is_t = st.checkbox("扭转效应明显 (启用更严上限)")
    st.latex(r"V_{EKi} > \lambda \sum G_j")
    st.success(f"### 🎯 楼层最小地震剪力系数限值 $\lambda = {SeismicMath.calc_min_shear(acc, t1, is_t):.4f}$")

def render_ssi() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.2.7 地基与结构动力相互作用折减系数 ψ</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2, c3 = st.columns(3)
        t1 = c1.number_input("基本周期 $T_1$ (s)", value=2.0)
        acc = c2.selectbox("设防烈度", ["8度", "9度"])
        site = c3.selectbox("场地类别", ["II类及以下", "III类", "IV类"], index=1)
    dt, psi = SeismicMath.calc_ssi(t1, acc, site)
    st.latex(r"\psi = \left( \frac{T_1}{T_1 + \Delta T} \right)^{0.9}")
    if psi == 1.0: 
        st.warning("该条件不符合折减标准，折减系数 $\psi = 1.0$")
    else: 
        st.success(f"### 🎯 附加周期 $\Delta T = {dt}s$ ，底部地震剪力折减系数 $\psi = {psi:.3f}$")

def render_vertical_eq() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.3.1 & 5.3.3 竖向地震作用标准值</h2>', unsafe_allow_html=True)
    with ui_card():
        is_can = st.radio("构件类型", ["长悬臂构件 / 大跨度屋盖", "9度区高层建筑"], horizontal=True) == "长悬臂构件 / 大跨度屋盖"
        g_total = st.number_input("结构/构件重力代表值 $G$ (kN)", value=1000.0)
        if is_can:
            intensity = st.selectbox("设防烈度", ["8度(0.20g)", "8度(0.30g)", "9度(0.40g)"])
            av, fevk = SeismicMath.calc_vertical_eq(0, g_total, True, intensity)
            st.success(f"### 🎯 竖向地震作用标准值 $F_{{Evk}} = {fevk:.1f}$ kN")
        else:
            alpha_max = st.number_input("水平地震影响系数最大值 $α_{max}$", value=0.32)
            av, fevk = SeismicMath.calc_vertical_eq(alpha_max, g_total, False, "")
            st.success(f"### 🎯 结构总竖向地震作用 $F_{{Evk}} = {fevk:.1f}$ kN")

def render_combo() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">🔥 5.4.1 地震作用效应基本组合 (2024版新规)</h2>', unsafe_allow_html=True)
    with ui_card():
        st.error("🚨 **2024版新规重磅变化（强制性条文）**：\n\n恒载分项系数 $\gamma_G$ 提升至 **1.3** (原1.2)；地震分项系数 $\gamma_{Eh}, \gamma_{Ev}$ 提升至 **1.4** (原1.3)；风荷载 $\gamma_w$ 提升至 **1.5** (原1.4)。")
        c1, c2, c3, c4 = st.columns(4)
        sg = c1.number_input("重力效应 $S_{GE}$", value=100.0)
        seh = c2.number_input("水平地震 $S_{Ehk}$", value=50.0)
        sev = c3.number_input("竖向地震 $S_{Evk}$", value=10.0)
        sw = c4.number_input("风载效应 $S_{wk}$", value=20.0)
        opts = ["仅水平地震作用", "仅竖向地震作用", "双向地震 (水平为主)", "双向地震 (竖向为主)"]
        ctype = st.radio("组合工况选择", opts, horizontal=True)
        c_a, c_b = st.columns(2)
        is_fav = c_a.checkbox("重力荷载对构件承载力有利 (启用后 γG=1.0)")
        has_w = c_b.checkbox("风荷载起控制作用 (启用后 ψw=0.2)")
    
    s, gg, gh, gv = SeismicMath.calc_combo_2024(sg, seh, sev, sw, opts.index(ctype), is_fav, has_w)
    st.latex(r"S = \gamma_G S_{GE} + \gamma_{Eh} S_{Ehk} + \gamma_{Ev} S_{Evk} + \psi_w \gamma_w S_{wk}")
    st.latex(rf"S = {gg} \times {sg} + {gh} \times {seh} + {gv} \times {sev} + {0.2 if has_w else 0.0} \times 1.5 \times {sw} = {s:.2f}")
    st.success(f"### 🎯 2024版组合设计值 $S = {s:.2f}$")

def render_gamma_re() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.4.2 承载力抗震调整系数 γ_RE 查表</h2>', unsafe_allow_html=True)
    with ui_card():
        data = {"材料": ["钢", "钢", "砌体", "砌体", "混凝土", "混凝土", "混凝土"], "构件与受力状态": ["柱梁支撑 (强度)", "柱/支撑 (稳定)", "两端构造柱墙 (受剪)", "其他抗震墙 (受剪)", "梁 (受弯)", "柱 (偏压)", "各类构件 (受剪)"], "γ_RE": [0.75, 0.80, 0.90, 1.0, 0.75, 0.75, 0.85]}
        st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)

def render_drift() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.5.1 & 5.5.5 层间位移角验算</h2>', unsafe_allow_html=True)
    with ui_card():
        stype = st.selectbox("选择结构类型", ["框架", "框架-抗震墙/核心筒", "抗震墙/筒体", "框支层", "钢结构"])
        c1, c2, c3 = st.columns(3)
        h = c1.number_input("楼层高度 $h$ (mm)", value=3000.0, min_value=1.0)
        due = c2.number_input("弹性位移 $\Delta u_e$ (mm)", value=4.5)
        dup = c3.number_input("弹塑性位移 $\Delta u_p$ (mm)", value=40.0)
    te, limit_e, tp, limit_p = SeismicMath.calc_drift(stype, h, due, dup)
    ca, cb = st.columns(2)
    with ca:
        st.markdown("**🔸 多遇地震 (弹性)**")
        if te <= limit_e: 
            st.success("✅ 满足规范要求")
        else: 
            st.error("❌ 超过规范限值")
    with cb:
        st.markdown("**🔸 罕遇地震 (弹塑性)**")
        if tp <= limit_p: 
            st.success("✅ 满足规范要求")
        else: 
            st.error("❌ 超过规范限值")

def render_capacity() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">6.2 节 框架能力设计</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        ftype = c1.radio("框架类型", ["框架结构", "其他结构中的框架"], horizontal=True)
        grade = c2.radio("框架抗震等级", [1, 2, 3, 4], horizontal=True)
        ca, cb, cc, cd = st.columns(4)
        mbl = ca.number_input("梁左端弯矩 $M_b^l$", value=150.0)
        mbr = cb.number_input("梁右端弯矩 $M_b^r$", value=180.0)
        ln = cc.number_input("梁净跨 $l_n$ (m)", value=6.0, min_value=0.1)
        vgb = cd.number_input("恒载剪力 $V_{Gb}$", value=50.0)
    mc_sum, v_design = SeismicMath.calc_capacity(grade, ftype, mbl, mbr, ln, vgb)
    st.success(f"节点柱端弯矩设计值之和需满足 $\sum M_c \ge {mc_sum:.1f}$ kN·m")
    st.success(f"梁端截面组合剪力设计值应调整为 $V = {v_design:.1f}$ kN")

def render_shear_limit() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">6.2.9 截面抗震受剪(剪压比)限值</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2, c3 = st.columns(3)
        fc = c1.number_input("混凝土轴压强度 $f_c$ (MPa)", value=16.7)
        b = c2.number_input("截面宽度 $b$ (mm)", value=400)
        h0 = c3.number_input("有效高度 $h_0$ (mm)", value=550)
        lam = st.number_input("剪跨比 $\\lambda$", value=3.0)
        is_short = st.checkbox("是否为跨高比不大于 2.5 的连梁 / 落地抗震墙加强部位")
        
    if fc < 11.9:
        st.error("❌ 违反 GB55002-2021 通规强条：抗震构件最低混凝土强度不得低于 C25 (fc=11.9 MPa)！")
        
    v_max = SeismicMath.calc_shear_limit(fc, b, h0, lam, is_short)
    st.latex(r"V \le \frac{1}{\gamma_{RE}} (0.15 \text{ 或是 } 0.20) f_c b h_0")
    st.success(f"### 🎯 截面受剪承载力上限 $V_{{max}} = {v_max:.1f} \\text{{ kN}}$")

def render_col_details() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">6.3.6 & 6.3.9 柱轴压比与体积配箍率</h2>', unsafe_allow_html=True)
    with ui_card():
        stype = st.selectbox("结构类型", ["框架结构", "框剪/筒体", "部分框支"])
        lvl = st.radio("抗震等级", [1, 2, 3, 4], horizontal=True)
        ca, cb, cc = st.columns(3)
        short = ca.checkbox("剪跨比 $\le 2$")
        hoop = cb.checkbox("采用井字/螺旋箍")
        core = cc.checkbox("附加芯柱")
        d1, d2, d3 = st.columns(3)
        lv = d1.number_input("配箍特征值 $\lambda_v$", value=0.15)
        fc = d2.number_input("混凝土强度 $f_c$ (MPa)", value=16.7)
        fyv = d3.number_input("箍筋强度 $f_{yv}$ (MPa)", value=360.0)
        
    if fc < 11.9:
        st.error("❌ 违反 GB55002-2021 通规强条：抗震柱最低混凝土强度不得低于 C25 (fc=11.9 MPa)！")
        
    lim, rho_v = SeismicMath.calc_col_limits(stype, lvl, short, hoop, core, lv, fc, fyv)
    if lim == 0.0: 
        st.error("❌ 规范无此要求。")
    else: 
        ca, cb = st.columns(2)
        ca.success(f"**柱轴压比上限** $[\mu_N] = {lim:.2f}$")
        cb.success(f"**最小体积配箍率** $\\rho_v \ge {rho_v:.2f}\\%$")

def render_wall_edge() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">6.4.5 抗震墙约束边缘构件尺寸</h2>', unsafe_allow_html=True)
    with ui_card():
        hw = st.number_input("墙肢长度 $h_w$ (mm)", value=2000.0)
        ax = st.number_input("墙肢轴压比", value=0.35, step=0.05)
        level_type = st.selectbox("等级与烈度", ["一级(9度)", "一级(7、8度)", "二、三级"])
    st.success(f"### 🎯 约束边缘构件长度 $l_c = {SeismicMath.calc_wall_edge(hw, ax, level_type):.1f}$ mm")

def render_masonry() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">7.2.6 & 7.2.7 砌体受剪验算</h2>', unsafe_allow_html=True)
    with ui_card():
        mtype = st.radio("砌体类别", ["普通砖/多孔砖", "小砌块"], horizontal=True)
        fv = st.number_input("抗剪强度 $f_v$ (MPa)", value=0.15)
        sig = st.number_input("平均压应力 $\sigma_0$ (MPa)", value=0.45)
        area = st.number_input("墙体截面积 $A$ (mm²)", value=600000.0)
        gamma_re = st.selectbox("调整系数 $\gamma_{RE}$", [1.0, 0.9, 0.75])
    zn, fve, vcap = SeismicMath.calc_masonry_v(fv, sig, mtype == "普通砖/多孔砖", area, float(gamma_re))
    st.success(f"砌体抗震抗剪强度 **$f_{{vE}} = {fve:.3f}$ MPa** \n\n 墙段受剪承载力上限 **$V \le {vcap:.1f}$ kN**")
