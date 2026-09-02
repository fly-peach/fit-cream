# NOTICE · 第三方素材与许可范围

本仓库的 `LICENSE`（MIT，© 2026 wangtong）适用于本项目**代码与自研内容**。以下内容许可**另行适用**，不因本仓库的 MIT 声明而改变。

---

## 1. 动作数据集 exercises-dataset（文本数据 → MIT）

- **来源**：<https://github.com/hasaneyldrm/exercises-dataset>（1,324 个动作，含多语言指令文本）
- **使用位置**：
  - `rogers/seeds/exercises_dataset_origin.json` —— 原始导出
  - `rogers/seeds/exercises_dataset_opt.json` —— 本仓库派生版（仅保留中英双语字段）
  - `rogers/src/fitme/services/exercise_seed.py` —— 导入与回退逻辑
  - `frontend/src/lib/exercise-labels.ts` —— 动作/肌群中英词表
- **许可**：上游为 MIT，且其授权文本明确覆盖 *software and associated documentation and **data files***，instruction text/translations 亦在 MIT 范围内。因此上述 JSON 文本数据随本仓库一并按 MIT 授权。
- **按上游 MIT 要求保留的原始声明**：

```
MIT License

Copyright (c) 2026 Hasan Emir Yıldırım

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation and data files (the "Software"),
to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. 动作示意图与 GIF 媒体（© Gym visual → **不含在 MIT 内**）

- **归属**：© Gym visual · <https://gymvisual.com/>
- **本仓库不含该媒体**：`rogers/static/` 已在 `.gitignore` 中排除，部署时以只读绑定挂载注入（见 README「Docker 部署」）。
- 上游 MIT 的 **MEDIA EXCEPTION** 明确排除 `images/` 与 `videos/`：该媒体由权利人书面许可给上游使用，**克隆上游仓库不构成对你的媒体授权**，其使用与再利用受 Gym visual 条款约束。
- **合规要求（按 Gym visual 条款）：**
  - 媒体许可只随"**你购买的**无水印高清素材"授予（N-CRFL，绑定购买账号、不可转让、不可再授权）
  - 其公开站点上展示的**缩略图与预览版（含 180×180）明确不受任何许可覆盖**，水印版仅限内部选型评估，禁止用于对外发布的成品或任何线上分发
  - 保留署名 `© Gym visual — https://gymvisual.com/` 是其条款要求之一，**但署名本身不构成授权**
  - 不得以任何形式转售、再分发，或作为独立素材包提供
- **本项目署名位置**：动作库页脚 `frontend/src/pages/exercises.tsx`、动作详情页 `frontend/src/pages/exercise-detail.tsx`。
- ⚠️ **使用本项目搭建线上产品时**：动作示意图 / GIF **需自行向 Gym visual 取得许可**（或替换为其他已获授权的素材）。上游 exercises-dataset 获得的书面许可**仅适用于该仓库本身，不传递给下游使用者**。本仓库不包含、也不分发任何此类媒体。

---

## 3. 自研 / AI 生成内容

`rogers/seeds/goal_knowledge.json` 与身材原型图、动作组媒体等项目自研或 AI 生成素材，随代码按 `LICENSE` 中的 MIT 条款授权。

## 4. 依赖库

`pyproject.toml` / `frontend/package.json` 列出的第三方依赖各自遵守其上游许可（含 shadcn/ui、LlamaIndex、LangChain、FastAPI、React 等），本文件不改变其条款。
