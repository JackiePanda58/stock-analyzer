
# 安全权限测试报告

**生成时间:** 2026-04-08 19:02:37
**测试总数:** 24
**通过率:** 64.7% (排除跳过项)

## 汇总

| 状态 | 数量 |
|------|------|
| ✓ 通过 | 11 |
| ✗ 失败 | 6 |
| ⊘ 跳过 | 7 |

## 详细结果


### RBAC 测试

- ✓ **RBAC-01**: Admin 角色成功访问 /api/auth/me
- ✓ **RBAC-02**: User 角色被正确拒绝访问管理接口
- ✗ **RBAC-03-admin**: admin Token 验证失败：{'detail': '无效或被篡改的 Token'}
- ✗ **RBAC-03-user**: user Token 验证失败：{'detail': '无效或被篡改的 Token'}
- ✗ **RBAC-03-analyst**: analyst Token 验证失败：{'detail': '无效或被篡改的 Token'}
- ✓ **RBAC-04**: 过期 Token 被正确拒绝 (401)
- ✓ **RBAC-05**: 无效签名 Token 被正确拒绝 (401)
- ⊘ **RBAC-06**: Token 刷新接口返回：200
- ✗ **RBAC-07**: 登出后 Token 未失效

### RATE 测试

- ⊘ **RATE-01**: 未触发速率限制（可能未配置或阈值较高）
- ⊘ **RATE-02**: 并发请求未触发速率限制
- ⊘ **RATE-03**: 未观察到速率限制差异

### SQL 测试

- ✓ **SQL-01**: 登录接口 SQL 注入防护有效
- ✓ **SQL-02**: 搜索接口 SQL 注入防护有效
- ✓ **SQL-03**: 收藏接口 SQL 注入防护有效
- ✗ **SQL-04**: 错误信息可能暴露数据库结构

### XSS 测试

- ✗ **XSS-01**: 搜索接口可能反射 XSS payload
- ✓ **XSS-02**: 收藏接口 XSS 防护有效（未存储 payload）
- ⊘ **XSS-03**: 响应头配置不完整：application/json
- ✓ **XSS-04**: CSP 头已配置

### CORS 测试

- ⊘ **CORS-01**: OPTIONS 请求返回：400
- ✓ **CORS-02**: CORS 头配置正确 (Origin: http://localhost:3000, Vary: Origin)
- ⊘ **CORS-03**: 凭证支持检查异常：HTTP Error 405: Method Not Allowed
- ✓ **CORS-04**: 恶意域名请求被拒绝
