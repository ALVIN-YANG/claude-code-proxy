import sys
import os
import threading
import uvicorn
import webview
import httpx
import logging
from typing import Dict, Any

# Ensure relative imports from project's absolute directory path work out-of-the-box
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import app, logger, get_config, save_config, test_connection, ConfigPayload, ConnectionTestPayload

PORT = int(os.environ.get("PROXY_PORT", "8082"))

def get_resource_path(relative_path):
    """Locate assets securely when compiled under PyInstaller (_MEIPASS) or running locally."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def run_backend():
    """Runs the FastAPI server silently in a background daemon thread."""
    try:
        # Binding only to localhost (127.0.0.1) for maximum user workstation safety
        uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")
    except Exception as e:
        logger.error(f"Uvicorn Background thread error: {e}")


class ApiBridge:
    """The secure Javascript-to-Python Native Bridge. Zero network ports used for UI config."""

    def get_config(self) -> Dict[str, Any]:
        """Provides the frontend UI with current live processes and environment configurations."""
        try:
            # We reuse the existing async FastAPI logic but run it synchronously for the JS bridge
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            config_data = loop.run_until_complete(get_config())
            loop.close()
            return config_data
        except Exception as e:
            logger.error(f"JS Bridge Failed to fetch configuration: {e}")
            return {"status": "error", "message": str(e)}

    def save_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Saves settings dynamically from form input straight to .env and system process environment."""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Map JS dictionary to FastAPI Pydantic payload
            cfg = ConfigPayload(
                gemini_key=payload.get("gemini_key", ""),
                anthropic_key=payload.get("anthropic_key", ""),
                preferred_provider=payload.get("preferred_provider", "openai"),
                openai_base_url=payload.get("openai_base_url", "https://generativelanguage.googleapis.com/v1beta/openai"),
                big_model=payload.get("big_model", "gemini-3.5-flash"),
                small_model=payload.get("small_model", "gemini-3.5-flash"),
                http_proxy=payload.get("http_proxy", ""),
                https_proxy=payload.get("https_proxy", "")
            )

            res = loop.run_until_complete(save_config(cfg))
            loop.close()
            return {"status": "success", "message": "Settings updated dynamically"}
        except Exception as e:
            logger.error(f"JS Bridge Failed to save config: {e}")
            return {"status": "error", "message": str(e)}

    def test_connection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Runs immediate connectivity tests to Google endpoints using customized proxy parameters."""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            test_payload = ConnectionTestPayload(
                gemini_key=payload.get("gemini_key", ""),
                anthropic_key=payload.get("anthropic_key", ""),
                http_proxy=payload.get("http_proxy", ""),
                https_proxy=payload.get("https_proxy", ""),
                openai_base_url=payload.get("openai_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
            )

            res = loop.run_until_complete(test_connection(test_payload))
            loop.close()
            return res
        except Exception as e:
            logger.error(f"JS Bridge Failed network connectivity test: {e}")
            return {
                "gemini": {"status": "failed", "message": str(e)},
                "proxy_status": "failed",
                "proxy_type": "error"
            }


def start_gui():
    """Builds and launches the native OS application window."""
    ui_index = get_resource_path("ui/index.html")

    if not os.path.exists(ui_index):
        logger.error(f"Critical Error: Frontend assets not found at: {ui_index}")
        # Build-time safeguard
        print(f"Error: UI HTML file does not exist at {ui_index}")
        sys.exit(1)

    # Initialize pywebview window
    # WKWebView (Mac) or WebView2 (Windows Edge/Chromium)
    window = webview.create_window(
        title="Claude Code Proxy 极简面板",
        url=ui_index,
        width=520,
        height=660,
        min_size=(460, 580),
        resizable=True,
        text_select=True,  # Permit logs and token selection copy-pasting
        js_api=ApiBridge()
    )

    def on_closed():
        """Lifecycle callback to gracefully and fully terminate background FastAPI thread upon exit."""
        logger.info("Native GUI window shut down by user. Terminating process environment...")
        os._exit(0)

    window.events.closed += on_closed

    # Spin up OS window and block main thread in native event loop
    webview.start(debug=False)


if __name__ == "__main__":
    logger.info("Initializing Claude Code Proxy Native Desktop Service...")

    # 1. Spawn FastAPI server in separate worker thread (daemon thread dies when app dies)
    server_thread = threading.Thread(target=run_backend, daemon=True)
    server_thread.start()

    # 2. Start the graphical native window on the main OS thread (blocking call)
    start_gui()
