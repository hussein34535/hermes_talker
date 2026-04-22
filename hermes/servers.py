"""
═════════════════════════════════════════════════════════════════════════════
  servers.py - خوادم المراقبة (HTTP + Webhook)
═════════════════════════════════════════════════════════════════════════════
  يحتوي على:
    - MonitorHTTPHandler: معالج طلبات المراقبة HTTP
    - start_http_monitor: دالة بدء خادم المراقبة
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from hermes.config import log


class MonitorHTTPHandler(BaseHTTPRequestHandler):
    """معالج طلبات المراقبة HTTP - يعيد JSON ببيانات النظام"""
    engine_ref = None

    def do_GET(self):
        if self.engine_ref:
            data = {
                'state': self.engine_ref.state.state.name,
                'uptime': self.engine_ref.metrics.uptime,
                'metrics': self.engine_ref.metrics.summary(),
                'health': self.engine_ref.health_tracker.health_report(),
            }
            response = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            response = '{"error": "no engine"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def log_message(self, format, *args):
        """كتم سجل HTTP"""
        pass


def start_http_monitor(engine, port: int):
    """بدء خادم HTTP للمراقبة في خيط خلفي"""
    MonitorHTTPHandler.engine_ref = engine
    try:
        server = HTTPServer(('0.0.0.0', port), MonitorHTTPHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        log.info(f"🌐 خادم المراقبة: http://0.0.0.0:{port}")
    except Exception as e:
        log.warning(f"فشل خادم المراقبة: {e}")
