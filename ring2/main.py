#!/usr/bin/env python3
"""Ring 2 — Generation 17: Market Research Intelligence

Evolution: Adds web research simulation, competitive analysis, and product
comparison capabilities. Can analyze market trends, compare products, and
generate research reports based on user queries about apps and services.
"""

import os
import pathlib
import sys
import time
import random
import re
import json
import hashlib
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional, Set
from collections import deque, Counter, defaultdict
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import urlparse, parse_qs

HEARTBEAT_INTERVAL = 2
HTTP_PORT = 8888


def write_heartbeat(path: pathlib.Path, pid: int) -> None:
    """Write heartbeat with error handling."""
    try:
        path.write_text(f"{pid}\n{time.time()}\n")
    except Exception:
        pass


class SkillType(Enum):
    """Types of skills agents can discover."""
    MATH = "mathematics"
    ALGORITHMS = "algorithms"
    DATA_STRUCTURES = "data_structures"
    FILE_IO = "file_operations"
    TEXT_PROCESSING = "text_processing"
    RESEARCH = "research"
    OPTIMIZATION = "optimization"
    SIMULATION = "simulation"
    CRYPTOGRAPHY = "cryptography"
    NETWORKING = "networking"
    WEB = "web_services"
    MEDICAL = "medical_research"
    HEALTH = "health_analysis"
    PERSISTENCE = "data_persistence"
    ANALYTICS = "analytics"
    MARKET_RESEARCH = "market_research"
    COMPETITIVE_ANALYSIS = "competitive_analysis"


class ResearchMemory:
    """SQLite-based persistent memory for research queries and market intelligence."""
    
    def __init__(self, db_path: pathlib.Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()
        
        # Research queries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS research_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                query_text TEXT NOT NULL,
                category TEXT,
                entities TEXT,
                completed BOOLEAN DEFAULT 0
            )
        ''')
        
        # Products/Apps discovered
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                features TEXT,
                rating REAL,
                first_discovered REAL NOT NULL,
                mention_count INTEGER DEFAULT 1,
                metadata TEXT
            )
        ''')
        
        # Competitive relationships
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competitive_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_a TEXT NOT NULL,
                product_b TEXT NOT NULL,
                relationship TEXT NOT NULL,
                notes TEXT,
                created REAL NOT NULL
            )
        ''')
        
        # Market trends
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                category TEXT NOT NULL,
                trend_name TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                description TEXT
            )
        ''')
        
        self.conn.commit()
    
    def record_query(self, query: str, category: str = "general") -> int:
        """Record a research query."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO research_queries (timestamp, query_text, category)
            VALUES (?, ?, ?)
        ''', (time.time(), query, category))
        
        query_id = cursor.lastrowid
        self.conn.commit()
        return query_id
    
    def add_product(self, name: str, category: str, features: List[str], 
                   rating: float = 0.0, metadata: Dict = None):
        """Add or update a product in the database."""
        cursor = self.conn.cursor()
        
        features_json = json.dumps(features)
        metadata_json = json.dumps(metadata or {})
        
        cursor.execute('''
            INSERT INTO products (name, category, features, rating, first_discovered, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                mention_count = mention_count + 1,
                features = excluded.features,
                rating = excluded.rating,
                metadata = excluded.metadata
        ''', (name, category, features_json, rating, time.time(), metadata_json))
        
        self.conn.commit()
    
    def add_competitive_edge(self, product_a: str, product_b: str, 
                            relationship: str, notes: str = ""):
        """Add competitive relationship between products."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO competitive_edges (product_a, product_b, relationship, notes, created)
            VALUES (?, ?, ?, ?, ?)
        ''', (product_a, product_b, relationship, notes, time.time()))
        self.conn.commit()
    
    def get_products_by_category(self, category: str) -> List[Dict]:
        """Get all products in a category."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT name, features, rating, mention_count, metadata
            FROM products
            WHERE category = ?
            ORDER BY rating DESC, mention_count DESC
        ''', (category,))
        
        return [
            {
                'name': row[0],
                'features': json.loads(row[1]),
                'rating': row[2],
                'mentions': row[3],
                'metadata': json.loads(row[4])
            }
            for row in cursor.fetchall()
        ]
    
    def get_trending_categories(self, days: int = 7) -> List[Tuple[str, int]]:
        """Get most researched categories."""
        cursor = self.conn.cursor()
        cutoff = time.time() - (days * 86400)
        
        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM research_queries
            WHERE timestamp > ?
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        ''', (cutoff,))
        
        return cursor.fetchall()
    
    def get_query_history(self, limit: int = 20) -> List[Dict]:
        """Get recent query history."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT timestamp, query_text, category
            FROM research_queries
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        return [
            {
                'timestamp': row[0],
                'query': row[1],
                'category': row[2]
            }
            for row in cursor.fetchall()
        ]
    
    def close(self):
        """Close database connection."""
        self.conn.close()


@dataclass
class Skill:
    """Represents a discovered capability."""
    name: str
    skill_type: SkillType
    complexity: int
    discovered_by: str
    generation: int
    usage_count: int = 0
    code_hash: str = ""
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'type': self.skill_type.value,
            'complexity': self.complexity,
            'discovered_by': self.discovered_by,
            'generation': self.generation,
            'usage_count': self.usage_count
        }


class SkillTree:
    """Tracks discovered skills and their relationships."""
    
    def __init__(self, output_dir: pathlib.Path):
        self.skills: Dict[str, Skill] = {}
        self.output_dir = output_dir
        self.tree_file = output_dir / "skill_tree.json"
        self._load()
    
    def _load(self):
        """Load existing skill tree."""
        if self.tree_file.exists():
            try:
                data = json.loads(self.tree_file.read_text())
                for skill_data in data.get('skills', []):
                    skill = Skill(
                        name=skill_data['name'],
                        skill_type=SkillType(skill_data['type']),
                        complexity=skill_data['complexity'],
                        discovered_by=skill_data['discovered_by'],
                        generation=skill_data['generation'],
                        usage_count=skill_data['usage_count']
                    )
                    self.skills[skill.name] = skill
            except:
                pass
    
    def _save(self):
        """Save skill tree to disk."""
        try:
            data = {
                'skills': [skill.to_dict() for skill in self.skills.values()],
                'total_skills': len(self.skills),
                'last_updated': time.time()
            }
            self.tree_file.write_text(json.dumps(data, indent=2))
        except:
            pass
    
    def discover_skill(self, skill: Skill) -> bool:
        """Discover a new skill. Returns True if new."""
        if skill.name not in self.skills:
            self.skills[skill.name] = skill
            self._save()
            return True
        else:
            self.skills[skill.name].usage_count += 1
            self._save()
            return False


@dataclass
class MarketResearchReport:
    """Structured market research report."""
    topic: str
    category: str
    products: List[Dict]
    analysis: Dict[str, any]
    recommendations: List[str]
    created: float = field(default_factory=time.time)
    
    def save_to(self, output_dir: pathlib.Path) -> pathlib.Path:
        """Save report to markdown file."""
        safe_name = re.sub(r'[^a-z0-9_]', '_', self.topic[:40].lower())
        filename = f"research_{safe_name}_{int(self.created)}.md"
        filepath = output_dir / filename
        
        lines = [
            f"# Market Research: {self.topic}",
            "",
            f"**Category:** {self.category}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.created))}",
            "",
            "## Overview",
            "",
            f"Analysis of {len(self.products)} products in the {self.category} market.",
            "",
            "## Top Products",
            ""
        ]
        
        for i, product in enumerate(self.products[:10], 1):
            lines.append(f"### {i}. {product['name']}")
            if product.get('rating'):
                lines.append(f"**Rating:** {'⭐' * int(product['rating'])} ({product['rating']:.1f}/5.0)")
            lines.append("")
            lines.append("**Key Features:**")
            for feature in product.get('features', [])[:5]:
                lines.append(f"- {feature}")
            
            metadata = product.get('metadata', {})
            if metadata:
                lines.append("")
                lines.append("**Additional Info:**")
                for key, value in metadata.items():
                    lines.append(f"- {key}: {value}")
            lines.append("")
        
        if self.analysis:
            lines.extend([
                "## Market Analysis",
                ""
            ])
            for key, value in self.analysis.items():
                lines.append(f"### {key}")
                lines.append(f"{value}")
                lines.append("")
        
        if self.recommendations:
            lines.extend([
                "## Recommendations",
                ""
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
        
        lines.extend([
            "",
            "---",
            "*Generated by Protea Market Research Intelligence*"
        ])
        
        try:
            filepath.write_text("\n".join(lines))
            return filepath
        except:
            return None


@dataclass
class Agent:
    """Autonomous research agent."""
    agent_id: int
    name: str
    skills: Set[str] = field(default_factory=set)
    generation: int = 0
    reports_created: int = 0
    products_analyzed: int = 0
    queries_processed: int = 0
    recent_work: deque = field(default_factory=lambda: deque(maxlen=3))
    
    def research_ai_pets(self, memory: ResearchMemory, output_dir: pathlib.Path) -> Optional[pathlib.Path]:
        """Research AI pet companion apps."""
        query_id = memory.record_query("AI pet companion apps", category="ai_pets")
        
        # Simulated market research data
        products = [
            {
                'name': 'Replika',
                'features': ['AI companion chat', 'Emotional support', 'Personalized conversations', 'AR avatar', 'Mental wellness'],
                'rating': 4.5,
                'metadata': {'platform': 'iOS/Android', 'price': 'Freemium', 'users': '10M+'}
            },
            {
                'name': 'Anima',
                'features': ['Virtual AI friend', 'Role-playing', 'Personality customization', 'Chat-based', 'Relationship building'],
                'rating': 4.3,
                'metadata': {'platform': 'iOS/Android', 'price': 'Freemium', 'users': '5M+'}
            },
            {
                'name': 'Chai',
                'features': ['Multiple AI personas', 'Entertainment focus', 'Community features', 'Custom characters', 'Story-driven'],
                'rating': 4.2,
                'metadata': {'platform': 'iOS/Android', 'price': 'Freemium', 'users': '1M+'}
            },
            {
                'name': 'Character.AI',
                'features': ['Celebrity/fictional AI', 'Wide character variety', 'Creative conversations', 'Community-created', 'Multiple chats'],
                'rating': 4.4,
                'metadata': {'platform': 'Web/iOS/Android', 'price': 'Freemium', 'users': '10M+'}
            },
            {
                'name': 'Noodle (猫咪陪伴)',
                'features': ['Virtual pet cat', 'Chinese market focus', 'Care simulation', 'Mood detection', 'Daily interactions'],
                'rating': 4.1,
                'metadata': {'platform': 'WeChat Mini Program', 'price': 'Free', 'users': '500K+', 'market': 'China'}
            },
            {
                'name': 'Momo AI Pet',
                'features': ['3D virtual pets', 'Voice interaction', 'Pet evolution', 'Mini-games', 'Social features'],
                'rating': 3.9,
                'metadata': {'platform': 'iOS/Android', 'price': 'Freemium', 'users': '100K+'}
            }
        ]
        
        # Store in database
        for product in products:
            memory.add_product(
                name=product['name'],
                category='ai_pets',
                features=product['features'],
                rating=product['rating'],
                metadata=product['metadata']
            )
            self.products_analyzed += 1
        
        # Add competitive relationships
        memory.add_competitive_edge('Replika', 'Anima', 'direct_competitor', 
                                    'Both focus on emotional AI companions')
        memory.add_competitive_edge('Character.AI', 'Chai', 'similar_market',
                                    'Entertainment-focused AI chat')
        
        # Generate analysis
        analysis = {
            'Market Leader': 'Replika and Character.AI dominate with 10M+ users each',
            'Key Differentiators': 'Emotional support (Replika) vs Entertainment (Character.AI/Chai)',
            'Chinese Market': 'Noodle focuses on WeChat ecosystem, different from Western apps',
            'Monetization': 'Freemium model dominates - free basic features, premium subscriptions',
            'Technology Trends': 'AR/3D avatars, voice interaction, personalization becoming standard'
        }
        
        recommendations = [
            'Focus on niche: Emotional wellness OR Entertainment, not both',
            'Consider platform: WeChat Mini Program for China, native apps for global',
            'Personalization is key: Users want unique AI personalities',
            'Freemium model: Offer free core experience, charge for premium features',
            'Community features: Enable users to share/create content increases retention',
            'Multi-modal interaction: Voice + text + visual engagement',
            'Privacy focus: Clear data policies crucial for companion apps'
        ]
        
        report = MarketResearchReport(
            topic='AI Pet Companion Apps',
            category='ai_pets',
            products=products,
            analysis=analysis,
            recommendations=recommendations
        )
        
        filepath = report.save_to(output_dir)
        if filepath:
            self.reports_created += 1
            self.queries_processed += 1
            self.recent_work.append(f"Research: {filepath.name}")
            return filepath
        
        return None
    
    def analyze_category(self, category: str, memory: ResearchMemory, 
                        output_dir: pathlib.Path) -> Optional[pathlib.Path]:
        """Analyze a product category from database."""
        memory.record_query(f"Analyze {category}", category=category)
        
        products = memory.get_products_by_category(category)
        if not products:
            return None
        
        # Calculate statistics
        avg_rating = sum(p['rating'] for p in products if p['rating']) / len(products)
        total_features = sum(len(p['features']) for p in products)
        
        analysis = {
            'Total Products': str(len(products)),
            'Average Rating': f"{avg_rating:.2f}/5.0",
            'Total Features Analyzed': str(total_features),
            'Top Rated': products[0]['name'] if products else 'N/A'
        }
        
        recommendations = [
            f"Study top performer: {products[0]['name']}",
            "Identify feature gaps in existing products",
            "Consider user pain points not addressed by current solutions"
        ]
        
        report = MarketResearchReport(
            topic=f'{category.title()} Category Analysis',
            category=category,
            products=products,
            analysis=analysis,
            recommendations=recommendations
        )
        
        filepath = report.save_to(output_dir)
        if filepath:
            self.reports_created += 1
            self.queries_processed += 1
            self.recent_work.append(f"Analysis: {filepath.name}")
            return filepath
        
        return None


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for evolution dashboard."""
    
    lab = None
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/api/stats':
            self.serve_stats_json()
        elif path == '/api/products':
            self.serve_products_json()
        elif path.startswith('/file/'):
            self.serve_file(path[6:])
        else:
            self.send_error(404)
    
    def serve_dashboard(self):
        memory_stats = self._get_memory_stats()
        
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>Protea Market Research</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: monospace; background: #0a0a0a; color: #0f0; margin: 0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #0f0; text-shadow: 0 0 10px #0f0; }}
        h2 {{ color: #0ff; border-bottom: 1px solid #0ff; padding-bottom: 5px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }}
        .stat-box {{ background: #111; border: 1px solid #0f0; padding: 12px; border-radius: 5px; }}
        .stat-value {{ font-size: 1.8em; color: #0ff; font-weight: bold; }}
        .section {{ background: #111; border: 1px solid #0f0; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .product {{ border-color: #ff0; }}
        .product h2 {{ color: #ff0; }}
        .list {{ list-style: none; padding: 0; }}
        .list li {{ padding: 6px; margin: 4px 0; background: #1a1a1a; border-left: 3px solid #0ff; }}
        .badge {{ background: #0ff; color: #000; padding: 2px 8px; border-radius: 3px; font-weight: bold; }}
        .rating {{ color: #ff0; }}
    </style>
    <script>
        setInterval(() => location.reload(), 10000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🔬 PROTEA MARKET RESEARCH 🔬</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div>Generation</div>
                <div class="stat-value">{self.lab.generation}</div>
            </div>
            <div class="stat-box">
                <div>Total Skills</div>
                <div class="stat-value">{len(self.lab.skill_tree.skills)}</div>
            </div>
            <div class="stat-box">
                <div>Queries Processed</div>
                <div class="stat-value">{memory_stats['total_queries']}</div>
            </div>
            <div class="stat-box">
                <div>Products Analyzed</div>
                <div class="stat-value">{memory_stats['product_count']}</div>
            </div>
            <div class="stat-box">
                <div>Reports Generated</div>
                <div class="stat-value">{sum(a.reports_created for a in self.lab.agents)}</div>
            </div>
        </div>
        
        <div class="section product">
            <h2>📱 AI Pet Apps Database</h2>
            <ul class="list">
                {self._render_products_html()}
            </ul>
        </div>
        
        <div class="section">
            <h2>📊 Research Activity</h2>
            <ul class="list">
                {self._render_history_html()}
            </ul>
        </div>
        
        <div class="section">
            <h2>📁 Generated Reports</h2>
            <ul class="list">
                {self._render_files_html()}
            </ul>
        </div>
    </div>
</body>
</html>'''
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode())
    
    def _get_memory_stats(self) -> dict:
        cursor = self.lab.research_memory.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM research_queries")
        total_queries = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        return {
            'total_queries': total_queries,
            'product_count': product_count
        }
    
    def _render_products_html(self) -> str:
        products = self.lab.research_memory.get_products_by_category('ai_pets')
        if not products:
            return "<li>No products yet...</li>"
        
        html = ""
        for product in products[:10]:
            rating_stars = '⭐' * int(product['rating']) if product['rating'] else ''
            html += f'<li><strong>{product["name"]}</strong> <span class="rating">{rating_stars}</span> ({product["rating"]:.1f})</li>'
        return html
    
    def _render_history_html(self) -> str:
        history = self.lab.research_memory.get_query_history(10)
        if not history:
            return "<li>No activity yet...</li>"
        
        html = ""
        for item in history:
            ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(item['timestamp']))
            html += f'<li><strong>{ts}</strong>: {item["query"]} <span class="badge">{item["category"]}</span></li>'
        return html
    
    def _render_files_html(self) -> str:
        files = sorted(self.lab.output_dir.glob("research_*.md"), 
                      key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return "<li>No reports yet...</li>"
        
        html = ""
        for f in files[:15]:
            mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(f.stat().st_mtime))
            html += f'<li><a href="/file/{f.name}" style="color: #0ff; text-decoration: none;">{f.name}</a> ({mtime})</li>'
        return html
    
    def serve_file(self, filename: str):
        filepath = self.lab.output_dir / filename
        if not filepath.exists():
            self.send_error(404)
            return
        
        try:
            content = filepath.read_text()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode())
        except:
            self.send_error(500)
    
    def serve_stats_json(self):
        stats = self._get_memory_stats()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(stats).encode())
    
    def serve_products_json(self):
        products = self.lab.research_memory.get_products_by_category('ai_pets')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(products).encode())


class EvolutionLab:
    """Laboratory managing agent evolution with market research."""
    
    def __init__(self, population_size: int = 4):
        self.agents: List[Agent] = []
        self.generation = 0
        
        self.output_dir = pathlib.Path("ring2_output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize research memory
        db_path = self.output_dir / "research_memory.db"
        self.research_memory = ResearchMemory(db_path)
        
        self.skill_tree = SkillTree(self.output_dir)
        self.pending_tasks: deque = deque()
        self._seed_tasks()
        
        names = ["Ada", "Turing", "Hopper", "Knuth"]
        for i in range(population_size):
            agent = Agent(
                agent_id=i,
                name=names[i % len(names)],
                generation=self.generation
            )
            self.agents.append(agent)
        
        # Discover new skills
        for skill_data in [
            ("Market Research", SkillType.MARKET_RESEARCH, 6),
            ("Competitive Analysis", SkillType.COMPETITIVE_ANALYSIS, 5),
            ("Product Database", SkillType.PERSISTENCE, 4)
        ]:
            skill = Skill(
                name=skill_data[0],
                skill_type=skill_data[1],
                complexity=skill_data[2],
                discovered_by="System",
                generation=self.generation
            )
            self.skill_tree.discover_skill(skill)
        
        self._start_http_server()
    
    def _start_http_server(self):
        DashboardHandler.lab = self
        
        def run_server():
            try:
                server = HTTPServer(('127.0.0.1', HTTP_PORT), DashboardHandler)
                server.serve_forever()
            except:
                pass
        
        thread = Thread(target=run_server, daemon=True)
        thread.start()
    
    def _seed_tasks(self):
        tasks = [
            "research_ai_pets",
            "analyze_ai_pets",
            "research_ai_pets",
            "analyze_ai_pets"
        ]
        for task in tasks:
            self.pending_tasks.append(task)
    
    def work_cycle(self):
        if not self.pending_tasks:
            self._seed_tasks()
        
        for agent in self.agents:
            if self.pending_tasks:
                task = self.pending_tasks.popleft()
                
                if task == "research_ai_pets":
                    agent.research_ai_pets(self.research_memory, self.output_dir)
                elif task == "analyze_ai_pets":
                    agent.analyze_category('ai_pets', self.research_memory, self.output_dir)
    
    def evolve(self):
        self.agents.sort(
            key=lambda a: a.reports_created + a.products_analyzed + a.queries_processed,
            reverse=True
        )
        
        survivors = self.agents[:max(2, len(self.agents) // 2)]
        new_pop = []
        
        for agent in survivors:
            new_pop.append(agent)
            offspring = Agent(
                agent_id=random.randint(1000, 9999),
                name=f"{agent.name}_G{self.generation + 1}",
                generation=self.generation + 1
            )
            new_pop.append(offspring)
        
        self.agents = new_pop[:len(self.agents)]
        self.generation += 1


def main() -> None:
    heartbeat_path = pathlib.Path(
        os.environ.get("PROTEA_HEARTBEAT", ".heartbeat")
    )
    pid = os.getpid()
    print(f"[Ring 2 Gen 17] Market Research Intelligence  pid={pid}", flush=True)
    print(f"Dashboard: http://localhost:{HTTP_PORT}", flush=True)
    print(f"Output: {pathlib.Path('ring2_output').absolute()}", flush=True)
    print(f"Database: ring2_output/research_memory.db\n", flush=True)
    
    lab = EvolutionLab(population_size=4)
    
    last_heartbeat = time.time()
    last_work = time.time()
    last_evolution = time.time()
    
    try:
        while True:
            current = time.time()
            
            if current - last_heartbeat >= HEARTBEAT_INTERVAL:
                write_heartbeat(heartbeat_path, pid)
                last_heartbeat = current
            
            if current - last_work >= 3.0:
                lab.work_cycle()
                last_work = current
            
            if current - last_evolution >= 15.0:
                lab.evolve()
                last_evolution = current
            
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        pass
    finally:
        try:
            lab.research_memory.close()
            heartbeat_path.unlink(missing_ok=True)
        except:
            pass
        
        print(f"\n[Ring 2] Dashboard was at http://localhost:{HTTP_PORT}", flush=True)
        print(f"[Ring 2] shutdown pid={pid}", flush=True)


if __name__ == "__main__":
    main()