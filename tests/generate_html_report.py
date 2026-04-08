#!/usr/bin/env python3
"""
生成 HTML 格式测试报告
用法：python3 generate_html_report.py [报告标题]
"""

import os
import sys
import json
import glob
from datetime import datetime
from pathlib import Path

# ─── 配置 ────────────────────────────────────────────────────────────────────
TEST_DIR = Path('/root/stock-analyzer/tests')
REPORT_DIR = TEST_DIR / 'reports'
REPORT_DIR.mkdir(exist_ok=True)

TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
TITLE = sys.argv[1] if len(sys.argv) > 1 else '回归测试报告'

# ─── 解析测试结果 ────────────────────────────────────────────────────────────
def parse_test_log(log_file):
    """解析测试日志文件"""
    result = {
        'name': log_file.name,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 统计通过
            result['passed'] = content.count('✓') + content.count('通过') + content.count('[92m✓')
            
            # 统计失败
            result['failed'] = content.count('✗') + content.count('失败') + content.count('[91m✗')
            
            # 统计跳过
            result['skipped'] = content.count('⊘') + content.count('跳过') + content.count('[93m⊘')
            
            # 提取错误信息
            if 'Error' in content or 'error' in content:
                for line in content.split('\n'):
                    if 'Error' in line or 'error' in line:
                        result['errors'].append(line.strip()[:200])
    except Exception as e:
        result['errors'].append(f'读取失败：{str(e)}')
    
    return result

# ─── 收集测试结果 ────────────────────────────────────────────────────────────
print("收集测试结果...")

test_results = []
log_files = list(REPORT_DIR.glob('*.log')) + list(TEST_DIR.glob('*.log'))

for log_file in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
    result = parse_test_log(log_file)
    if result['passed'] > 0 or result['failed'] > 0:
        test_results.append(result)

# 汇总统计
total_passed = sum(r['passed'] for r in test_results)
total_failed = sum(r['failed'] for r in test_results)
total_skipped = sum(r['skipped'] for r in test_results)
total_tests = total_passed + total_failed + total_skipped
pass_rate = (total_passed / max(1, total_tests)) * 100

print(f"总计：{total_tests} 项测试，{total_passed} 通过，{total_failed} 失败，{pass_rate:.1f}% 通过率")

# ─── 生成 HTML 报告 ──────────────────────────────────────────────────────────
print("生成 HTML 报告...")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{TITLE} - TradingAgents-CN</title>
    <style>
        :root {{
            --primary: #007bff;
            --success: #28a745;
            --warning: #ffc107;
            --danger: #dc3545;
            --light: #f8f9fa;
            --dark: #343a40;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, #0056b3 100%);
            color: white;
            padding: 40px;
        }}
        
        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        
        .header p {{
            opacity: 0.9;
            font-size: 14px;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .card {{
            background: var(--light);
            padding: 30px;
            border-radius: 8px;
            border-left: 5px solid var(--primary);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        .card.success {{ border-left-color: var(--success); }}
        .card.warning {{ border-left-color: var(--warning); }}
        .card.danger {{ border-left-color: var(--danger); }}
        
        .card .stat {{
            font-size: 48px;
            font-weight: bold;
            color: var(--dark);
            line-height: 1;
        }}
        
        .card .label {{
            color: #666;
            font-size: 14px;
            margin-top: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .card .sublabel {{
            color: #999;
            font-size: 12px;
            margin-top: 5px;
        }}
        
        h2 {{
            color: var(--dark);
            margin: 40px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--light);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        
        th {{
            background: var(--light);
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: var(--dark);
        }}
        
        td {{
            padding: 15px;
            border-bottom: 1px solid #dee2e6;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .pass {{ color: var(--success); font-weight: bold; }}
        .fail {{ color: var(--danger); font-weight: bold; }}
        .skip {{ color: var(--warning); font-weight: bold; }}
        
        .status-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .status-badge.pass {{
            background: var(--success);
            color: white;
        }}
        
        .status-badge.fail {{
            background: var(--danger);
            color: white;
        }}
        
        .status-badge.warning {{
            background: var(--warning);
            color: var(--dark);
        }}
        
        .progress-bar {{
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        
        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--success) 0%, #20c997 100%);
            transition: width 0.5s ease;
        }}
        
        .error-list {{
            background: #fff5f5;
            border: 1px solid #fed7d7;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        
        .error-list h3 {{
            color: var(--danger);
            margin-bottom: 15px;
        }}
        
        .error-item {{
            background: white;
            padding: 10px 15px;
            border-radius: 4px;
            margin: 10px 0;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            border-left: 3px solid var(--danger);
        }}
        
        .timestamp {{
            color: #999;
            font-size: 13px;
        }}
        
        .footer {{
            background: var(--light);
            padding: 20px 40px;
            text-align: center;
            color: #666;
            font-size: 13px;
        }}
        
        @media print {{
            body {{ background: white; padding: 0; }}
            .container {{ box-shadow: none; }}
            .card:hover {{ transform: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {TITLE}</h1>
            <p>TradingAgents-CN 项目回归测试</p>
            <p class="timestamp">执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="content">
            <h2>测试汇总</h2>
            <div class="summary">
                <div class="card success">
                    <div class="stat">{total_passed}</div>
                    <div class="label">通过</div>
                    <div class="sublabel">测试用例</div>
                </div>
                
                <div class="card {'danger' if total_failed > 0 else 'success'}">
                    <div class="stat">{total_failed}</div>
                    <div class="label">失败</div>
                    <div class="sublabel">测试用例</div>
                </div>
                
                <div class="card warning">
                    <div class="stat">{total_skipped}</div>
                    <div class="label">跳过</div>
                    <div class="sublabel">测试用例</div>
                </div>
                
                <div class="card {'success' if pass_rate >= 95 else 'warning' if pass_rate >= 80 else 'danger'}">
                    <div class="stat">{pass_rate:.1f}%</div>
                    <div class="label">通过率</div>
                    <div class="sublabel">目标：≥95%</div>
                </div>
            </div>
            
            <div class="progress-bar">
                <div class="progress-bar-fill" style="width: {pass_rate}%"></div>
            </div>
            
            <h2>测试详情</h2>
            <table>
                <thead>
                    <tr>
                        <th>测试文件</th>
                        <th>通过</th>
                        <th>失败</th>
                        <th>跳过</th>
                        <th>通过率</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
"""

for result in test_results:
    total = result['passed'] + result['failed'] + result['skipped']
    rate = (result['passed'] / max(1, total)) * 100
    status = 'pass' if result['failed'] == 0 else 'fail' if result['failed'] > total * 0.1 else 'warning'
    
    html += f"""
                    <tr>
                        <td><code>{result['name']}</code></td>
                        <td class="pass">{result['passed']}</td>
                        <td class="fail">{result['failed']}</td>
                        <td class="skip">{result['skipped']}</td>
                        <td>{rate:.1f}%</td>
                        <td><span class="status-badge {status}">{'✅ 通过' if status == 'pass' else '❌ 失败' if status == 'fail' else '⚠️ 部分失败'}</span></td>
                    </tr>
"""

html += """
                </tbody>
            </table>
"""

# 添加错误信息
all_errors = []
for result in test_results:
    if result['errors']:
        all_errors.extend(result['errors'][:3])

if all_errors:
    html += """
            <h2>错误信息</h2>
            <div class="error-list">
                <h3>⚠️ 检测到的错误</h3>
"""
    for error in all_errors[:10]:
        html += f'                <div class="error-item">{error}</div>\n'
    html += """
            </div>
"""

html += f"""
            <h2>日志文件</h2>
            <p>详细日志文件已保存到：<code>{REPORT_DIR}</code></p>
            <ul>
"""

for log_file in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
    html += f'                <li><a href="{log_file.name}">{log_file.name}</a> ({log_file.stat().st_size // 1024} KB)</li>\n'

html += f"""
            </ul>
            
            <h2>结论</h2>
            <p>
                {'✅ <strong>测试通过！</strong> 所有核心测试用例均已通过，系统可以发布。' if total_failed == 0 else 
                 '⚠️ <strong>部分测试失败</strong> 请查看上方错误信息并修复后重新测试。' if total_failed < total_tests * 0.1 else
                 '❌ <strong>测试失败</strong> 多项测试未通过，建议修复后重新执行回归测试。'}
            </p>
        </div>
        
        <div class="footer">
            <p>TradingAgents-CN 回归测试报告 | 版本 v1.2.2 | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""

# 保存报告
report_path = REPORT_DIR / f'report_{TIMESTAMP}.html'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ HTML 报告已生成：{report_path}")
print(f"📊 总计：{total_tests} 项测试，{total_passed} 通过，{total_failed} 失败，{pass_rate:.1f}% 通过率")

# 同时生成 Markdown 简版报告
md_report = f"""# {TITLE}

**执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**版本**: v1.2.2

## 测试汇总

| 指标 | 数值 |
|------|------|
| 总测试数 | {total_tests} |
| 通过 | {total_passed} |
| 失败 | {total_failed} |
| 跳过 | {total_skipped} |
| 通过率 | {pass_rate:.1f}% |

## 测试详情

| 测试文件 | 通过 | 失败 | 跳过 | 通过率 | 状态 |
|---------|------|------|------|--------|------|
"""

for result in test_results:
    total = result['passed'] + result['failed'] + result['skipped']
    rate = (result['passed'] / max(1, total)) * 100
    status = '✅' if result['failed'] == 0 else '❌' if result['failed'] > total * 0.1 else '⚠️'
    md_report += f"| {result['name']} | {result['passed']} | {result['failed']} | {result['skipped']} | {rate:.1f}% | {status} |\n"

md_report_path = REPORT_DIR / f'report_{TIMESTAMP}.md'
with open(md_report_path, 'w', encoding='utf-8') as f:
    f.write(md_report)

print(f"📝 Markdown 报告已生成：{md_report_path}")
