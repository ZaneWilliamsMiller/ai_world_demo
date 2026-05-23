# 项目结构规范修正

**目标**：根据用户反馈修正青笺录项目的文档与文件组织规范。

**执行**：

1. 将根目录 3 个 `task-artifact-*.md` 移至 `docs/iterations/`
2. README.md 删除冗长的「更新日志」章节，替换为一行链接 `docs/iterations/`
3. README.md 技术栈去掉具体模型名 `glm-4-flash`，改为 `OpenAI 兼容 API（默认智谱 GLM 系列）`
4. PROJECT_STRUCTURE.md 合并 `docs/task-artifact-*.md` 描述到 `docs/iterations/` 行

**结论**：后续迭代产物统一写入 `docs/iterations/`，README 不再堆放更新日志，模型名不出现在项目说明中。

**Commit**：`fbcf244` → 已推送 `origin/qclaw`