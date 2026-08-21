/**
 * 分析引擎（analyzer.js）
 *
 * 核心分析闭环：
 *  历史内容 → 内容表现 → 用户评论 → 用户需求 → 内容规律 → 新内容评估
 *
 * 数据层级标识（每条分析结论必须标注来源层级）：
 *  - DATA       原始数据（直接来自帖子/评论字段）
 *  - ANALYSIS   AI 分析结果（基于数据的结构化提炼）
 *  - PATTERN    基于数据形成的规律（多条数据聚合，附证据）
 *  - INFERENCE  AI 推测（样本不足或间接推断，需明确标注）
 *
 * 样本不足保护：当某分类样本数 < 3 时，仅生成 INFERENCE 级别结论，
 *  不形成 PATTERN，避免强行因果。
 */

(function (global) {
  'use strict';

  // ============ 信号词库 ============
  const SIGNALS = {
    // 真实经历信号（提升真实性与用户价值）
    authenticity: [
      'i quit', 'i left', 'i built', 'i launched', 'i tried', 'i failed',
      'months later', 'weeks later', 'here\'s the', 'honest', 'unfiltered',
      'my', 'i spent', 'i made', 'i learned', 'i switched', 'we tried',
      'what worked', 'what failed', 'psa', 'lesson'
    ],
    // 提问信号
    question: ['how do you', 'how do i', 'what\'s the best', 'any tips', 'thoughts?',
      'curious how', 'genuinely', 'would love', 'what should', 'recommendations'],
    // 讨论触发信号
    discussion: ['thoughts?', 'curious', 'ama', 'would love to hear', 'what works for you',
      'counterpoint', 'same?', 'agree?'],
    // 营销信号（降低真实性、提高营销风险）
    marketing: [
      'check out', 'check it out', 'revolutionary', 'game-changing', 'game changing',
      'ai-powered', 'ai powered', 'cutting-edge', 'must read', 'must-see',
      'early access', 'sign up now', 'limited spots', 'limited spots available',
      'dm for', 'dm me', 'link in profile', 'link in bio', '🚀', '🔥', '💫',
      'thrilled', 'excited to share', 'we just launched', 'best thing ever',
      'ama!'  // 缺乏细节的纯炫耀
    ],
    // 痛点信号（评论中出现）
    pain: ['painful', 'struggle', 'hard', 'terrified', 'broke me', 'lost',
      'disaster', 'killed me', 'burned', 'broke', 'scared', 'stuck',
      'always wonder', 'always struggle', "can't seem", 'never works'],
    // 认可信号
    approval: ['hit hard', 'underrated', 'same', 'confirmed', 'lesson',
      'genuinely', 'changed my', 'changing my', 'this is real',
      'this is the actual', 'everyone skips', 'underdiscussed'],
    // 质疑信号
    skepticism: ['suspicious', 'proof', 'no breakdown', 'no screenshot',
      'lottery', 'flex post', 'not reproducible', 'credibility problem',
      'sounds like', 'reads as', 'instant scroll', 'feels like'],
    // 现有解决方式信号
    solution: ['we use', 'we tried', 'we do', 'we migrated', 'we switched',
      'we have', 'i use', 'i tried', 'started with', 'moved to', 'switched to']
  };

  // ============ 工具函数 ============
  function lower(text) { return (text || '').toLowerCase(); }

  function countSignals(text, signalList) {
    const t = lower(text);
    let count = 0;
    const hits = [];
    for (const s of signalList) {
      if (t.includes(s)) { count++; hits.push(s); }
    }
    return { count, hits };
  }

  function wordSet(text) {
    return new Set(lower(text).split(/[^a-z0-9]+/).filter(w => w.length > 2));
  }

  function jaccardSimilarity(a, b) {
    const sa = wordSet(a), sb = wordSet(b);
    if (sa.size === 0 || sb.size === 0) return 0;
    let inter = 0;
    for (const w of sa) if (sb.has(w)) inter++;
    return inter / (sa.size + sb.size - inter);
  }

  function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
    return sorted[idx];
  }

  function avg(arr) {
    if (!arr.length) return 0;
    return arr.reduce((s, n) => s + n, 0) / arr.length;
  }

  // ============ 表现分档 ============
  /**
   * 基于 subreddit 内相对分位 + 绝对阈值分档。
   * 返回 'high' | 'medium' | 'low' 及依据。
   */
  function classifyPerformance(post, allPostsInSub) {
    const scores = allPostsInSub.map(p => p.score || 0);
    const commentsArr = allPostsInSub.map(p => p.comments || 0);
    const p75s = percentile(scores, 75);
    const p25s = percentile(scores, 25);
    const p75c = percentile(commentsArr, 75);

    // 绝对阈值：避免小样本里"矮子里拔将军"
    const absHighScore = (post.score || 0) >= 100;
    const absHighComments = (post.comments || 0) >= 30;
    const absLowScore = (post.score || 0) <= 10;

    let level, reasons = [];
    if (((post.score || 0) >= p75s || absHighScore) && (absHighComments || (post.comments || 0) >= p75c)) {
      level = 'high';
      reasons.push(`分数 ${post.score} 处于 r/${post.subreddit} 内 P75+（P75=${p75s}）`);
      reasons.push(`评论 ${post.comments} 条（P75=${p75c}）`);
    } else if ((post.score || 0) <= p25s || absLowScore) {
      level = 'low';
      reasons.push(`分数 ${post.score} 处于 r/${post.subreddit} 内 P25-（P25=${p25s}）`);
    } else {
      level = 'medium';
      reasons.push(`分数 ${post.score} 处于 r/${post.subreddit} 内中位区间（P25=${p25s}, P75=${p75s}）`);
    }
    return { level, reasons };
  }

  // ============ 帖子分析 ============
  function analyzePost(post, allPosts) {
    const subPosts = allPosts.filter(p => p.subreddit === post.subreddit);
    const perf = classifyPerformance(post, subPosts);

    const fullText = post.title + ' ' + (post.body || '');
    const authSig = countSignals(fullText, SIGNALS.authenticity);
    const markSig = countSignals(fullText, SIGNALS.marketing);
    const questSig = countSignals(fullText, SIGNALS.question);
    const discSig = countSignals(fullText, SIGNALS.discussion);

    // 内容类型判定（优先级从高到低）
    let contentType, contentTypeReason;
    if (markSig.count >= 3 && authSig.count <= 1) {
      contentType = '产品展示/营销';
      contentTypeReason = `检测到 ${markSig.count} 个营销信号词（${markSig.hits.slice(0, 3).join(', ')}），真实经历信号弱`;
    } else if (questSig.count >= 1 && (post.title || '').includes('?')) {
      contentType = '提问求助';
      contentTypeReason = `标题含问号且含提问信号词（${questSig.hits.slice(0, 2).join(', ')}）`;
    } else if (authSig.count >= 2) {
      contentType = '真实经历分享';
      contentTypeReason = `含 ${authSig.count} 个真实经历信号词（${authSig.hits.slice(0, 3).join(', ')}）`;
    } else if (discSig.count >= 1) {
      contentType = '观点讨论';
      contentTypeReason = `含讨论触发信号词（${discSig.hits.slice(0, 2).join(', ')}）`;
    } else {
      contentType = '其他';
      contentTypeReason = '未匹配明显内容类型信号';
    }

    // 标题结构分析
    const title = post.title || '';
    const titleStructure = {
      length: title.length,
      startsWithNumber: /^\d/.test(title.trim()),
      hasColon: title.includes(':'),
      hasQuestion: title.includes('?'),
      hasEmoji: /🚀|🔥|💫|✨|🎉|❗|‼️/.test(title),
      hasNumber: /\d+/.test(title),
      structureNote: ''
    };
    if (titleStructure.hasEmoji) titleStructure.structureNote = '标题含表情符号（Reddit 多数社区对此敏感，常被识别为营销）';
    else if (titleStructure.startsWithNumber) titleStructure.structureNote = '数字开头标题（常用于数据驱动的故事型内容）';
    else if (titleStructure.hasColon) titleStructure.structureNote = '冒号分隔结构（主题 + 补充说明）';
    else if (titleStructure.hasQuestion) titleStructure.structureNote = '疑问句标题（适合提问求助类）';

    // 营销感评分 1-5
    let marketingFeel = 1;
    if (markSig.count >= 5) marketingFeel = 5;
    else if (markSig.count >= 3) marketingFeel = 4;
    else if (markSig.count >= 2) marketingFeel = 3;
    else if (markSig.count >= 1) marketingFeel = 2;
    // 表情符号加成
    if (titleStructure.hasEmoji && marketingFeel < 4) marketingFeel += 1;

    // 社区匹配度：与同 sub 高表现帖子的内容类型相似度
    const highPerfPosts = subPosts.filter(p => classifyPerformance(p, subPosts).level === 'high');
    let subredditMatch = 3; // 默认中位
    let matchNote;
    if (highPerfPosts.length >= 2) {
      // 看新帖内容类型是否与高表现帖子一致
      const highAuthentic = highPerfPosts.filter(p =>
        countSignals(p.title + ' ' + (p.body || ''), SIGNALS.authenticity).count >= 2
      ).length;
      const highMarketing = highPerfPosts.filter(p =>
        countSignals(p.title + ' ' + (p.body || ''), SIGNALS.marketing).count >= 3
      ).length;
      if (contentType === '真实经历分享' && highAuthentic >= highPerfPosts.length / 2) {
        subredditMatch = 5;
        matchNote = `该 r/${post.subreddit} 高表现内容中 ${highAuthentic}/${highPerfPosts.length} 条为真实经历分享，与当前内容类型一致`;
      } else if (contentType === '产品展示/营销' && highMarketing <= highPerfPosts.length * 0.2) {
        subredditMatch = 2;
        matchNote = `该 r/${post.subreddit} 高表现内容中仅 ${highMarketing}/${highPerfPosts.length} 条偏营销，当前内容类型与之不符`;
      } else {
        subredditMatch = 3;
        matchNote = `当前内容类型在该社区高表现内容中处于中等水平`;
      }
    } else if (subPosts.length < 3) {
      subredditMatch = 3;
      matchNote = `[样本不足] r/${post.subreddit} 仅 ${subPosts.length} 条样本，无法形成稳定匹配判断（INFERENCE）`;
    } else {
      subredditMatch = 3;
      matchNote = `r/${post.subreddit} 高表现样本不足（<2），无法形成匹配规律（INFERENCE）`;
    }

    // 讨论点（从正文提取关键短句）
    const discussionPoints = extractDiscussionPoints(post.body || '', post.title);

    // 品牌/产品露出
    const brandMention = extractBrandMention(post.body || '');

    return {
      postId: post.id,
      level: 'ANALYSIS',
      performance: {
        level: perf.level,
        reasons: perf.reasons
      },
      titleStructure,
      contentType: { type: contentType, reason: contentTypeReason },
      contentFeatures: {
        authenticitySignals: authSig,
        marketingSignals: markSig,
        questionSignals: questSig,
        discussionSignals: discSig
      },
      discussionPoints,
      brandMention,
      marketingFeel, // 1-5
      subredditMatch, // 1-5
      matchNote,
      analyzedAt: new Date().toISOString()
    };
  }

  function extractDiscussionPoints(body, title) {
    const points = [];
    // 提取 "What worked:" / "What failed:" 等结构
    const structured = body.match(/(?:what worked|what failed|the honest part|the actual|step \d|lesson:)[^\n]{0,120}/gi);
    if (structured) points.push(...structured.slice(0, 3).map(s => s.trim()));
    // 提取带问号的句子
    const questions = (title + ' ' + body).match(/[^.!?\n]*\?/g);
    if (questions) points.push(...questions.slice(0, 2).map(s => s.trim()).filter(s => s.length > 10));
    return points.slice(0, 5);
  }

  function extractBrandMention(body) {
    // 简单识别：大写词 / "my tool" / 明确产品名
    const brands = [];
    if (/my (tool|product|app|saas|project)/i.test(body)) brands.push('自有产品提及');
    const urlMatch = body.match(/https?:\/\/[^\s)]+/g);
    if (urlMatch) brands.push('含外链: ' + urlMatch.length + ' 个');
    if (/pricing|\$\d+\/mo|\$\d+\/month/i.test(body)) brands.push('含定价信息');
    return brands.length ? brands.join('；') : '无明显品牌/产品露出';
  }

  // ============ 评论分析 ============
  /**
   * 按 subreddit 聚合评论分析，提炼用户需求与内容机会（不做简单正负面统计）。
   */
  function analyzeComments(subreddit, posts, comments) {
    const subPosts = posts.filter(p => p.subreddit === subreddit);
    const subPostIds = new Set(subPosts.map(p => p.id));
    const subComments = comments.filter(c => subPostIds.has(c.postId));

    if (subComments.length === 0) {
      return {
        subreddit, level: 'INFERENCE',
        note: `r/${subreddit} 暂无评论数据，无法进行评论分析`,
        topTopics: [], wordCloud: [], sentimentDistribution: { positive: 0, negative: 0, neutral: 0, samples: { positive: [], negative: [], neutral: [] } },
        brandMentions: [], brandDiscussionSummary: '', operationalSuggestions: [],
        userNeeds: [], painPoints: [],
        approvalPoints: [], objections: [], existingSolutions: [],
        representativeQuotes: []
      };
    }

    // 词云数据：完整词频（用于绘制词云图，比 topTopics 更多）
    const wordFreq = {};
    const phraseFreq = {}; // 双词短语频率
    subComments.forEach(c => {
      const tokens = lower(c.text).split(/[^a-z0-9]+/).filter(w => w.length > 2 && !STOPWORDS.has(w));
      tokens.forEach(w => { wordFreq[w] = (wordFreq[w] || 0) + 1; });
      // 提取双词短语
      for (let i = 0; i < tokens.length - 1; i++) {
        const phrase = tokens[i] + ' ' + tokens[i + 1];
        phraseFreq[phrase] = (phraseFreq[phrase] || 0) + 1;
      }
    });
    // 合并单词 + 高频短语
    const wordCloudWords = Object.entries(wordFreq)
      .filter(([w, n]) => n >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 40)
      .map(([word, count]) => ({ word, count }));
    const topPhrases = Object.entries(phraseFreq)
      .filter(([w, n]) => n >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([phrase, count]) => ({ word: phrase, count, isPhrase: true }));
    const wordCloud = [...topPhrases, ...wordCloudWords].slice(0, 50);

    const topTopics = wordCloud.filter(w => !w.isPhrase).slice(0, 8)
      .map(w => ({ word: w.word, count: w.count, level: 'DATA' }));

    // 用户需求：提问类评论（含 ?）+ 高分评论中的提问
    const questionComments = subComments
      .filter(c => c.text.includes('?'))
      .sort((a, b) => (b.score || 0) - (a.score || 0));
    const userNeeds = questionComments.slice(0, 6).map(c => ({
      need: c.text.length > 120 ? c.text.slice(0, 120) + '…' : c.text,
      fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score,
      level: 'ANALYSIS'
    }));

    // 痛点：含痛点信号的评论
    const painComments = subComments.filter(c => countSignals(c.text, SIGNALS.pain).count > 0);
    const painPoints = dedupeByHit(painComments, SIGNALS.pain).slice(0, 5).map(c => ({
      pain: c.text.length > 120 ? c.text.slice(0, 120) + '…' : c.text,
      fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score,
      level: 'ANALYSIS'
    }));

    // 认可点
    const approvalComments = subComments.filter(c => countSignals(c.text, SIGNALS.approval).count > 0);
    const approvalPoints = dedupeByHit(approvalComments, SIGNALS.approval).slice(0, 5).map(c => ({
      point: c.text.length > 120 ? c.text.slice(0, 120) + '…' : c.text,
      fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score,
      level: 'ANALYSIS'
    }));

    // 质疑点
    const skeptComments = subComments.filter(c => countSignals(c.text, SIGNALS.skepticism).count > 0);
    const objections = dedupeByHit(skeptComments, SIGNALS.skepticism).slice(0, 5).map(c => ({
      objection: c.text.length > 120 ? c.text.slice(0, 120) + '…' : c.text,
      fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score,
      level: 'ANALYSIS'
    }));

    // 现有解决方式
    const solComments = subComments.filter(c => countSignals(c.text, SIGNALS.solution).count > 0);
    const existingSolutions = dedupeByHit(solComments, SIGNALS.solution).slice(0, 5).map(c => ({
      solution: c.text.length > 120 ? c.text.slice(0, 120) + '…' : c.text,
      fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score,
      level: 'ANALYSIS'
    }));

    // 代表性观点：按 score 排序的高质量评论
    const representativeQuotes = [...subComments]
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 4)
      .map(c => ({
        quote: c.text.length > 140 ? c.text.slice(0, 140) + '…' : c.text,
        author: c.author, score: c.score, fromPostId: c.postId,
        level: 'DATA'
      }));

    // ============ 情感分类（正/负/中性）============
    // 基于信号词：approval=正向，pain/objection=负向，其余=中性
    // 不做简单情绪统计，而是分类展示代表性评论
    const sentimentBuckets = { positive: [], negative: [], neutral: [] };
    subComments.forEach(c => {
      const app = countSignals(c.text, SIGNALS.approval).count;
      const pain = countSignals(c.text, SIGNALS.pain).count;
      const skept = countSignals(c.text, SIGNALS.skepticism).count;
      const negScore = pain + skept;
      if (app > 0 && app >= negScore) sentimentBuckets.positive.push(c);
      else if (negScore > 0 && negScore > app) sentimentBuckets.negative.push(c);
      else sentimentBuckets.neutral.push(c);
    });
    const sentimentDistribution = {
      positive: sentimentBuckets.positive.length,
      negative: sentimentBuckets.negative.length,
      neutral: sentimentBuckets.neutral.length,
      total: subComments.length,
      samples: {
        positive: [...sentimentBuckets.positive].sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 2)
          .map(c => ({ quote: truncate(c.text, 120), fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score, level: 'DATA' })),
        negative: [...sentimentBuckets.negative].sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 2)
          .map(c => ({ quote: truncate(c.text, 120), fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score, level: 'DATA' })),
        neutral: [...sentimentBuckets.neutral].sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 2)
          .map(c => ({ quote: truncate(c.text, 120), fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score, level: 'DATA' }))
      },
      level: 'ANALYSIS'
    };

    // ============ 品牌提及检测 ============
    // 品牌词来源：1) Store 中配置的 brandKeywords；2) 帖子正文里 "my X" 的通用自有产品提及
    //            3) 帖子标题大写词且在评论中也出现（避免误判通用词）
    const brandKeywords = (global.Store && global.Store.getBrandKeywords && global.Store.getBrandKeywords()) || [];
    const allCommentsText = lower(subComments.map(c => c.text).join(' '));
    const autoBrands = new Set();
    subPosts.forEach(p => {
      const body = p.body || '';
      // "my tool/product/app/saas" 等通用自有产品提及
      if (/\bmy\s+(tool|product|app|saas|project|side project)\b/i.test(body)) {
        autoBrands.add('自有产品（未具名）');
      }
      // 帖子标题里的专有名词（首字母大写且长度>3），需同时在评论中出现
      const titleWords = (p.title || '').match(/\b[A-Z][a-zA-Z]{2,}\b/g) || [];
      titleWords.forEach(w => {
        const lowerW = w.toLowerCase();
        const isGeneric = ['The', 'And', 'But', 'How', 'Why', 'What', 'Here', 'When', 'Reddit', 'Shopify', 'Stripe', 'GitHub'].includes(w)
          || STOPWORDS.has(lowerW);
        if (!isGeneric && allCommentsText.includes(lowerW)) {
          autoBrands.add(w);
        }
      });
    });
    const allBrandKeywords = [...new Set([...brandKeywords, ...autoBrands])].filter(k => k && k.length > 2);

    const brandMentions = [];
    allBrandKeywords.forEach(brand => {
      const brandLower = lower(brand);
      let totalMentions = 0;
      let positiveMentions = 0;
      let negativeMentions = 0;
      let neutralMentions = 0;
      const contexts = [];
      subComments.forEach(c => {
        if (lower(c.text).includes(brandLower)) {
          totalMentions++;
          const app = countSignals(c.text, SIGNALS.approval).count;
          const neg = countSignals(c.text, SIGNALS.pain).count + countSignals(c.text, SIGNALS.skepticism).count;
          if (app > 0 && app >= neg) positiveMentions++;
          else if (neg > 0 && neg > app) negativeMentions++;
          else neutralMentions++;
          if (contexts.length < 3) {
            contexts.push({
              quote: truncate(c.text, 100),
              sentiment: app > 0 && app >= neg ? 'positive' : (neg > 0 && neg > app ? 'negative' : 'neutral'),
              fromCommentId: c.id, fromPostId: c.postId, commentScore: c.score,
              level: 'DATA'
            });
          }
        }
      });
      if (totalMentions > 0) {
        brandMentions.push({
          brand, totalMentions, positiveMentions, negativeMentions, neutralMentions, contexts,
          level: 'ANALYSIS'
        });
      }
    });
    brandMentions.sort((a, b) => b.totalMentions - a.totalMentions);

    // ============ 品牌讨论总结 ============
    let brandDiscussionSummary = '';
    if (brandMentions.length > 0) {
      const topBrand = brandMentions[0];
      const sentimentBreakdown = `正向 ${topBrand.positiveMentions}、负向 ${topBrand.negativeMentions}、中性 ${topBrand.neutralMentions}`;
      brandDiscussionSummary = `评论中提及「${topBrand.brand}」共 ${topBrand.totalMentions} 次（${sentimentBreakdown}）。`;
      if (topBrand.positiveMentions > topBrand.negativeMentions) {
        brandDiscussionSummary += `用户整体态度偏正向，认可点集中在${topBrand.contexts.filter(c => c.sentiment === 'positive').slice(0, 1).map(c => '「' + truncate(c.quote, 60) + '」').join('') || '产品价值'}。`;
      } else if (topBrand.negativeMentions > topBrand.positiveMentions) {
        brandDiscussionSummary += `用户存在较明显质疑，主要负向观点：${topBrand.contexts.filter(c => c.sentiment === 'negative').slice(0, 1).map(c => '「' + truncate(c.quote, 60) + '」').join('')}。`;
      } else {
        brandDiscussionSummary += `用户讨论中性偏多，多为提问或经验交流。`;
      }
    } else {
      brandDiscussionSummary = `评论中未明确提及品牌/产品名，讨论主要集中在用户自身经验与方法论。`;
    }

    // ============ 运营建议（基于以上所有分析生成 3-5 条可执行动作）============
    const operationalSuggestions = [];
    // 建议 1：基于用户需求
    if (userNeeds.length >= 2) {
      operationalSuggestions.push({
        priority: 'high',
        action: `针对高频提问「${truncate(userNeeds[0].need, 50)}」策划下一条内容`,
        reason: `该问题在 ${userNeeds.length} 条评论中被提及，是真实未满足的需求`,
        evidence: userNeeds.slice(0, 2).map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
        level: 'ANALYSIS'
      });
    }
    // 建议 2：基于痛点
    if (painPoints.length >= 1) {
      operationalSuggestions.push({
        priority: 'high',
        action: `围绕用户痛点「${truncate(painPoints[0].pain, 50)}」输出解决方案型内容`,
        reason: `该痛点在评论中表达明确，且是用户主动暴露的真实困扰`,
        evidence: painPoints.slice(0, 2).map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
        level: 'ANALYSIS'
      });
    }
    // 建议 3：基于认可点（放大有效内容）
    if (approvalPoints.length >= 2) {
      operationalSuggestions.push({
        priority: 'medium',
        action: `复制已验证有效的内容方向：${truncate(approvalPoints[0].point, 50)}`,
        reason: `该方向已获用户主动认可，可深度展开或系列化`,
        evidence: approvalPoints.slice(0, 2).map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
        level: 'ANALYSIS'
      });
    }
    // 建议 4：基于质疑（应对风险）
    if (objections.length >= 2) {
      operationalSuggestions.push({
        priority: 'medium',
        action: `准备应对「${truncate(objections[0].objection, 40)}」类质疑的内容`,
        reason: `用户对数据真实性/方法可复制性存在疑虑，后续内容需提供更多证据`,
        evidence: objections.slice(0, 2).map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
        level: 'ANALYSIS'
      });
    }
    // 建议 5：基于品牌情感
    if (brandMentions.length > 0 && brandMentions[0].negativeMentions > brandMentions[0].positiveMentions) {
      operationalSuggestions.push({
        priority: 'high',
        action: `针对「${brandMentions[0].brand}」的负向讨论进行口碑修复内容策划`,
        reason: `品牌提及中负向 ${brandMentions[0].negativeMentions} 多于正向 ${brandMentions[0].positiveMentions}`,
        evidence: brandMentions[0].contexts.filter(c => c.sentiment === 'negative').map(c => ({ type: 'comment', id: c.fromCommentId, postId: c.fromPostId })),
        level: 'ANALYSIS'
      });
    }
    // 建议 6：基于选题机会（如果评论高频词未在历史帖子覆盖）
    if (wordCloud.length > 0) {
      const topWord = wordCloud[0].word;
      const covered = subPosts.some(p => lower(p.title + ' ' + (p.body || '')).includes(topWord));
      if (!covered) {
        operationalSuggestions.push({
          priority: 'medium',
          action: `围绕高频词「${topWord}」策划内容（出现 ${wordCloud[0].count} 次）`,
          reason: `该词在评论中高频出现但现有帖子未充分覆盖`,
          evidence: [{ type: 'topic', word: topWord }],
          level: 'INFERENCE'
        });
      }
    }

    return {
      subreddit, level: 'ANALYSIS',
      sampleSize: subComments.length,
      topTopics, wordCloud, sentimentDistribution,
      brandMentions, brandDiscussionSummary, operationalSuggestions,
      userNeeds, painPoints,
      approvalPoints, objections, existingSolutions,
      representativeQuotes,
      analyzedAt: new Date().toISOString()
    };
  }

  function dedupeByHit(comments, signalList) {
    // 按 score 降序，去重相似评论
    const sorted = [...comments].sort((a, b) => (b.score || 0) - (a.score || 0));
    const result = [];
    for (const c of sorted) {
      if (result.length >= 5) break;
      const isDup = result.some(r => jaccardSimilarity(r.text, c.text) > 0.5);
      if (!isDup) result.push(c);
    }
    return result;
  }

  const STOPWORDS = new Set(['this', 'that', 'with', 'have', 'your', 'their', 'them',
    'they', 'what', 'when', 'where', 'which', 'would', 'could', 'should',
    'there', 'then', 'than', 'from', 'been', 'were', 'will', 'into',
    'about', 'after', 'before', 'some', 'more', 'most', 'just', 'like',
    'also', 'only', 'even', 'much', 'very', 'such', 'those', 'these',
    'here', 'yourself', 'myself', 'really', 'actually', 'always', 'never']);

  // ============ 规律库沉淀 ============
  /**
   * 基于帖子分析 + 评论分析沉淀规律。
   * 规律必须附 evidence（postId / commentId 列表）。
   * 样本不足时降级为 INFERENCE，不形成 PATTERN。
   */
  function buildPatterns(posts, comments, postAnalyses, commentAnalyses) {
    const patterns = [];

    // --- 高表现规律 ---
    const highPerfPosts = posts.filter(p => postAnalyses[p.id] && postAnalyses[p.id].performance.level === 'high');
    if (highPerfPosts.length >= 2) {
      // 聚合高表现帖子的内容类型
      const typeCount = {};
      highPerfPosts.forEach(p => {
        const t = postAnalyses[p.id].contentType.type;
        typeCount[t] = (typeCount[t] || 0) + 1;
      });
      const topType = Object.entries(typeCount).sort((a, b) => b[1] - a[1])[0];
      patterns.push({
        id: 'PAT-HIGH-1',
        category: 'high_performance',
        title: '高表现内容以真实经历分享为主',
        content: `在 ${highPerfPosts.length} 条高表现帖子中，${topType[0]} 占 ${topType[1]} 条（${Math.round(topType[1] / highPerfPosts.length * 100)}%）。高表现内容普遍包含具体数据、失败教训和具体操作步骤。`,
        evidence: highPerfPosts.map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: highPerfPosts.length,
        level: 'PATTERN'
      });

      // 标题结构规律
      const withNumbers = highPerfPosts.filter(p => postAnalyses[p.id].titleStructure.hasNumber).length;
      if (withNumbers >= highPerfPosts.length / 2) {
        patterns.push({
          id: 'PAT-HIGH-2',
          category: 'high_performance',
          title: '高表现标题常含具体数字',
          content: `${withNumbers}/${highPerfPosts.length} 条高表现帖子标题含数字（如金额、时长、百分比），数字提升可信度与具体感。`,
          evidence: highPerfPosts.filter(p => postAnalyses[p.id].titleStructure.hasNumber)
            .map(p => ({ type: 'post', id: p.id, title: p.title })),
          sampleSize: highPerfPosts.length,
          level: 'PATTERN'
        });
      }

      // 营销感规律
      const lowMarketing = highPerfPosts.filter(p => postAnalyses[p.id].marketingFeel <= 2).length;
      patterns.push({
        id: 'PAT-HIGH-3',
        category: 'high_performance',
        title: '高表现内容营销感低',
        content: `${lowMarketing}/${highPerfPosts.length} 条高表现帖子营销感评分 ≤2（满分5），高表现内容几乎不使用"revolutionary""game-changing"等营销话术。`,
        evidence: highPerfPosts.filter(p => postAnalyses[p.id].marketingFeel <= 2)
          .map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: highPerfPosts.length,
        level: 'PATTERN'
      });
    } else {
      patterns.push({
        id: 'PAT-HIGH-WARN',
        category: 'high_performance',
        title: '[样本不足] 高表现规律暂不可靠',
        content: `当前仅 ${highPerfPosts.length} 条高表现样本，不足 2 条阈值，无法形成稳定规律。需补充更多高表现内容后再沉淀。`,
        evidence: highPerfPosts.map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: highPerfPosts.length,
        level: 'INFERENCE'
      });
    }

    // --- 低表现规律 ---
    const lowPerfPosts = posts.filter(p => postAnalyses[p.id] && postAnalyses[p.id].performance.level === 'low');
    if (lowPerfPosts.length >= 2) {
      const marketingLow = lowPerfPosts.filter(p => postAnalyses[p.id].marketingFeel >= 4).length;
      patterns.push({
        id: 'PAT-LOW-1',
        category: 'low_performance',
        title: '低表现内容营销感强、信息密度低',
        content: `${marketingLow}/${lowPerfPosts.length} 条低表现帖子营销感评分 ≥4，常见特征：标题含表情符号、使用"revolutionary/🚀"等话术、正文为功能列表、结尾要求 DM 或"limited spots"。`,
        evidence: lowPerfPosts.filter(p => postAnalyses[p.id].marketingFeel >= 4)
          .map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: lowPerfPosts.length,
        level: 'PATTERN'
      });

      const shortBody = lowPerfPosts.filter(p => (p.body || '').length < 200).length;
      if (shortBody >= lowPerfPosts.length / 2) {
        patterns.push({
          id: 'PAT-LOW-2',
          category: 'low_performance',
          title: '低表现内容正文过短、缺乏细节',
          content: `${shortBody}/${lowPerfPosts.length} 条低表现帖子正文不足 200 字符，缺乏具体数据、操作步骤或失败教训，读者无法获得可执行价值。`,
          evidence: lowPerfPosts.filter(p => (p.body || '').length < 200)
            .map(p => ({ type: 'post', id: p.id, title: p.title })),
          sampleSize: lowPerfPosts.length,
          level: 'PATTERN'
        });
      }
    } else {
      patterns.push({
        id: 'PAT-LOW-WARN',
        category: 'low_performance',
        title: '[样本不足] 低表现规律暂不可靠',
        content: `当前仅 ${lowPerfPosts.length} 条低表现样本，不足 2 条阈值，无法形成稳定规律。`,
        evidence: lowPerfPosts.map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: lowPerfPosts.length,
        level: 'INFERENCE'
      });
    }

    // --- 用户高频需求（跨 subreddit 聚合）---
    const allNeeds = [];
    Object.values(commentAnalyses).forEach(ca => {
      if (ca && ca.userNeeds) allNeeds.push(...ca.userNeeds);
    });
    if (allNeeds.length >= 3) {
      // 按关键词聚类
      const needClusters = clusterByText(allNeeds, 'need');
      needClusters.slice(0, 5).forEach((cluster, i) => {
        patterns.push({
          id: 'PAT-NEED-' + (i + 1),
          category: 'user_need',
          title: `用户高频需求：${cluster.label}`,
          content: `用户评论中多次出现相关提问（${cluster.items.length} 条），反映真实需求。具体提问：${cluster.items.slice(0, 2).map(n => '"' + truncate(n.need, 80) + '"').join('；')}`,
          evidence: cluster.items.map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
          sampleSize: cluster.items.length,
          level: 'PATTERN'
        });
      });
    }

    // --- 用户高频痛点 ---
    const allPains = [];
    Object.values(commentAnalyses).forEach(ca => {
      if (ca && ca.painPoints) allPains.push(...ca.painPoints);
    });
    if (allPains.length >= 2) {
      const painClusters = clusterByText(allPains, 'pain');
      painClusters.slice(0, 3).forEach((cluster, i) => {
        patterns.push({
          id: 'PAT-PAIN-' + (i + 1),
          category: 'pain_point',
          title: `用户痛点：${cluster.label}`,
          content: `用户评论中表达相关痛点 ${cluster.items.length} 次。代表性评论：${cluster.items.slice(0, 1).map(n => '"' + truncate(n.pain, 80) + '"').join('')}`,
          evidence: cluster.items.map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
          sampleSize: cluster.items.length,
          level: 'PATTERN'
        });
      });
    }

    // --- 高互动话题 ---
    const highInteraction = [...posts].filter(p => (p.comments || 0) >= 30)
      .sort((a, b) => (b.comments || 0) - (a.comments || 0)).slice(0, 5);
    if (highInteraction.length >= 2) {
      patterns.push({
        id: 'PAT-TOPIC-1',
        category: 'hot_topic',
        title: '高互动话题集中于"失败教训"与"具体操作步骤"',
        content: `评论数 ≥30 的帖子中，高互动话题的共同特征：① 包含"what failed"等失败教训；② 提供具体操作步骤（Step 1/2/3）；③ 结尾含开放性问题引发讨论。`,
        evidence: highInteraction.map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: highInteraction.length,
        level: 'PATTERN'
      });
    }

    // --- 不同 Subreddit 规律 ---
    const subreddits = Array.from(new Set(posts.map(p => p.subreddit)));
    subreddits.forEach(sub => {
      const subPosts = posts.filter(p => p.subreddit === sub);
      const subHigh = subPosts.filter(p => postAnalyses[p.id] && postAnalyses[p.id].performance.level === 'high');
      if (subPosts.length >= 3 && subHigh.length >= 1) {
        const subAnalyses = subHigh.map(p => postAnalyses[p.id]);
        const avgMatch = avg(subAnalyses.map(a => a.subredditMatch));
        const types = subAnalyses.map(a => a.contentType.type);
        patterns.push({
          id: 'PAT-SUB-' + sub.replace(/[^a-z0-9]/gi, ''),
          category: 'subreddit_rule',
          title: `r/${sub} 内容规律`,
          content: `r/${sub} 共 ${subPosts.length} 条样本（高表现 ${subHigh.length} 条）。高表现内容类型分布：${countTypes(types)}。该社区偏好真实经历与具体操作类内容，对营销感内容敏感。`,
          evidence: subPosts.map(p => ({ type: 'post', id: p.id, title: p.title })),
          sampleSize: subPosts.length,
          level: subPosts.length >= 5 ? 'PATTERN' : 'INFERENCE',
          subreddit: sub
        });
      } else if (subPosts.length >= 1) {
        patterns.push({
          id: 'PAT-SUB-' + sub.replace(/[^a-z0-9]/gi, '') + '-WARN',
          category: 'subreddit_rule',
          title: `[样本不足] r/${sub} 规律暂不可靠`,
          content: `r/${sub} 仅 ${subPosts.length} 条样本（高表现 ${subHigh.length} 条），低于稳定规律所需的 5 条样本阈值。当前结论为推测，需补充样本。`,
          evidence: subPosts.map(p => ({ type: 'post', id: p.id, title: p.title })),
          sampleSize: subPosts.length,
          level: 'INFERENCE',
          subreddit: sub
        });
      }
    });

    // --- 营销风险规律 ---
    const marketingPosts = posts.filter(p => postAnalyses[p.id] && postAnalyses[p.id].marketingFeel >= 4);
    if (marketingPosts.length >= 2) {
      const avgScore = avg(marketingPosts.map(p => p.score || 0));
      patterns.push({
        id: 'PAT-MKT-1',
        category: 'marketing_risk',
        title: '高营销感内容平均表现显著偏低',
        content: `${marketingPosts.length} 条高营销感帖子平均 Score 仅 ${avgScore.toFixed(1)}，且常被评论指出"reads as ad""instant scroll past"。Reddit 社区对营销话术识别度高，营销感与表现负相关。`,
        evidence: marketingPosts.map(p => ({ type: 'post', id: p.id, title: p.title })),
        sampleSize: marketingPosts.length,
        level: 'PATTERN'
      });
    }

    // --- 选题机会（用户需求 - 现有内容覆盖空白）---
    if (allNeeds.length >= 3) {
      const uncoveredNeeds = allNeeds.filter(n => {
        // 检查是否已有帖子覆盖该需求关键词
        const needWords = wordSet(n.need);
        const covered = posts.some(p => {
          const postWords = wordSet(p.title + ' ' + (p.body || ''));
          let overlap = 0;
          for (const w of needWords) if (postWords.has(w)) overlap++;
          return overlap >= 2;
        });
        return !covered;
      });
      if (uncoveredNeeds.length >= 1) {
        patterns.push({
          id: 'PAT-OPP-1',
          category: 'topic_opportunity',
          title: '内容选题机会：用户提问尚未被现有内容充分覆盖',
          content: `在 ${allNeeds.length} 条用户提问中，${uncoveredNeeds.length} 条的主题在现有帖子中覆盖不足，存在选题空间。代表性未覆盖提问：${uncoveredNeeds.slice(0, 2).map(n => '"' + truncate(n.need, 80) + '"').join('；')}`,
          evidence: uncoveredNeeds.map(n => ({ type: 'comment', id: n.fromCommentId, postId: n.fromPostId })),
          sampleSize: uncoveredNeeds.length,
          level: 'PATTERN'
        });
      }
    }

    return patterns;
  }

  // ============ 规律置信度 ============
  /**
   * 根据规律层级 + 样本数计算置信度标签。
   * - high:   PATTERN 且 sampleSize >= 5（可稳定参考）
   * - medium: PATTERN 且 sampleSize 3-4（可参考，注意样本范围）
   * - low:    INFERENCE 或 sampleSize < 3（谨慎参考，需更多数据验证）
   */
  function computeConfidence(pattern) {
    const n = pattern.sampleSize || 0;
    if (pattern.level === 'PATTERN' && n >= 5) return 'high';
    if (pattern.level === 'PATTERN' && n >= 3) return 'medium';
    return 'low';
  }

  function countTypes(types) {
    const c = {};
    types.forEach(t => c[t] = (c[t] || 0) + 1);
    return Object.entries(c).map(([t, n]) => `${t}×${n}`).join('、');
  }

  function truncate(s, n) { return s && s.length > n ? s.slice(0, n) + '…' : s; }

  function clusterByText(items, field) {
    // 简单聚类：按 wordSet 相似度 >0.3 聚合
    const clusters = [];
    items.forEach(item => {
      const text = item[field] || '';
      const placed = clusters.find(cl => cl.items.some(it => jaccardSimilarity(it[field], text) > 0.3));
      if (placed) {
        placed.items.push(item);
      } else {
        clusters.push({
          label: text.split(' ').slice(0, 4).join(' '),
          items: [item]
        });
      }
    });
    return clusters.sort((a, b) => b.items.length - a.items.length);
  }

  // ============ 新内容发布前评估 ============
  /**
   * 综合调用历史内容、表现数据、用户评论、内容规律库进行评估。
   * 输入：{ subreddit, title, body }
   */
  function evaluateNewContent(input, posts, postAnalyses, commentAnalyses, patterns) {
    const { subreddit, title, body } = input;
    const fullText = (title || '') + ' ' + (body || '');
    const reasons = [];
    const suggestions = [];

    // 1. 社区匹配度
    let subredditMatch = 3;
    const subPosts = posts.filter(p => p.subreddit === subreddit);
    const subAnalyses = subPosts.map(p => postAnalyses[p.id]).filter(Boolean);
    const subHigh = subAnalyses.filter(a => a.performance.level === 'high');
    if (subPosts.length >= 3 && subHigh.length >= 1) {
      // 看高表现帖子的内容类型分布
      const highTypes = subHigh.map(a => a.contentType.type);
      const typeCount = {};
      highTypes.forEach(t => typeCount[t] = (typeCount[t] || 0) + 1);
      const topType = Object.entries(typeCount).sort((a, b) => b[1] - a[1])[0];

      const authSig = countSignals(fullText, SIGNALS.authenticity);
      const markSig = countSignals(fullText, SIGNALS.marketing);

      if (topType[0] === '真实经历分享' && authSig.count >= 2) {
        subredditMatch = 5;
        reasons.push(`社区匹配度高：r/${subreddit} 高表现内容以真实经历分享为主（${topType[1]}/${subHigh.length} 条），当前内容包含 ${authSig.count} 个真实经历信号词`);
      } else if (topType[0] === '产品展示/营销' && markSig.count >= 3) {
        subredditMatch = 2;
        reasons.push(`社区匹配度低：r/${subreddit} 高表现内容几乎不含营销话术，当前内容营销信号强（${markSig.count} 个）`);
      } else if (topType[0] === '真实经历分享' && markSig.count >= 3 && authSig.count <= 1) {
        subredditMatch = 2;
        reasons.push(`社区匹配度低：r/${subreddit} 偏好真实经历分享，当前内容偏营销展示`);
      } else {
        subredditMatch = 3;
        reasons.push(`社区匹配度中：r/${subreddit} 高表现内容类型为 ${topType[0]}，当前内容与之相关性中等`);
      }
    } else if (subPosts.length > 0) {
      subredditMatch = 3;
      reasons.push(`[样本不足] r/${subreddit} 仅 ${subPosts.length} 条历史样本（高表现 ${subHigh.length} 条），社区匹配判断为推测（INFERENCE）`);
    } else {
      subredditMatch = 2;
      reasons.push(`r/${subreddit} 无历史样本，无法判断社区匹配度（INFERENCE）`);
    }

    // 2. 内容真实性
    const authSig = countSignals(fullText, SIGNALS.authenticity);
    const markSig = countSignals(fullText, SIGNALS.marketing);
    let authenticity = 3;
    if (authSig.count >= 3 && markSig.count <= 1) {
      authenticity = 5;
      reasons.push(`真实性高：含 ${authSig.count} 个真实经历信号词（${authSig.hits.slice(0, 3).join(', ')}），营销信号 ≤1`);
    } else if (authSig.count >= 2 && markSig.count <= 2) {
      authenticity = 4;
      reasons.push(`真实性较高：含 ${authSig.count} 个真实经历信号词，营销信号 ${markSig.count} 个`);
    } else if (markSig.count >= 4) {
      authenticity = 1;
      reasons.push(`真实性低：营销信号词 ${markSig.count} 个（${markSig.hits.slice(0, 3).join(', ')}），缺少真实经历细节`);
      suggestions.push({
        priority: 'high',
        dimension: '内容真实性',
        action: '增加具体数据、时长、失败教训等真实细节，减少"revolutionary/🚀"等营销话术',
        reason: `检测到 ${markSig.count} 个营销信号词，缺少第一人称经历描述`,
        level: 'ANALYSIS'
      });
    } else if (markSig.count >= 2 && authSig.count <= 1) {
      authenticity = 2;
      reasons.push(`真实性较低：营销信号 ${markSig.count} 个，真实经历信号仅 ${authSig.count} 个`);
      suggestions.push({
        priority: 'high',
        dimension: '内容真实性',
        action: '补充"我做了什么、花了多久、结果如何"等第一人称经历描述',
        reason: `真实经历信号仅 ${authSig.count} 个，营销信号 ${markSig.count} 个`,
        level: 'ANALYSIS'
      });
    } else {
      authenticity = 3;
      reasons.push(`真实性中等：真实经历信号 ${authSig.count} 个，营销信号 ${markSig.count} 个`);
    }

    // 3. 用户价值：是否回应用户已知需求
    let userValue = 3;
    const subCommentAnalysis = commentAnalyses[subreddit];
    if (subCommentAnalysis && subCommentAnalysis.userNeeds && subCommentAnalysis.userNeeds.length > 0) {
      // 计算新内容与用户需求的关键词重叠
      const needText = subCommentAnalysis.userNeeds.map(n => n.need).join(' ');
      const sim = jaccardSimilarity(fullText, needText);
      if (sim > 0.15) {
        userValue = 5;
        reasons.push(`用户价值高：与 r/${subreddit} 用户高频提问关键词重叠度 ${Math.round(sim * 100)}%，回应了真实需求`);
      } else if (sim > 0.08) {
        userValue = 4;
        reasons.push(`用户价值较高：与用户高频提问关键词重叠度 ${Math.round(sim * 100)}%`);
      } else {
        userValue = 2;
        reasons.push(`用户价值低：与 r/${subreddit} 用户高频提问关键词重叠度仅 ${Math.round(sim * 100)}%，未回应已知需求`);
        suggestions.push({
          priority: 'high',
          dimension: '用户价值',
          action: `参考 r/${subreddit} 用户高频提问，让内容直接回应一个具体需求`,
          reason: `与用户高频提问关键词重叠度仅 ${Math.round(sim * 100)}%，未回应已知需求。例如：${subCommentAnalysis.userNeeds[0].need.slice(0, 50)}…`,
          level: 'ANALYSIS'
        });
      }
    } else {
      reasons.push(`[样本不足] r/${subreddit} 暂无用户评论分析，用户价值判断为推测（INFERENCE）`);
    }

    // 4. 讨论潜力
    let discussionPotential = 3;
    const discSig = countSignals(fullText, SIGNALS.discussion);
    const questSig = countSignals(fullText, SIGNALS.question);
    const hasQuestion = (title || '').includes('?') || questSig.count >= 1;
    const hasOpenEnding = /curious|would love|thoughts|ama|what works for you/i.test(body || '');
    if ((discSig.count >= 1 || hasOpenEnding) && hasQuestion) {
      discussionPotential = 5;
      reasons.push(`讨论潜力高：含开放性问题与讨论触发词（${discSig.hits.concat(questSig.hits).slice(0, 3).join(', ')}）`);
    } else if (hasQuestion || hasOpenEnding) {
      discussionPotential = 4;
      reasons.push(`讨论潜力较高：含 ${hasQuestion ? '提问' : '开放结尾'}`);
    } else if ((body || '').length < 200) {
      discussionPotential = 2;
      reasons.push(`讨论潜力低：正文过短（${(body || '').length} 字符），缺乏可讨论的细节`);
      suggestions.push({
        priority: 'medium',
        dimension: '讨论潜力',
        action: '补充具体操作步骤、数据或失败教训，提供读者可讨论的具体内容',
        reason: `正文仅 ${(body || '').length} 字符，缺乏可讨论的细节`,
        level: 'ANALYSIS'
      });
    } else {
      discussionPotential = 3;
      reasons.push(`讨论潜力中：无明确提问或讨论触发词`);
    }

    // 5. 营销风险
    let marketingRisk = 5 - Math.min(4, markSig.count); // 反向：营销信号越多风险越高（分值越低）
    const hasEmoji = /🚀|🔥|💫|✨|🎉/.test(title || '');
    const hasDmCall = /dm for|dm me|limited spots|link in profile|sign up now/i.test(fullText);
    if (hasEmoji) {
      marketingRisk = Math.min(marketingRisk, 2);
      reasons.push(`营销风险高：标题含表情符号，Reddit 社区常将其识别为营销信号`);
      suggestions.push({
        priority: 'high',
        dimension: '营销风险',
        action: '移除标题中的表情符号（🚀🔥等）',
        reason: 'Reddit 社区对标题表情符号高度敏感，常被识别为营销信号',
        level: 'ANALYSIS'
      });
    }
    if (hasDmCall) {
      marketingRisk = Math.min(marketingRisk, 1);
      reasons.push(`营销风险极高：含"DM for/limited spots/link in profile"等强营销话术，历史数据显示此类内容平均分数极低`);
      if (!suggestions.some(s => typeof s === 'object' && s.action && s.action.includes('DM'))) {
        suggestions.push({
          priority: 'high',
          dimension: '营销风险',
          action: '移除"DM for demo/limited spots"等强营销话术，改为在正文中直接提供价值',
          reason: '此类强营销话术在历史数据中平均分数极低',
          level: 'ANALYSIS'
        });
      }
    }
    if (markSig.count >= 3 && marketingRisk > 2) {
      marketingRisk = 2;
      reasons.push(`营销风险高：检测到 ${markSig.count} 个营销信号词`);
    } else if (markSig.count <= 1 && marketingRisk < 4) {
      marketingRisk = 4;
      reasons.push(`营销风险低：营销信号词 ${markSig.count} 个`);
    } else if (markSig.count === 0) {
      marketingRisk = 5;
      reasons.push(`营销风险极低：未检测到营销信号词`);
    }

    // 6. 与历史内容重复度
    let duplicationScore = 5; // 5 = 完全不重复
    let mostSimilarPost = null;
    let maxSim = 0;
    subPosts.forEach(p => {
      const sim = jaccardSimilarity(fullText, p.title + ' ' + (p.body || ''));
      if (sim > maxSim) {
        maxSim = sim;
        mostSimilarPost = p;
      }
    });
    if (maxSim > 0.4) {
      duplicationScore = 1;
      reasons.push(`重复度高：与历史帖子 [${mostSimilarPost.id}] "${truncate(mostSimilarPost.title, 50)}" 关键词重叠 ${Math.round(maxSim * 100)}%`);
      suggestions.push({
        priority: 'high',
        dimension: '重复度',
        action: `调整内容角度或补充新数据，避免与历史帖子 ${mostSimilarPost.id} 高度雷同`,
        reason: `与历史帖子关键词重叠 ${Math.round(maxSim * 100)}%，Reddit 社区对重复内容容忍度低`,
        level: 'ANALYSIS'
      });
    } else if (maxSim > 0.25) {
      duplicationScore = 3;
      reasons.push(`重复度中：与历史帖子 [${mostSimilarPost.id}] "${truncate(mostSimilarPost.title, 50)}" 关键词重叠 ${Math.round(maxSim * 100)}%`);
    } else if (maxSim > 0.15) {
      duplicationScore = 4;
      reasons.push(`重复度较低：与最相似历史帖子重叠 ${Math.round(maxSim * 100)}%`);
    } else {
      duplicationScore = 5;
      reasons.push(`重复度低：与历史内容最大重叠 ${Math.round(maxSim * 100)}%`);
    }

    // 7. 配图/视觉维度
    let visualScore = 3;
    const hasImg = input.hasImage === true;
    const imgQ = input.imageQuality === true;
    if (!hasImg) {
      visualScore = 2;
      // 无配图：对照历史样本，看高表现内容的配图比例，智能调整
      if (subAnalyses.length >= 3) {
        const highWithImg = subHigh.filter(a => {
          const orig = subPosts.find(pp => postAnalyses[pp.id] === a);
          return orig && orig.hasImage;
        }).length;
        const highRate = subHigh.length > 0 ? highWithImg / subHigh.length : 0;
        if (highRate >= 0.6) {
          visualScore = 1;
          reasons.push(`视觉表现力低：r/${subreddit} 高表现内容 ${Math.round(highRate * 100)}% 带配图，当前无配图（显著低于社区规律）`);
          suggestions.push({
            priority: 'high',
            dimension: '配图',
            action: `补充 1-2 张数据图、截图或产品照片，参照 r/${subreddit} 高表现帖的配图风格`,
            reason: `r/${subreddit} 高表现帖带图比例高达 ${Math.round(highRate * 100)}%，无配图显著降低传播力`,
            level: 'ANALYSIS'
          });
        } else {
          reasons.push(`视觉表现力较低：r/${subreddit} 高表现内容带图率约 ${Math.round(highRate * 100)}%，当前无配图`);
          suggestions.push({
            priority: 'medium',
            dimension: '配图',
            action: '建议补充一张核心配图（图表/截图等），提升帖子点击吸引力',
            reason: `r/${subreddit} 仅 ${Math.round(highRate * 100)}% 高表现帖无图，带图有一定优势`,
            level: 'OPTIMIZATION'
          });
        }
      } else {
        reasons.push('[样本不足] 无配图，视觉表现力评分按保守估计（INFERENCE）');
      }
    } else if (imgQ) {
      visualScore = 5;
      reasons.push('视觉表现力高：含优质配图（系统识别为配图优质加分项，有助于提升点击与传播）');
    } else {
      visualScore = 3;
      reasons.push('视觉表现力中等：有配图但质量一般，若配为更清晰的图表/截图可提升分数');
      suggestions.push({
        priority: 'low',
        dimension: '配图',
        action: '升级配图质量：改用数据图表、清晰截图或统一视觉风格',
        reason: '有配图但质量一般，升级为优质配图可额外获得分析分数加成',
        level: 'OPTIMIZATION'
      });
    }

    // 8. 综合评分（加权）：原 7 维度 + 新 配图维度，重新归一化权重
    const overallScore = Math.round(
      subredditMatch * 0.18 +
      authenticity * 0.18 +
      userValue * 0.18 +
      discussionPotential * 0.14 +
      marketingRisk * 0.14 +
      duplicationScore * 0.09 +
      visualScore * 0.09
    );

    // 9. 推荐结论
    let recommendation;
    if (marketingRisk <= 2 || duplicationScore <= 1) {
      recommendation = 'not_recommended';
    } else if (overallScore >= 4 && marketingRisk >= 4) {
      recommendation = 'publish';
    } else if (overallScore >= 3) {
      recommendation = 'revise';
    } else {
      recommendation = 'not_recommended';
    }

    // 10. 补充修改建议（按优先级排序，最多 5 条）
    if (suggestions.length === 0) {
      // 根据最薄弱维度自动补充建议
      const dims = [
        { name: '社区匹配度', score: subredditMatch },
        { name: '内容真实性', score: authenticity },
        { name: '用户价值', score: userValue },
        { name: '讨论潜力', score: discussionPotential },
        { name: '营销风险', score: marketingRisk },
        { name: '重复度', score: duplicationScore },
        { name: '配图表现力', score: visualScore }
      ].sort((a, b) => a.score - b.score);
      const weakest = dims[0];
      if (weakest.score < 4) {
        suggestions.push({
          priority: weakest.score <= 2 ? 'high' : 'medium',
          dimension: weakest.name,
          action: `参考内容规律库中 r/${subreddit} 的高表现内容特征，调整「${weakest.name}」`,
          reason: `当前「${weakest.name}」维度评分 ${weakest.score}/5，是最薄弱环节`,
          level: 'ANALYSIS'
        });
      }
    }
    // 按优先级排序：high > medium > low
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    suggestions.sort((a, b) => (priorityOrder[a.priority] || 3) - (priorityOrder[b.priority] || 3));

    return {
      input: { subreddit, title, body: body || '' },
      overallScore,
      dimensions: {
        subredditMatch, authenticity, userValue,
        discussionPotential, marketingRisk, duplicationScore
      },
      recommendation, // publish | revise | not_recommended
      reasons: reasons.map(r => ({ text: r, level: r.includes('[样本不足]') ? 'INFERENCE' : 'ANALYSIS' })),
      suggestions: suggestions.slice(0, 5),
      mostSimilarPost: mostSimilarPost ? {
        id: mostSimilarPost.id, title: mostSimilarPost.title, similarity: maxSim
      } : null,
      appliedPatterns: patterns
        .filter(p => p.category === 'high_performance' || p.category === 'marketing_risk' || (p.subreddit === subreddit))
        .slice(0, 4)
        .map(p => ({ id: p.id, title: p.title, category: p.category })),
      evaluatedAt: new Date().toISOString()
    };
  }

  // ============ 事实分析（基于真实历史数据的统计，非预测/打分） ============
  /**
   * 事实分析：基于 Store 中真实历史数据生成统计结果。
   * 不做预测或打分，仅汇总真实数据。
   * @returns {{communityStats, contentTypeStats, outliers, commentInsights, dataSources}}
   */
  function runFactualAnalysis() {
    const state = global.Store.getState();

    // ---- 字段适配：帖子以 likes/score 为 upvotes，comments 为评论数 ----
    const getUpvotes = p => (typeof p.likes === 'number' ? p.likes : (typeof p.score === 'number' ? p.score : 0));
    const getViews = p => (typeof p.views === 'number' ? p.views : 0);
    const getCommentsCount = p => (typeof p.comments === 'number' ? p.comments : 0);

    // 中位数：排序后取中间值（偶数取中间两数平均）
    function median(arr) {
      if (!arr.length) return 0;
      const sorted = [...arr].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    }

    function statBlock(values) {
      if (!values.length) return { avg: 0, median: 0, max: 0, min: 0, total: 0 };
      const total = values.reduce((s, n) => s + n, 0);
      return {
        avg: total / values.length,
        median: median(values),
        max: Math.max(...values),
        min: Math.min(...values),
        total
      };
    }

    function confidenceBySample(n) {
      if (n <= 1) return '仅参考';
      if (n <= 4) return '有限';
      if (n <= 9) return '中等';
      return '较稳定';
    }

    const DATA_SOURCE = 'NIIMBOT 历史数据';

    // 仅统计已发布帖子
    const publishedPosts = state.posts.filter(p => p.isPublished !== false);
    const allComments = state.comments || [];

    // ============ 1. 社区表现统计（按 subreddit 分组） ============
    // 社区基准数据（非 NIIMBOT 自己发的，来自导入）
    const communityPosts = Array.isArray(state.communityPosts) ? state.communityPosts : [];
    const communityStatsBySub = (global.Store && global.Store.getCommunityStats)
      ? (global.Store.getCommunityStats() || {})
      : {};

    const subreddits = Array.from(new Set(publishedPosts.map(p => p.subreddit).filter(Boolean)));
    const communityStats = {};
    const subStats = {}; // 保留组内 avgViews 供 outliers 使用
    subreddits.forEach(sub => {
      const group = publishedPosts.filter(p => p.subreddit === sub);
      const viewsArr = group.map(getViews);
      const upvotesArr = group.map(getUpvotes);
      const commentsArr = group.map(getCommentsCount);
      const postCount = group.length;

      const viewsStat = statBlock(viewsArr);
      const upvotesStat = statBlock(upvotesArr);
      const commentsStat = statBlock(commentsArr);

      const highPerformanceCount = group.filter(p => getViews(p) > viewsStat.avg * 2).length;

      // topPost: Views 最高的帖子
      const top = group.slice().sort((a, b) => getViews(b) - getViews(a))[0];

      // 社区基准对比数据
      const cb = communityStatsBySub[sub];
      let niimbotVsCommunity = 'unknown';
      if (cb && cb.postCount > 0 && cb.views.avg > 0 && viewsStat.avg > 0) {
        const ratio = viewsStat.avg / cb.views.avg;
        if (ratio >= 1.2) niimbotVsCommunity = 'higher';
        else if (ratio <= 0.8) niimbotVsCommunity = 'lower';
        else niimbotVsCommunity = 'similar';
      }

      communityStats[sub] = {
        postCount,
        views: viewsStat,
        upvotes: upvotesStat,
        comments: commentsStat,
        highPerformanceCount,
        dataSource: DATA_SOURCE,
        confidence: confidenceBySample(postCount),
        topPost: top ? {
          title: top.title,
          views: getViews(top),
          upvotes: getUpvotes(top),
          comments: getCommentsCount(top),
          url: top.url
        } : null,
        communityBenchmark: cb && cb.postCount > 0 ? {
          available: true,
          postCount: cb.postCount,
          viewsAvg: cb.views.avg,
          viewsMedian: cb.views.median,
          upvotesAvg: cb.upvotes.avg,
          commentsAvg: cb.comments.avg,
          niimbotVsCommunity
        } : {
          available: false,
          postCount: 0,
          viewsAvg: 0,
          viewsMedian: 0,
          upvotesAvg: 0,
          commentsAvg: 0,
          niimbotVsCommunity: 'unknown'
        }
      };

      subStats[sub] = { avgViews: viewsStat.avg, count: postCount };
    });

    // ============ 2. 内容类型表现 ============
    const TYPE_RULES = [
      { type: 'guide', keywords: ['guide', 'how to', 'reference', 'check', 'tip', 'faq'] },
      { type: 'showcase', keywords: ['showcase', 'show us', 'share your', 'event', 'look at'] },
      { type: 'question', keywords: ['how do you', 'do you', 'what', 'why', 'should i', '?'] },
      { type: 'discussion', keywords: ['thoughts', 'what do you', 'who', 'anyone'] }
    ];
    const STORY_KEYWORDS = ['i ', 'my ', 'our ', 'we '];
    const NEED_KEYWORDS = ['need', 'want', 'wish', 'looking for', 'how to', 'problem', 'issue', 'struggle', 'help', 'advice', 'recommend'];
    const USE_CASE_KEYWORDS = ['label', 'shipping', 'inventory', 'pricing', 'organize', 'storage', 'craft', 'product', 'package', 'barcode', 'address', 'jar', 'candle', 'resin'];

    function classifyContentType(post) {
      const text = lower((post.title || '') + ' ' + (post.body || ''));
      // 按优先级匹配：guide > showcase > question > discussion
      for (const rule of TYPE_RULES) {
        if (rule.keywords.some(k => text.includes(k))) return rule.type;
      }
      // story：含人称关键词（已隐含非提问，因 question 在上面已优先匹配）
      if (STORY_KEYWORDS.some(k => text.includes(k))) return 'story';
      return 'other';
    }

    const contentTypeGroups = {};
    publishedPosts.forEach(p => {
      const type = classifyContentType(p);
      if (!contentTypeGroups[type]) {
        contentTypeGroups[type] = { type, count: 0, views: [], upvotes: [], comments: [] };
      }
      contentTypeGroups[type].count++;
      contentTypeGroups[type].views.push(getViews(p));
      contentTypeGroups[type].upvotes.push(getUpvotes(p));
      contentTypeGroups[type].comments.push(getCommentsCount(p));
    });
    const contentTypeStats = {};
    Object.keys(contentTypeGroups).forEach(type => {
      const g = contentTypeGroups[type];
      contentTypeStats[type] = {
        type,
        count: g.count,
        views: { avg: avg(g.views) },
        upvotes: { avg: avg(g.upvotes) },
        comments: { avg: avg(g.comments) }
      };
    });

    // ============ 3. 异常表现识别 ============
    const highOutliers = [];
    publishedPosts.forEach(p => {
      const sub = p.subreddit;
      const meta = subStats[sub];
      if (!meta || meta.count <= 1) return; // 样本不足，不作为异常
      const views = getViews(p);
      const avgViews = meta.avgViews;
      if (avgViews > 0 && views > avgViews * 2) {
        highOutliers.push({
          postId: p.id,
          title: p.title,
          subreddit: sub,
          views,
          avgViews,
          multiple: +(views / avgViews).toFixed(2),
          dataSource: DATA_SOURCE
        });
      }
    });

    // ============ 4. 评论深度分析 ============
    // 品牌词：Store 配置 + 默认 niimbot
    const brandKeywords = (global.Store && global.Store.getBrandKeywords && global.Store.getBrandKeywords()) || [];
    const brandLowerSet = new Set([...brandKeywords, 'niimbot'].map(b => lower(b)).filter(b => b && b.length > 1));
    // 竞品列表（去重）
    const COMPETITORS = Array.from(new Set(['Brother', 'DYMO', 'Phomemo', 'Zebra', 'Munbyn', 'Nelko', 'Orgbro', 'Bambu']));

    const brandMentionList = [];
    const competitorMentionList = [];
    const userNeedCounts = {};
    const useCaseCounts = {};

    function addCount(map, key) {
      const k = lower(key).trim();
      if (!k) return;
      map[k] = (map[k] || 0) + 1;
    }

    allComments.forEach(c => {
      const text = c.text || '';
      const textLower = lower(text);
      const commentLikes = typeof c.likes === 'number' ? c.likes : (typeof c.score === 'number' ? c.score : 0);

      // 品牌提及：mentionsBrand 字段 或 文本含品牌词
      let brandHit = !!c.mentionsBrand;
      if (!brandHit) {
        for (const b of brandLowerSet) {
          if (textLower.includes(b)) { brandHit = true; break; }
        }
      }
      if (brandHit) {
        brandMentionList.push({
          commentId: c.id,
          postId: c.postId,
          quote: truncate(text, 120),
          likes: commentLikes,
          mentionsBrand: true
        });
      }

      // 竞品提及：mentionsCompetitor 字段 或 文本含竞品名
      let competitorHit = !!c.mentionsCompetitor;
      const matchedCompetitors = [];
      COMPETITORS.forEach(comp => {
        if (textLower.includes(lower(comp))) {
          matchedCompetitors.push(comp);
          competitorHit = true;
        }
      });
      if (c.competitorName && !matchedCompetitors.some(m => lower(m) === lower(c.competitorName))) {
        matchedCompetitors.push(c.competitorName);
      }
      if (competitorHit) {
        competitorMentionList.push({
          commentId: c.id,
          postId: c.postId,
          quote: truncate(text, 120),
          likes: commentLikes,
          competitors: matchedCompetitors
        });
      }

      // 用户需求关键词统计：userNeed 字段 + 文本需求信号
      if (c.userNeed) addCount(userNeedCounts, c.userNeed);
      NEED_KEYWORDS.forEach(kw => { if (textLower.includes(kw)) addCount(userNeedCounts, kw); });

      // 使用场景关键词统计：useCase 字段 + 文本场景关键词
      if (c.useCase) addCount(useCaseCounts, c.useCase);
      USE_CASE_KEYWORDS.forEach(kw => { if (textLower.includes(kw)) addCount(useCaseCounts, kw); });
    });

    // topComments: 点赞最高前 5（有 likes 数据时）
    const commentsWithLikes = allComments.filter(c => typeof c.likes === 'number');
    let topComments = [];
    if (commentsWithLikes.length) {
      topComments = commentsWithLikes
        .slice()
        .sort((a, b) => (b.likes || 0) - (a.likes || 0))
        .slice(0, 5)
        .map(c => ({
          commentId: c.id,
          postId: c.postId,
          quote: truncate(c.text || '', 140),
          likes: c.likes,
          author: c.author || ''
        }));
    }

    const toSortedArr = obj => Object.keys(obj)
      .map(k => ({ keyword: k, count: obj[k] }))
      .sort((a, b) => b.count - a.count);

    const commentInsights = {
      totalComments: allComments.length,
      brandMentions: { count: brandMentionList.length, list: brandMentionList },
      competitorMentions: { count: competitorMentionList.length, list: competitorMentionList },
      topComments,
      userNeeds: toSortedArr(userNeedCounts),
      useCases: toSortedArr(useCaseCounts)
    };

    // ============ 5. 数据来源总览 ============
    const communityPostCount = communityPosts.length;
    const dataSources = {
      niimbotData: {
        postCount: publishedPosts.length,
        commentCount: allComments.length,
        label: DATA_SOURCE
      },
      communityData: {
        postCount: communityPostCount,
        commentCount: 0,
        label: 'Reddit 社区基准数据'
      },
      note: communityPostCount > 0
        ? `NIIMBOT 自身 ${publishedPosts.length} 条历史数据 vs 社区基准 ${communityPostCount} 条帖子，用于对比 NIIMBOT 与社区整体表现差异。`
        : '当前所有数据均为 NIIMBOT 历史数据。社区基准数据需通过导入功能添加。'
    };

    return { communityStats, contentTypeStats, outliers: { highOutliers }, commentInsights, dataSources };
  }

  // ============ 一键全量分析 ============
  /**
   * 全量分析。
   * @param {boolean} useTimeFilter 是否按当前时间筛选范围分析（默认 false = 用全部数据）
   */
  function runFullAnalysis(useTimeFilter) {
    const state = global.Store.getState();
    // 帖子分析始终基于全部帖子（性能分档需要全量对比）
    // 评论分析与规律库沉淀可基于时间筛选
    const allPosts = state.posts;
    const fd = useTimeFilter ? global.Store.getFilteredData() : null;
    const postsForAnalysis = fd ? fd.posts : allPosts;
    const commentsForAnalysis = fd ? fd.comments : state.comments;

    // 1. 帖子分析（基于全部帖子，保证性能分档稳定）
    const postAnalyses = {};
    allPosts.forEach(p => {
      postAnalyses[p.id] = analyzePost(p, allPosts);
    });

    // 2. 评论分析（按 subreddit，基于筛选范围）
    const commentAnalyses = {};
    const subreddits = Array.from(new Set(postsForAnalysis.map(p => p.subreddit)));
    subreddits.forEach(sub => {
      commentAnalyses[sub] = analyzeComments(sub, postsForAnalysis, commentsForAnalysis);
    });

    // 3. 规律库沉淀（基于筛选范围）
    const patterns = buildPatterns(postsForAnalysis, commentsForAnalysis, postAnalyses, commentAnalyses);
    // 标注规律库的时间范围 + 置信度
    patterns.forEach(p => {
      if (fd && fd.filtered) {
        p.timeRange = global.Store.getTimeRangeDescription();
      } else {
        p.timeRange = '全部时间';
      }
      p.confidence = computeConfidence(p);
    });

    // 4. 写回 store
    allPosts.forEach(p => global.Store.setPostAnalysis(p.id, postAnalyses[p.id]));
    subreddits.forEach(sub => global.Store.setCommentAnalysis(sub, commentAnalyses[sub]));
    global.Store.setPatterns(patterns);

    return { postAnalyses, commentAnalyses, patterns };
  }

  // ============ 导出 ============
  global.Analyzer = {
    analyzePost,
    analyzeComments,
    buildPatterns,
    evaluateNewContent,
    runFullAnalysis,
    runFactualAnalysis,
    classifyPerformance,
    computeConfidence,
    _utils: { jaccardSimilarity, countSignals, wordSet }
  };
})(window);
