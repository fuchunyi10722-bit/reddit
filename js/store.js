/**
 * 存储层（store.js）
 *
 * 职责：
 *  - localStorage 持久化（帖子、评论、规律库、评估记录）
 *  - Post ID 去重：同一条 Reddit 内容只录入一次
 *  - 数据追加更新：在已有 Post ID 下持续补充 Score / Comments / Views / 新评论，
 *    无需重复录入帖子正文
 *  - 数据导入：CSV / 批量粘贴解析
 *  - 数据清洗与去重（评论按 author+text 去重）
 *
 * 数据层级：
 *  - 原始数据：posts / comments（用户录入或导入，不修改）
 *  - 分析结果：postAnalyses / commentAnalyses（由 analyzer 生成，可重建）
 *  - 规律库：patterns（由 analyzer 沉淀，可重建）
 *  - 评估记录：evaluations（用户每次发布前评估的快照）
 */

(function (global) {
  'use strict';

  const STORAGE_KEY = 'reddit_analyzer_v1';
  const SCHEMA_VERSION = 1;

  // ---------- 默认空状态 ----------
  function emptyState() {
    return {
      schemaVersion: SCHEMA_VERSION,
      meta: { isMock: false, label: '自定义数据', note: '' },
      brandKeywords: [],   // 用户配置的品牌词（覆盖自动识别）
      timeRange: 'month',  // 全局时间筛选：all | week | month | last30 | custom
      customRange: { start: '', end: '' },
      posts: [],
      comments: [],
      communityPosts: [],  // 社区基准帖子（非 NIIMBOT 数据，用于整体表现基准对比）
      postAnalyses: {},
      commentAnalyses: {},
      patterns: [],
      evaluations: [],
      updatedAt: null
    };
  }

  // ---------- 持久化读写 ----------
  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.schemaVersion !== SCHEMA_VERSION) return null;
      // 向后兼容：旧版本 1 缓存可能缺少 communityPosts 字段
      if (!Array.isArray(parsed.communityPosts)) parsed.communityPosts = [];
      return parsed;
    } catch (e) {
      console.warn('[store] load failed:', e);
      return null;
    }
  }

  function save(state) {
    state.updatedAt = new Date().toISOString();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      return true;
    } catch (e) {
      console.error('[store] save failed:', e);
      return false;
    }
  }

  // ---------- 内存状态 ----------
  // state 在 initializeState() 中初始化，不再此处赋值
  let state;

  function getState() { return state; }

  function persist() { return save(state); }

  function replaceState(newState) {
    state = newState;
    return persist();
  }

  // ---------- 重置 / 初始化 ----------
  function resetToEmpty() {
    state = emptyState();
    persist();
    return state;
  }

  function loadDemoData() {
    const demo = global.DEMO_DATA;
    if (!demo) throw new Error('未找到模拟数据 (DEMO_DATA)');
    const next = emptyState();
    next.meta = { ...demo.meta };
    next.posts = JSON.parse(JSON.stringify(demo.posts));
    next.comments = JSON.parse(JSON.stringify(demo.comments));
    state = next;
    persist();
    return state;
  }

  /**
   * 初始化 Store：
   * 1. 先读 localStorage 缓存
   * 2. 如果缓存存在，对比 DEMO_DATA.meta.version 和缓存 meta.version
   * 3. 版本不同或缓存无 version → 自动用最新真实数据覆盖
   * 4. 缓存为空 → 加载真实数据
   */
  function initializeState() {
    const cached = load();
    const demo = global.DEMO_DATA;
    if (!demo) {
      state = cached || emptyState();
      return;
    }
    const demoVersion = demo.meta && demo.meta.version;
    const cachedVersion = cached && cached.meta && cached.meta.version;
    if (!cached) {
      // 无缓存，直接加载真实数据
      loadDemoData();
      return;
    }
    if (!demoVersion) {
      // DEMO_DATA 无版本号（极旧），保持缓存
      state = cached;
      return;
    }
    if (demoVersion !== cachedVersion) {
      // 版本不一致，自动使用最新真实数据覆盖
      state = cached; // 先保留缓存，loadDemoData 会覆盖
      loadDemoData();
      return;
    }
    // 版本一致，使用缓存
    state = cached;
  }

  // 初始化
  initializeState();

  // ---------- Post ID 生成与去重 ----------
  function generatePostId(existingIds) {
    const ids = new Set(existingIds || state.posts.map(p => p.id));
    let i = state.posts.length + 1;
    let candidate;
    do {
      candidate = 'P-' + String(i).padStart(4, '0');
      i++;
    } while (ids.has(candidate));
    return candidate;
  }

  /**
   * 录入或更新一条帖子。
   * - 若 id 已存在：仅更新 score / comments / views / 正文（若提供），保留原 id
   * - 若 id 不存在：作为新帖子录入
   * - 若未提供 id：自动生成
   */
  function upsertPost(post) {
    if (!post || !post.title) throw new Error('帖子缺少 title');
    const id = post.id || generatePostId();
    let existing = state.posts.find(p => p.id === id);

    if (existing) {
      existing.subreddit = post.subreddit || existing.subreddit;
      existing.title = post.title || existing.title;
      if (post.body !== undefined && post.body !== '') existing.body = post.body;
      if (post.postedAt) existing.postedAt = post.postedAt;
      if (post.url) existing.url = post.url;
      if (typeof post.likes === 'number') existing.likes = post.likes;
      if (typeof post.comments === 'number') existing.comments = post.comments;
      if (typeof post.views === 'number') existing.views = post.views;
      if (typeof post.analysisScore === 'number') existing.analysisScore = post.analysisScore;
      if (post.analysisDiff !== undefined) existing.analysisDiff = post.analysisDiff;
      if (post.analysisEvaluatedAt) existing.analysisEvaluatedAt = post.analysisEvaluatedAt;
      if (typeof post.predictedScore === 'number') existing.predictedScore = post.predictedScore;
      else if (post.predictedScore === null) existing.predictedScore = undefined;
      if (typeof post.hasImage === 'boolean') existing.hasImage = post.hasImage;
      if (typeof post.imageQuality === 'boolean') existing.imageQuality = post.imageQuality;
      if (post.imageDescription !== undefined) existing.imageDescription = post.imageDescription;
      // 品牌身份与发布状态
      if (typeof post.isPublished === 'boolean') existing.isPublished = post.isPublished;
      if (post.authorType) existing.authorType = post.authorType;
      if (post.brandRelation) existing.brandRelation = post.brandRelation;
      existing.updatedAt = new Date().toISOString();
      persist();
      return { post: existing, isNew: false };
    }

    const newPost = {
      id,
      subreddit: post.subreddit || 'unknown',
      title: post.title,
      body: post.body || '',
      postedAt: post.postedAt || post.publishedAt || new Date().toISOString(),
      url: post.url || '',
      likes: typeof post.likes === 'number' ? post.likes : (typeof post.score === 'number' ? post.score : 0),
      comments: typeof post.comments === 'number' ? post.comments : 0,
      views: typeof post.views === 'number' ? post.views : 0,
      predictedScore: post.predictedScore != null ? post.predictedScore : undefined,
      hasImage: typeof post.hasImage === 'boolean' ? post.hasImage : false,
      imageQuality: typeof post.imageQuality === 'boolean' ? post.imageQuality : false,
      imageDescription: post.imageDescription || '',
      // 品牌身份与发布状态
      isPublished: typeof post.isPublished === 'boolean' ? post.isPublished : true,
      authorType: post.authorType || 'community',
      brandRelation: post.brandRelation || 'none',
      analysisScore: typeof post.analysisScore === 'number' ? post.analysisScore : undefined,
      analysisDiff: post.analysisDiff || null,
      analysisEvaluatedAt: post.analysisEvaluatedAt || null,
      importedAt: new Date().toISOString()
    };
    state.posts.push(newPost);
    persist();
    return { post: newPost, isNew: true };
  }

  /**
   * 录入评论。去重规则：同一 postId 下 author+text 已存在则跳过（更新 score）。
   */
  function upsertComment(comment) {
    if (!comment || !comment.postId) throw new Error('评论缺少 postId');
    const postExists = state.posts.some(p => p.id === comment.postId);
    if (!postExists) throw new Error('评论关联的帖子不存在: ' + comment.postId);

    const existing = state.comments.find(c =>
      c.postId === comment.postId &&
      c.author === comment.author &&
      c.text === comment.text
    );

    if (existing) {
      if (typeof comment.score === 'number') existing.score = comment.score;
      if (typeof comment.likes === 'number') existing.likes = comment.likes;
      if (typeof comment.replyCount === 'number') existing.replyCount = comment.replyCount;
      if (typeof comment.level === 'number') existing.level = comment.level;
      if (comment.parentCommentId !== undefined) existing.parentCommentId = comment.parentCommentId;
      if (typeof comment.mentionsBrand === 'boolean') existing.mentionsBrand = comment.mentionsBrand;
      if (typeof comment.mentionsCompetitor === 'boolean') existing.mentionsCompetitor = comment.mentionsCompetitor;
      if (comment.competitorName !== undefined) existing.competitorName = comment.competitorName;
      if (comment.userNeed !== undefined) existing.userNeed = comment.userNeed;
      if (comment.useCase !== undefined) existing.useCase = comment.useCase;
      persist();
      return { comment: existing, isNew: false };
    }

    const newComment = {
      id: comment.id || 'C-' + Date.now() + '-' + Math.floor(Math.random() * 1000),
      postId: comment.postId,
      author: comment.author || 'u/anonymous',
      text: comment.text,
      score: typeof comment.score === 'number' ? comment.score : 1,
      // 评论深度与层级
      likes: typeof comment.likes === 'number' ? comment.likes : 0,
      replyCount: typeof comment.replyCount === 'number' ? comment.replyCount : 0,
      level: typeof comment.level === 'number' ? comment.level : 0,
      parentCommentId: comment.parentCommentId || null,
      // 品牌与竞品分析
      mentionsBrand: typeof comment.mentionsBrand === 'boolean' ? comment.mentionsBrand : false,
      mentionsCompetitor: typeof comment.mentionsCompetitor === 'boolean' ? comment.mentionsCompetitor : false,
      competitorName: comment.competitorName || '',
      // 用户需求与使用场景
      userNeed: comment.userNeed || '',
      useCase: comment.useCase || '',
      createdAt: comment.createdAt || new Date().toISOString()
    };
    state.comments.push(newComment);
    persist();
    return { comment: newComment, isNew: true };
  }

  // ---------- 查询 ----------
  function getPost(postId) {
    return state.posts.find(p => p.id === postId) || null;
  }

  function getCommentsByPost(postId) {
    return state.comments.filter(c => c.postId === postId);
  }

  function getPostsWithComments() {
    return state.posts.map(p => ({
      ...p,
      _comments: state.comments.filter(c => c.postId === p.id)
    }));
  }

  function getSubreddits() {
    return Array.from(new Set(state.posts.map(p => p.subreddit))).sort();
  }

  function getCommentsBySubreddit(subreddit) {
    const postIds = new Set(state.posts.filter(p => p.subreddit === subreddit).map(p => p.id));
    return state.comments.filter(c => postIds.has(c.postId));
  }

  // ---------- 分析结果 / 规律库 / 评估记录 ----------
  function setPostAnalysis(postId, analysis) {
    state.postAnalyses[postId] = analysis;
    persist();
  }

  function getPostAnalysis(postId) {
    return state.postAnalyses[postId] || null;
  }

  function setCommentAnalysis(subreddit, analysis) {
    state.commentAnalyses[subreddit] = analysis;
    persist();
  }

  function getCommentAnalysis(subreddit) {
    return state.commentAnalyses[subreddit] || null;
  }

  function setPatterns(patterns) {
    state.patterns = patterns;
    persist();
  }

  function getPatterns() {
    return state.patterns || [];
  }

  function addEvaluation(evaluation) {
    state.evaluations.unshift({
      id: 'E-' + Date.now(),
      createdAt: new Date().toISOString(),
      ...evaluation
    });
    // 仅保留最近 50 条评估记录
    state.evaluations = state.evaluations.slice(0, 50);
    persist();
  }

  function getEvaluations() {
    return state.evaluations || [];
  }

  // ---------- 品牌词配置 ----------
  function getBrandKeywords() {
    return state.brandKeywords || [];
  }

  function setBrandKeywords(keywords) {
    state.brandKeywords = (Array.isArray(keywords) ? keywords : [])
      .map(k => String(k).trim()).filter(k => k);
    persist();
    return state.brandKeywords;
  }

  // ---------- 时间筛选 ----------
  function getTimeRange() {
    return { range: state.timeRange || 'month', custom: state.customRange || { start: '', end: '' } };
  }

  function setTimeRange(range, custom) {
    state.timeRange = range;
    if (custom) state.customRange = custom;
    persist();
    return getTimeRange();
  }

  /**
   * 按当前时间筛选范围过滤帖子。
   * range: all | week | month | last30 | custom
   * 返回 { posts, postIds(集合), comments }
   */
  function getFilteredData() {
    const { range, custom } = getTimeRange();
    const now = new Date();
    let start = null, end = null;
    if (range === 'week') {
      const day = now.getDay() || 7; // 周日=0 转 7
      start = new Date(now); start.setHours(0, 0, 0, 0);
      start.setDate(start.getDate() - (day - 1));
      end = now;
    } else if (range === 'month') {
      start = new Date(now.getFullYear(), now.getMonth(), 1);
      end = now;
    } else if (range === 'last30') {
      start = new Date(now); start.setDate(start.getDate() - 30);
      end = now;
    } else if (range === 'custom') {
      if (custom && custom.start) start = new Date(custom.start);
      if (custom && custom.end) {
        end = new Date(custom.end);
        end.setHours(23, 59, 59, 999);
      }
    }
    // all 或解析失败 → 不过滤
    if (!start && !end) {
      return { posts: state.posts, postIds: new Set(state.posts.map(p => p.id)), comments: state.comments, filtered: false };
    }
    const filtered = state.posts.filter(p => {
      const t = new Date(p.postedAt || p.importedAt || Date.now());
      if (start && t < start) return false;
      if (end && t > end) return false;
      return true;
    });
    const postIds = new Set(filtered.map(p => p.id));
    const comments = state.comments.filter(c => postIds.has(c.postId));
    return { posts: filtered, postIds, comments, filtered: true, rangeStart: start, rangeEnd: end };
  }

  /**
   * 时间范围描述（用于 UI 显示）
   */
  function getTimeRangeDescription() {
    const { range, custom } = getTimeRange();
    const now = new Date();
    const fmt = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    if (range === 'all') return '全部时间';
    if (range === 'week') {
      const day = now.getDay() || 7;
      const start = new Date(now); start.setHours(0, 0, 0, 0); start.setDate(start.getDate() - (day - 1));
      return `本周（${fmt(start)} ~ ${fmt(now)}）`;
    }
    if (range === 'month') {
      const start = new Date(now.getFullYear(), now.getMonth(), 1);
      return `本月（${fmt(start)} ~ ${fmt(now)}）`;
    }
    if (range === 'last30') {
      const start = new Date(now); start.setDate(start.getDate() - 30);
      return `近 30 天（${fmt(start)} ~ ${fmt(now)}）`;
    }
    if (range === 'custom') {
      return `自定义（${custom.start || '?'} ~ ${custom.end || '?'}）`;
    }
    return '';
  }

  // ---------- 导入解析 ----------
  /**
   * 解析 CSV 文本为帖子数组。
   * 期望表头（不区分大小写）：
   *  id, subreddit, title, body, postedAt, url, likes, comments, views
   * body 字段可包含换行（需用双引号包裹）。
   */
  function parseCsvPosts(csvText) {
    const rows = csvToRows(csvText);
    if (rows.length < 2) throw new Error('CSV 数据为空或缺少表头');
    const headers = rows[0].map(h => h.trim().toLowerCase());
    const idx = (name) => headers.indexOf(name);
    const bool = (v) => {
      if (v == null || v === '') return undefined;
      const s = String(v).trim().toLowerCase();
      if (['1', 'true', 'yes', 'y', '是', '优质', '有', '有图'].includes(s)) return true;
      if (['0', 'false', 'no', 'n', '否', '无', '没', '没图'].includes(s)) return false;
      return undefined;
    };
    const str = (v) => (v != null ? String(v).trim() : '');
    // brandRelation 标准化
    const normalizeBrandRelation = (v) => {
      const s = str(v).toLowerCase();
      if (['official', '官方'].includes(s)) return 'official';
      if (['promotional', '推广', 'promote'].includes(s)) return 'promotional';
      if (['organic_mention', 'organic', '自然提及', '提及'].includes(s)) return 'organic_mention';
      return 'none';
    };

    // 检测是否为 Dashboard 格式（有 Title 和 Content 列）
    const isDashboard = idx('title') >= 0 && idx('content') >= 0;
    // Dashboard 格式：Comments 列可能出现多次，第 1 个是数量，后续是评论内容
    const commentColIndices = [];
    if (isDashboard) {
      headers.forEach((h, i) => { if (h === 'comments') commentColIndices.push(i); });
    }

    const posts = [];
    const embeddedComments = []; // {postTitle, text}
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i];
      if (!row || row.every(c => c === '')) continue;

      let post;
      if (isDashboard) {
        // Dashboard 格式解析
        const subredditRaw = str(row[idx('subreddit')] || '');
        const subreddit = subredditRaw.replace(/^r\//i, '').trim();
        const authorRaw = str(row[idx('author')] || '');
        // 判断 authorType：niimbot_official 社区 → official，其他 → personal
        const isOfficialSub = subreddit.toLowerCase() === 'niimbot_official';
        post = {
          id: undefined, // Dashboard 无 id，自动生成
          subreddit: subreddit,
          title: str(row[idx('title')] || ''),
          body: str(row[idx('content')] || ''),
          postedAt: str(row[idx('publishedat')] || row[idx('published at')] || row[idx('published_at')] || ''),
          url: str(row[idx('url')] || ''),
          likes: num(row[idx('upvotes')] || row[idx('likes')] || row[idx('score')]),
          comments: num(row[idx('comments')]),
          views: num(row[idx('views')] || row[idx('impressions')]),
          hasImage: false,
          imageQuality: false,
          imageDescription: '',
          predictedScore: undefined,
          isPublished: str(row[idx('status')] || '').toLowerCase() !== 'draft',
          authorType: isOfficialSub ? 'official' : 'personal',
          brandRelation: isOfficialSub ? 'official' : 'promotional',
          author: authorRaw
        };
        // 提取嵌入评论（第 2 个及之后的 Comments 列）
        if (commentColIndices.length > 1) {
          for (let ci = 1; ci < commentColIndices.length; ci++) {
            const commentText = str(row[commentColIndices[ci]]);
            if (commentText) {
              embeddedComments.push({ postTitle: post.title, text: commentText });
            }
          }
        }
      } else {
        // 原有格式解析
        post = {
          id: row[idx('id')] || undefined,
          subreddit: row[idx('subreddit')] || '',
          title: row[idx('title')] || '',
          body: row[idx('body')] || row[idx('content')] || '',
          postedAt: row[idx('postedat')] || row[idx('posted_at')] || row[idx('publishedat')] || row[idx('published_at')] || '',
          url: row[idx('url')] || '',
          likes: num(row[idx('likes')] || row[idx('score')] || row[idx('upvotes')]),
          comments: num(row[idx('comments')]),
          views: num(row[idx('views')] || row[idx('impressions')]),
          hasImage: bool(row[idx('hasimage')] || row[idx('has_image')] || row[idx('image')]),
          imageQuality: bool(row[idx('imagequality')] || row[idx('image_quality')]),
          imageDescription: str(row[idx('imagedescription')] || row[idx('image_description')]),
          predictedScore: num(row[idx('predictedscore')] || row[idx('predicted_score')]),
          isPublished: bool(row[idx('ispublished')] || row[idx('is_published')]),
          authorType: str(row[idx('authortype')] || row[idx('author_type')]),
          brandRelation: normalizeBrandRelation(row[idx('brandrelation')] || row[idx('brand_relation')])
        };
        // hasImage=false 时强制 imageQuality=false
        if (post.hasImage === false) post.imageQuality = false;
        // 默认 isPublished=true
        if (post.isPublished === undefined) post.isPublished = true;
        // authorType 标准化
        const at = (post.authorType || '').toLowerCase();
        if (['official', '官方', 'niimbot'].includes(at)) post.authorType = 'official';
        else if (['personal', '个人', '推广'].includes(at)) post.authorType = 'personal';
        else if (['third_party', '第三方', '别人'].includes(at)) post.authorType = 'third_party';
        else post.authorType = 'community';
        // brandRelation 默认推断
        if (!post.brandRelation || post.brandRelation === 'none') {
          if (post.authorType === 'official') post.brandRelation = 'official';
          else if (post.authorType === 'personal') post.brandRelation = 'promotional';
          else if (post.authorType === 'third_party') post.brandRelation = 'organic_mention';
        }
      }
      if (post.title) posts.push(post);
    }

    // 如果有嵌入评论，存到全局供 importPosts 后使用
    if (embeddedComments.length > 0) {
      global.__pendingEmbeddedComments = embeddedComments;
    }
    return posts;
  }

  /**
   * 解析 CSV 文本为评论数组。
   * 期望表头：postId, body/text, isAuthor, likes, replyCount, level,
   *           parentCommentId, mentionsBrand, mentionsCompetitor,
   *           competitorName, userNeed, useCase
   * （兼容旧格式 author, score）
   */
  function parseCsvComments(csvText) {
    const rows = csvToRows(csvText);
    if (rows.length < 2) throw new Error('CSV 数据为空或缺少表头');
    const headers = rows[0].map(h => h.trim().toLowerCase());
    const idx = (name) => headers.indexOf(name);
    const bool = (v) => {
      if (v == null || v === '') return false;
      const s = String(v).trim().toLowerCase();
      return ['1', 'true', 'yes', 'y', '是', '作者', 'op'].includes(s);
    };
    const boolNullable = (v) => {
      if (v == null || v === '') return undefined;
      const s = String(v).trim().toLowerCase();
      if (['1', 'true', 'yes', 'y', '是'].includes(s)) return true;
      if (['0', 'false', 'no', 'n', '否'].includes(s)) return false;
      return undefined;
    };
    const str = (v) => (v != null ? String(v).trim() : '');
    const comments = [];
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i];
      if (!row || row.every(c => c === '')) continue;
      const rawAuthor = (row[idx('author')] || '').trim();
      const rawIsAuthor = row[idx('isauthor')] || row[idx('is_author')];
      let isAuthor = bool(rawIsAuthor);
      if (rawIsAuthor == null || rawIsAuthor === '') {
        const a = rawAuthor.toLowerCase();
        isAuthor = a === 'u/作者' || a === 'op' || a === '作者' || a.indexOf('author') !== -1;
      }
      const comment = {
        id: row[idx('id')] || undefined,
        postId: row[idx('postid')] || row[idx('post_id')] || '',
        author: isAuthor ? 'u/作者' : 'u/受众',
        text: row[idx('text')] || row[idx('body')] || row[idx('comment')] || '',
        score: 1,
        // 评论深度与层级
        likes: num(row[idx('likes')] || row[idx('upvotes')]) || 0,
        replyCount: num(row[idx('replycount')] || row[idx('reply_count')]) || 0,
        level: num(row[idx('level')]) || 0,
        parentCommentId: str(row[idx('parentcommentid')] || row[idx('parent_comment_id')]) || null,
        // 品牌与竞品分析
        mentionsBrand: boolNullable(row[idx('mentionsbrand')] || row[idx('mentions_brand')]) ?? false,
        mentionsCompetitor: boolNullable(row[idx('mentionscompetitor')] || row[idx('mentions_competitor')]) ?? false,
        competitorName: str(row[idx('competitorname')] || row[idx('competitor_name')]),
        // 用户需求与使用场景
        userNeed: str(row[idx('userneed')] || row[idx('user_need')]),
        useCase: str(row[idx('usecase')] || row[idx('use_case')] || row[idx('scenario')])
      };
      if (comment.postId && comment.text) comments.push(comment);
    }
    return comments;
  }

  /**
   * 批量导入帖子（去重 + 追加更新）。
   * 返回 { added, updated, skipped } 统计。
   */
  function importPosts(posts) {
    let added = 0, updated = 0, skipped = 0;
    for (const p of posts) {
      if (!p.title) { skipped++; continue; }
      const result = upsertPost(p);
      if (result.isNew) added++; else updated++;
    }
    return { added, updated, skipped };
  }

  function importComments(comments) {
    let added = 0, updated = 0, skipped = 0;
    for (const c of comments) {
      if (!c.postId || !c.text) { skipped++; continue; }
      const postExists = state.posts.some(p => p.id === c.postId);
      if (!postExists) { skipped++; continue; }
      const result = upsertComment(c);
      if (result.isNew) added++; else updated++;
    }
    return { added, updated, skipped };
  }

  // ---------- CSV 工具 ----------
  function csvToRows(text) {
    // 简易 CSV 解析：支持双引号包裹的字段（含换行）和转义双引号 ""
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (inQuotes) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else { inQuotes = false; }
        } else {
          field += ch;
        }
      } else {
        if (ch === '"') { inQuotes = true; }
        else if (ch === ',') { row.push(field); field = ''; }
        else if (ch === '\n' || ch === '\r') {
          if (ch === '\r' && text[i + 1] === '\n') i++;
          row.push(field);
          if (row.some(c => c !== '')) rows.push(row);
          row = []; field = '';
        } else {
          field += ch;
        }
      }
    }
    if (field !== '' || row.length) { row.push(field); if (row.some(c => c !== '')) rows.push(row); }
    return rows;
  }

  function num(v) {
    if (v === undefined || v === null || v === '') return undefined;
    const n = Number(String(v).replace(/[,%\s]/g, ''));
    return isNaN(n) ? undefined : n;
  }

  // ---------- 社区基准数据 ----------
  /**
   * 导入社区基准帖子（非 NIIMBOT 自己发的，用于整体表现基准对比）。
   * 去重规则：按 url 优先去重，url 为空时按 title（不区分大小写）去重。
   * 返回 { added, skipped }
   */
  function importCommunityPosts(posts) {
    let added = 0, skipped = 0;
    if (!Array.isArray(posts)) return { added, skipped };
    const existing = state.communityPosts || [];
    const urlSet = new Set(existing.map(p => (p.url || '').trim()).filter(u => u));
    const titleSet = new Set(existing.map(p => (p.title || '').toLowerCase().trim()).filter(t => t));
    for (const p of posts) {
      if (!p || !p.title) { skipped++; continue; }
      const url = (p.url || '').trim();
      const titleLower = (p.title || '').toLowerCase().trim();
      const dup = (url && urlSet.has(url)) || (!url && titleLower && titleSet.has(titleLower));
      if (dup) { skipped++; continue; }
      const item = {
        subreddit: p.subreddit || 'unknown',
        title: p.title,
        body: p.body || '',
        postedAt: p.postedAt || p.publishedAt || new Date().toISOString(),
        url,
        likes: typeof p.likes === 'number' ? p.likes : (typeof p.upvotes === 'number' ? p.upvotes : (typeof p.score === 'number' ? p.score : 0)),
        comments: typeof p.comments === 'number' ? p.comments : 0,
        views: typeof p.views === 'number' ? p.views : 0,
        author: p.author || '',
        importedAt: new Date().toISOString()
      };
      existing.push(item);
      if (url) urlSet.add(url);
      if (titleLower) titleSet.add(titleLower);
      added++;
    }
    state.communityPosts = existing;
    persist();
    return { added, skipped };
  }

  /**
   * 按 subreddit 分组统计社区基准数据。
   * 返回 { subreddit: { postCount, views: {avg,median,max}, upvotes: {avg,median,max}, comments: {avg,median,max} } }
   */
  function getCommunityStats() {
    const arr = state.communityPosts || [];
    const groups = {};
    arr.forEach(p => {
      const sub = p.subreddit || 'unknown';
      if (!groups[sub]) groups[sub] = [];
      groups[sub].push(p);
    });
    const stats = {};
    Object.keys(groups).forEach(sub => {
      const list = groups[sub];
      const views = list.map(p => (typeof p.views === 'number' ? p.views : 0));
      const upvotes = list.map(p => (typeof p.likes === 'number' ? p.likes : 0));
      const comments = list.map(p => (typeof p.comments === 'number' ? p.comments : 0));
      stats[sub] = {
        postCount: list.length,
        views: { avg: avgOf(views), median: medianOf(views), max: maxOf(views) },
        upvotes: { avg: avgOf(upvotes), median: medianOf(upvotes), max: maxOf(upvotes) },
        comments: { avg: avgOf(comments), median: medianOf(comments), max: maxOf(comments) }
      };
    });
    return stats;
  }

  function clearCommunityData() {
    state.communityPosts = [];
    persist();
  }

  function avgOf(arr) {
    if (!arr.length) return 0;
    return arr.reduce((s, n) => s + n, 0) / arr.length;
  }

  function medianOf(arr) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  function maxOf(arr) {
    if (!arr.length) return 0;
    return Math.max(...arr);
  }

  // ---------- 导出 ----------
  global.Store = {
    load, save, getState, persist, replaceState,
    resetToEmpty, loadDemoData,
    upsertPost, upsertComment,
    getPost, getCommentsByPost, getPostsWithComments,
    getSubreddits, getCommentsBySubreddit,
    setPostAnalysis, getPostAnalysis,
    setCommentAnalysis, getCommentAnalysis,
    setPatterns, getPatterns,
    addEvaluation, getEvaluations,
    getBrandKeywords, setBrandKeywords,
    getTimeRange, setTimeRange, getFilteredData, getTimeRangeDescription,
    parseCsvPosts, parseCsvComments,
    importPosts, importComments,
    importCommunityPosts, getCommunityStats, clearCommunityData,
    generatePostId
  };
})(window);
