# Community Content System (V1)

Reddit 社区内容分析工具:给定一篇拟发布的 NIIMBOT Reddit 内容 + 目标社区,系统会基于该社区的真实规则、历史高/低表现案例和提炼规律,输出**适配判断 + 关键问题 + 修改建议 + 评论参与建议**,并提供发布前快照(immutable)与发布后结果回填/复盘闭环。

V1 范围:**能跑起来用 + 完成一次真实内容分析闭环**。前端、自动发帖、自动抓结果、增量 Pattern 提炼等不做。

---

## 1. 架构概览

```
Adapter(file/reddit) → Parser → ReferenceItem + Comment
                                ↓
                      PerformanceClassifier(high/mid/low)
                                ↓
                          Classifier(标签) + Embedder
                                ↓
                PatternMiner → KnowledgePattern(candidate)
                                ↓
                      CommunityProfile 落库
                                ↓
新内容 → Classifier(标签) → Retrieval(规则+案例+Pattern 召回)
                                ↓
                  LLM(基于 evidence 判断) → ContentAnalysisSnapshot(immutable)
                                ↓
                  发布后 → ActualResult(回填) → Review(复盘)
                                ↓
                  KnowledgePattern.validation_history(累计达阈值迁移 status)
```

关键设计:
- **Adapter 可切换**:`file`(沙箱用 fixture)/ `reddit`(生产用 PRAW),下游零改动
- **LLM Provider 可切换**:`mock` / `ollama` / `openai_compatible`,业务层只调 `complete()`
- **Snapshot immutable**:发布前判断不可回写,复盘必须能回看当时判断
- **Pattern 状态迁移需累计**:单条结果只追加 `validation_history`,不直接迁移 status

---

## 2. 部署步骤

### 2.1 前置依赖

- Python 3.10+
- 本地 Ollama(用于 LLM,默认 Qwen2.5:7b)
- (可选)Reddit App 凭据(若要真实 Reddit 数据)

### 2.2 安装

```bash
cd community_content_system
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env,按需填值(见 2.3)
```

生产用 Reddit 数据,需额外安装 PRAW:

```bash
pip install praw
```

### 2.3 配置 `.env`(关键项)

| 项 | V1 默认值 | 说明 |
|---|---|---|
| `CCS_ADAPTER` | `file` | 沙箱用 fixture;真实用 `reddit` |
| `CCS_LLM_PROVIDER` | `ollama` | 默认本地 Ollama;可切 `openai_compatible` |
| `CCS_LLM_CLASSIFIER_MODEL` | `qwen2.5:7b` | 标签轻量模型 |
| `CCS_LLM_ANALYZER_MODEL` | `qwen2.5:7b` | 分析用模型 |
| `CCS_LLM_API_BASE` | `http://localhost:11434` | Ollama 地址 |
| `CCS_DATABASE_URL` | `sqlite:///./community.db` | V1 单文件 |
| `CCS_REDDIT_*` | 留空 | 仅 `CCS_ADAPTER=reddit` 时必填 |

切到付费 OpenAI 兼容 API 时:
```bash
CCS_LLM_PROVIDER=openai_compatible
CCS_LLM_API_BASE=https://api.openai.com/v1
CCS_LLM_API_KEY=sk-...
CCS_LLM_ANALYZER_MODEL=gpt-4o-mini
```

### 2.4 拉 LLM 模型(Ollama 模式)

```bash
ollama pull qwen2.5:7b
ollama list   # 确认下载
```

### 2.5 启动服务

```bash
uvicorn app.main:app --reload
```

启动后访问:
- API 文档(Swagger UI):http://localhost:8000/docs
- 健康检查:http://localhost:8000/

---

## 3. 最小使用流程(完成一次真实内容分析)

以 r/organization 为例。所有 API 调用都可从 http://localhost:8000/docs 直接发起。

### Step 1:初始化社区

```http
POST /community/init
Content-Type: application/json

{
  "subreddit": "organization"
}
```

返回:
- 社区基本信息(subscribers / rules_count)
- 采到的帖子数 / 评论深采数 / 提炼出的 Pattern 数

数据落库:`CommunityProfile` / `ReferenceItem` / `ContentAnalysis` / `PerformanceAnalysis` / `KnowledgePattern`。

`CCS_ADAPTER=file` 时,社区必须已在 `fixtures/<subreddit>/` 下有 `about.json`、`rules.json`、`top_month.json`、`hot.json`、`new.json`。仓库自带 organization / Etsy / Peptides / learnprogramming 四个示例 fixture。

### Step 2:输入 Reddit 内容,触发 AI 分析

```http
POST /content/analyze
Content-Type: application/json

{
  "title": "Finally organized my pantry with a label maker — here's what I learned",
  "selftext": "I've been struggling with pantry chaos for years. Bought a Niimbot label printer last month, and it completely changed how my family uses the kitchen. Sharing before/after photos and what worked/didn't. Not affiliated, just genuinely happy with it.",
  "target_subreddit": "organization",
  "use_llm": true
}
```

返回字段:
- `verdict`: `fit` / `fit_after_fix` / `not_fit`
- `verdict_reason`: 判断理由
- `key_issues`: 数组,每条带 `issue` / `why` / `evidence_type` / `evidence_item_ids` / `fix`
- `modification_suggestions`: 数组,每条带 `target` / `current` / `suggested` / `reason`
- `comment_participation_advice`: 评论参与建议(文本)
- `evidence_count`: 引用的 evidence 数(来自 Retrieval 真实召回)
- `patterns_applied`: 引用的 KnowledgePattern 数
- `snapshot_id`: 本次判断的 immutable 快照 ID(后续复盘要用)
- `model_version`: 本次判断使用的模型标识

**关键**:evidence_item_ids 必须来自本次 Retrieval 召回的真实 ID,LLM 不能凭空生成。系统已对此做校验(详见 Retrieval `build_llm_context()` 末尾的 `ALLOWED EVIDENCE_ITEM_IDS` 清单)。

### Step 3:查看 verdict / key_issues / suggestions / evidence

```http
GET /content/{snapshot_id}/snapshot
```

返回 Step 2 落库的完整 snapshot 数据(immutable,不可修改)。

如需查看社区画像(规则、Pattern):

```http
GET /community/organization
```

返回 rules_summary、top_topics、common_structures、product_acceptance、patterns 列表。

### Step 4:人工修正(如需要)

如果对 AI 判断不满意,可发起修正。**原快照 immutable 不变**,系统创建新快照引用同一 submitted_content:

```http
PUT /human/verdict/{snapshot_id}
Content-Type: application/json

{
  "verdict": "fit",
  "verdict_reason": "修正理由",
  "key_issues": [...],
  "modification_suggestions": [...],
  "override_reason": "user disagree with LLM on promotional concern"
}
```

返回 `new_snapshot_id`,后续流程基于新快照。

也可对历史 ReferenceItem 的标签做人工修正(不覆盖历史,新增版本):

```http
PUT /human/label/{reference_item_id}
```

### Step 5:实际发布(系统外)

系统**不代发**。用户根据 AI 建议(或自行决定)修改内容,手动登录 Reddit 发布。**记录**:
- Reddit post URL 或 `t3_xxx`
- 实际发布版 title / body(用于后续归因,可存到 `result_assets` 引用的文档)

### Step 6:发布后回填结果

等 7-14 天 Reddit 真实反馈出来,手动从 Reddit 抓 ups/score/num_comments/is_deleted 填回来:

```http
POST /content/{snapshot_id}/result
Content-Type: application/json

{
  "ups": 15,
  "score": 12,
  "num_comments": 4,
  "is_deleted": false,
  "is_edited": false,
  "published_at": "2026-09-23T10:00:00Z",
  "source_post_id": "t3_abc123",
  "result_source": "manual"
}
```

`result_source` 支持 `manual` / `auto` / `screenshot` / `url`,V1 用 `manual`。`result_assets` 可放采纳清单文档 URL / 截图路径(可选,用于后续归因)。

### Step 7:复盘(对照判断 vs 实际)

```http
POST /content/{snapshot_id}/review
```

返回:
- `validated_items`: 被实际结果验证的判断项(verdict / predicted_engagement 等)
- `invalidated_items`: 未被验证的判断项
- `discrepancy_attribution`: 差异归因层(`community_error` / `pattern_error` / `prediction_error` / ...)
- `pattern_outcomes`: 每条 `{pattern_id, outcome: confirmed|contradicted|inconclusive}`

**关键**:
- 单条结果只追加到 `KnowledgePattern.validation_history`,**不直接迁移 Pattern status**
- Pattern 从 candidate → supported 需要 `confirmed >= 3 且 contradicted = 0`(可配置)
- AI 不能自行认定规律已验证,需人工触发

---

## 4. 关键 API 一览

| 端点 | 用途 |
|---|---|
| `POST /community/init` | 初始化社区 |
| `POST /content/analyze` | 新内容分析(保存发布前快照) |
| `POST /content/{id}/result` | 结果回填 |
| `POST /content/{id}/review` | 复盘 |
| `GET /community/{sub}` | 查看社区画像 |
| `GET /content/{id}/snapshot` | 查看快照 |
| `PUT /human/verdict/{snapshot_id}` | 人工修正判断 |
| `PUT /human/label/{item_id}` | 人工修正标签 |
| `POST /human/retrieval/filter` | 人工过滤召回案例 |
| `POST /human/pattern/{id}/confirm` | 人工确认规律验证 |
| `PUT /human/pattern/{id}/status` | 人工覆盖规律状态 |
| `GET /llm/last-call-log` | 查看最近 LLM 调用日志 |

全部可从 `/docs` 直接调用。

---

## 5. 数据流核心模型

| 模型 | 含义 |
|---|---|
| `ReferenceItem` | 一条 Reddit 帖子的结构化事实层,不含 AI 标签 |
| `Comment` | 评论,通过 `parent_post_id` 关联 |
| `ContentAnalysis` | ReferenceItem 的 AI 标签(版本化,可被人工修正) |
| `PerformanceAnalysis` | ReferenceItem 的 tier 分层(high/mid/low) |
| `KnowledgePattern` | 内容规律,状态机 candidate → supported/refuted/inconclusive |
| `CommunityProfile` | 社区画像聚合视图,引用 Pattern |
| `ContentAnalysisSnapshot` | **发布前判断快照,immutable** |
| `ActualResult` | 发布后实际表现(回填) |
| `Review` | 复盘结果 |

---

## 6. V1 已知限制

1. **沙箱无 Reddit 访问**:开发期用 `file` adapter + fixture,真实使用必须切 `reddit` adapter
2. **沙箱无 Ollama**:沙箱默认 `mock` provider,真实使用必须本地装 Ollama + 拉 Qwen 模型
3. **不自动抓结果**:Step 6 需手动从 Reddit 抄数字到 API
4. **不自动发帖**:Step 5 由用户手动登录 Reddit 发布
5. **Pattern 不会因单条结果迁移**:Step 7 一条结果只追加到 validation_history,需累计达阈值
6. **Embedding 未启用 Retrieval**:Retrieval 用 tag+token 匹配,未用向量召回
7. **无前端**:仅 FastAPI Swagger UI
8. **无鉴权**:单机自用,生产需自加
9. **沙箱数据库是 SQLite 单文件**:并发写入受限,生产建议切 Postgres
10. **fixture 不含评论深采**:`learnprogramming` 社区有 posts 子目录,其他社区只到 listing 层,评论深采可能空跑

---

## 7. V1 验证状态

- ✅ Phase 1 Step 1:organization 链路打通(沙箱 fixture)
- ✅ Phase 2 Step 2:9 条跨社区对比,真实 Ollama+Qwen2.5:7b 能消费 Retrieval evidence 并产生差异化判断(9 条中 8 条 evidence 校验 100% 通过)
- ⚠️ RedditAdapter 真机验证:沙箱无法访问 Reddit,需在能联网 Reddit 的机器上跑一次 `POST /community/init` 验证 PRAW 字段映射

详见 `/workspace/phase2_step2_validation_report.md`。

---

## 8. V1 不做的事

- 前端 UI(用 Swagger)
- 自动发帖
- 自动抓 Reddit 结果
- 增量 Pattern 提炼(只在 init 时提炼一次)
- Embedding 召回(继续用 tag+token)
- 鉴权
- 数据库迁移机制
- LLM Review(继续用规则式 `review_snapshot()`)
- 预测模型(继续用 low/mid/high 软预测)

V1 之外的功能留给 V2 决定。
