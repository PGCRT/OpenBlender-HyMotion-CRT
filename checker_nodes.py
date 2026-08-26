import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip().lower())


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)


def _cpu_id() -> str:
    if os.name == "nt":
        code, out, _ = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ]
        )
        if code == 0 and out:
            line = out.splitlines()[0].strip()
            if line:
                return line
        code, out, _ = _run(["wmic", "cpu", "get", "Name"])
        if code == 0 and out:
            lines = [ln.strip() for ln in out.splitlines() if ln.strip() and "Name" not in ln]
            if lines:
                return lines[0]
        code, out, _ = _run(["wmic", "cpu", "get", "ProcessorId"])
        if code == 0 and out:
            lines = [ln.strip() for ln in out.splitlines() if ln.strip() and "ProcessorId" not in ln]
            if lines:
                return lines[0]
    return platform.processor() or "unknown"


def _ram_available_gb() -> str:
    try:
        import psutil
        gb = psutil.virtual_memory().available / (1024 ** 3)
        return f"{gb:.2f} GB"
    except Exception:
        return "unknown"


def _nvidia_smi_summary() -> str:
    cmd = [
        "nvidia-smi",
        "--query-gpu=name,compute_cap,memory.total,memory.free,driver_version",
        "--format=csv,noheader",
    ]
    code, out, err = _run(cmd)
    if code != 0:
        return f"unavailable ({err or 'nvidia-smi failed'})"
    rows = [r.strip() for r in out.splitlines() if r.strip()]
    if not rows:
        return "unavailable (no GPU rows)"
    return " | ".join(rows)


def _comfyui_version() -> str:
    try:
        import comfyui_version
        v = getattr(comfyui_version, "__version__", None)
        rev = getattr(comfyui_version, "__git_hash__", None)
        if v and rev:
            return f"{v} ({rev})"
        return str(v or "unknown")
    except Exception:
        return "unknown"


def _comfyui_location() -> str:
    try:
        import folder_paths
        return str(Path(folder_paths.base_path).resolve())
    except Exception:
        return str(Path(__file__).resolve().parents[3])


def _embedded_runtime() -> dict:
    result = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "pytorch": "missing",
        "cuda": "missing",
    }
    try:
        import torch
        result["pytorch"] = getattr(torch, "__version__", "unknown")
        result["cuda"] = getattr(getattr(torch, "version", object()), "cuda", None) or "none"
    except Exception:
        pass
    return result


def _python_json(python_exe: str, code: str) -> dict:
    rc, out, err = _run([python_exe, "-c", code])
    if rc != 0:
        return {"ok": False, "error": err or out or f"exit code {rc}"}
    try:
        return {"ok": True, "data": json.loads(out)}
    except Exception:
        return {"ok": False, "error": f"invalid json output: {out}"}


def _extract_embedded_requirements(custom_nodes_dir: Path) -> list[str]:
    names: list[str] = ["tomli", "tomli-w"]
    for req_file in sorted(custom_nodes_dir.glob("*/requirements.txt")):
        for raw in req_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("--"):
                continue
            name = re.split(r"[<>=!~ ;@\\[]", line, maxsplit=1)[0].strip()
            if name:
                names.append(name)
    seen = set()
    out = []
    for n in names:
        c = _canonical(n)
        if c and c not in seen:
            seen.add(c)
            out.append(n)
    return out


def _installed_distributions(python_exe: str | None) -> set[str]:
    if python_exe is None:
        try:
            import importlib.metadata as md
            return {_canonical(d.metadata.get("Name", "")) for d in md.distributions()}
        except Exception:
            return set()
    code = (
        "import json,re,importlib.metadata as m;"
        "c=lambda s: re.sub(r'[-_.]+','-',(s or '').strip().lower());"
        "print(json.dumps(sorted({c(d.metadata.get('Name','')) for d in m.distributions() if d.metadata.get('Name')})))"
    )
    info = _python_json(python_exe, code)
    if not info.get("ok"):
        return set()
    return set(info["data"])


class OpenBlenderChecker:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "include_package_lists": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    FUNCTION = "run"
    CATEGORY = "OpenBlender/Checker"

    def run(self, include_package_lists=True):
        custom_nodes_dir = Path(__file__).resolve().parents[1]
        embedded_python = sys.executable
        comfy_location = _comfyui_location()
        embedded_runtime = _embedded_runtime()

        embedded_expected = sorted({_canonical(x): x for x in _extract_embedded_requirements(custom_nodes_dir)}.values(), key=str.lower)
        embedded_installed = _installed_distributions(None)
        embedded_missing = [n for n in embedded_expected if _canonical(n) not in embedded_installed]

        lines = [
            "OpenBlender Checker",
            "",
            f"- OS: {platform.platform()}",
            f"- CPU ID: {_cpu_id()}",
            f"- System RAM available: {_ram_available_gb()}",
            f"- NVIDIA SMI: {_nvidia_smi_summary()}",
            f"- ComfyUI location: {comfy_location}",
            f"- ComfyUI version: {_comfyui_version()}",
            f"- ComfyUI embedded python version: {embedded_runtime['python']}",
            f"- ComfyUI embedded pytorch version: {embedded_runtime['pytorch']}",
            f"- ComfyUI embedded cuda version: {embedded_runtime['cuda']}",
            "",
            f"- Missing ComfyUI embedded dependencies: {', '.join(embedded_missing) if embedded_missing else 'none'}",
            f"- Embedded checked package count: {len(embedded_expected)} (from custom_nodes/*/requirements.txt)",
            "- Isolated environments: removed in OpenBlender v0.38; standalone CRT packs run in the main environment",
            "",
            f"- Embedded python path: {embedded_python}",
        ]
        if include_package_lists:
            lines.extend(
                [
                    "",
                    "Embedded checked packages:",
                    ", ".join(embedded_expected) if embedded_expected else "none",
                ]
            )

        report = "\n".join(lines)
        print("[OpenBlender Checker]\n" + report)
        return (report,)


NODE_CLASS_MAPPINGS = {
    "OpenBlenderChecker": OpenBlenderChecker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OpenBlenderChecker": "Checker",
}
