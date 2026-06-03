import os
import json
import datetime
import frontmatter
import re
import markdown

# ==========================================
# Configuration
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISTAKE_ROOT = os.path.join(BASE_DIR, "01_错题库")
OUTPUT_FILE = os.path.join(BASE_DIR, "萌萌智能错题看板.html")

def markdown_to_html(text):
    return markdown.markdown(text, extensions=['fenced_code', 'tables'])

def collect_data():
    all_mistakes = []
    subjects = set()
    
    if not os.path.exists(MISTAKE_ROOT):
        return [], []

    # Use os.walk for recursive searching
    for root, dirs, files in os.walk(MISTAKE_ROOT):
        for filename in files:
            if filename.endswith(".md"):
                file_path = os.path.join(root, filename)
                
                # Determine subject from path (01_错题库/Subject/...)
                rel_path = os.path.relpath(file_path, MISTAKE_ROOT)
                subject = rel_path.split(os.sep)[0]
                subjects.add(subject)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        post = frontmatter.load(f)
                        
                        content = post.content
                        question = content
                        solution = ""
                        
                        if "## 解析" in content:
                            parts = content.split("## 解析")
                            question = parts[0].replace("## 题目", "").strip()
                            solution = parts[1].strip()
                        elif "## 答案" in content:
                            parts = content.split("## 答案")
                            question = parts[0].replace("## 题目", "").strip()
                            solution = parts[1].strip()

                        mistake = {
                            "id": post.get('id', filename.split('.')[0]),
                            "title": post.get('title', filename.split('.')[0]),
                            "subject": subject,
                            "mastery": post.get('mastery', 1),
                            "difficulty": post.get('difficulty', '中'),
                            "error_type": post.get('error_type', '未知'),
                            "tags": post.get('tags', []),
                            "date": str(post.get('date', datetime.date.today())),
                            "question_md": question,
                            "solution_md": solution,
                            "question_html": markdown_to_html(question),
                            "solution_html": markdown_to_html(solution)
                        }
                        all_mistakes.append(mistake)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
                    
    return all_mistakes, list(subjects)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>萌萌智能错题看板 - Premium</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+SC:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --danger: #ef4444;
            --warning: #f59e0b;
            --success: #10b981;
            --glass: rgba(30, 41, 59, 0.7);
            --border: rgba(255, 255, 255, 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', 'Noto Sans SC', sans-serif;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            overflow-x: hidden;
            background-image: radial-gradient(circle at 0% 0%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                              radial-gradient(circle at 100% 100%, rgba(239, 68, 68, 0.1) 0%, transparent 50%);
        }

        /* Sidebar */
        .sidebar {
            position: fixed;
            left: 0;
            top: 0;
            width: 260px;
            height: 100vh;
            background: var(--glass);
            backdrop-filter: blur(12px);
            border-right: 1px solid var(--border);
            padding: 2rem;
            z-index: 100;
            display: flex;
            flex-direction: column;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 3rem;
            background: linear-gradient(to right, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .nav-item {
            padding: 0.8rem 1rem;
            margin-bottom: 0.5rem;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s;
            color: var(--text-dim);
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .nav-item:hover {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-main);
        }

        .nav-item.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
        }

        /* Main Content */
        .main-content {
            margin-left: 260px;
            padding: 2rem 3rem;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2.5rem;
        }

        .user-badge {
            display: flex;
            align-items: center;
            gap: 12px;
            background: var(--glass);
            padding: 0.5rem 1rem;
            border-radius: 50px;
            border: 1px solid var(--border);
        }

        .avatar {
            width: 32px;
            height: 32px;
            background: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
        }

        /* Dashboard Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }

        .stat-card {
            background: var(--glass);
            padding: 1.5rem;
            border-radius: 24px;
            border: 1px solid var(--border);
            transition: transform 0.3s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            margin: 0.5rem 0;
        }

        .stat-label {
            color: var(--text-dim);
            font-size: 0.9rem;
        }

        /* Mistake List */
        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .mistake-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }

        .mistake-card {
            background: var(--bg-card);
            border-radius: 20px;
            padding: 1.5rem;
            border: 1px solid var(--border);
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }

        .mistake-card:hover {
            border-color: var(--primary);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }

        .subject-tag {
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 20px;
            background: rgba(99, 102, 241, 0.2);
            color: #a5b4fc;
            margin-bottom: 1rem;
            display: inline-block;
        }

        .mastery-indicator {
            position: absolute;
            top: 1.5rem;
            right: 1.5rem;
            display: flex;
            gap: 4px;
        }

        .star {
            font-size: 0.8rem;
            color: #475569;
        }

        .star.filled {
            color: #fbbf24;
        }

        .mistake-id {
            color: var(--text-dim);
            font-size: 0.8rem;
            margin-top: 1rem;
            font-family: monospace;
        }

        /* Modal */
        .modal {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.8);
            backdrop-filter: blur(8px);
            z-index: 1000;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }

        .modal-content {
            background: var(--bg-dark);
            width: 100%;
            max-width: 900px;
            max-height: 90vh;
            border-radius: 32px;
            border: 1px solid var(--border);
            overflow-y: auto;
            position: relative;
            animation: slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes slideUp {
            from { transform: translateY(50px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .modal-header {
            padding: 2rem;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            background: var(--bg-dark);
            z-index: 10;
        }

        .modal-body {
            padding: 2rem;
        }

        .q-box, .a-box {
            background: rgba(255,255,255,0.03);
            padding: 1.5rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }

        .a-box {
            border-left: 4px solid var(--success);
            display: none;
        }

        .btn {
            padding: 0.8rem 1.5rem;
            border-radius: 12px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }

        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-main); }
        .btn-outline:hover { background: rgba(255,255,255,0.05); }

        .hidden { display: none !important; }

        @media (max-width: 1024px) {
            .sidebar { width: 80px; padding: 1rem; }
            .sidebar span { display: none; }
            .main-content { margin-left: 80px; }
            .logo { justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            <span>MENG HUB</span>
        </div>
        <div class="nav-item active" onclick="showSection('dashboard')">
            <span>概览看板</span>
        </div>
        <div class="nav-item" onclick="showSection('library')">
            <span>错题库</span>
        </div>
        <div class="nav-item" onclick="startPractice()">
            <span>专项练兵</span>
        </div>
    </div>

    <div class="main-content">
        <header>
            <h1>你好，萌萌 👋</h1>
            <div class="user-badge">
                <div class="avatar">M</div>
                <span>Sissy Meng</span>
            </div>
        </header>

        <section id="dashboard">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">总录入错题</div>
                    <div class="stat-value" id="total-count">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">待攻克 (1-2星)</div>
                    <div class="stat-value" style="color: var(--danger)" id="urgent-count">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">平均掌握度</div>
                    <div class="stat-value" style="color: var(--success)" id="avg-mastery">0.0</div>
                </div>
            </div>

            <div class="section-title">最近更新</div>
            <div class="mistake-grid" id="recent-grid"></div>
        </section>

        <section id="library" class="hidden">
            <div class="section-title">所有错题</div>
            <div class="mistake-grid" id="library-grid"></div>
        </section>

        <section id="practice" class="hidden">
            <div id="practice-area"></div>
        </section>
    </div>

    <div id="modal" class="modal" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div style="display: flex; justify-content: space-between;">
                    <h2 id="modal-title">题目加载中...</h2>
                    <button class="btn btn-outline" onclick="closeModal()">关闭</button>
                </div>
            </div>
            <div class="modal-body">
                <div class="q-box" id="modal-question"></div>
                <button class="btn btn-primary" onclick="toggleSolution()">查看解析</button>
                <div id="solution-container" class="a-box" style="margin-top: 1rem;">
                    <div id="modal-solution"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const data = {{DATA_JSON}};

        function init() {
            document.getElementById('total-count').textContent = data.length;
            const urgent = data.filter(m => m.mastery <= 2).length;
            document.getElementById('urgent-count').textContent = urgent;
            const avg = data.length > 0 ? (data.reduce((acc, m) => acc + m.mastery, 0) / data.length).toFixed(1) : 0;
            document.getElementById('avg-mastery').textContent = avg;

            renderGrid('recent-grid', data.slice(0, 6));
            renderGrid('library-grid', data);
        }

        function renderGrid(containerId, items) {
            const container = document.getElementById(containerId);
            container.innerHTML = items.map(m => `
                <div class="mistake-card" onclick="openMistake('${m.id}')">
                    <div class="subject-tag">${m.subject}</div>
                    <div class="mastery-indicator">
                        ${[1,2,3,4,5].map(s => `<span class="star ${s <= m.mastery ? 'filled' : ''}">★</span>`).join('')}
                    </div>
                    <h3>${m.title}</h3>
                    <div class="mistake-id">${m.id}</div>
                </div>
            `).join('');
        }

        function showSection(id) {
            ['dashboard', 'library', 'practice'].forEach(sec => document.getElementById(sec).classList.add('hidden'));
            document.getElementById(id).classList.remove('hidden');
        }

        function openMistake(id) {
            const m = data.find(item => item.id === id);
            document.getElementById('modal-title').textContent = m.title;
            document.getElementById('modal-question').innerHTML = m.question_html;
            document.getElementById('modal-solution').innerHTML = m.solution_html;
            document.getElementById('solution-container').style.display = 'none';
            document.getElementById('modal').style.display = 'flex';
        }

        function closeModal() { document.getElementById('modal').style.display = 'none'; }

        function toggleSolution() {
            const container = document.getElementById('solution-container');
            container.style.display = container.style.display === 'none' ? 'block' : 'none';
        }

        function startPractice() {
            showSection('practice');
            const lowMastery = data.filter(m => m.mastery <= 3).sort(() => 0.5 - Math.random()).slice(0, 3);
            const container = document.getElementById('practice-area');
            container.innerHTML = lowMastery.length ? lowMastery.map(m => `
                <div class="mistake-card" style="margin-bottom: 2rem;">
                    <h3>${m.title}</h3>
                    <div style="margin: 1.5rem 0">${m.question_html}</div>
                    <button class="btn btn-outline" onclick="openMistake('${m.id}')">查看解析</button>
                </div>
            `).join('') : "<h3>暂无待攻克题目</h3>";
        }

        init();
    </script>
</body>
</html>
"""

def generate_hub():
    mistakes, subjects = collect_data()
    mistakes.sort(key=lambda x: x['date'], reverse=True)
    json_data = json.dumps(mistakes, ensure_ascii=False)
    html_content = HTML_TEMPLATE.replace("{{DATA_JSON}}", json_data)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✨ 成功生成智能看板：{OUTPUT_FILE}")

if __name__ == "__main__":
    generate_hub()
