"""Turn LaTeX math into WeChat-friendly HTML.

WeChat strips MathJax/KaTeX, so formulas become either:
- styled HTML text with <sub>/<sup> for simple inline expressions, or
- PNG images rendered by matplotlib mathtext (uploaded like any article image).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import escape
from pathlib import Path
import re

_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ",
    "tau": "τ", "upsilon": "υ", "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
_SYMBOLS = {
    "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆", "cup": "∪", "cap": "∩",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "neq": "≠", "ne": "≠", "approx": "≈",
    "sim": "∼", "times": "×", "cdot": "·", "pm": "±", "to": "→", "rightarrow": "→",
    "leftarrow": "←", "Rightarrow": "⇒", "mapsto": "↦", "infty": "∞", "forall": "∀",
    "exists": "∃", "emptyset": "∅", "mid": "|", "ldots": "…", "cdots": "⋯", "dots": "…",
    "propto": "∝", "partial": "∂", "nabla": "∇", "ell": "ℓ", "star": "⋆", "circ": "∘",
    "lbrace": "{", "rbrace": "}", "{": "{", "}": "}", "|": "‖", ",": " ", ";": " ", " ": " ",
    "quad": " ", "qquad": "  ", "langle": "⟨", "rangle": "⟩", "top": "⊤",
}
_FONT_MAPS = {
    "mathcal": {chr(ord("A") + i): c for i, c in enumerate("𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵")},
    "mathbb": {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "E": "𝔼", "P": "ℙ", "I": "𝕀"},
}
_TEXT_COMMANDS = {"text", "mathrm", "textrm", "operatorname", "mathit", "textit", "mathbf", "textbf", "boldsymbol", "mathsf", "texttt"}
_ACCENT_COMMANDS = {"hat": "\u0302", "tilde": "\u0303", "bar": "\u0304", "vec": "\u20d7", "dot": "\u0307"}
_NAMED_FUNCTIONS = {"log", "exp", "max", "min", "sum", "prod", "arg", "argmax", "argmin", "softmax", "sin", "cos", "tanh", "Pr", "KL", "mean", "std", "lim", "sup", "inf"}
# Anything structural beyond simple scripts is drawn as an image.
_COMPLEX_RE = re.compile(r"\\(frac|dfrac|tfrac|sqrt|sum_|prod_|int|begin|end|left|right|binom|overset|underset|underbrace|overbrace|matrix|cases|\\)")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class _Unsupported(Exception):
    pass


@dataclass(frozen=True)
class RenderedFormula:
    path: Path
    width: int
    height: int


def _read_group(expr: str, index: int) -> tuple[str, int]:
    """Read one TeX argument (braced group, command or single char) starting at index."""
    while index < len(expr) and expr[index] == " ":
        index += 1
    if index >= len(expr):
        raise _Unsupported("missing argument")
    if expr[index] == "{":
        depth = 0
        for end in range(index, len(expr)):
            if expr[end] == "{":
                depth += 1
            elif expr[end] == "}":
                depth -= 1
                if depth == 0:
                    return expr[index + 1 : end], end + 1
        raise _Unsupported("unbalanced braces")
    if expr[index] == "\\":
        match = re.match(r"\\([A-Za-z]+|.)", expr[index:])
        assert match
        return match.group(0), index + len(match.group(0))
    return expr[index], index + 1


def _convert(expr: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(expr):
        char = expr[index]
        if char == "\\":
            match = re.match(r"\\([A-Za-z]+|.)", expr[index:])
            if not match:
                raise _Unsupported(expr[index:])
            name = match.group(1)
            index += len(match.group(0))
            if name in _GREEK:
                out.append(_GREEK[name])
            elif name in _SYMBOLS:
                out.append(escape(_SYMBOLS[name]))
            elif name in _NAMED_FUNCTIONS:
                out.append(f'<span style="font-style:normal;">{name}</span>')
            elif name in _FONT_MAPS:
                arg, index = _read_group(expr, index)
                mapping = _FONT_MAPS[name]
                if not all(c in mapping for c in arg):
                    raise _Unsupported(name)
                out.append("".join(mapping[c] for c in arg))
            elif name in _TEXT_COMMANDS:
                arg, index = _read_group(expr, index)
                inner = _convert(arg)
                weight = "font-weight:700;" if name in {"mathbf", "textbf", "boldsymbol"} else ""
                out.append(f'<span style="font-style:normal;{weight}">{inner}</span>')
            elif name in _ACCENT_COMMANDS:
                arg, index = _read_group(expr, index)
                if len(arg) != 1:
                    raise _Unsupported(name)
                out.append(escape(arg) + _ACCENT_COMMANDS[name])
            else:
                raise _Unsupported(name)
        elif char in "_^":
            arg, index = _read_group(expr, index + 1)
            tag = "sub" if char == "_" else "sup"
            out.append(f'<{tag} style="font-size:75%;">{_convert(arg)}</{tag}>')
        elif char == "{":
            arg, index = _read_group(expr, index)
            out.append(_convert(arg))
        elif char == "}":
            raise _Unsupported("unbalanced braces")
        elif char == "&":
            raise _Unsupported("alignment")
        else:
            out.append(escape(char))
            index += 1
    return "".join(out)


def latex_to_inline_html(expr: str) -> str | None:
    """Convert a simple inline expression to HTML text; None when it needs an image."""
    expr = expr.strip()
    if re.fullmatch(r"[-+]?\d[\d.,]*\s*\\?%?", expr):
        return f'<span leaf="">{escape(expr.replace(chr(92), ""))}</span>'
    expr = expr.replace("\\%", "%")
    if not expr or _COMPLEX_RE.search(expr) or len(expr) > 80:
        return None
    try:
        body = _convert(expr)
    except _Unsupported:
        return None
    return (
        '<span style="font-family:\'Times New Roman\',Cambria,serif;font-style:italic;'
        f'font-size:15px;color:#111827;">{body}</span>'
    )


def _mathtext_source(expr: str) -> list[str]:
    """Rewrite LaTeX into mathtext-compatible lines (mathtext has no environments)."""
    cleaned = re.sub(r"\\(begin|end)\{[a-zA-Z*]+\}(\{[^}]*\})?", "", expr)
    cleaned = cleaned.replace("&", "")
    cleaned = re.sub(r"\\(dfrac|tfrac)", r"\\frac", cleaned)
    cleaned = re.sub(r"\\(nonumber|notag|label\{[^}]*\})", "", cleaned)
    cleaned = cleaned.replace(r"\lVert", r"\|").replace(r"\rVert", r"\|").replace(r"\coloneqq", ":=")
    lines = [line.strip() for line in re.split(r"\\\\", cleaned)]
    return [line for line in lines if line]


def render_formula_png(expr: str, output_dir: Path, *, display: bool, dpi: int = 220) -> RenderedFormula:
    """Render a formula to PNG with matplotlib mathtext; raises ValueError when unsupported."""
    if _CJK_RE.search(expr):
        raise ValueError("formula contains CJK text")
    import logging

    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    from PIL import Image

    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    lines = _mathtext_source(expr)
    if not lines:
        raise ValueError("empty formula")
    digest = hashlib.sha1(f"{display}:{expr}".encode("utf-8")).hexdigest()[:16]
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"formula_{digest}.png"
    size = 17 if display else 14
    if not target.exists():
        parts: list[Image.Image] = []
        for index, line in enumerate(lines):
            part_path = output_dir / f".formula_{digest}_{index}.png"
            mathtext.math_to_image(f"${line}$", str(part_path), prop=FontProperties(size=size), dpi=dpi, format="png")
            with Image.open(part_path) as img:
                parts.append(img.convert("RGBA"))
            part_path.unlink(missing_ok=True)
        gap = int(dpi * 0.06)
        width = max(part.width for part in parts)
        height = sum(part.height for part in parts) + gap * (len(parts) - 1)
        canvas = Image.new("RGB", (width + 8, height + 8), (255, 255, 255))
        y = 4
        for part in parts:
            x = 4 + (width - part.width) // 2
            canvas.paste(part, (x, y), part)
            y += part.height + gap
        canvas.save(target, format="PNG", optimize=True)
    with Image.open(target) as img:
        width, height = img.size
    # Display at roughly screen resolution: mathtext output is rendered at `dpi`.
    scale = 96 / dpi
    return RenderedFormula(path=target, width=max(1, round(width * scale)), height=max(1, round(height * scale)))


def formula_fallback_html(expr: str, *, display: bool) -> str:
    code = escape(expr.strip())
    if display:
        return (
            '<section style="margin:0 0 18px;padding:10px 14px;background:#F9FAFB;border-radius:8px;'
            'overflow-x:auto;font-family:Consolas,Monaco,monospace;font-size:13px;color:#374151;">'
            f'<span leaf="">{code}</span></section>'
        )
    return (
        '<span style="font-family:Consolas,Monaco,monospace;font-size:13px;color:#059669;">'
        f'{code}</span>'
    )
