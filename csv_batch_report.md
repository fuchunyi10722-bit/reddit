# 批量分析报告: csv-e2e-test

- 任务 ID: `cb090c00-71ed-48b8-8d60-ae2bcc69b138`
- 状态: completed
- 总数: 9  成功: 7  失败: 0  跳过: 2
- 创建: 2026-10-09T02:36:08.666087
- 完成: 2026-10-09T02:36:39.155864

## 1. 数据完整度

以下字段在部分帖子中缺失(影响分析覆盖度):
- `selftext`: 2 条缺失
- `title`: 2 条缺失
- `subreddit`: 1 条缺失

- 数据来源: CSV 导入 9 条, URL 抓取 0 条

## 2. 客观事实(基于真实互动数据)

### 2.1 社区分布
- r/learnprogramming: 8 条

### 2.2 评分分布
- high(>=50): 4
- mid(10-49): 0
- low(<10): 3
- unknown: 2

### 2.3 评论数分布
- 0: 0
- 1-5: 1
- 6-20: 2
- 21+: 4
- unknown: 2

### 2.4 表现分层(基于本批内评分基线)
- high: 7

### 2.5 高分 Top 3
- [3394] When you finally fix a bug after 4 hours and it was a missing semicolon (r/learnprogramming) [详情](item_id=c202b43c-4623-431e-a021-fdfcd31fb52f)
- [1827] I spent 6 months grinding LeetCode and here's what I'd do differently (r/learnprogramming) [详情](item_id=4d81c72d-c5e0-412f-a77c-37525b1e68d8)
- [895] After 3 months of struggling, I finally understood pointers in C. Here's what cl (r/learnprogramming) [详情](item_id=f677ce3a-a49e-4e28-9156-5751f5c7e5d4)

### 2.6 低分 Top 3
- [-36] My new app makes learning Python 10x faster! Free beta access inside (r/learnprogramming) [详情](item_id=4b04a374-f6c4-4775-8433-c06902effff3)
- [3] Check out my new course on learning to code fast! (r/learnprogramming) [详情](item_id=4206a772-6e44-481c-905c-b4864eb66bac)
- [5]  (r/learnprogramming) [详情](item_id=5540b48f-0c39-4dff-ba22-2587a3116282)

## 3. AI 推断(基于内容标签 + LLM 判断)

> 注:以下为 AI 对内容的标签化判断,非客观事实。verdict 反映 AI 认为该内容是否适合该社区。

### 3.1 Verdict 分布
- fit: 4
- not_fit: 2
- fit_after_fix: 1

### 3.2 主题分布(topic_tags)
- python: 3
- c_language: 1
- debugging: 1
- career: 1
- general: 1

### 3.3 内容结构分布
- experience: 3
- promotional: 2
- question: 2
- general: 2
- resource_share: 1

### 3.4 产品露出程度分布
- none: 5
- promotional: 2

### 3.5 搜索价值分布
- mid: 5
- low: 2

## 4. 本批引用的规律(KnowledgePattern)

> 注:规律状态标注其验证程度。`candidate`=待验证,`fire/supported`=多案例支持,`refuted`=被反例推翻。
- `9ff22fc6-763f-4236-b5db-59d0d6f8b790` [fire/candidate] samples=15: mid tier 帖子中,experience 结构出现 14/15 次。代表性帖子: The underrated skill that made me 10x faster: reading stack traces
- `8c72252b-2e59-4ea0-8553-805fc4ac9a9e` [fire/candidate] samples=8: high tier 帖子中,experience 结构出现 8/8 次。代表性帖子: I kept getting stuck on recursion until I tried this one approach
- `869d3a58-e000-4f5f-94c4-ea24fc2aa17e` [failure/candidate] samples=8: low tier 帖子中,experience 结构出现 6/8 次。代表性帖子: Best language to learn?

## 5. 业务观察(客观事实 + AI 推断的综合解读)

### 5.1 高分案例特征(score>=50)
- [895] After 3 months of struggling, I finally understood pointers  (r/learnprogramming) verdict=fit
- [3394] When you finally fix a bug after 4 hours and it was a missin (r/learnprogramming) verdict=fit
- [1827] I spent 6 months grinding LeetCode and here's what I'd do di (r/learnprogramming) verdict=fit

### 5.2 低分案例特征(score<10)
- [3] Check out my new course on learning to code fast! (r/learnprogramming) verdict=not_fit
- [-36] My new app makes learning Python 10x faster! Free beta acces (r/learnprogramming) verdict=not_fit
- [5]  (r/learnprogramming) verdict=fit_after_fix

### 5.3 产品植入观察
- 无产品露出(none): 5 (100%)
- 隐性植入(subtle): 0 (0%)
- 显性植入(explicit): 0 (0%)

## 6. NIIMBOT 后续 Reddit 内容规划建议

> 以下建议基于本批数据的客观事实 + AI 推断,**非定论**,需结合更多样本验证。

1. 高分帖子中存在 AI 判为 fit 的内容,可作为后续内容参考方向
2. 有 1 条帖子缺失 subreddit 字段,无法做社区差异分析,后续采集需补齐
3. 本批含提问型/经验型内容,这两类在 Reddit 通常接受度较高,可作为 NIIMBOT 后续内容的主结构方向

---

**免责声明**:
- 客观事实部分(评分/评论数/tier)来自导入数据,如实反映历史互动表现
- AI 推断部分(verdict/标签)由 LLM 生成,反映模型对内容的判断,不等于客观正确
- 规律部分来自已有 KnowledgePattern,其状态反映多案例验证程度,单条结果不改变规律状态
- 历史互动数据不能直接证明 AI 事前预测准确;单条案例不能直接定性为普遍规律
- 所有案例可通过 `GET /batch/items/{item_id}` 查看原始数据与分析详情
- 明细数据可通过 `GET /batch/{job_id}/export?format=csv` 导出