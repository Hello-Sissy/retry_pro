import os
import frontmatter
import datetime

# 获取当前脚本所在目录的父目录，即“错题记录”根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_exam(subject, min_mastery=3, tag=None):
    mistake_dir = os.path.join(BASE_DIR, "01_错题库", subject)
    output_dir = os.path.join(BASE_DIR, "02_自定义组卷")
    
    if not os.path.exists(mistake_dir):
        print(f"错误：未找到科目目录 {mistake_dir}")
        return

    exam_questions = []

    for filename in os.listdir(mistake_dir):
        if filename.endswith(".md"):
            file_path = os.path.join(mistake_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
                # 筛选条件：掌握度低 且 匹配特定标签
                # 注意：YAML 中的 mastery 可能是 int，tags 是 list
                mastery = post.get('mastery', 5)
                tags = post.get('tags', [])
                
                if mastery <= min_mastery:
                    if tag is None or tag in tags:
                        # 提取题目内容（排除 YAML 头部）
                        exam_questions.append({
                            "id": post.get('id', 'Unknown'),
                            "content": post.content.strip()
                        })

    if not exam_questions:
        print(f"未找到符合条件（掌握度<={min_mastery}, 标签={tag}）的{subject}错题。")
        return

    # 导出为一份新的试卷 Markdown
    date_str = datetime.date.today().strftime("%y%m%d")
    exam_id = f"{date_str}1" # 简易序号逻辑
    output_filename = f"Custom_Exam_{subject}_{date_str}.md"
    output_path = os.path.join(output_dir, output_filename)
    
    # 生成题目映射表
    mapping = {i+1: q['id'] for i, q in enumerate(exam_questions)}
    
    with open(output_path, "w", encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"exam_id: {exam_id}\n")
        f.write(f"date: \"{datetime.date.today()}\"\n")
        f.write(f"title: \"{subject}专项复习卷\"\n")
        f.write("mapping:\n")
        for num, qid in mapping.items():
            f.write(f"  {num}: {qid}\n")
        f.write("---\n\n")
        
        f.write(f"# 学生的 {subject} 专项冲刺卷\n")
        f.write(f"> 生成日期：{datetime.date.today()} | 筛选标准：掌握度 <={min_mastery} | 标签：{tag if tag else '全部'}\n\n")
        f.write("---\n\n")
        
        for i, q in enumerate(exam_questions):
            f.write(f"## 第 {i+1} 题\n\n") # 注意这里只保留外显题号
            f.write(f"{q['content']}\n\n")
            f.write("---\n\n")

    print(f"成功！Markdown 试卷已生成至：{output_path}")

    # 自动化步骤：将 Markdown 转换为 PDF（图片内嵌，避免 file:// 无法加载本地图）
    print("正在生成 PDF 复习卷...")
    try:
        from md_to_exam_pdf import md_to_pdf
        pdf_path = md_to_pdf(output_path)
        print(f"✨ 最终 PDF 已生成：{pdf_path}")
    except Exception as e:
        print(f"PDF 生成失败：{e}")

if __name__ == "__main__":
    # 调用示例：生成数学、掌握度低于3星、包含“几何”标签的试卷
    # 你可以根据需要修改这里的参数
    generate_exam("数学", 3, "几何")
