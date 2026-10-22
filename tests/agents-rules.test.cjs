const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const rules = fs.readFileSync(path.join(root, "AGENTS.md"), "utf8");

test("AGENTS.md requires a commit for every logical change", () => {
  assert.match(rules, /每个逻辑改动必须对应一个 Git commit/);
  assert.match(rules, /交付前必须完成提交/);
});

test("AGENTS.md requires tests and successful verification", () => {
  assert.match(rules, /都必须新增或更新相关自动化测试/);
  assert.match(rules, /所有测试、Lint、类型检查和构建验证均通过/);
});

test("AGENTS.md defines a complete delivery workflow", () => {
  for (const heading of ["改动必 Commit", "测试必覆盖", "标准工作流", "完成定义"]) {
    assert.match(rules, new RegExp(`^## \\d+\\. ${heading}$`, "m"));
  }
});
