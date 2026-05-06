"""
修复浮点数深度参数问题

在api_server.py的analysis_single函数中，修改research_depth校验逻辑
"""

# 原代码：
"""
    # research_depth 参数校验
    research_depth = (req.parameters or {}).get("research_depth")
    if research_depth is not None:
        try:
            rd = int(research_depth)
            if not (1 <= rd <= 5):
                raise HTTPException(status_code=400, detail=f"research_depth 必须为 1-5，当前值: {rd}")
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"research_depth 必须为整数 1-5")
"""

# 修复后代码：
"""
    # research_depth 参数校验
    research_depth = (req.parameters or {}).get("research_depth")
    if research_depth is not None:
        # 拒绝浮点数
        if isinstance(research_depth, float):
            raise HTTPException(status_code=400, detail=f"research_depth 必须为整数 1-5，不支持浮点数: {research_depth}")
        
        try:
            rd = int(research_depth)
            if not (1 <= rd <= 5):
                raise HTTPException(status_code=400, detail=f"research_depth 必须为 1-5，当前值: {rd}")
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"research_depth 必须为整数 1-5")
"""

print("浮点数深度参数问题修复补丁已生成")
print("请将上述代码替换api_server.py中的对应部分")
