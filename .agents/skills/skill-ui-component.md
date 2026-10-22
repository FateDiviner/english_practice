# Skill：新增一个前端 UI 组件

## 触发场景
需要新组件（按钮、卡片、输入、标记等）。

## 步骤
1. 先查 tokens.css 是否有现成色值/字号，无则先补 token
2. 组件文件放 components/，PascalCase 命名
3. 样式 scoped，只用 token 变量
4. 实现全部状态：默认 / hover / active / disabled / 正确 / 错误 / 空
5. 对照 08-ui-style.md 检查是否违反禁令
6. 在页面中引用并验证响应式

## 红线
- 不硬编码颜色
- 不用 emoji 当图标
- 不引入重型 UI 库默认皮肤
