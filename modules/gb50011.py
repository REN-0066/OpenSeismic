import streamlit as st
import numpy as np
import pandas as pd
import math
import plotly.graph_objects as go
from typing import Tuple
from ui.components import ui_back_button, ui_card, ui_button_grid, nav_to, ui_file_download_card

# ==========================================
# 核心数学计算引擎 (Pure Math Model)
# ==========================================
class SeismicMath:
    @staticmethod
    def calc_vse(d_cover: float, df: pd.DataFrame) -> Tuple[bool, float, float, float, str]:
        d0 = min(d_cover, 20.0)
        t = 0.0
        current = 0.0
        for _, row in df.iterrows():
            try:
                di = float(row.get('层厚(m)', 0))
                vsi = float(row.get('波速(m/s)', 0))
            except (ValueError, TypeError, KeyError):
                continue
            if pd.isna(di) or pd.isna(vsi) or di <= 0 or vsi <= 0: continue
            if current + di <= d0:
                t += di / vsi
                current += di
            else:
                t += (d0 - current) / vsi
                current = d0
                break
        vse = d0 / t if t > 0 else 0.0
        
        if vse > 800: site = "I0 类"
        elif 500 < vse <= 800: site = "I1 类"
        elif 250 < vse <= 500: site = "I1 类" if d_cover < 5 else "II 类"
        elif 150 < vse <= 250: site = "I1 类" if d_cover < 3 else ("II 类" if d_cover <= 50 else "III 类")
        else: site = "I1 类" if d_cover < 3 else ("II 类" if d_cover <= 15 else ("III 类" if d_cover <= 80 else "IV 类"))
        return (current >= d0 - 1e-4), d0, t, vse, site

    @staticmethod
    def calc_fae_pressure(zeta_a: float, fa: float, n: float, m: float, a: float, b: float) -> Tuple[float, float, float]:
        fae = zeta_a * fa
        area = a * b
        w = (b * a ** 2) / 6 if a > 0 else 1.0 
        p_avg = n / area if area > 0 else 0
        p_max = p_avg + m / w if w > 0 else p_avg
        return fae, p_avg, p_max

    @staticmethod
    def calc_liq_pre(du: float, dw: float, d0: float, db: float) -> Tuple[bool, str]:
        db_calc = max(db, 2.0)
        c1 = du > d0 + db_calc - 2.0
        c2 = dw > d0 + db_calc - 3.0
        c3 = du + dw > 1.5 * d0 + 2 * db_calc - 4.5
        ok = c1 or c2 or c3
        msg = "满足" if ok else "不满足"
        return ok, f"条件1: {c1} | 条件2: {c2} | 条件3: {c3} -> 综合判别：{msg}不液化条件"

    @staticmethod
    def calc_liq(acc: str, grp: str, dw: float, df_spt: pd.DataFrame) -> Tuple[float, str]:
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
            if pd.isna(ds) or ds <= 0 or di <= 0: continue
            rhoc_calc = 3.0 if is_sand else max(3.0, rhoc)
            ncr = max(0.0, n0 * beta * (math.log(0.6 * ds + 1.5) - 0.1 * dw) * math.sqrt(3 / rhoc_calc))
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
        gamma = 0.9 + (0.05 - zeta) / (0.3 + 6 * zeta) 
        eta2 = max(0.55, 1.0 + (0.05 - zeta) / (0.08 + 1.6 * zeta))
        eta1 = max(0.0, 0.02 + (0.05 - zeta) / (4 + 32 * zeta))
        return gamma, eta1, eta2

    @staticmethod
    def calc_base_shear(alpha1: float, tg: float, t1: float, df: pd.DataFrame) -> Tuple[float, float, float, pd.DataFrame]:
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
            if i == len(df_calc) - 1: fi += dfn  
            fi_list.append(round(fi, 2))
        df_calc['水平地震力Fi(kN)'] = fi_list
        df_calc['楼层剪力Vi(kN)'] = df_calc['水平地震力Fi(kN)'].iloc[::-1].cumsum().iloc[::-1]
        return fek, dfn, g_eq, df_calc

    # 🐛 FIX: 修复了分母代数展开式错误，修正为标准的同阻尼比耦联系数公式
    @staticmethod
    def calc_cqc_rho(lam_t: float, zeta: float) -> float:
        numerator = 8 * (zeta ** 2) * (1 + lam_t) * (lam_t ** 1.5)
        denominator = (1 - lam_t ** 2) ** 2 + 4 * (zeta ** 2) * lam_t * ((1 + lam_t) ** 2)
        return numerator / denominator if denominator != 0 else 1.0

    # 🚀 NEW: 双向地震扭转效应组合 (5.2.3)
    @staticmethod
    def calc_bidirectional_eq(sx: float, sy: float) -> Tuple[float, float, float]:
        s1 = math.sqrt(sx**2 + (0.85 * sy)**2)
        s2 = math.sqrt(sy**2 + (0.85 * sx)**2)
        return s1, s2, max(s1, s2)

    @staticmethod
    def calc_min_shear(intensity: str, t1: float, is_torsion: bool) -> float:
        vals = {'6度':(0.008, 0.006), '7度(0.10g)':(0.016, 0.012), '7度(0.15g)':(0.024, 0.018), 
                '8度(0.20g)':(0.032, 0.024), '8度(0.30g)':(0.048, 0.036), '9度':(0.064, 0.048)}
        v1, v2 = vals.get(intensity, (0.016, 0.012))
        v2 = v1 if is_torsion else v2
        if t1 <= 3.5: return v1
        if t1 >= 5.0: return v2
        return v1 - (v1 - v2) * (t1 - 3.5) / 1.5

    # 🐛 FIX: 增加了基本周期 T1 在 1.2Tg 到 5Tg 之间的限制条件，并区分高宽比
    @staticmethod
    def calc_ssi(t1: float, tg: float, aspect_ratio: float, acc: str, site: str) -> Tuple[float, float, str]:
        if site not in ["III类", "IV类"] or acc not in ["8度", "9度"]: 
            return 0.0, 1.0, "不符合场地和烈度要求，不予折减"
        if not (1.2 * tg <= t1 <= 5 * tg):
            return 0.0, 1.0, f"基本周期 T1 ({t1}s) 不在 1.2Tg~5Tg ({1.2*tg:.2f}s~{5*tg:.2f}s) 范围内，不予折减"
            
        dt_map = {"8度": {"III类": 0.08, "IV类": 0.20}, "9度": {"III类": 0.10, "IV类": 0.25}}
        dt = dt_map[acc][site]
        psi = (t1 / (t1 + dt)) ** 0.9 if dt > 0 else 1.0
        
        msg = "高宽比 < 3，各层均可按此系数折减" if aspect_ratio < 3.0 else "高宽比 ≥ 3，底部折减，顶部不折减，中间层线性插入"
        return dt, psi, msg

    # 🐛 FIX: 9度高层竖向地震总重力需乘 0.75 的折减系数 (5.3.1条)
    @staticmethod
    def calc_vertical_eq(amax: float, geq: float, is_cantilever: bool, intensity: str) -> Tuple[float, float]:
        if is_cantilever:
            coeff = 0.10 if intensity == '8度(0.20g)' else (0.15 if intensity == '8度(0.30g)' else 0.20)
            return coeff, coeff * geq
        else:
            av_max = 0.65 * amax
            return av_max, av_max * geq * 0.75 

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

    # 🚀 NEW: 柱和抗震墙的剪力放大计算 (6.2.5 & 6.2.8)
    @staticmethod
    def calc_col_wall_shear(ctype: str, grade: int, m_t: float, m_b: float, hn: float, vw: float, ftype: str) -> float:
        if ctype == "框架柱":
            eta_vc = {1: 1.5, 2: 1.3, 3: 1.2, 4: 1.1}.get(grade, 1.1) if ftype == "框架结构" else {1: 1.4, 2: 1.2, 3: 1.1, 4: 1.1}.get(grade, 1.1)
            return eta_vc * (m_t + m_b) / hn if hn > 0 else 0.0
        else:
            eta_vw = {1: 1.6, 2: 1.4, 3: 1.2, 4: 1.0}.get(grade, 1.0)
            return eta_vw * vw

    # 🐛 FIX: 移除了 C35 的错误保底；同时区分了梁的跨高比 2.5 和柱的剪跨比 2.0
    @staticmethod
    def calc_shear_limit(fc: float, b: float, h0: float, lam: float, is_short: bool, is_beam: bool = False) -> float:
        threshold = 2.5 if is_beam else 2.0
        coeff = 0.15 if is_short or lam <= threshold else 0.20
        return coeff * fc * b * h0 / 0.85 / 1000 

    # 🚀 NEW: 梁柱节点核芯区受剪承载力计算 (附录 D)
    @staticmethod
    def calc_joint_core_shear(grade: int, orthogonal: bool, is_9deg_1: bool, fc: float, bj: float, hj: float, ft: float, n: float, bc: float, fyv: float, asvj_s: float, hb0: float, as_prime: float) -> Tuple[float, float]:
        eta_j = 1.5 if orthogonal else 1.0
        coeff_limit = 0.25 if is_9deg_1 else 0.30
        limit = (coeff_limit * eta_j * fc * bj * hj) / 0.85 / 1000
        
        coeff_cap = 0.9 if is_9deg_1 else 1.1
        cap = (coeff_cap * eta_j * ft * bj * hj + 0.05 * eta_j * n * 1000 * bj / bc + fyv * asvj_s * (hb0 - as_prime)) / 0.85 / 1000
        return limit, cap

    @staticmethod
    def calc_col_limits(stype: str, lvl: int, short: bool, hoop: bool, core: bool, lv: float, fc: float, fyv: float) -> Tuple[float, float]:
        lims = {"框架结构": [0.65, 0.75, 0.85, 0.90], "框剪/筒体": [0.75, 0.85, 0.90, 0.95], "部分框支": [0.60, 0.70, 0.0, 0.0]}
        base = lims.get(stype, [0.0]*4)[lvl - 1]
        if base > 0:
            if short: base -= 0.05
            if hoop and core: base += 0.15
            elif hoop: base += 0.10
            elif core: base += 0.05
        # 仅在计算体积配箍率时，fc有C35保底规定
        rho_v = lv * max(fc, 16.7) / fyv * 100 if fyv > 0 else 0
        return min(base, 1.05), rho_v

    # 🐛 FIX: 修复了轴压比判定的方向，轴压比越大边缘构件必须越长！
    @staticmethod
    def calc_wall_edge(hw: float, ax_ratio: float, level_type: str) -> float:
        if level_type == "一级(9度)": 
            return 0.15 * hw if ax_ratio <= 0.1 else (0.20 * hw if ax_ratio <= 0.2 else 0.25 * hw)
        elif level_type == "一级(7、8度)": 
            return 0.10 * hw if ax_ratio <= 0.2 else (0.15 * hw if ax_ratio <= 0.3 else 0.20 * hw)
        else: # 二、三级
            return 0.10 * hw if ax_ratio <= 0.3 else (0.15 * hw if ax_ratio <= 0.4 else 0.20 * hw)

    @staticmethod
    def calc_masonry_v(fv: float, sig: float, is_brick: bool, area: float, gamma_re: float) -> Tuple[float, float, float]:
        rat = sig / fv if fv > 0 else 0
        xp = [0.0, 1.0, 3.0, 5.0, 7.0, 10.0, 12.0, 16.0]
        yp = [0.80, 0.99, 1.25, 1.47, 1.65, 1.90, 2.05, 2.05] if is_brick else [1.00, 1.23, 1.69, 2.15, 2.57, 3.02, 3.32, 3.92]
        zn = float(np.interp(rat, xp, yp))
        return zn, zn * fv, (zn * fv * area / gamma_re / 1000 if gamma_re > 0 else 0)

    # 🚀 NEW: 含构造柱/水平拉结筋的砌体受剪承载力计算 (7.2.7-3)
    @staticmethod
    def calc_masonry_col_shear(gamma_re: float, fve: float, a: float, ac: float, ft: float, asc: float, fyc: float, ash: float, fyh: float, col_count: int, col_spacing: float, hw_ratio: float) -> Tuple[float, float, float, float, float]:
        eta_c = 0.5 if col_count == 1 else 0.4
        zeta_c = 1.1 if col_spacing <= 3.0 else 1.0
        
        xp = [0.0, 0.4, 0.6, 0.8, 1.0, 1.2, 2.0]
        yp = [0.10, 0.10, 0.12, 0.14, 0.15, 0.12, 0.12]
        zeta_s = float(np.interp(hw_ratio, xp, yp))
        
        p1 = eta_c * fve * max(0.0, a - ac)
        p2 = zeta_c * ft * ac
        p3 = 0.08 * fyc * asc
        p4 = zeta_s * fyh * ash
        
        v_cap = (p1 + p2 + p3 + p4) / gamma_re / 1000
        return p1/1000, p2/1000, p3/1000, p4/1000, v_cap


# ==========================================
# 视图层 (View Controllers)
# ==========================================
def view_gb50011_menu() -> None:
    import config.registry as registry 
    
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
    ui_file_download_card("📖 建筑抗震设计标准 (2024版局部修订)", "data/建筑抗震设计标准 (2024).pdf", "包含最新局部修订条文，适用于 2024 年以后的最新项目抗震计算。")
    ui_file_download_card("📝 建筑抗震设计规范 (2016版完整正文)", "data/建筑抗震设计规范 (2016).pdf", "GB 50011-2010 (2016年修订) 完整正文与条文说明原件。")

def render_material() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">🔥 3.1.3 & 3.9.2 条 抗震材料强条 <span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.9rem;">2024版新规</span></h2>', unsafe_allow_html=True)
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
        edf = st.data_editor(st.session_state.df_vse, num_rows="dynamic", width="stretch")
        st.session_state.df_vse = edf
    ok, d0, t, vse, site = SeismicMath.calc_vse(d_cov, edf)
    st.markdown("### 🧮 数字化工程计算书")
    c1, c2 = st.columns(2)
    c1.latex(r"t = \sum_{i=1}^{n} \frac{d_i}{v_{si}} = " + f"{t:.4f} \\text{{ s}}")
    c2.latex(r"v_{se} = \frac{d_0}{t} = " + f"{vse:.2f} \\text{{ m/s}}")
    if not ok: st.warning(f"⚠️ 当前累计填写层厚不足限值(当前: {d0:.2f}m)，系统已按实际总土层计算，建议补全深部数据。")
    st.markdown(f"<div style='background-color: #f8fafc; border-left: 5px solid #3b82f6; padding: 15px; margin: 15px 0;'><span style='color: #1e3a8a; font-weight: 800; font-size: 1.2rem;'>🎯 建筑勘察场地类别判定： {site}</span> (等效剪切波速计为 {vse:.1f} m/s)</div>", unsafe_allow_html=True)
    fig = go.Figure()
    for idx, row in edf.iterrows():
        try:
            h, v = float(row.get('层厚(m)', 0)), float(row.get('波速(m/s)', 0))
            if h > 0 and v > 0: fig.add_trace(go.Bar(name=f"第{idx+1}层", x=[v], y=[h], orientation='h', marker=dict(color='#60a5fa', line=dict(color='#1e3a8a', width=1))))
        except: continue
    fig.add_vline(x=vse, line_dash="dashdot", line_color="#ef4444", line_width=2.5, annotation_text=f"等效波速 {vse:.1f}")
    fig.update_layout(barmode='stack', yaxis=dict(autorange="reversed", title="深度标高 (m)"), xaxis=dict(title="剪切波速 Vs (m/s)", side="top"), height=320, margin=dict(l=40, r=40, t=40, b=40), plot_bgcolor='white')
    st.plotly_chart(fig, width="stretch")

def render_fae() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.2.3 天然地基抗震承载力与底压</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        za = c1.selectbox("调整系数 ζa", [1.5, 1.3, 1.1, 1.0])
        fa = c2.number_input("深宽修正后地基承载力 $f_a$ (kPa)", value=200.0)
        c3, c4, c5, c6 = st.columns(4)
        n = c3.number_input("轴力 N (kN)", value=3000.0)
        m = c4.number_input("弯矩 M (kN·m)", value=600.0)
        a = c5.number_input("底长 a (m)", value=4.0)
        b = c6.number_input("底宽 b (m)", value=4.0)
    fae, p_avg, p_max = SeismicMath.calc_fae_pressure(za, fa, n, m, a, b)
    st.latex(rf"f_{{aE}} = \zeta_a f_a = {fae:.1f} \text{{ kPa}}")
    ca, cb = st.columns(2)
    ca.success(f"**平均压应力** $p = {p_avg:.1f}$ kPa ({'✅ 满足' if p_avg <= fae else '❌ 超限'})")
    cb.success(f"**边缘最大应力** $p_{{max}} = {p_max:.1f}$ kPa ({'✅ 满足' if p_max <= 1.2*fae else '❌ 超限'})")

def render_liq_pre() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.3.3 地基液化初步判别</h2>', unsafe_allow_html=True)
    with ui_card():
        st.info("提示：规范要求基础埋深 $d_b$ 小于 2m 时按 2m 计算，系统已内置该截断规则。")
        c1, c2, c3, c4 = st.columns(4)
        du = c1.number_input("上覆非液化土厚 $d_u$ (m)", value=4.0)
        dw = c2.number_input("地下水位 $d_w$ (m)", value=2.0)
        d0 = c3.number_input("液化特征深度 $d_0$ (m)", value=7.0)
        db = c4.number_input("基础埋深 $d_b$ (m)", value=1.5)
    ok, msg = SeismicMath.calc_liq_pre(du, dw, d0, db)
    if ok: st.success(f"✅ {msg}")
    else: st.error(f"❌ {msg}")

def render_liq() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.3.4 & 4.3.5 地基液化判别与指数精算</h2>', unsafe_allow_html=True)
    if 'df_spt' not in st.session_state: 
        st.session_state.df_spt = pd.DataFrame({"深度(m)": [3.0, 7.0], "实测Ni": [6.0, 12.0], "厚度(m)": [4.0, 5.0], "黏粒(%)": [12.0, 5.0], "纯砂不折减": [False, True]})
    with ui_card():
        c1, c2, c3 = st.columns(3)
        acc = c1.selectbox("设计基本加速度", ['0.10g', '0.15g', '0.20g', '0.30g', '0.40g'], index=1)
        grp = c2.selectbox("分组", ['第一组', '第二组', '第三组'])
        dw = c3.number_input("地下水位 $d_w$ (m)", value=2.0)
        edf = st.data_editor(st.session_state.df_spt, num_rows="dynamic", width="stretch")
        st.session_state.df_spt = edf
    ile, level = SeismicMath.calc_liq(acc, grp, dw, edf)
    if ile > 0: st.error(f"判定结论：综合地基液化指数 **$I_{{lE}} = {ile:.3f}$** ，属于 **【{level}】** 场地。")
    else: st.success(f"判定结论：综合地基液化指数 **$I_{{lE}} = {ile:.3f}$** ，该场地 **【安全不液化】**。")

def render_pile_spt() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">4.4.3 打入式挤土桩打桩后 SPT 估算</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        np_val = c1.number_input("打桩前标贯击数 $N_p$", value=10.0)
        rho = c2.number_input("挤土预制桩面积置换率 $ρ$", value=0.03, step=0.01)
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
    st.latex(r"\gamma = " + f"{g:.3f}" + r"\quad \eta_1 = " + f"{e1:.3f}" + r"\quad \eta_2 = " + f"{e2:.3f}")
    
    # BUG FIX 5: 彻底修复反应谱边界形状（直线上升段 0~0.1s 及水平段缺失的阻尼乘数修正）
    t_vals = np.arange(0, 7.0, 0.01)
    a_vals = []
    for t in t_vals:
        if t < 0.1: val = (0.45 + (e2 - 0.45) * (t / 0.1)) * amax 
        elif t < tg: val = e2 * amax 
        elif t < 5 * tg: val = ((tg / t) ** g) * e2 * amax
        else: val = max(0.0, (e2 * 0.2 ** g - e1 * (t - 5 * tg)) * amax)
        a_vals.append(val)
        
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t_vals, y=a_vals, mode='lines', name=r'影响系数 α', line=dict(color='#1e3a8a', width=3)))
    fig.add_vline(x=0.1, line_dash="dot", line_color="gray", annotation_text="0.1s", annotation_position="bottom right", annotation_yshift=20, annotation_xshift=5)
    fig.add_vline(x=tg, line_dash="dash", line_color="#ef4444", annotation_text=f"Tg={tg}s", annotation_position="top right", annotation_xshift=5)
    if 5*tg <= 6.0: fig.add_vline(x=5*tg, line_dash="dashdot", line_color="#10b981", annotation_text=f"5Tg={5*tg:.2f}s", annotation_position="bottom right", annotation_yshift=20, annotation_xshift=5)
    fig.update_layout(title="结构地震影响系数曲线", xaxis_title="自振周期 T (s)", yaxis_title="地震影响系数 α", plot_bgcolor='white', hovermode="x unified")
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
        edf = st.data_editor(st.session_state.df_fl, num_rows="dynamic", width="stretch")
        st.session_state.df_fl = edf
    fek, dfn, geq, df_res = SeismicMath.calc_base_shear(alpha1, tg, t1, edf)
    ca, cb, cc = st.columns(3)
    ca.metric("等效总重力 Geq", f"{geq:.1f} kN")
    cb.metric("底部总水平剪力 FEk", f"{fek:.1f} kN")
    cc.metric("顶层附加剪力 ΔFn", f"{dfn:.1f} kN")
    st.dataframe(df_res.style.format({"计算标高Hi(m)": "{:.2f}", "水平地震力Fi(kN)": "{:.2f}", "楼层剪力Vi(kN)": "{:.2f}"}).background_gradient(subset=['楼层剪力Vi(kN)'], cmap='YlGnBu'), width="stretch", hide_index=True)

def render_cqc() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.2.3 振型组合 CQC 耦联系数 ρ</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        lam_t = c1.number_input("振型周期比 $λ_T = T_k / T_j$", value=0.85, step=0.05)
        zeta = c2.number_input("阻尼比 $ζ$", value=0.05)
    st.latex(r"\rho_{jk} = \frac{8\zeta^2(1+\lambda_T)\lambda_T^{1.5}}{(1-\lambda_T^2)^2 + 4\zeta^2\lambda_T(1+\lambda_T)^2}")
    st.success(f"### 🎯 CQC 耦联系数 $\\rho_{{jk}} = {SeismicMath.calc_cqc_rho(lam_t, zeta):.4f}$")

def render_bidirectional_eq() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">✨ 5.2.3 条 3款 双向地震扭转效应组合</h2>', unsafe_allow_html=True)
    with ui_card():
        st.info("对于双向水平地震作用下的扭转耦联效应，规范要求取完全组合后的较大值进行设计。")
        c1, c2 = st.columns(2)
        sx = c1.number_input("X向单向地震效应 $S_x$", value=1000.0)
        sy = c2.number_input("Y向单向地震效应 $S_y$", value=400.0)
    s1, s2, s_max = SeismicMath.calc_bidirectional_eq(sx, sy)
    st.latex(r"S_{Ek} = \max \left( \sqrt{S_x^2 + (0.85 S_y)^2}, \sqrt{S_y^2 + (0.85 S_x)^2} \right)")
    c3, c4 = st.columns(2)
    c3.success(f"X向为主组合效应: **{s1:.2f}**")
    c4.success(f"Y向为主组合效应: **{s2:.2f}**")
    st.info(f"### 🎯 最终包络设计值 $S_{{Ek}} = {s_max:.2f}$")

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
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">✨ 5.2.7 条 地基与结构动力相互作用折减系数 ψ</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2, c3 = st.columns(3)
        t1 = c1.number_input("基本周期 $T_1$ (s)", value=2.0)
        tg = c2.number_input("特征周期 $T_g$ (s)", value=0.45)
        ar = c3.number_input("房屋高宽比 H/B", value=2.5)
        ca, cb = st.columns(2)
        acc = ca.selectbox("设防烈度", ["8度", "9度"])
        site = cb.selectbox("场地类别", ["II类及以下", "III类", "IV类"], index=1)
        
    dt, psi, msg = SeismicMath.calc_ssi(t1, tg, ar, acc, site)
    st.latex(r"\psi = \left( \frac{T_1}{T_1 + \Delta T} \right)^{0.9}")
    if psi == 1.0: 
        st.warning(f"🚨 判别依据：{msg}。\n\n**不满足折减条件，折减系数 $\psi = 1.0$**")
    else: 
        st.success(f"✅ 判别依据：{msg}")
        st.success(f"### 🎯 附加周期 $\Delta T = {dt}s$ ，底部地震剪力折减系数 $\psi = {psi:.3f}$")

def render_vertical_eq() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">5.3.1 & 5.3.3 竖向地震作用标准值</h2>', unsafe_allow_html=True)
    with ui_card():
        is_can = st.radio("构件类型", ["长悬臂构件 / 大跨度屋盖", "9度区高层建筑"], horizontal=True) == "长悬臂构件 / 大跨度屋盖"
        g_total = st.number_input("重力代表值 $G$ (kN)", value=1000.0)
        if is_can:
            intensity = st.selectbox("设防烈度", ["8度(0.20g)", "8度(0.30g)", "9度(0.40g)"])
            av, fevk = SeismicMath.calc_vertical_eq(0, g_total, True, intensity)
            st.success(f"### 🎯 竖向地震作用标准值 $F_{{Evk}} = {fevk:.1f}$ kN")
        else:
            alpha_max = st.number_input("水平地震影响系数最大值 $α_{max}$", value=0.32)
            av, fevk = SeismicMath.calc_vertical_eq(alpha_max, g_total, False, "")
            st.info("💡 提示：按规范 5.3.1 条，9度区高层建筑总竖向地震算式中，**等效总重力只取总重力的 75%**。")
            st.success(f"### 🎯 结构总竖向地震作用 (已计入折减) $F_{{Evk}} = {fevk:.1f}$ kN")

def render_combo() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">🔥 5.4.1 地震组合 <span style="background-color:#ef4444; color:white; padding:4px 8px; border-radius:4px; font-size:0.5em; vertical-align:middle;">2024版新规强条</span></h2>', unsafe_allow_html=True)
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
        h = c1.number_input("楼层高度 $h$ (mm)", value=3000.0)
        due = c2.number_input("弹性位移 $\Delta u_e$ (mm)", value=4.5)
        dup = c3.number_input("弹塑性位移 $\Delta u_p$ (mm)", value=40.0)
    te, limit_e, tp, limit_p = SeismicMath.calc_drift(stype, h, due, dup)
    ca, cb = st.columns(2)
    ca.markdown(f"**🔸 弹性位移角** 1/{int(1/te if te>0 else 0)} ({'✅' if te <= limit_e else '❌'})")
    cb.markdown(f"**🔸 弹塑性位移角** 1/{int(1/tp if tp>0 else 0)} ({'✅' if tp <= limit_p else '❌'})")

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
        ln = cc.number_input("梁净跨 $l_n$ (m)", value=6.0)
        vgb = cd.number_input("恒载剪力 $V_{Gb}$", value=50.0)
    mc_sum, v_design = SeismicMath.calc_capacity(grade, ftype, mbl, mbr, ln, vgb)
    st.success(f"节点柱端弯矩设计值之和需满足 $\sum M_c \ge {mc_sum:.1f}$ kN·m")
    st.success(f"梁端截面组合剪力设计值应调整为 $V = {v_design:.1f}$ kN")

def render_col_wall_shear() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">✨ 6.2.5 & 6.2.8 条 柱与抗震墙底剪力放大设计</h2>', unsafe_allow_html=True)
    with ui_card():
        c1, c2 = st.columns(2)
        ctype = c1.radio("构件类别", ["框架柱", "抗震墙底部加强部位"], horizontal=True)
        grade = c2.radio("抗震等级", [1, 2, 3, 4], horizontal=True, key="col_wall_grade")
        
        if ctype == "框架柱":
            ftype = st.selectbox("结构类型", ["框架结构", "其他结构中的框架"])
            c3, c4, c5 = st.columns(3)
            m_t = c3.number_input("柱上端弯矩 $M_c^t$", value=200.0)
            m_b = c4.number_input("柱下端弯矩 $M_c^b$", value=220.0)
            hn = c5.number_input("柱净高 $H_n$ (m)", value=3.0, min_value=0.1)
            vw = 0.0
        else:
            ftype = "墙"
            vw = st.number_input("抗震墙截面组合剪力计算值 $V_w$ (kN)", value=1000.0)
            m_t = m_b = hn = 0.0
            
    v_adj = SeismicMath.calc_col_wall_shear(ctype, grade, m_t, m_b, hn, vw, ftype)
    
    if ctype == "框架柱":
        st.latex(r"V = \frac{\eta_{vc}(M_c^t + M_c^b)}{H_n}")
    else:
        st.latex(r"V = \eta_{vw} V_w")
    st.success(f"### 🎯 强剪弱弯放大后，剪力设计值 $V = {v_adj:.1f}$ kN")

def render_shear_limit() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">6.2.9 截面抗震受剪(剪压比)限值</h2>', unsafe_allow_html=True)
    with ui_card():
        c_type = st.radio("构件类型", ["框架柱 / 抗震墙", "框架梁 / 连梁"], horizontal=True)
        is_beam = (c_type == "框架梁 / 连梁")
        c1, c2, c3 = st.columns(3)
        fc = c1.number_input("混凝土轴压强度 $f_c$ (MPa)", value=16.7)
        b = c2.number_input("截面宽度 $b$ (mm)", value=400)
        h0 = c3.number_input("有效高度 $h_0$ (mm)", value=550)
        c4, c5 = st.columns(2)
        lam = c4.number_input("剪跨比或跨高比 $\\lambda$", value=3.0)
        is_short = c5.checkbox("是否为部分框支抗震墙的框支柱/加强部位墙体等特例")
        
    if fc < 11.9: st.error("❌ 违反 GB55002-2021 通规强条：抗震构件最低混凝土强度不得低于 C25 (fc=11.9 MPa)！")
        
    v_max = SeismicMath.calc_shear_limit(fc, b, h0, lam, is_short, is_beam)
    st.latex(r"V \le \frac{1}{\gamma_{RE}} (0.15 \text{ 或是 } 0.20) f_c b h_0")
    st.success(f"### 🎯 截面受剪承载力上限 $V_{{max}} = {v_max:.1f} \\text{{ kN}}$")

def render_node_core() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">✨ 附录 D 梁柱节点核芯区受剪验算</h2>', unsafe_allow_html=True)
    with ui_card():
        st.info("💡 框架抗震审查最容易超限、也是手算频率最高的核心公式。")
        c1, c2 = st.columns(2)
        orthogonal = c1.checkbox("正交梁约束 (四面有梁且梁宽不小于柱宽的1/2)")
        is_9deg_1 = c2.checkbox("是否为 9 度区一级框架")
        
        ca, cb, cc, cd = st.columns(4)
        fc = ca.number_input("混凝土 $f_c$ (MPa)", value=16.7)
        ft = cb.number_input("混凝土 $f_t$ (MPa)", value=1.57)
        bj = cc.number_input("节点宽度 $b_j$ (mm)", value=500.0)
        hj = cd.number_input("节点高度 $h_j$ (mm)", value=600.0)
        
        ce, cf, cg, ch = st.columns(4)
        bc = ce.number_input("柱宽 $b_c$ (mm)", value=600.0)
        n = cf.number_input("地震组合极小轴压 $N$ (kN)", value=3000.0)
        fyv = cg.number_input("箍筋 $f_{yv}$ (MPa)", value=360.0)
        asvj_s = ch.number_input("配箍 $A_{svj}/s$ (mm²/mm)", value=3.0)
        
        ci, cj = st.columns(2)
        hb0 = ci.number_input("梁有效高度 $h_{b0}$ (mm)", value=550.0)
        as_prime = cj.number_input("受压筋距边 $a_s'$ (mm)", value=50.0)

    limit, cap = SeismicMath.calc_joint_core_shear(0, orthogonal, is_9deg_1, fc, bj, hj, ft, n, bc, fyv, asvj_s, hb0, as_prime)
    
    st.latex(r"V_{j} \le \frac{1}{\gamma_{RE}} (0.3 \eta_j f_c b_j h_j)")
    st.error(f"### 🛑 截面抗剪上限 (防压溃) $V_{{j,max}} = {limit:.1f}$ kN")
    if is_9deg_1:
        st.latex(r"V_{j} \le \frac{1}{\gamma_{RE}} \left( 0.9 \eta_j f_t b_j h_j + f_{yv} \frac{A_{svj}}{s} (h_{b0} - a_s') \right)")
    else:
        st.latex(r"V_{j} \le \frac{1}{\gamma_{RE}} \left( 1.1 \eta_j f_t b_j h_j + 0.05 \eta_j N \frac{b_j}{b_c} + f_{yv} \frac{A_{svj}}{s} (h_{b0} - a_s') \right)")
    st.success(f"### 🎯 节点实际受剪承载力 $V_{{cap}} = {cap:.1f}$ kN")

def render_col_details() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">6.3.6 & 6.3.9 柱轴压比与体积配箍率</h2>', unsafe_allow_html=True)
    with ui_card():
        stype = st.selectbox("结构类型", ["框架结构", "框剪/筒体", "部分框支"])
        lvl = st.radio("抗震等级  ", [1, 2, 3, 4], horizontal=True)
        ca, cb, cc = st.columns(3)
        short = ca.checkbox("剪跨比 $\le 2$")
        hoop = cb.checkbox("采用井字/复合螺旋箍")
        core = cc.checkbox("附加芯柱")
        d1, d2, d3 = st.columns(3)
        lv = d1.number_input("配箍特征值 $\lambda_v$", value=0.15)
        fc = d2.number_input("混凝土强度 $f_c$ (MPa)", value=16.7)
        fyv = d3.number_input("箍筋强度 $f_{yv}$ (MPa)", value=360.0)
        
    lim, rho_v = SeismicMath.calc_col_limits(stype, lvl, short, hoop, core, lv, fc, fyv)
    if lim == 0.0: st.error("❌ 规范无此要求。")
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
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">7.2.6 & 7.2.7 砌体无筋墙段受剪验算 (公式7.2.7-1)</h2>', unsafe_allow_html=True)
    with ui_card():
        mtype = st.radio("砌体类别", ["普通砖/多孔砖", "小砌块"], horizontal=True)
        c1, c2, c3 = st.columns(3)
        fv = c1.number_input("抗剪强度 $f_v$ (MPa)", value=0.15)
        sig = c2.number_input("平均压应力 $\sigma_0$ (MPa)", value=0.45)
        area = c3.number_input("墙体截面积 $A$ (mm²)", value=600000.0)
        gamma_re = st.selectbox("调整系数 $\gamma_{RE}$", [1.0, 0.9, 0.75])
    zn, fve, vcap = SeismicMath.calc_masonry_v(fv, sig, mtype == "普通砖/多孔砖", area, float(gamma_re))
    st.success(f"砌体抗震抗剪强度 **$f_{{vE}} = {fve:.3f}$ MPa** \n\n 无筋墙段受剪承载力上限 **$V \le {vcap:.1f}$ kN**")

def render_masonry_col() -> None:
    ui_back_button('GB50011')
    st.markdown('<h2 style="color:#0f172a; font-weight:800;">✨ 7.2.7 条 3款 含构造柱砌体墙综合抗剪验算</h2>', unsafe_allow_html=True)
    with ui_card():
        st.info("当纯无筋砌体算不过时，本模块计入均匀设置于墙段中部的构造柱及其水平配筋对受剪承载力的综合提高作用。")
        c1, c2, c3 = st.columns(3)
        gamma_re = c1.selectbox("抗震调整系数 $\gamma_{RE}$ ", [0.9, 1.0])
        fve = c2.number_input("砌体抗震抗剪强度 $f_{vE}$ (MPa)", value=0.18)
        a = c3.number_input("墙体总截面积 $A$ (mm²)", value=900000.0)
        
        c4, c5, c6 = st.columns(3)
        ac = c4.number_input("中部构造柱总面积 $A_c$ (mm²)", value=57600.0)
        ft = c5.number_input("构造柱抗拉强度 $f_t$ (MPa)", value=1.43)
        asc = c6.number_input("构造柱纵筋总面积 $A_{sc}$ (mm²)", value=452.0)
        
        c7, c8, c9 = st.columns(3)
        fyc = c7.number_input("柱纵筋强度 $f_{yc}$ (MPa)", value=360.0)
        ash = c8.number_input("墙体水平拉结筋面积 $A_{sh}$ (mm²)", value=0.0)
        fyh = c9.number_input("水平拉结筋强度 $f_{yh}$ (MPa)", value=300.0)
        
        c10, c11, c12 = st.columns(3)
        col_count = c10.selectbox("中部构造柱数量", [1, 2, 3, 4])
        col_spacing = c11.number_input("构造柱间距 (m)", value=2.8)
        hw_ratio = c12.number_input("墙段高宽比", value=1.0)
        
    p1, p2, p3, p4, vcap = SeismicMath.calc_masonry_col_shear(float(gamma_re), fve, a, ac, ft, asc, fyc, ash, fyh, col_count, col_spacing, hw_ratio)
    
    st.latex(r"V \le \frac{1}{\gamma_{RE}} [\eta_c f_{vE} (A - A_c) + \zeta_c f_t A_c + 0.08 f_{yc} A_{sc} + \zeta_s f_{yh} A_{sh}]")
    
    st.markdown("#### 🧮 承载力组成拆解")
    ca, cb, cc, cd = st.columns(4)
    ca.metric(label="砌体部分", value=f"{p1:.1f} kN")
    cb.metric(label="构造柱砼", value=f"{p2:.1f} kN")
    cc.metric(label="构造柱钢筋", value=f"{p3:.1f} kN")
    cd.metric(label="墙体水平筋", value=f"{p4:.1f} kN")
    
    st.success(f"### 🎯 含构造柱墙段受剪承载力 $V \le {vcap:.1f}$ kN")
