from enum import Enum


class PriorWorkRole(str, Enum):
    """前作在当前论文创新中的角色分类。"""

    BASELINE = "Baseline"
    INSPIRATION = "Inspiration"
    GAP_IDENTIFICATION = "Gap Identification"
    FOUNDATION = "Foundation"
    EXTENSION = "Extension"
    RELATED_PROBLEM = "Related Problem"


class ContributionType(str, Enum):
    """summary.md frontmatter 中记录的四类贡献类型。"""

    PROBLEM_DEFINITION = "问题定义型"
    MECHANISM_EXPLANATION = "机制解释型"
    METHOD_IMPROVEMENT = "方法改进型"
    BENCHMARK = "评测基准型"


class PatternID(str, Enum):
    """Sci-Reasoning 15 种科学创新范式的稳定 ID。"""

    P01 = "P01"
    P02 = "P02"
    P03 = "P03"
    P04 = "P04"
    P05 = "P05"
    P06 = "P06"
    P07 = "P07"
    P08 = "P08"
    P09 = "P09"
    P10 = "P10"
    P11 = "P11"
    P12 = "P12"
    P13 = "P13"
    P14 = "P14"
    P15 = "P15"


class ConfidenceLevel(str, Enum):
    """LLM 对范式分类结果的置信度。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
