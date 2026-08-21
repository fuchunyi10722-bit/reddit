# Reddit 内容分析工具 — 变更日志

> 本文件记录所有改动，方便跨设备同步上下文。
> 另一台电脑 `git clone` 后先看这个文件就能快速了解项目当前状态。

---

## 2026-08-21（移除访问码 + P3 事实分析）

### 移除访问码登录机制
- 删除访问码登录页面（access-login div）
- 删除访问设置按钮
- init() 直接调用 initMain()，页面打开即用
- 删除 openAccessSettings() 函数

### P3 事实分析（社区分析标签页）
- 数据来源标注卡（NIIMBOT 历史数据 / Reddit 社区基准）
- 社区表现统计（按 Subreddit 分组：帖子数、Views、Upvotes、Comments、置信度）
- 内容类型分析（指南/展示/提问/讨论/经历/其他）
- 异常表现识别（Views 超同社区均值 2 倍标注）
- 评论深度分析（品牌/竞品提及、热门评论、需求/场景关键词）
- 置信度分级（1条=仅参考 / 2-4条=有限 / 5-9条=中等 / 10+条=较稳定）

### P4 社区基准导入
- 支持导入外部 Reddit Subreddit 基准数据 CSV
- 三层对比：NIIMBOT历史 vs Subreddit整体 vs 单帖
- Dashboard CSV 格式原生支持

### 数据更新
- 真实数据扩展到 29 条帖子 + 91 条评论
- 覆盖 20 个 Subreddit
- 版本号升级为 20260821-real-v2

### UI 清理
- 删除「载入真实数据」按钮（改为后台自动版本检测）
- 删除「导入评论」独立弹窗（评论直接在帖子 CSV 里）
- 批量导入模板改为 Dashboard 格式

---

## 2026-08-21（P1+P2 底层数据模型重构）

### P1: 帖子数据模型重构

帖子新增字段：
| 字段 | 类型 | 说明 |
|------|------|------|
| `isPublished` | boolean | true=已发布历史数据，false=待发布草稿 |
| `authorType` | enum | `official`(NIIMBOT官方) / `personal`(个人账号推广) / `third_party`(第三方提及) / `community`(社区普通) |
| `brandRelation` | enum | `official` / `promotional` / `organic_mention` / `none` |
| `imageDescription` | string | 配图描述（替代 boolean imageQuality 的补充） |

### P1: 评论数据模型重构

评论新增字段：
| 字段 | 类型 | 说明 |
|------|------|------|
| `likes` | number | 评论点赞数 |
| `replyCount` | number | 回复数 |
| `level` | number | 0=顶级评论，1+=嵌套回复 |
| `parentCommentId` | string/null | 父评论ID，建立评论层级关系 |
| `mentionsBrand` | boolean | 是否提及 NIIMBOT |
| `mentionsCompetitor` | boolean | 是否提及竞品 |
| `competitorName` | string | 竞品名称（如 Brother, DYMO, Phomemo, Zebra, Munbyn） |
| `userNeed` | string | 用户需求（如 购买意图/痛点/使用经验） |
| `useCase` | string | 使用场景（如 标签分类/收纳/DIY/Inventory/Small Business） |

### P2: CSV 导入支持全部新字段

**帖子 CSV 新列**（兼容旧格式）：
```
subreddit, title, body, postedAt/publishedAt, url, likes/score, comments, views,
hasImage, imageQuality, imageDescription, isPublished, authorType, brandRelation, predictedScore
```

**评论 CSV 新列**（兼容旧格式）：
```
postId, isAuthor, text/body, likes, replyCount, level, parentCommentId,
mentionsBrand, mentionsCompetitor, competitorName, userNeed, useCase
```

- CSV 模板已更新（下载按钮）
- authorType 和 brandRelation 留空时自动推断
- 评论 text/body 两种列名都支持
- 帖子 likes/score/upvotes 三种列名都支持
- 时间字段 postedAt/publishedAt 都支持

### 表单 UI 更新

帖子录入表单新增：
- 发布者身份下拉框（community/official/personal/third_party）
- 品牌关系下拉框（none/official/promotional/organic_mention）
- 发布状态下拉框（已发布/待发布）
- 配图描述输入框

评论录入表单新增（扩展字段行）：
- 点赞数输入框
- 🏷 NIIMBOT 提及勾选
- ⚔ 竞品提及勾选 + 竞品名称输入
- 用户需求输入
- 使用场景输入

### 后续阶段（待实施）

- P3: 事实分析视图（社区表现/内容类型/异常识别/评论分析）
- P4: 品牌数据 vs 社区数据分离统计
- P5: 发布前评估重构（历史事实→相似内容→预测→置信度）
- P6: 置信度系统（样本数量+数据一致性+内容相似度）
- P7: 清空模拟数据，替换为真实数据录入流程

### 录入新帖子 — 新增配图功能

- **🖼 是否有配图** 复选框（独立勾选）
- **✨ 配图优质** 复选框（勾选「是否有配图」后才能勾）
  - 没勾选「配图优质」= 一般或质量较差
  - 勾选了「配图优质」= 系统自动作为**加分维度**参与综合评分
- 联动：没勾「有配图」时勾「优质」会自动清空并灰掉

### 分析引擎 — 配图成为第 7 个评分维度

新增维度 **配图表现力**（权重 9%）：
- 优质配图 → 5 分
- 有配图但质量一般 → 3 分
- 无配图 → 2 分；若该社区高表现帖 60% 以上带图，则降为 1 分（high 优先建议）
- 其他 6 个维度权重轻微下调（重新归一化到 100%）

### 帖子卡片 — 显示配图信息标签

每张历史内容卡片显示彩色 Pill 标签：
- 🟢 配图优质 → 高表现加分项
- ⚪ 有配图（一般）→ 中性
- 🔴 无配图 → 注意可能扣分

### CSV 模板 + 批量导入评论格式更新

- **帖子模板**新增 3 列：`hasImage, imageQuality, predictedScore`
- **评论模板**改用新格式：`postId, isAuthor, text`（不再有 author / score 列）
  - `isAuthor=true` → 作者回复（OP）
  - `isAuthor=false` → 受众回复（默认）
  - 兼容旧 author 字段，`author=u/作者` 或 `OP` 自动识别为作者回复

### 社区分析 — 明确分析范围

社区分析（Subreddit）标签顶部新增蓝紫色说明卡：
> 分析范围：r/xxx 社区整体样本
> 基于你录入的 r/xxx 全部帖子样本（不论是否由你本人账号发布）提炼而成。
> 包含：你自己发的帖子、从社区中观察收集到的帖子、竞品帖子等。

底部显示当前样本量（帖子+评论条数）。

### 批量导入帖子时同时导入评论

「批量导入帖子」弹窗改名为「批量导入帖子（可同时附加评论）」：
- 步骤一：粘贴帖子 CSV（建议第一列填短 id 如 p1/p2 方便关联）
- 步骤二（可选）：粘贴评论 CSV，`postId` 填上面第一列的 id
  - 评论关联支持：精确 postId 匹配 或 按帖子 title 匹配
- 底部按钮改为「一次性导入帖子+评论」
- 导入结果一次 toast 显示：帖子 + 评论的新增/跳过统计

### 批量录入评论 — 作者改为勾选框

每条评论开头变成可点击复选框：
- **没勾选（默认）** → 灰色标签「受众回复」，保存为 `u/受众`
- **勾选了** → 蓝色标签「作者回复（OP）」，保存为 `u/作者`
- 分数字段从 UI 和表单中完全移除

---

## 2026-08-20

### 录入新帖子 — 字段优化

- **增加点赞录入**（likes 字段，替代原来的 score）
- **分数改为系统自动计算**（0-5 分，不可手动填写）
- **发布前评估预测分数（可选）**：predictedScore 字段，与发布后实际分析分数形成「预测 vs 实际」对比
- **增加评论录入**：帖子录入模态框底部可直接批量录入多条评论
- **标题/正文可选择发布前评估历史**：避免重复录入

### 访问码登录机制

- 首次打开需输入访问码（默认：`reddit2026`）
- 登录后可修改访问码或退出登录
- sessionStorage 确保刷新页面不需重复输入
- 新增「访问码忘了？点击重置」功能
- 新增默认码一键填入

### 访问码登录 Bug 修复

- **核心 Bug**：`initMain` 函数被错误嵌套在 `init()` 内部，导致整个 app.js 无法执行
- **修复**：把 `initMain` 提到和 `init` 同级
- **额外兜底**：
  - index.html 顶部加入全局错误捕获（脚本加载失败 alert 提示）
  - Toast z-index 提升到 99999
  - 访问码错误时同时弹 toast + alert 双重提示
  - init() 整个 try/catch 包裹

### 悬停定义看不到字修复

- tooltip 的 z-index 提升到 99999
- 改用固定深黑背景白字，不再依赖主题变量

---

## 2026-08-19

### 词云文字堆叠修复

- 改用阿基米德螺旋线布局算法（r = angle × 1.8）
- 角度步长从 0.3 弧度减小到 0.15 弧度
- 词间距从 2px 增加到 3px
- 优化碰撞检测边界条件

### 批量导入模板下载

- 帖子导入和评论导入模态框中添加模板下载按钮
- 生成的 CSV 带 BOM 头，Excel 打开不乱码
- 通过 Blob + 临时 `<a>` 元素触发浏览器下载

---

## 项目结构

```
6a86a33a44de73fd1f336ae2/
  ├── index.html          # 主页面（含访问码登录、全局错误捕获）
  ├── styles.css           # 全部样式
  ├── CHANGELOG.md         # 本文件
  └── js/
      ├── app.js           # 主逻辑（UI渲染、表单、导入、访问码）
      ├── store.js         # 数据存储（localStorage、CSV解析、CRUD）
      ├── analyzer.js      # 分析引擎（7维度评分、内容规律、发布前评估）
      └── demo-data.js     # 模拟数据（12条帖子+评论）
```

## 访问码

- 默认：`reddit2026`
- 修改方式：登录后点右上角「访问设置」
- 重置方式：登录页点「访问码忘了？点击这里重置为默认码」

## GitHub Pages 部署

1. 创建 GitHub 仓库（Public 才能用免费 Pages）
2. 上传 index.html + styles.css + js/ 文件夹
3. Settings → Pages → Source → Branch: main → / (root) → Save
4. 1-2 分钟后获得 `https://用户名.github.io/仓库名/`
5. 更新代码：直接在 GitHub 网页替换文件 → Commit → 30-60 秒自动生效
