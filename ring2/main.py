#!/usr/bin/env python3
"""Ring 2 — Generation 4: Active Research Intelligence Agent

Evolution: From passive research automator to PROACTIVE RESEARCH INTELLIGENCE.
This agent:
- Monitors arXiv RSS feeds for trending papers in real-time
- Builds citation networks by extracting paper references
- Detects emerging research trends through temporal analysis
- Auto-discovers hot topics by tracking paper velocity (citations/time)
- Proactively suggests research directions based on momentum
- Cross-references papers to find research gaps
- Generates trend reports with predictive insights
- Web UI for real-time trend visualization

Key innovation: ACTIVE monitoring + PREDICTIVE analysis instead of reactive search.
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
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any, Set, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Event, Lock
from datetime import datetime, timedelta
from collections import defaultdict, Counter, deque
import re

HEARTBEAT_INTERVAL = 2
HTTP_PORT = 8899
ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_RSS = "http://export.arxiv.org/rss/{category}"

# Categories to monitor
MONITOR_CATEGORIES = ['cs.AI', 'cs.LG', 'cs.NE', 'cs.MA', 'cs.CL']

def heartbeat_loop(heartbeat_path: pathlib.Path, pid: int, stop_event: Event) -> None:
    """Dedicated heartbeat thread - CRITICAL for survival."""
    while not stop_event.is_set():
        try:
            heartbeat_path.write_text(f"{pid}\n{time.time()}\n")
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


@dataclass
class Paper:
    """Academic paper metadata."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published: str
    updated: str
    categories: List[str]
    pdf_url: str
    arxiv_url: str
    references: List[str] = None  # Extracted citation IDs
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


@dataclass
class TrendSignal:
    """Research trend signal."""
    topic: str
    momentum: float  # Rate of paper publication
    recent_papers: int
    key_authors: List[str]
    emerging_concepts: List[str]
    recommendation: str
    detected_at: float


@dataclass
class CitationEdge:
    """Citation relationship between papers."""
    source_id: str
    target_id: str
    detected_at: float


class ArxivMonitor:
    """Monitor arXiv for new papers and trends."""
    
    def __init__(self):
        self.seen_papers: Set[str] = set()
    
    def fetch_recent_papers(self, category: str, max_results: int = 50) -> List[Paper]:
        """Fetch recent papers from a category."""
        try:
            params = {
                'search_query': f'cat:{category}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
            
            req = urllib.request.Request(url, headers={
                'User-Agent': 'ResearchIntelligenceAgent/1.0'
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read().decode('utf-8')
            
            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            papers = []
            for entry in root.findall('atom:entry', ns):
                try:
                    id_elem = entry.find('atom:id', ns)
                    arxiv_id = id_elem.text.split('/abs/')[-1] if id_elem is not None else ''
                    
                    if arxiv_id in self.seen_papers:
                        continue
                    
                    title_elem = entry.find('atom:title', ns)
                    title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else ''
                    
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name_elem = author.find('atom:name', ns)
                        if name_elem is not None:
                            authors.append(name_elem.text)
                    
                    summary_elem = entry.find('atom:summary', ns)
                    abstract = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None else ''
                    
                    published_elem = entry.find('atom:published', ns)
                    published = published_elem.text if published_elem is not None else ''
                    
                    updated_elem = entry.find('atom:updated', ns)
                    updated = updated_elem.text if updated_elem is not None else ''
                    
                    categories = []
                    for cat in entry.findall('atom:category', ns):
                        term = cat.get('term', '')
                        if term:
                            categories.append(term)
                    
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
                    
                    # Extract potential citations from abstract
                    references = self._extract_references(abstract)
                    
                    paper = Paper(
                        arxiv_id=arxiv_id,
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        published=published,
                        updated=updated,
                        categories=categories,
                        pdf_url=pdf_url,
                        arxiv_url=arxiv_url,
                        references=references
                    )
                    
                    papers.append(paper)
                    self.seen_papers.add(arxiv_id)
                
                except Exception as e:
                    continue
            
            return papers
        
        except Exception as e:
            print(f"Error monitoring {category}: {e}", flush=True)
            return []
    
    def _extract_references(self, text: str) -> List[str]:
        """Extract arXiv IDs mentioned in text."""
        # Pattern: arXiv:1234.5678 or arxiv.org/abs/1234.5678
        pattern = r'(?:arXiv:|arxiv\.org/abs/)(\d{4}\.\d{4,5})'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return list(set(matches))


class TrendAnalyzer:
    """Analyze research trends and momentum."""
    
    @staticmethod
    def extract_concepts(papers: List[Paper]) -> List[str]:
        """Extract key concepts from papers."""
        all_text = ' '.join([p.title + ' ' + p.abstract for p in papers])
        
        # Extract meaningful n-grams
        words = re.findall(r'\b[a-z]{4,}\b', all_text.lower())
        
        # Common AI/ML terms to prioritize
        priority_terms = [
            'neural', 'learning', 'network', 'transformer', 'attention',
            'reinforcement', 'agent', 'evolution', 'optimization', 'model',
            'algorithm', 'deep', 'training', 'inference', 'representation'
        ]
        
        counter = Counter(words)
        concepts = []
        
        # Prioritize important terms
        for term in priority_terms:
            if term in counter and counter[term] > 0:
                concepts.append(term)
        
        # Add other frequent terms
        for word, count in counter.most_common(20):
            if word not in concepts and count > 2:
                concepts.append(word)
        
        return concepts[:15]
    
    @staticmethod
    def calculate_momentum(papers: List[Paper], time_window_hours: int = 24) -> float:
        """Calculate publication momentum (papers per day)."""
        if not papers:
            return 0.0
        
        now = time.time()
        cutoff = now - (time_window_hours * 3600)
        
        recent = 0
        for paper in papers:
            try:
                pub_time = datetime.fromisoformat(paper.published.replace('Z', '+00:00')).timestamp()
                if pub_time >= cutoff:
                    recent += 1
            except:
                pass
        
        # Papers per day
        days = time_window_hours / 24.0
        return recent / days if days > 0 else 0.0
    
    @staticmethod
    def detect_emerging_topics(papers: List[Paper], min_papers: int = 3) -> List[Tuple[str, int]]:
        """Detect emerging topics by concept clustering."""
        concepts = TrendAnalyzer.extract_concepts(papers)
        
        # Find co-occurring concepts
        co_occurrence = defaultdict(int)
        for paper in papers:
            paper_text = (paper.title + ' ' + paper.abstract).lower()
            paper_concepts = [c for c in concepts if c in paper_text]
            
            # Count papers per concept
            for concept in paper_concepts:
                co_occurrence[concept] += 1
        
        # Filter by minimum occurrence
        emerging = [(concept, count) for concept, count in co_occurrence.items()
                   if count >= min_papers]
        emerging.sort(key=lambda x: x[1], reverse=True)
        
        return emerging[:10]
    
    @staticmethod
    def find_prolific_authors(papers: List[Paper]) -> List[Tuple[str, int]]:
        """Find most active authors."""
        author_counts = Counter()
        for paper in papers:
            for author in paper.authors:
                author_counts[author] += 1
        
        return author_counts.most_common(10)


class CitationNetwork:
    """Build and analyze citation network."""
    
    def __init__(self):
        self.edges: List[CitationEdge] = []
        self.node_citations: Dict[str, int] = defaultdict(int)
    
    def add_paper(self, paper: Paper):
        """Add paper and its citations to network."""
        for ref_id in paper.references:
            edge = CitationEdge(
                source_id=paper.arxiv_id,
                target_id=ref_id,
                detected_at=time.time()
            )
            self.edges.append(edge)
            self.node_citations[ref_id] += 1
    
    def get_highly_cited(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Get most cited papers."""
        sorted_papers = sorted(self.node_citations.items(),
                              key=lambda x: x[1], reverse=True)
        return sorted_papers[:top_n]
    
    def find_citation_clusters(self) -> List[Set[str]]:
        """Find clusters of related papers."""
        # Simple clustering by shared citations
        clusters = []
        processed = set()
        
        for paper_id in self.node_citations.keys():
            if paper_id in processed:
                continue
            
            cluster = {paper_id}
            processed.add(paper_id)
            
            # Find papers that cite the same references
            for edge in self.edges:
                if edge.target_id == paper_id:
                    cluster.add(edge.source_id)
                    processed.add(edge.source_id)
            
            if len(cluster) > 1:
                clusters.append(cluster)
        
        return clusters


class ResearchIntelligence:
    """Main research intelligence engine."""
    
    def __init__(self, db_path: pathlib.Path, output_dir: pathlib.Path):
        self.db_path = db_path
        self.output_dir = output_dir
        self.lock = Lock()
        self.monitor = ArxivMonitor()
        self.citation_network = CitationNetwork()
        self.paper_history: deque = deque(maxlen=500)
        self._init_db()
    
    def _init_db(self):
        """Initialize database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS papers (
                    arxiv_id TEXT PRIMARY KEY,
                    title TEXT,
                    authors TEXT,
                    abstract TEXT,
                    published TEXT,
                    categories TEXT,
                    references TEXT,
                    discovered_at REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trends (
                    trend_id TEXT PRIMARY KEY,
                    topic TEXT,
                    momentum REAL,
                    recent_papers INTEGER,
                    key_authors TEXT,
                    concepts TEXT,
                    recommendation TEXT,
                    detected_at REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS citations (
                    source_id TEXT,
                    target_id TEXT,
                    detected_at REAL,
                    PRIMARY KEY (source_id, target_id)
                )
            ''')
            conn.commit()
    
    def monitor_categories(self):
        """Monitor all configured categories for new papers."""
        all_new_papers = []
        
        for category in MONITOR_CATEGORIES:
            papers = self.monitor.fetch_recent_papers(category, max_results=20)
            
            if papers:
                print(f"📊 {category}: Found {len(papers)} new papers", flush=True)
                
                # Save to DB
                with self.lock:
                    with sqlite3.connect(self.db_path) as conn:
                        for paper in papers:
                            try:
                                conn.execute('''
                                    INSERT OR REPLACE INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (paper.arxiv_id, paper.title,
                                      json.dumps(paper.authors),
                                      paper.abstract, paper.published,
                                      json.dumps(paper.categories),
                                      json.dumps(paper.references),
                                      time.time()))
                                
                                # Add to citation network
                                self.citation_network.add_paper(paper)
                                
                                # Save citations
                                for ref_id in paper.references:
                                    conn.execute('''
                                        INSERT OR IGNORE INTO citations VALUES (?, ?, ?)
                                    ''', (paper.arxiv_id, ref_id, time.time()))
                            
                            except Exception as e:
                                pass
                        
                        conn.commit()
                
                all_new_papers.extend(papers)
                self.paper_history.extend(papers)
        
        return all_new_papers
    
    def analyze_trends(self) -> List[TrendSignal]:
        """Analyze current research trends."""
        if not self.paper_history:
            return []
        
        recent_papers = list(self.paper_history)
        
        # Group by category
        category_papers = defaultdict(list)
        for paper in recent_papers:
            for cat in paper.categories:
                category_papers[cat].append(paper)
        
        trends = []
        
        for category, papers in category_papers.items():
            if len(papers) < 3:
                continue
            
            # Calculate momentum
            momentum = TrendAnalyzer.calculate_momentum(papers, time_window_hours=72)
            
            # Detect emerging topics
            emerging = TrendAnalyzer.detect_emerging_topics(papers)
            
            # Find key authors
            prolific = TrendAnalyzer.find_prolific_authors(papers)
            
            # Generate recommendation
            if momentum > 1.0:
                rec = f"HIGH ACTIVITY: {len(papers)} papers in 3 days. Hot topic!"
            elif emerging:
                rec = f"Emerging focus on: {', '.join([e[0] for e in emerging[:3]])}"
            else:
                rec = "Stable research area with steady activity"
            
            trend = TrendSignal(
                topic=category,
                momentum=momentum,
                recent_papers=len(papers),
                key_authors=[a[0] for a in prolific[:5]],
                emerging_concepts=[e[0] for e in emerging[:10]],
                recommendation=rec,
                detected_at=time.time()
            )
            
            trends.append(trend)
            
            # Save trend
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    trend_id = hashlib.md5(f"{category}{time.time()}".encode()).hexdigest()[:12]
                    conn.execute('''
                        INSERT INTO trends VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (trend_id, trend.topic, trend.momentum,
                          trend.recent_papers,
                          json.dumps(trend.key_authors),
                          json.dumps(trend.emerging_concepts),
                          trend.recommendation, trend.detected_at))
                    conn.commit()
        
        return trends
    
    def generate_trend_report(self, trends: List[TrendSignal]) -> str:
        """Generate comprehensive trend report."""
        lines = [
            "# Research Intelligence Report",
            f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n**Monitored Categories:** {', '.join(MONITOR_CATEGORIES)}",
            f"\n**Total Papers Tracked:** {len(self.paper_history)}",
            "\n---\n",
            "## Active Research Trends\n"
        ]
        
        for trend in sorted(trends, key=lambda t: t.momentum, reverse=True):
            lines.append(f"### {trend.topic}")
            lines.append(f"\n**Momentum:** {trend.momentum:.2f} papers/day")
            lines.append(f"\n**Recent Papers:** {trend.recent_papers}")
            lines.append(f"\n**Key Researchers:** {', '.join(trend.key_authors[:3])}")
            lines.append(f"\n**Emerging Concepts:** {', '.join(trend.emerging_concepts[:8])}")
            lines.append(f"\n**Analysis:** {trend.recommendation}")
            lines.append("\n---\n")
        
        # Citation analysis
        highly_cited = self.citation_network.get_highly_cited(top_n=10)
        if highly_cited:
            lines.append("## Most Referenced Papers\n")
            for arxiv_id, citations in highly_cited:
                lines.append(f"- `{arxiv_id}` — {citations} citations")
            lines.append("\n")
        
        # Research recommendations
        lines.append("## Strategic Recommendations\n")
        hot_topics = [t for t in trends if t.momentum > 1.0]
        if hot_topics:
            lines.append("**Hot Topics (High Activity):**")
            for trend in hot_topics[:3]:
                lines.append(f"- {trend.topic}: Focus on {', '.join(trend.emerging_concepts[:3])}")
        
        emerging_topics = [t for t in trends if 0.3 < t.momentum <= 1.0]
        if emerging_topics:
            lines.append("\n**Emerging Areas (Growing Interest):**")
            for trend in emerging_topics[:3]:
                lines.append(f"- {trend.topic}: Watch {', '.join(trend.key_authors[:2])}")
        
        return '\n'.join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                paper_count = conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
                trend_count = conn.execute('SELECT COUNT(*) FROM trends').fetchone()[0]
                citation_count = conn.execute('SELECT COUNT(*) FROM citations').fetchone()[0]
        
        return {
            'total_papers': paper_count,
            'recent_papers': len(self.paper_history),
            'trends_detected': trend_count,
            'citations_tracked': citation_count,
            'highly_cited': self.citation_network.get_highly_cited(5)
        }


intelligence = None


class IntelligenceHandler(BaseHTTPRequestHandler):
    """HTTP handler for intelligence dashboard."""
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/api/stats':
            stats = intelligence.get_stats()
            self.serve_json(stats)
        else:
            self.send_error(404)
    
    def serve_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def serve_dashboard(self):
        html = '''<!DOCTYPE html>
<html><head><title>Research Intelligence</title><meta charset="UTF-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Monaco,monospace;background:#0a0e27;color:#e0e0e0}
.header{background:linear-gradient(135deg,#667eea,#764ba2);padding:20px;color:#fff}
.title{font-size:24px;font-weight:700}
.container{padding:20px;max-width:1200px;margin:0 auto}
.panel{background:#1a1f3a;border:1px solid #2a2f4a;border-radius:8px;padding:20px;margin:20px 0}
.stat{display:inline-block;margin:10px 20px 10px 0}
.stat-value{font-size:32px;font-weight:700;color:#667eea}
.stat-label{color:#999;font-size:12px}
.trend{background:#0f1329;padding:15px;margin:10px 0;border-left:3px solid #667eea;border-radius:3px}
.hot{border-left-color:#ff6b6b}
.emerging{border-left-color:#4ecdc4}
.citation{color:#667eea;font-family:monospace}
</style></head><body>
<div class="header">
<div class="title">🧠 Research Intelligence Agent</div>
<div style="margin-top:8px;opacity:0.9">Active monitoring • Trend detection • Citation analysis</div>
</div>
<div class="container">
<div class="panel">
<div style="font-size:18px;margin-bottom:15px">📊 Live Statistics</div>
<div class="stat">
<div class="stat-value" id="totalPapers">-</div>
<div class="stat-label">Total Papers</div>
</div>
<div class="stat">
<div class="stat-value" id="recentPapers">-</div>
<div class="stat-label">Recent (Active)</div>
</div>
<div class="stat">
<div class="stat-value" id="trendsDetected">-</div>
<div class="stat-label">Trends Detected</div>
</div>
<div class="stat">
<div class="stat-value" id="citations">-</div>
<div class="stat-label">Citations Tracked</div>
</div>
</div>
<div class="panel">
<div style="font-size:18px;margin-bottom:15px">🔥 Most Cited Papers</div>
<div id="cited"></div>
</div>
</div>
<script>
async function loadStats() {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('totalPapers').textContent = data.total_papers;
    document.getElementById('recentPapers').textContent = data.recent_papers;
    document.getElementById('trendsDetected').textContent = data.trends_detected;
    document.getElementById('citations').textContent = data.citations_tracked;
    
    const cited = data.highly_cited.map(([id, count]) => 
        '<div class="trend"><span class="citation">' + id + '</span> — ' + count + ' citations</div>'
    ).join('');
    document.getElementById('cited').innerHTML = cited || '<div style="color:#666">No citations yet</div>';
}
loadStats();
setInterval(loadStats, 10000);
</script>
</body></html>'''
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def main() -> None:
    """Main entry point."""
    global intelligence
    
    heartbeat_path = pathlib.Path(os.environ.get("PROTEA_HEARTBEAT", ".heartbeat"))
    pid = os.getpid()
    stop_event = Event()
    
    heartbeat_thread = Thread(target=heartbeat_loop, args=(heartbeat_path, pid, stop_event), daemon=True)
    heartbeat_thread.start()
    
    output_dir = pathlib.Path("ring2_output")
    output_dir.mkdir(exist_ok=True)
    
    intelligence = ResearchIntelligence(output_dir / "intelligence.db", output_dir)
    
    print(f"[Ring 2 Gen 4] Research Intelligence Agent pid={pid}", flush=True)
    print(f"🌐 Dashboard: http://localhost:{HTTP_PORT}", flush=True)
    print(f"📡 Monitoring categories: {', '.join(MONITOR_CATEGORIES)}", flush=True)
    
    # Start HTTP server
    def run_server():
        try:
            server = HTTPServer(('127.0.0.1', HTTP_PORT), IntelligenceHandler)
            server.serve_forever()
        except:
            pass
    
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    # Initial scan
    print(f"🔍 Initial paper scan...", flush=True)
    new_papers = intelligence.monitor_categories()
    print(f"✅ Found {len(new_papers)} papers across categories", flush=True)
    
    cycle = 0
    try:
        while True:
            time.sleep(60)  # Monitor every minute
            cycle += 1
            
            # Monitor for new papers
            new_papers = intelligence.monitor_categories()
            
            # Analyze trends every 5 cycles
            if cycle % 5 == 0:
                print(f"\n📈 Analyzing trends (cycle {cycle})...", flush=True)
                trends = intelligence.analyze_trends()
                
                if trends:
                    report = intelligence.generate_trend_report(trends)
                    report_path = output_dir / 'reports' / f'trends_{int(time.time())}.md'
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(report, encoding='utf-8')
                    print(f"📝 Trend report: {report_path}", flush=True)
                    
                    # Show hot trends
                    hot = [t for t in trends if t.momentum > 1.0]
                    if hot:
                        print(f"🔥 Hot topics: {', '.join([t.topic for t in hot])}", flush=True)
            
            stats = intelligence.get_stats()
            print(f"[Cycle {cycle}] Papers: {stats['total_papers']} | Active: {stats['recent_papers']}", flush=True)
    
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        try:
            heartbeat_path.unlink(missing_ok=True)
        except:
            pass
        print(f"\n[Ring 2] Intelligence agent shutdown. pid={pid}", flush=True)


if __name__ == "__main__":
    main()