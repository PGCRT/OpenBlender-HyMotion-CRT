"""
OpenBlender-HyMotion-CRT

Text-to-Motion generation with FBX/GLB export support.

Based on ComfyUI-HY-Motion1 (jtydhr88 / PozzettiAndrea repack).
"""

import os
import sys

# Set web directory for JavaScript extensions (Motion viewer widget)
WEB_DIRECTORY = "./web"

# Track initialization status
INIT_SUCCESS = False

# Hot-reload (e.g. ComfyUI-HotReloadHack) re-imports this module repeatedly;
# os.environ markers survive reloads so logs/routes happen only once.
_LOGGED = bool(os.environ.get("OB_HYMOTION_LOGGED"))


def _log(msg):
    if not _LOGGED:
        print(msg)


if not os.environ.get('PYTEST_CURRENT_TEST'):
    _log("[ComfyUI-HY-Motion1] Initializing custom node...")

    try:
        from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
        from .bridge_nodes import HYMotionNPZToSMPLParams, HYMotionSMPLToData, HYMotionRetargetFBX as BridgeRetargetFBX
        NODE_CLASS_MAPPINGS.update({
            "HYMotionNPZToSMPLParams": HYMotionNPZToSMPLParams,
            "HYMotionSMPLToData": HYMotionSMPLToData,
            "HYMotionRetargetFBX": BridgeRetargetFBX,
        })
        NODE_DISPLAY_NAME_MAPPINGS.update({
            "HYMotionNPZToSMPLParams": "HY-Motion NPZ to SMPL Params",
            "HYMotionSMPLToData": "HY-Motion SMPL to Data",
            "HYMotionRetargetFBX": "HY-Motion Retarget to FBX",
        })
        _log("[ComfyUI-HY-Motion1] [OK] Node classes imported successfully")
        INIT_SUCCESS = True
    except Exception as e:
        import traceback
        print(f"[ComfyUI-HY-Motion1] [WARNING] Failed to import node classes: {e}")
        print(f"[ComfyUI-HY-Motion1] Traceback:\n{traceback.format_exc()}")
        NODE_CLASS_MAPPINGS = {}
        NODE_DISPLAY_NAME_MAPPINGS = {}

    # Add static route for Three.js and model assets (only possible before the
    # aiohttp router is frozen; after first startup the routes already exist)
    if not os.environ.get("OB_HYMOTION_ROUTES"):
        try:
            from server import PromptServer
            from aiohttp import web

            static_path = os.path.join(os.path.dirname(__file__), "static")
            if os.path.exists(static_path):
                PromptServer.instance.app.add_routes([
                    web.static('/extensions/ComfyUI-HY-Motion1/static', static_path)
                ])
                os.environ["OB_HYMOTION_ROUTES"] = "1"
                print(f"[ComfyUI-HY-Motion1] [OK] Static routes added: {static_path}")
        except Exception as e:
            if not _LOGGED:
                print(f"[ComfyUI-HY-Motion1] Warning: Could not add static routes: {e}")

    if INIT_SUCCESS:
        _log("[ComfyUI-HY-Motion1] [OK] Loaded successfully!")
    else:
        print("[ComfyUI-HY-Motion1] [ERROR] Failed to load - check errors above")

    os.environ["OB_HYMOTION_LOGGED"] = "1"

else:
    print("[ComfyUI-HY-Motion1] Running in pytest mode - skipping initialization")
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
__version__ = "0.3.1"
