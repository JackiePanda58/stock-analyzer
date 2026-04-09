# Bug 修复报告：research_depth 类型错误

**日期**: 2026-04-09  
**优先级**: P0 (阻塞性问题)  
**状态**: ✅ 已修复

---

## 🐛 问题描述

### 错误现象
用户在提交股票分析时遇到 400 错误：
```
research_depth 必须为整数 1-5
Request failed with status code 400
```

### 错误堆栈
```javascript
POST http://139.155.146.217:62879/api/analysis/single 400 (Bad Request)
analysis.ts:127
```

### 控制台报错
```
❌ API 错误：400 /api/analysis/single 
{
  error: AxiosError, 
  message: 'Request failed with status code 400', 
  code: 'ERR_BAD_REQUEST'
}
```

---

## 🔍 问题分析

### 根本原因
前端发送的 `research_depth` 参数是**字符串**（如"标准"），但后端期望的是**整数**（1-5）。

### 代码位置

**前端错误代码** (`SingleAnalysis.vue:946`):
```typescript
research_depth: getDepthDescription(analysisForm.researchDepth),
// ↑ 返回字符串："快速" | "标准" | "深度" | "全面" | "极致"
```

**后端校验代码** (`api_server.py:1484-1491`):
```python
research_depth = (req.parameters or {}).get("research_depth")
if research_depth is not None:
    try:
        rd = int(research_depth)  # ← 期望整数
        if not (1 <= rd <= 5):
            raise HTTPException(status_code=400, detail=f"research_depth 必须为 1-5")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"research_depth 必须为整数 1-5")
```

### 深度映射关系
| 前端值 | 后端期望 | 当前发送 |
|--------|----------|----------|
| 1 - 快速 | 1 | "快速" ❌ |
| 2 - 标准 | 2 | "标准" ❌ |
| 3 - 深度 | 3 | "深度" ❌ |
| 4 - 全面 | 4 | "全面" ❌ |
| 5 - 极致 | 5 | "极致" ❌ |

---

## ✅ 修复方案

### 1. 修复 SingleAnalysis.vue

**修改前**:
```typescript
research_depth: getDepthDescription(analysisForm.researchDepth),
```

**修改后**:
```typescript
research_depth: analysisForm.researchDepth,  // 直接传递整数 1-5
```

**文件**: `/root/stock-analyzer/frontend/src/views/Analysis/SingleAnalysis.vue:946`

### 2. 修复 API 类型定义

**修改前**:
```typescript
export interface SingleAnalysisRequest {
  parameters?: {
    research_depth?: string  // ❌ 错误类型
  }
}
```

**修改后**:
```typescript
export interface SingleAnalysisRequest {
  parameters?: {
    research_depth?: number  // ✅ 整数 1-5
  }
}
```

**文件**: `/root/stock-analyzer/frontend/src/api/analysis.ts:29`

---

## 🧪 验证步骤

### 1. 前端验证
```typescript
// SingleAnalysis.vue 中的 analysisForm.researchDepth
// 应该是数字类型：1 | 2 | 3 | 4 | 5
analysisForm: {
  researchDepth: number  // 5 级深度选择
}
```

### 2. 请求验证
```typescript
const request = {
  symbol: '000001',
  parameters: {
    research_depth: 5,  // ✅ 整数
    // research_depth: "全面" ❌ 字符串（旧代码）
  }
}
```

### 3. 后端验证
```python
# api_server.py 接收到请求
research_depth = 5  # ✅ 可以转换为整数
rd = int(research_depth)  # rd = 5
assert 1 <= rd <= 5  # ✅ 通过
```

---

## 📝 相关文件

| 文件 | 修改内容 | 行数 |
|------|----------|------|
| `frontend/src/views/Analysis/SingleAnalysis.vue` | 修改 research_depth 传值 | 946 |
| `frontend/src/api/analysis.ts` | 修改类型定义 | 29 |

---

## 🎯 测试用例

### 测试场景 1: 快速分析 (depth=1)
```typescript
{
  symbol: '000001',
  parameters: { research_depth: 1 }
}
// ✅ 应该成功
```

### 测试场景 2: 标准分析 (depth=2)
```typescript
{
  symbol: '000001',
  parameters: { research_depth: 2 }
}
// ✅ 应该成功
```

### 测试场景 3: 全面分析 (depth=5)
```typescript
{
  symbol: '000001',
  parameters: { research_depth: 5 }
}
// ✅ 应该成功（用户报告的场景）
```

### 测试场景 4: 边界值 (depth=0)
```typescript
{
  symbol: '000001',
  parameters: { research_depth: 0 }
}
// ❌ 应该返回 400: research_depth 必须为 1-5
```

### 测试场景 5: 边界值 (depth=6)
```typescript
{
  symbol: '000001',
  parameters: { research_depth: 6 }
}
// ❌ 应该返回 400: research_depth 必须为 1-5
```

---

## 🚀 部署步骤

### 1. 热更新（推荐）
前端是 Vite 开发模式，保存后自动热更新：
```bash
# 无需重启，自动生效
```

### 2. 验证修复
1. 访问 http://139.155.146.217:62879/analysis/single
2. 输入股票代码（如：000001）
3. 选择深度：5 - 全面分析
4. 选择分析师
5. 点击"开始分析"
6. ✅ 应该成功提交，不再报 400 错误

---

## 📊 影响范围

### 影响的功能
- ✅ 单股分析提交
- ✅ 批量分析提交（如果使用相同 API）

### 不受影响的功能
- ✅ 分析历史查看
- ✅ 分析报告展示
- ✅ 自选股管理
- ✅ 股票搜索

---

## 🔧 后续优化建议

### 1. 添加前端校验
```typescript
// 在提交前验证
if (analysisForm.researchDepth < 1 || analysisForm.researchDepth > 5) {
  ElMessage.error('分析深度必须为 1-5')
  return
}
```

### 2. 统一深度枚举
```typescript
// 定义常量
export const ANALYSIS_DEPTH = {
  QUICK: 1,
  STANDARD: 2,
  DEEP: 3,
  COMPREHENSIVE: 4,
  EXTREME: 5
} as const
```

### 3. 后端返回友好错误
```python
# 当前
raise HTTPException(status_code=400, detail="research_depth 必须为整数 1-5")

# 优化后
raise HTTPException(
    status_code=400,
    detail={
        "code": "INVALID_DEPTH",
        "message": "分析深度必须为 1-5 的整数",
        "received": research_depth,
        "valid_range": "1-5"
    }
)
```

---

## ✅ 修复确认

- [x] SingleAnalysis.vue 已修复
- [x] analysis.ts 类型定义已修复
- [x] 代码已保存
- [ ] 前端热更新完成
- [ ] 用户测试通过

---

**修复时间**: 2 分钟  
**修复人员**: AI Assistant  
**测试状态**: 待用户验证
