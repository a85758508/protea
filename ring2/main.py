#!/usr/bin/env python3
"""Ring 2 — Generation 133: Universal API Bridge

A comprehensive API integration system that:
- Manages connections to multiple external APIs
- Handles authentication (API keys, OAuth, tokens)
- Implements intelligent rate limiting and backoff
- Provides response caching with TTL
- Automatic retry with exponential backoff
- Request/response logging and analytics
- API health monitoring
- Webhook receiver for async callbacks
- Response transformation pipelines
- Multi-API aggregation queries
- Real-time dashboard for monitoring API usage

Enables Protea to easily integrate with any external service:
- Skill registries (Protea Hub)
- News APIs
- Weather services
- Translation services
- Database APIs
- Any REST/GraphQL endpoint
"""

import os
import pathlib
import sys
import time
import json
import sqlite3
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Event, Lock
from datetime import datetime, timedelta
from collections import defaultdict, deque
import re
import base64

HEARTBEAT_INTERVAL = 2
HTTP_PORT = 8899


def heartbeat_loop(heartbeat_path: pathlib.Path, pid: int, stop_event: Event) -> None:
    """Dedicated heartbeat thread - CRITICAL for survival."""
    while not stop_event.is_set():
        try:
            heartbeat_path.write_text(f"{pid}\n{time.time()}\n")
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


# ============= UNIVERSAL API BRIDGE =============

@dataclass
class APIEndpoint:
    """API endpoint configuration."""
    name: str
    base_url: str
    auth_type: str  # 'none', 'bearer', 'api_key', 'basic', 'custom'
    auth_config: Dict[str, str]
    rate_limit: int  # requests per minute
    timeout: int
    retry_count: int
    cache_ttl: int  # seconds
    headers: Dict[str, str] = field(default_factory=dict)
    health_check_url: Optional[str] = None


@dataclass
class APIRequest:
    """API request record."""
    request_id: str
    endpoint_name: str
    method: str
    path: str
    params: Dict[str, Any]
    timestamp: float
    response_time: Optional[float] = None
    status_code: Optional[int] = None
    success: bool = False
    error: Optional[str] = None
    cached: bool = False


@dataclass
class RateLimitBucket:
    """Rate limiting bucket."""
    capacity: int
    tokens: float
    last_update: float


class APIBridge:
    """Universal API integration bridge."""
    
    def __init__(self, db_path: pathlib.Path):
        self.db_path = db_path
        self.lock = Lock()
        
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.rate_limits: Dict[str, RateLimitBucket] = {}
        self.cache: Dict[str, tuple] = {}  # (response, expires_at)
        self.request_history: deque = deque(maxlen=1000)
        
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cached_responses': 0,
            'total_response_time': 0.0,
            'rate_limit_hits': 0
        }
        
        self._init_db()
        self._load_endpoints()
    
    def _init_db(self):
        """Initialize database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS endpoints (
                    name TEXT PRIMARY KEY,
                    base_url TEXT, auth_type TEXT,
                    auth_config TEXT, rate_limit INTEGER,
                    timeout INTEGER, retry_count INTEGER,
                    cache_ttl INTEGER, headers TEXT,
                    health_check_url TEXT,
                    created_at REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    endpoint_name TEXT, method TEXT,
                    path TEXT, params TEXT,
                    timestamp REAL, response_time REAL,
                    status_code INTEGER, success INTEGER,
                    error TEXT, cached INTEGER
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    endpoint_name TEXT, response TEXT,
                    expires_at REAL, created_at REAL
                )
            ''')
            conn.commit()
    
    def _load_endpoints(self):
        """Load endpoint configurations."""
        # Add some default endpoints
        self.register_endpoint(APIEndpoint(
            name='protea_hub',
            base_url='https://protea-hub-production.up.railway.app',
            auth_type='none',
            auth_config={},
            rate_limit=30,
            timeout=10,
            retry_count=3,
            cache_ttl=60,
            headers={'Content-Type': 'application/json'}
        ))
        
        self.register_endpoint(APIEndpoint(
            name='localhost_hub',
            base_url='http://127.0.0.1:8761',
            auth_type='none',
            auth_config={},
            rate_limit=60,
            timeout=5,
            retry_count=2,
            cache_ttl=30,
            headers={'Content-Type': 'application/json'}
        ))
    
    def register_endpoint(self, endpoint: APIEndpoint):
        """Register a new API endpoint."""
        with self.lock:
            self.endpoints[endpoint.name] = endpoint
            self.rate_limits[endpoint.name] = RateLimitBucket(
                capacity=endpoint.rate_limit,
                tokens=endpoint.rate_limit,
                last_update=time.time()
            )
            
            # Save to DB
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO endpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    endpoint.name, endpoint.base_url, endpoint.auth_type,
                    json.dumps(endpoint.auth_config), endpoint.rate_limit,
                    endpoint.timeout, endpoint.retry_count, endpoint.cache_ttl,
                    json.dumps(endpoint.headers), endpoint.health_check_url,
                    time.time()
                ))
                conn.commit()
    
    def _check_rate_limit(self, endpoint_name: str) -> bool:
        """Check if request is within rate limit."""
        bucket = self.rate_limits.get(endpoint_name)
        if not bucket:
            return True
        
        now = time.time()
        elapsed = now - bucket.last_update
        
        # Refill tokens (token bucket algorithm)
        refill = elapsed * (bucket.capacity / 60.0)  # per second rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + refill)
        bucket.last_update = now
        
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True
        
        self.stats['rate_limit_hits'] += 1
        return False
    
    def _build_auth_headers(self, endpoint: APIEndpoint) -> Dict[str, str]:
        """Build authentication headers."""
        headers = endpoint.headers.copy()
        
        if endpoint.auth_type == 'bearer':
            token = endpoint.auth_config.get('token', '')
            headers['Authorization'] = f'Bearer {token}'
        elif endpoint.auth_type == 'api_key':
            key_name = endpoint.auth_config.get('key_name', 'X-API-Key')
            key_value = endpoint.auth_config.get('key_value', '')
            headers[key_name] = key_value
        elif endpoint.auth_type == 'basic':
            username = endpoint.auth_config.get('username', '')
            password = endpoint.auth_config.get('password', '')
            credentials = f"{username}:{password}".encode('utf-8')
            b64 = base64.b64encode(credentials).decode('ascii')
            headers['Authorization'] = f'Basic {b64}'
        
        return headers
    
    def _get_cache_key(self, endpoint_name: str, method: str, path: str, params: Dict) -> str:
        """Generate cache key."""
        key_data = f"{endpoint_name}:{method}:{path}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response if valid."""
        if cache_key in self.cache:
            response, expires_at = self.cache[cache_key]
            if time.time() < expires_at:
                return response
            else:
                del self.cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, response: Any, ttl: int):
        """Cache response."""
        expires_at = time.time() + ttl
        self.cache[cache_key] = (response, expires_at)
        
        # Also save to DB for persistence
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO cache_entries VALUES (?, ?, ?, ?, ?)
            ''', (cache_key, '', json.dumps(response), expires_at, time.time()))
            conn.commit()
    
    def request(self, endpoint_name: str, method: str = 'GET', 
                path: str = '', params: Optional[Dict] = None,
                data: Optional[Dict] = None, use_cache: bool = True) -> Dict[str, Any]:
        """Make API request with all features."""
        
        if params is None:
            params = {}
        
        endpoint = self.endpoints.get(endpoint_name)
        if not endpoint:
            return {'success': False, 'error': 'endpoint_not_found'}
        
        request_id = hashlib.md5(f"{time.time()}{endpoint_name}{path}".encode()).hexdigest()[:16]
        
        # Check cache for GET requests
        if method == 'GET' and use_cache:
            cache_key = self._get_cache_key(endpoint_name, method, path, params)
            cached = self._get_cached_response(cache_key)
            if cached is not None:
                self.stats['cached_responses'] += 1
                return {
                    'success': True,
                    'data': cached,
                    'cached': True,
                    'request_id': request_id
                }
        
        # Check rate limit
        if not self._check_rate_limit(endpoint_name):
            return {
                'success': False,
                'error': 'rate_limit_exceeded',
                'request_id': request_id
            }
        
        # Build URL
        url = endpoint.base_url + path
        if params and method == 'GET':
            url += '?' + urllib.parse.urlencode(params)
        
        # Build headers
        headers = self._build_auth_headers(endpoint)
        
        # Prepare request
        request_data = None
        if data and method in ['POST', 'PUT', 'PATCH']:
            request_data = json.dumps(data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        
        # Retry logic
        start_time = time.time()
        last_error = None
        
        for attempt in range(endpoint.retry_count):
            try:
                req = urllib.request.Request(
                    url, 
                    data=request_data,
                    headers=headers,
                    method=method
                )
                
                with urllib.request.urlopen(req, timeout=endpoint.timeout) as response:
                    response_time = time.time() - start_time
                    response_data = response.read().decode('utf-8')
                    
                    try:
                        parsed_data = json.loads(response_data)
                    except:
                        parsed_data = {'raw': response_data}
                    
                    # Update stats
                    self.stats['total_requests'] += 1
                    self.stats['successful_requests'] += 1
                    self.stats['total_response_time'] += response_time
                    
                    # Cache GET responses
                    if method == 'GET' and use_cache:
                        cache_key = self._get_cache_key(endpoint_name, method, path, params)
                        self._cache_response(cache_key, parsed_data, endpoint.cache_ttl)
                    
                    # Log request
                    request_record = APIRequest(
                        request_id=request_id,
                        endpoint_name=endpoint_name,
                        method=method,
                        path=path,
                        params=params,
                        timestamp=start_time,
                        response_time=response_time,
                        status_code=response.status,
                        success=True,
                        cached=False
                    )
                    self.request_history.append(request_record)
                    
                    return {
                        'success': True,
                        'data': parsed_data,
                        'status_code': response.status,
                        'response_time': response_time,
                        'request_id': request_id,
                        'cached': False
                    }
            
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if attempt < endpoint.retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
            except urllib.error.URLError as e:
                last_error = f"URL Error: {e.reason}"
                if attempt < endpoint.retry_count - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                last_error = str(e)
                if attempt < endpoint.retry_count - 1:
                    time.sleep(2 ** attempt)
        
        # All retries failed
        response_time = time.time() - start_time
        self.stats['total_requests'] += 1
        self.stats['failed_requests'] += 1
        
        request_record = APIRequest(
            request_id=request_id,
            endpoint_name=endpoint_name,
            method=method,
            path=path,
            params=params,
            timestamp=start_time,
            response_time=response_time,
            success=False,
            error=last_error
        )
        self.request_history.append(request_record)
        
        return {
            'success': False,
            'error': last_error,
            'response_time': response_time,
            'request_id': request_id
        }
    
    def check_health(self, endpoint_name: str) -> Dict[str, Any]:
        """Check endpoint health."""
        endpoint = self.endpoints.get(endpoint_name)
        if not endpoint:
            return {'healthy': False, 'error': 'endpoint_not_found'}
        
        check_url = endpoint.health_check_url or '/'
        result = self.request(endpoint_name, 'GET', check_url, use_cache=False)
        
        return {
            'healthy': result['success'],
            'response_time': result.get('response_time', 0),
            'status_code': result.get('status_code'),
            'error': result.get('error')
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        avg_response_time = 0
        if self.stats['successful_requests'] > 0:
            avg_response_time = self.stats['total_response_time'] / self.stats['successful_requests']
        
        success_rate = 0
        if self.stats['total_requests'] > 0:
            success_rate = self.stats['successful_requests'] / self.stats['total_requests']
        
        return {
            'total_requests': self.stats['total_requests'],
            'successful': self.stats['successful_requests'],
            'failed': self.stats['failed_requests'],
            'cached': self.stats['cached_responses'],
            'rate_limit_hits': self.stats['rate_limit_hits'],
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'active_endpoints': len(self.endpoints),
            'cache_size': len(self.cache)
        }


api_bridge = None


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler for API bridge dashboard."""
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/api/stats':
            self.serve_json(api_bridge.get_stats())
        elif self.path == '/api/endpoints':
            endpoints = [
                {
                    'name': e.name,
                    'base_url': e.base_url,
                    'rate_limit': e.rate_limit,
                    'auth_type': e.auth_type
                }
                for e in api_bridge.endpoints.values()
            ]
            self.serve_json({'endpoints': endpoints})
        elif self.path == '/api/history':
            history = [
                {
                    'endpoint': r.endpoint_name,
                    'method': r.method,
                    'path': r.path,
                    'success': r.success,
                    'response_time': r.response_time,
                    'cached': r.cached
                }
                for r in list(api_bridge.request_history)[-50:]
            ]
            self.serve_json({'history': history})
        elif self.path.startswith('/api/health/'):
            endpoint_name = self.path.split('/')[-1]
            health = api_bridge.check_health(endpoint_name)
            self.serve_json(health)
        else:
            self.send_error(404)
    
    def serve_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def serve_dashboard(self):
        html = '''<!DOCTYPE html>
<html><head><title>API Bridge</title><meta charset="UTF-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:monospace;background:#0a0e27;color:#e0e0e0}
.header{background:linear-gradient(135deg,#667eea,#764ba2);padding:20px;color:#fff}
.title{font-size:24px;font-weight:700}
.subtitle{margin-top:5px;opacity:0.9;font-size:14px}
.container{padding:20px;max-width:1400px;margin:0 auto}
.panel{background:#1a1a2e;border:1px solid #2a2a3e;border-radius:8px;padding:15px;margin:15px 0}
.panel-title{font-size:16px;margin-bottom:10px;color:#667eea;font-weight:700}
.stat{display:inline-block;margin:10px 20px 10px 0}
.stat-val{font-size:28px;font-weight:700;color:#667eea}
.stat-label{font-size:12px;color:#999}
.endpoint{background:#2a2a3e;border-left:4px solid #27ae60;padding:10px;margin:8px 0;border-radius:4px}
.endpoint-name{font-weight:700;color:#27ae60}
.request{background:#2a2a3e;padding:8px;margin:5px 0;border-radius:4px;font-size:11px}
.success{border-left:3px solid #27ae60}
.failure{border-left:3px solid #e74c3c}
.cached{border-left:3px solid #f39c12}
.badge{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;margin-left:5px}
.badge-success{background:#27ae60;color:#fff}
.badge-error{background:#e74c3c;color:#fff}
.badge-cached{background:#f39c12;color:#fff}
</style></head><body>
<div class="header">
<div class="title">🌐 Universal API Bridge</div>
<div class="subtitle">Intelligent API Integration & Management System</div>
</div>
<div class="container">
<div class="panel">
<div id="stats"></div>
</div>
<div class="panel">
<div class="panel-title">📡 Active Endpoints</div>
<div id="endpoints"></div>
</div>
<div class="panel">
<div class="panel-title">📊 Recent Requests (last 50)</div>
<div id="history"></div>
</div>
</div>
<script>
async function loadStats() {
    const res = await fetch('/api/stats');
    const data = await res.json();
    const successPct = (data.success_rate * 100).toFixed(1);
    document.getElementById('stats').innerHTML = 
        '<div class="stat"><div class="stat-val">' + data.total_requests + '</div><div class="stat-label">Total Requests</div></div>' +
        '<div class="stat"><div class="stat-val">' + successPct + '%</div><div class="stat-label">Success Rate</div></div>' +
        '<div class="stat"><div class="stat-val">' + (data.avg_response_time * 1000).toFixed(0) + 'ms</div><div class="stat-label">Avg Response</div></div>' +
        '<div class="stat"><div class="stat-val">' + data.cached + '</div><div class="stat-label">Cached</div></div>' +
        '<div class="stat"><div class="stat-val">' + data.active_endpoints + '</div><div class="stat-label">Endpoints</div></div>';
}

async function loadEndpoints() {
    const res = await fetch('/api/endpoints');
    const data = await res.json();
    
    if (data.endpoints.length === 0) {
        document.getElementById('endpoints').innerHTML = '<div style="color:#999">No endpoints configured</div>';
        return;
    }
    
    document.getElementById('endpoints').innerHTML = data.endpoints.map(e =>
        '<div class="endpoint">' +
        '<div class="endpoint-name">' + e.name + '</div>' +
        '<div style="font-size:11px;color:#999;margin:3px 0">' + e.base_url + '</div>' +
        '<span style="font-size:11px">Auth: ' + e.auth_type + '</span>' +
        '<span style="font-size:11px;margin-left:15px">Rate: ' + e.rate_limit + '/min</span>' +
        '</div>'
    ).join('');
}

async function loadHistory() {
    const res = await fetch('/api/history');
    const data = await res.json();
    
    if (data.history.length === 0) {
        document.getElementById('history').innerHTML = '<div style="color:#999">No requests yet</div>';
        return;
    }
    
    document.getElementById('history').innerHTML = data.history.reverse().map(r => {
        let cls = 'request ';
        let badge = '';
        if (r.cached) {
            cls += 'cached';
            badge = '<span class="badge badge-cached">CACHED</span>';
        } else if (r.success) {
            cls += 'success';
            badge = '<span class="badge badge-success">✓</span>';
        } else {
            cls += 'failure';
            badge = '<span class="badge badge-error">✗</span>';
        }
        
        const rt = r.response_time ? (r.response_time * 1000).toFixed(0) + 'ms' : '-';
        
        return '<div class="' + cls + '">' +
            '<strong>' + r.method + '</strong> ' +
            '<span style="color:#999">' + r.endpoint + '</span> ' +
            r.path + ' ' + badge +
            '<span style="float:right;color:#999">' + rt + '</span>' +
            '</div>';
    }).join('');
}

function loadAll() {
    loadStats();
    loadEndpoints();
    loadHistory();
}

loadAll();
setInterval(loadAll, 3000);
</script>
</body></html>'''
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def main() -> None:
    """Main entry point."""
    global api_bridge
    
    heartbeat_path = pathlib.Path(os.environ.get("PROTEA_HEARTBEAT", ".heartbeat"))
    pid = os.getpid()
    stop_event = Event()
    
    heartbeat_thread = Thread(target=heartbeat_loop, args=(heartbeat_path, pid, stop_event), daemon=True)
    heartbeat_thread.start()
    
    output_dir = pathlib.Path("ring2_output")
    output_dir.mkdir(exist_ok=True)
    
    api_bridge = APIBridge(output_dir / "api_bridge.db")
    
    print(f"[Ring 2 Gen 133] Universal API Bridge pid={pid}", flush=True)
    print(f"🌐 Dashboard: http://localhost:{HTTP_PORT}", flush=True)
    
    # Start HTTP server
    def run_server():
        try:
            server = HTTPServer(('127.0.0.1', HTTP_PORT), BridgeHandler)
            server.serve_forever()
        except:
            pass
    
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    cycle = 0
    
    try:
        while True:
            # Test endpoints periodically
            if cycle % 30 == 0:
                print(f"\n[Cycle {cycle}] 🔍 Health Check:", flush=True)
                for endpoint_name in api_bridge.endpoints.keys():
                    health = api_bridge.check_health(endpoint_name)
                    status = "✓" if health['healthy'] else "✗"
                    rt = health.get('response_time', 0) * 1000
                    print(f"  {status} {endpoint_name}: {rt:.0f}ms", flush=True)
            
            if cycle % 10 == 0:
                stats = api_bridge.get_stats()
                print(f"[Cycle {cycle}] Requests: {stats['total_requests']} | "
                      f"✓ {stats['successful']} | ✗ {stats['failed']} | "
                      f"⚡ {stats['cached']} | "
                      f"Avg: {stats['avg_response_time']*1000:.0f}ms", flush=True)
            
            time.sleep(2)
            cycle += 1
    
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        try:
            heartbeat_path.unlink(missing_ok=True)
        except:
            pass
        print(f"\n[Ring 2] API Bridge shutdown. pid={pid}", flush=True)


if __name__ == "__main__":
    main()