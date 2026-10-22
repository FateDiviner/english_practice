# Vue 代码规范

- 组件文件 PascalCase（SpellInput.vue）；组合式函数 useXxx
- API 调用统一走 src/api/，组件内不直接写 axios
- 跨组件状态放 Pinia store，不用事件总线
- 样式 scoped，颜色/字号必须引用 styles/tokens.css 的 CSS 变量
- 练习页使用状态机：idle → answering → submitted(correct/wrong) → next → finished
- 提交中禁用按钮，防重复提交
- 组件 props 必须声明类型与默认值
- 共享逻辑抽成 composable，不复制粘贴
