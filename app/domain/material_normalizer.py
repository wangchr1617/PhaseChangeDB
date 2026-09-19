"""PhaseChangeDB 材料名称归一化与变体条件解析领域模块。

核心职责：
1. 统一材料主名称：去除特殊符号与全角下标，统一标准大小写与元素顺序；
2. 建立化学别名映射字典（如 antimony telluride / 碲化锑 -> Sb2Te3）；
3. 结构化剥离掺杂前缀（如 Sc0.2Sb2Te3 -> 主材料 Sb2Te3 + 掺杂 Sc 0.2）；
4. 结构化剥离测试/工艺/样品后缀（如 Sb2Te3_d70d0962 -> 主材料 Sb2Te3 + 样品后缀）；
5. 提供严格量化的“低毒性”与“成本可控”科学判定逻辑。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 周期表有效元素集合
VALID_ELEMENTS: set[str] = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
    "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
}

# 剧毒/重金属管制元素黑名单
TOXIC_ELEMENTS: set[str] = {"Cd", "Pb", "Hg", "As", "Tl", "Be"}

# 贵金属/昂贵稀缺元素黑名单
EXPENSIVE_ELEMENTS: set[str] = {"Au", "Pt", "Pd", "Ru", "Rh", "Ir", "Sc"}

# Unicode 下标数字转换表
UNICODE_SUBSCRIPTS = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
})

def is_valid_chemical_alias(alias: str | None) -> bool:
    """判定是否为合法的化学同义词别名。

    严格过滤工艺后缀、样品编号、测试 ID、下划线标识等非真实别名字段。
    """
    if not alias or not alias.strip():
        return False
    a = alias.strip()
    if "_" in a:
        return False
    lower_a = a.lower()
    for bad in ("req", "cand", "test", "film", "bulk", "sample"):
        if bad in lower_a and len(a) > len(bad) + 2:
            return False
    return True


# 常见相变材料常用名称、中英文别名与缩写映射表
# 结构: alias_lowercase -> (canonical_formula, chemical_system, standard_name)
SYNONYM_MAP: dict[str, tuple[str, str, str]] = {
    # Sb2Te3
    "sb2te3": ("Sb2Te3", "Sb-Te", "碲化锑"),
    "antimony telluride": ("Sb2Te3", "Sb-Te", "碲化锑"),
    "antimony(iii) telluride": ("Sb2Te3", "Sb-Te", "碲化锑"),
    "diantimony tritelluride": ("Sb2Te3", "Sb-Te", "碲化锑"),
    "碲化锑": ("Sb2Te3", "Sb-Te", "碲化锑"),
    "三碲化二锑": ("Sb2Te3", "Sb-Te", "碲化锑"),

    # GeTe
    "gete": ("GeTe", "Ge-Te", "碲化锗"),
    "germanium telluride": ("GeTe", "Ge-Te", "碲化锗"),
    "germanium(ii) telluride": ("GeTe", "Ge-Te", "碲化锗"),
    "碲化锗": ("GeTe", "Ge-Te", "碲化锗"),
    "一碲化锗": ("GeTe", "Ge-Te", "碲化锗"),

    # GST 系列
    "ge2sb2te5": ("Ge2Sb2Te5", "Ge-Sb-Te", "GST-225"),
    "gst": ("Ge2Sb2Te5", "Ge-Sb-Te", "GST-225"),
    "gst225": ("Ge2Sb2Te5", "Ge-Sb-Te", "GST-225"),
    "gst-225": ("Ge2Sb2Te5", "Ge-Sb-Te", "GST-225"),
    "gst_225": ("Ge2Sb2Te5", "Ge-Sb-Te", "GST-225"),
    "germanium antimony telluride": ("Ge2Sb2Te5", "Ge-Sb-Te", "GST-225"),

    "ge1sb2te4": ("Ge1Sb2Te4", "Ge-Sb-Te", "GST-124"),
    "gesb2te4": ("Ge1Sb2Te4", "Ge-Sb-Te", "GST-124"),
    "gst124": ("Ge1Sb2Te4", "Ge-Sb-Te", "GST-124"),
    "gst-124": ("Ge1Sb2Te4", "Ge-Sb-Te", "GST-124"),

    "ge1sb4te7": ("Ge1Sb4Te7", "Ge-Sb-Te", "GST-147"),
    "gesb4te7": ("Ge1Sb4Te7", "Ge-Sb-Te", "GST-147"),
    "gst147": ("Ge1Sb4Te7", "Ge-Sb-Te", "GST-147"),
    "gst-147": ("Ge1Sb4Te7", "Ge-Sb-Te", "GST-147"),

    # AIST
    "aginsbte": ("AgInSbTe", "Ag-In-Sb-Te", "AIST"),
    "aist": ("AgInSbTe", "Ag-In-Sb-Te", "AIST"),

    # In2Se3
    "in2se3": ("In2Se3", "In-Se", "硒化铟"),
    "indium selenide": ("In2Se3", "In-Se", "硒化铟"),
    "硒化铟": ("In2Se3", "In-Se", "硒化铟"),

    # Sb2Se3
    "sb2se3": ("Sb2Se3", "Sb-Se", "硒化锑"),
    "antimony selenide": ("Sb2Se3", "Sb-Se", "硒化锑"),
    "硒化锑": ("Sb2Se3", "Sb-Se", "硒化锑"),

    # Bi2Te3
    "bi2te3": ("Bi2Te3", "Bi-Te", "碲化铋"),
    "bismuth telluride": ("Bi2Te3", "Bi-Te", "碲化铋"),
    "碲化铋": ("Bi2Te3", "Bi-Te", "碲化铋"),
}


@dataclass(frozen=True)
class NormalizedFormulaResult:
    canonical_formula: str
    reduced_formula: str
    chemical_system: str
    name: str | None
    doping_element: str | None = None
    doping_concentration: float | None = None
    sample_suffix: str | None = None
    raw_input: str = ""
    is_low_toxicity: bool = True
    is_cost_effective: bool = True
    is_valid: bool = True

    @property
    def aliases(self) -> list[str]:
        """生成与该化学式相关联的常见别名列表。"""
        res = [self.canonical_formula]
        if (
            self.raw_input != self.canonical_formula
            and not self.sample_suffix
            and "_" not in self.raw_input
        ):
            res.append(self.raw_input)
        if self.name and self.name not in res:
            res.append(self.name)
        low = self.canonical_formula.lower()
        if low not in res and low != self.canonical_formula:
            res.append(low)
        for k, v in SYNONYM_MAP.items():
            if v[0] == self.canonical_formula:
                if k not in res and "_" not in k:
                    res.append(k)
                if v[2] and v[2] not in res and "_" not in v[2]:
                    res.append(v[2])
        return [a for a in res if "_" not in a]


def extract_elements(formula: str) -> list[str]:
    """从化学式中提取出标准元素符号列表（保序且去重）。"""
    syms = re.findall(r"([A-Z][a-z]?)", formula)
    res: list[str] = []
    for s in syms:
        if s in VALID_ELEMENTS and s not in res:
            res.append(s)
    return res


def build_chemical_system(elements: list[str]) -> str:
    """根据元素列表构建标准相变材料化学体系表示（如 Ge-Sb-Te）。"""
    if not elements:
        return "Unknown"
    # 按照常见相变材料惯例优先排序，其余按字母排序
    order_priority = {"Ge": 1, "Sb": 2, "Te": 3, "Bi": 4, "Se": 5, "In": 6, "Ag": 7, "Sn": 8, "Si": 9}
    sorted_elems = sorted(elements, key=lambda x: (order_priority.get(x, 99), x))
    return "-".join(sorted_elems)


def is_low_toxicity(elements: list[str]) -> bool:
    """低毒性判定：不包含剧毒/管制重金属 (Cd, Pb, Hg, As, Tl, Be)。"""
    return not any(el in TOXIC_ELEMENTS for el in elements)


def is_cost_effective(elements: list[str]) -> bool:
    """成本可控判定：不依赖高价贵金属与稀贵元素 (Au, Pt, Pd, Ru, Rh, Ir, Sc 等)。"""
    return not any(el in EXPENSIVE_ELEMENTS for el in elements)


def normalize_formula(raw_input: str) -> NormalizedFormulaResult:
    """解析并归一化材料输入字符串。

    能够优雅处理：
    1. Unicode 下标：Sb₂Te₃ -> Sb2Te3；
    2. 大小写：sb2te3 -> Sb2Te3；
    3. 别名与中英文名称：antimony telluride -> Sb2Te3；
    4. 掺杂前缀分离：Sc0.2Sb2Te3 -> 主材料 Sb2Te3, 掺杂 Sc 0.2；
    5. 测试/工艺后缀分离：Sb2Te3_d70d0962 / Sb2Te3-film / GeTeReqId1 -> 主材料 Sb2Te3/GeTe。
    """
    if not raw_input or not raw_input.strip():
        raise ValueError("材料化学式不能为空")

    clean_str = raw_input.strip()
    # 替换 Unicode 下标字符
    clean_str = clean_str.translate(UNICODE_SUBSCRIPTS)

    # 去除常见的全角括号或首尾空白
    clean_str = re.sub(r"[\uff08\uff09]", "", clean_str).strip()

    # 1. 尝试直接查全名别名映射表
    lower_clean = clean_str.lower()
    if lower_clean in SYNONYM_MAP:
        c_form, c_sys, c_name = SYNONYM_MAP[lower_clean]
        elems = extract_elements(c_form)
        return NormalizedFormulaResult(
            canonical_formula=c_form,
            reduced_formula=c_form,
            chemical_system=c_sys,
            name=c_name,
            raw_input=raw_input,
            is_low_toxicity=is_low_toxicity(elems),
            is_cost_effective=is_cost_effective(elems),
        )

    # 2. 检查是否有后缀（如 Sb2Te3_d70d0962, Sb2Te3-demo, Sb2Te3_PErSiST, GeTeReqId1 等）
    suffix_match = re.match(
        r"^([A-Za-z0-9\.\-]+?)(?:[_#\-]+([a-zA-Z0-9_\-]+)|(?:(?<=[a-z0-9])(?=[A-Z])|[_#\-]+)(reqid.*|candreqid.*|test.*|sample.*|persist.*|dec\d+.*|film.*|bulk.*))$",
        clean_str,
        re.IGNORECASE,
    )
    extracted_suffix = None
    if suffix_match:
        base_cand = suffix_match.group(1).strip()
        extracted_suffix = (suffix_match.group(2) or suffix_match.group(3) or "").strip()
        if base_cand.lower() in SYNONYM_MAP:
            c_form, c_sys, c_name = SYNONYM_MAP[base_cand.lower()]
            elems = extract_elements(c_form)
            return NormalizedFormulaResult(
                canonical_formula=c_form,
                reduced_formula=c_form,
                chemical_system=c_sys,
                name=c_name,
                sample_suffix=extracted_suffix,
                raw_input=raw_input,
                is_low_toxicity=is_low_toxicity(elems),
                is_cost_effective=is_cost_effective(elems),
            )
        repaired = _repair_formula_case(base_cand)
        elems = extract_elements(repaired)
        if elems and len(repaired) >= 2:
            return NormalizedFormulaResult(
                canonical_formula=repaired,
                reduced_formula=repaired,
                chemical_system=build_chemical_system(elems),
                name=None,
                sample_suffix=extracted_suffix,
                raw_input=raw_input,
                is_low_toxicity=is_low_toxicity(elems),
                is_cost_effective=is_cost_effective(elems),
            )
        clean_str = base_cand

    # 3. 检查是否有掺杂前缀 (如 Sc0.2Sb2Te3, Ti0.1Ge2Sb2Te5, N0.05GeTe, Sc-Sb2Te3)
    dopant_elem = None
    dopant_conc = None
    dopant_match = re.match(r"^([A-Z][a-z]?)(0\.\d+|\d+\.?\d*|\d+)[-_]?([A-Za-z0-9]+)$", clean_str)
    if dopant_match:
        possible_dopant = dopant_match.group(1)
        possible_conc = float(dopant_match.group(2))
        possible_base = dopant_match.group(3)
        if possible_dopant in VALID_ELEMENTS and possible_base.lower() in SYNONYM_MAP:
            c_form, c_sys, c_name = SYNONYM_MAP[possible_base.lower()]
            elems = extract_elements(c_form)
            # 掺杂元素计入毒性与成本考量
            all_elems = list(set(elems + [possible_dopant]))
            return NormalizedFormulaResult(
                canonical_formula=c_form,
                reduced_formula=c_form,
                chemical_system=c_sys,
                name=c_name,
                doping_element=possible_dopant,
                doping_concentration=possible_conc,
                sample_suffix=extracted_suffix,
                raw_input=raw_input,
                is_low_toxicity=is_low_toxicity(all_elems),
                is_cost_effective=is_cost_effective(all_elems),
            )

    # 4. 规则化化学式大小写修复 (例如 sb2te3 -> Sb2Te3, gete -> GeTe)
    repaired_formula = _repair_formula_case(clean_str)
    elems = extract_elements(repaired_formula)

    if not elems:
        # 如果无法识别出任何化学元素，保持清洗后的字符串作为兜底
        return NormalizedFormulaResult(
            canonical_formula=clean_str,
            reduced_formula=clean_str,
            chemical_system="Unknown",
            name=clean_str,
            sample_suffix=extracted_suffix,
            raw_input=raw_input,
            is_low_toxicity=True,
            is_cost_effective=True,
        )

    chem_system = build_chemical_system(elems)

    return NormalizedFormulaResult(
        canonical_formula=repaired_formula,
        reduced_formula=repaired_formula,
        chemical_system=chem_system,
        name=None,
        doping_element=dopant_elem,
        doping_concentration=dopant_conc,
        sample_suffix=extracted_suffix,
        raw_input=raw_input,
        is_low_toxicity=is_low_toxicity(elems),
        is_cost_effective=is_cost_effective(elems),
    )


def _repair_formula_case(text_input: str) -> str:
    """尝试将全小写或不规则大小写的化学式修复为标准大小写。

    例如 'sb2te3' -> 'Sb2Te3', 'gete' -> 'GeTe'。
    """
    # 快速检查：如果已存在标准大写元素，直接返回
    existing_elems = re.findall(r"[A-Z][a-z]?", text_input)
    if existing_elems and all(e in VALID_ELEMENTS for e in existing_elems):
        return text_input

    # 贪心双字符匹配与单字符匹配
    res: list[str] = []
    i = 0
    s_lower = text_input.lower()
    n = len(s_lower)
    while i < n:
        if s_lower[i].isdigit() or s_lower[i] in ".-_":
            res.append(s_lower[i])
            i += 1
            continue

        # 尝试匹配双字母元素
        if i + 1 < n:
            two_char = s_lower[i : i + 2].capitalize()
            if two_char in VALID_ELEMENTS:
                res.append(two_char)
                i += 2
                continue

        # 尝试匹配单字母元素
        one_char = s_lower[i].upper()
        if one_char in VALID_ELEMENTS:
            res.append(one_char)
            i += 1
            continue

        # 未知字符原样追加
        res.append(text_input[i])
        i += 1

    return "".join(res)
