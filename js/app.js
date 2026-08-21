/**
 * 应用主逻辑（app.js）
 *
 * 职责：
 *  - 应用初始化、页面切换
 *  - 4 个页面渲染：历史内容 / 内容分析 / 内容规律 / 发布前评估
 *  - 模态框：录入帖子、批量导入帖子 CSV、导入评论 CSV
 *  - Toast 通知、事件绑定
 *
 * 依赖：Store（存储层）、Analyzer（分析引擎）、DEMO_DATA（模拟数据）
 */

(function () {
  'use strict';

  // ============ 工具函数 ============
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === 'class') node.className = attrs[k];
        else if (k === 'html') node.innerHTML = attrs[k];
        else if (k.startsWith('on') && typeof attrs[k] === 'function') node.addEventListener(k.slice(2), attrs[k]);
        else if (attrs[k] !== undefined && attrs[k] !== null) node.setAttribute(k, attrs[k]);
      }
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach(c => {
        if (c == null) return;
        node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      });
    }
    return node;
  }
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    } catch { return iso; }
  }
  function fmtNum(n) { return n == null ? '—' : Number(n).toLocaleString(); }
  function truncate(s, n) { return s && s.length > n ? s.slice(0, n) + '…' : s; }

  function toast(msg, type) {
    const t = $('#toast');
    t.textContent = msg;
    t.className = 'toast ' + (type || '');
    t.style.display = 'block';
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { t.style.display = 'none'; }, 2600);
  }

  function levelLabel(level) {
    return { high: '高表现', medium: '中表现', low: '低表现' }[level] || '未分析';
  }

  // ============ 页面切换 ============
  function switchPage(pageName) {
    $$('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.page === pageName));
    $$('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + pageName));
    // 按需渲染
    if (pageName === 'history') renderHistoryPage();
    else if (pageName === 'analysis') renderAnalysisPage();
    else if (pageName === 'patterns') renderPatternsPage();
    else if (pageName === 'subreddit') renderSubredditPage();
    else if (pageName === 'evaluate') renderEvaluatePage();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ============ 数据状态徽章 ============
  function refreshDataBadge() {
    const state = Store.getState();
    const badge = $('#data-badge');
    if (state.meta.isMock) {
      badge.textContent = '◆ ' + (state.meta.label || '模拟数据');
      badge.className = 'data-badge mock';
    } else {
      badge.textContent = '◇ 自定义数据';
      badge.className = 'data-badge custom';
    }
  }

  // ============ 页面 1: 历史内容 ============
  function renderHistoryPage() {
    renderDashboard();
    renderStatsRow();
    renderSubredditFilter();
    renderPostsList();
  }

  // ============ Dashboard 概览 ============
  function renderDashboard() {
    const container = $('#dashboard-overview');
    container.innerHTML = '';
    const fd = Store.getFilteredData();
    const rangeDesc = Store.getTimeRangeDescription();
    const posts = fd.posts;
    const comments = fd.comments;

    // 统计
    const high = posts.filter(p => (Store.getPostAnalysis(p.id) || {}).performance?.level === 'high').length;
    const low = posts.filter(p => (Store.getPostAnalysis(p.id) || {}).performance?.level === 'low').length;
    const avgScore = posts.length ? Math.round(posts.reduce((s, p) => s + ((p.likes ?? p.score) || 0), 0) / posts.length) : 0;

    // 可复用经验：取规律库中 high_performance 的前 3 条
    const patterns = Store.getPatterns();
    const reusableLessons = patterns.filter(p => p.category === 'high_performance' && p.level === 'PATTERN').slice(0, 3);

    // 待办动作：聚合所有 subreddit 的 operationalSuggestions
    const state = Store.getState();
    const allSuggestions = [];
    Object.values(state.commentAnalyses || {}).forEach(ca => {
      if (ca && ca.operationalSuggestions) allSuggestions.push(...ca.operationalSuggestions);
    });
    // 按优先级排序，去重
    const todos = allSuggestions
      .filter((s, i, arr) => i === arr.findIndex(x => x.action === s.action))
      .sort((a, b) => (a.priority === 'high' ? 0 : 1) - (b.priority === 'high' ? 0 : 1))
      .slice(0, 4);

    if (posts.length === 0 && state.posts.length === 0) {
      container.appendChild(el('div', { class: 'empty-state', style: 'grid-column:1/-1;' }, [
        el('div', { class: 'empty-icon' }, '📋'),
        el('h3', {}, '暂无数据'),
        el('p', {}, '点击右上角「载入模拟数据」开始演示。')
      ]));
      return;
    }

    // 卡片 1：数据概览
    const card1 = el('div', { class: 'dash-card' });
    card1.appendChild(el('div', { class: 'dash-card-title' }, [
      '数据概览', el('span', { class: 'range-tag' }, rangeDesc)
    ]));
    card1.appendChild(el('div', { class: 'dash-stats' }, [
      dashStat('帖子', posts.length, ''),
      dashStat('评论', comments.length, ''),
      dashStat('高表现', high, 'high'),
      dashStat('低表现', low, 'low')
    ]));
    card1.appendChild(el('div', { class: 'dash-stat' }, [
      el('div', { class: 'dash-stat-label' }, '平均分数'),
      el('div', { class: 'dash-stat-value' }, String(avgScore))
    ]));
    container.appendChild(card1);

    // 卡片 2：可复用经验
    const card2 = el('div', { class: 'dash-card' });
    card2.appendChild(el('div', { class: 'dash-card-title' }, ['可复用经验', el('span', { class: 'range-tag' }, '已验证')]));
    if (reusableLessons.length === 0) {
      card2.appendChild(el('div', { class: 'text-muted text-sm', style: 'padding:8px;' }, '暂无可复用经验，需更多高表现样本（≥2 条）。'));
    } else {
      reusableLessons.forEach(p => {
        card2.appendChild(el('div', { class: 'reusable-lesson' }, [
          el('div', { class: 'reusable-lesson-action' }, p.title),
          el('div', { class: 'reusable-lesson-reason' }, p.content)
        ]));
      });
    }
    container.appendChild(card2);

    // 卡片 3：待办动作
    const card3 = el('div', { class: 'dash-card' });
    card3.appendChild(el('div', { class: 'dash-card-title' }, ['待办动作', el('span', { class: 'range-tag' }, '运营建议')]));
    if (todos.length === 0) {
      card3.appendChild(el('div', { class: 'text-muted text-sm', style: 'padding:8px;' }, '暂无待办动作建议，需更多评论数据。'));
    } else {
      todos.forEach(t => {
        card3.appendChild(el('div', { class: 'todo-item' }, [
          el('div', { class: 'todo-action' }, [
            el('span', { class: 'todo-priority ' + t.priority }, t.priority.toUpperCase()),
            t.action
          ]),
          el('div', { class: 'todo-reason' }, t.reason)
        ]));
      });
    }
    container.appendChild(card3);
  }

  function dashStat(label, value, cls) {
    return el('div', { class: 'dash-stat' }, [
      el('div', { class: 'dash-stat-label' }, label),
      el('div', { class: 'dash-stat-value ' + (cls || '') }, String(value))
    ]);
  }

  function renderStatsRow() {
    const fd = Store.getFilteredData();
    const posts = fd.posts;
    const comments = fd.comments;
    const high = posts.filter(p => (Store.getPostAnalysis(p.id) || {}).performance?.level === 'high').length;
    const low = posts.filter(p => (Store.getPostAnalysis(p.id) || {}).performance?.level === 'low').length;
    const subreddits = new Set(posts.map(p => p.subreddit)).size;

    const container = $('#stats-row');
    container.innerHTML = '';
    [
      { label: '历史帖子', value: posts.length, cls: '' },
      { label: '用户评论', value: comments.length, cls: '' },
      { label: '覆盖 Subreddit', value: subreddits, cls: '' },
      { label: '高表现', value: high, cls: 'high' },
      { label: '低表现', value: low, cls: 'low' }
    ].forEach(s => {
      container.appendChild(el('div', { class: 'stat-card' }, [
        el('div', { class: 'stat-label' }, s.label),
        el('div', { class: 'stat-value ' + s.cls }, String(s.value))
      ]));
    });
  }

  function renderSubredditFilter() {
    const state = Store.getState();
    const subs = Array.from(new Set(state.posts.map(p => p.subreddit))).sort();
    const select = $('#filter-subreddit');
    const current = select.value;
    select.innerHTML = '<option value="">全部 Subreddit</option>' +
      subs.map(s => `<option value="${escapeHtml(s)}" ${s === current ? 'selected' : ''}>r/${escapeHtml(s)}</option>`).join('');
  }

  function renderPostsList() {
    const state = Store.getState();
    const fd = Store.getFilteredData();
    let posts = fd.posts;
    const titleFilter = lower($('#filter-title').value);
    const subFilter = $('#filter-subreddit').value;
    const levelFilter = $('#filter-level').value;
    const [sortBy, sortDir] = ($('#sort-by').value || 'postedAt-desc').split('-');

    if (titleFilter) posts = posts.filter(p => lower(p.title).includes(titleFilter) || lower(p.body || '').includes(titleFilter));
    if (subFilter) posts = posts.filter(p => p.subreddit === subFilter);
    if (levelFilter) posts = posts.filter(p => (Store.getPostAnalysis(p.id) || {}).performance?.level === levelFilter);

    posts.sort((a, b) => {
      let va = a[sortBy], vb = b[sortBy];
      if (typeof va === 'string') va = va || '';
      if (typeof vb === 'string') vb = vb || '';
      if (va < vb) return sortDir === 'desc' ? 1 : -1;
      if (va > vb) return sortDir === 'desc' ? -1 : 1;
      return 0;
    });

    const list = $('#posts-list');
    list.innerHTML = '';
    if (posts.length === 0) {
      list.appendChild(el('div', { class: 'empty-state' }, [
        el('div', { class: 'empty-icon' }, '📭'),
        el('h3', {}, '暂无历史内容'),
        el('p', {}, state.posts.length === 0
          ? '点击右上角「载入模拟数据」开始演示，或「+ 录入帖子」添加第一条内容。'
          : '没有匹配筛选条件的帖子，请调整筛选。')
      ]));
      return;
    }

    posts.forEach(p => {
      const analysis = Store.getPostAnalysis(p.id);
      const level = analysis?.performance?.level;
      const commentsCount = state.comments.filter(c => c.postId === p.id).length;
      const card = el('div', { class: 'post-card' });

      const header = el('div', { class: 'post-card-header' });
      header.appendChild(el('span', { class: 'post-id' }, p.id));
      header.appendChild(el('span', { class: 'sub-tag' }, 'r/' + p.subreddit));
      if (level) header.appendChild(el('span', { class: 'level-badge ' + level }, levelLabel(level)));
      header.appendChild(el('span', { class: 'post-title' }, p.title));
      if (p.url) {
        header.appendChild(el('a', {
          class: 'post-url', href: p.url, target: '_blank', rel: 'noopener',
          onclick: (e) => e.stopPropagation()
        }, '原文 ↗'));
      }
      card.appendChild(header);

      const meta = el('div', { class: 'post-meta' });
      const likesVal = p.likes ?? p.score;
      meta.appendChild(metaItem('👍 点赞', fmtNum(likesVal)));
      meta.appendChild(metaItem('💬 评论', fmtNum(p.comments) + (commentsCount ? ` (已录入 ${commentsCount})` : '')));
      if (p.views) meta.appendChild(metaItem('👁 浏览', fmtNum(p.views)));
      meta.appendChild(metaItem('📅 发布', fmtDate(p.postedAt)));
      if (analysis) {
        meta.appendChild(el('span', { class: 'post-meta-item' }, [
          '类型: ', el('strong', {}, analysis.contentType.type)
        ]));
        meta.appendChild(el('span', { class: 'post-meta-item' }, [
          '营销感: ', el('strong', {}, analysis.marketingFeel + '/5')
        ]));
      }
      card.appendChild(meta);

      // 配图信息标签
      if (p.hasImage) {
        const tag = el('span', {
          class: 'image-post-tag' + (p.imageQuality ? ' is-quality' : '')
        }, p.imageQuality ? '🖼 配图优质' : '🖼 有配图（一般）');
        card.appendChild(tag);
      } else {
        card.appendChild(el('span', { class: 'image-post-tag is-none' }, '🖼 无配图'));
      }

      // 分析分数 + 预测 vs 实际对比
      if (p.analysisScore != null) {
        const scoreDiff = p.analysisDiff;
        let diffRow;
        if (scoreDiff) {
          const accuracyMap = {
            accurate: { cls: 'calib-good', icon: '✅', text: '预测准确' },
            underestimated: { cls: 'calib-under', icon: '⬆️', text: '实际更高' },
            overestimated: { cls: 'calib-over', icon: '⬇️', text: '实际更低' }
          };
          const acc = accuracyMap[scoreDiff.accuracy] || accuracyMap.accurate;
          diffRow = el('div', { class: 'calibration-row ' + acc.cls }, [
            el('span', { class: 'calib-label' }, '🎯 评估闭环'),
            el('span', {}, `预测 ${scoreDiff.predicted}/5`),
            el('span', { class: 'calib-arrow' }, '→'),
            el('span', {}, `实际 ${scoreDiff.actual}/5`),
            el('span', { class: 'calib-diff' }, `${acc.icon} ${acc.text}（偏差 ${scoreDiff.diff}）`)
          ]);
        } else {
          diffRow = el('div', { class: 'calibration-row calib-neutral' }, [
            el('span', { class: 'calib-label' }, '🤖 分析分数'),
            el('span', {}, `${p.analysisScore}/5`),
            el('span', { class: 'calib-note' }, '(无发布前评估记录，无法对比)')
          ]);
        }
        card.appendChild(diffRow);
      }

      if (p.body) {
        card.appendChild(el('div', { class: 'post-body-preview' }, truncate(p.body, 200)));
      }

      const actions = el('div', { class: 'post-card-actions' });
      actions.appendChild(el('button', {
        class: 'btn btn-sm btn-ghost',
        onclick: (e) => { e.stopPropagation(); openEditPostModal(p.id); }
      }, '编辑'));
      actions.appendChild(el('button', {
        class: 'btn btn-sm btn-ghost',
        onclick: (e) => { e.stopPropagation(); openAddCommentModal(p.id); }
      }, '+ 评论'));
      actions.appendChild(el('button', {
        class: 'btn btn-sm btn-ghost',
        onclick: (e) => { e.stopPropagation(); switchPage('analysis'); selectPostForAnalysis(p.id); }
      }, '分析 →'));
      actions.appendChild(el('button', {
        class: 'btn btn-sm btn-ghost-danger',
        onclick: (e) => { e.stopPropagation(); confirmDeletePost(p.id); }
      }, '删除'));
      header.appendChild(actions);

      card.addEventListener('click', () => { switchPage('analysis'); selectPostForAnalysis(p.id); });
      list.appendChild(card);
    });
  }

  function metaItem(label, value) {
    return el('span', { class: 'post-meta-item' }, [label + ' ', el('strong', {}, String(value))]);
  }

  function lower(s) { return (s || '').toLowerCase(); }

  // ============ 页面 2: 内容分析 ============
  let currentAnalysisPostId = null;

  function renderAnalysisPage() {
    const state = Store.getState();
    const picker = $('#analysis-post-picker');
    picker.innerHTML = '';
    if (state.posts.length === 0) {
      $('#analysis-empty').style.display = 'block';
      $('#analysis-detail').style.display = 'none';
      picker.appendChild(el('p', { class: 'text-muted text-sm' }, '暂无帖子，请先在「历史内容」页面录入或载入模拟数据。'));
      return;
    }
    state.posts.forEach(p => {
      picker.appendChild(el('div', {
        class: 'picker-item',
        title: p.title,
        onclick: () => selectPostForAnalysis(p.id)
      }, `${p.id} · r/${p.subreddit} · ${truncate(p.title, 40)}`));
    });
    if (currentAnalysisPostId && state.posts.some(p => p.id === currentAnalysisPostId)) {
      selectPostForAnalysis(currentAnalysisPostId);
    } else {
      $('#analysis-empty').style.display = 'block';
      $('#analysis-detail').style.display = 'none';
    }
  }

  function selectPostForAnalysis(postId) {
    currentAnalysisPostId = postId;
    const post = Store.getPost(postId);
    if (!post) return;
    const analysis = Store.getPostAnalysis(postId);
    const comments = Store.getCommentsByPost(postId);
    const state = Store.getState();
    const commentAnalysis = state.commentAnalyses[post.subreddit];

    $('#analysis-empty').style.display = 'none';
    const detail = $('#analysis-detail');
    detail.style.display = 'flex';
    detail.innerHTML = '';

    // 帖子头
    const head = el('div', { class: 'analysis-post-head' });
    const likesVal = post.likes ?? post.score;
    head.appendChild(el('div', {}, [
      el('div', { class: 'analysis-post-title' }, post.title),
      el('div', { class: 'analysis-post-info' }, [
        metaChip('r/' + post.subreddit, 'sub'),
        metaChip(post.id, 'id'),
        metaChip('👍 点赞 ' + fmtNum(likesVal), likesVal >= 100 ? 'high' : (likesVal <= 10 ? 'low' : '')),
        metaChip('💬 评论 ' + fmtNum(post.comments), ''),
        post.views ? metaChip('👁 浏览 ' + fmtNum(post.views), '') : null,
        metaChip('📅 ' + fmtDate(post.postedAt), '')
      ].filter(Boolean))
    ]));
    if (post.url) {
      head.appendChild(el('a', { class: 'btn btn-sm btn-secondary', href: post.url, target: '_blank', rel: 'noopener' }, '查看原文 ↗'));
    }
    detail.appendChild(head);

    // 分析分数卡片
    if (post.analysisScore != null) {
      const scoreCard = el('div', { class: 'analysis-score-card' });
      const scoreDiff = post.analysisDiff;
      scoreCard.appendChild(el('div', { class: 'analysis-score-main' }, [
        el('div', { class: 'analysis-score-num' }, String(post.analysisScore)),
        el('div', { class: 'analysis-score-label' }, '🤖 系统分析分数 / 5')
      ]));
      if (scoreDiff) {
        const accuracyMap = {
          accurate: { cls: 'acc-good', text: '✅ 预测准确' },
          underestimated: { cls: 'acc-under', text: '⬆️ 实际高于预测' },
          overestimated: { cls: 'acc-over', text: '⬇️ 实际低于预测' }
        };
        const acc = accuracyMap[scoreDiff.accuracy] || accuracyMap.accurate;
        scoreCard.appendChild(el('div', { class: 'analysis-score-compare ' + acc.cls }, [
          el('span', {}, `🎯 发布前预测: ${scoreDiff.predicted}/5`),
          el('span', { class: 'analysis-score-arrow' }, '→'),
          el('span', {}, `🤖 实际分析: ${scoreDiff.actual}/5`),
          el('span', { class: 'analysis-score-result' }, `${acc.text}（偏差 ${scoreDiff.diff}）`)
        ]));
      } else {
        scoreCard.appendChild(el('div', { class: 'analysis-score-compare' }, [
          el('span', { class: 'analysis-score-note' }, '（未填写发布前评估分数，无法对比）')
        ]));
      }
      detail.appendChild(scoreCard);
    }

    // 帖子正文
    if (post.body) {
      detail.appendChild(card('帖子正文', [
        el('div', { class: 'post-body-full', style: 'font-size:13px;line-height:1.7;white-space:pre-wrap;color:var(--text);' }, post.body)
      ]));
    }

    // 表现分析
    if (analysis) {
      const perfCard = card('帖子表现分析', []);

      // 表现分档 + 依据
      perfCard.appendChild(section('表现分档', [
        el('div', { style: 'display:flex;align-items:center;gap:10px;margin-bottom:8px;' }, [
          el('span', { class: 'level-badge ' + analysis.performance.level }, perfLabelCN(analysis.performance.level)),
          el('span', { class: 'text-xs text-muted' }, '基于分位与绝对阈值（P75=前25% / P25=后25%）')
        ]),
        ...analysis.performance.reasons.map(r => el('div', { class: 'text-xs', style: 'color:var(--text-muted);margin-bottom:3px;' }, '· ' + r.replace(/分数/, '分数').replace(/内 P75\+/, '进入前25%').replace(/内 P25-/, '进入后25%').replace(/内中位区间/, '处于中位区间')))
      ]));

      // 内容类型
      perfCard.appendChild(section('内容类型', [
        el('div', { style: 'margin-bottom:6px;' }, [
          el('strong', { style: 'font-size:16px;' }, analysis.contentType.type),
          el('span', { class: 'level-tag ANALYSIS', style: 'margin-left:8px;' }, levelLabelCN('ANALYSIS'))
        ]),
        el('div', { class: 'text-xs text-muted' }, analysis.contentType.reason)
      ]));

      // 标题结构
      const ts = analysis.titleStructure;
      perfCard.appendChild(section('标题结构', [
        el('div', { class: 'text-sm', style: 'margin-bottom:6px;' }, ts.structureNote || '无明显结构特征'),
        el('div', { class: 'chip-row' }, [
          ts.length > 0 ? chip(`长度 ${ts.length}`) : null,
          ts.hasNumber ? chip('含数字', 'authentic') : null,
          ts.hasColon ? chip('冒号分隔') : null,
          ts.hasQuestion ? chip('疑问句') : null,
          ts.hasEmoji ? chip('含表情符号', 'marketing') : null
        ].filter(Boolean))
      ]));

      // 信号检测
      perfCard.appendChild(section('内容特征信号', [
        signalChip('真实经历信号', analysis.contentFeatures.authenticitySignals, 'authentic'),
        signalChip('营销信号', analysis.contentFeatures.marketingSignals, 'marketing'),
        signalChip('提问信号', analysis.contentFeatures.questionSignals, ''),
        signalChip('讨论触发信号', analysis.contentFeatures.discussionSignals, '')
      ]));

      // 维度评分
      perfCard.appendChild(section('维度评分', [
        dimGrid([
          { label: '营销感', value: analysis.marketingFeel, note: '1=低 / 5=极高' },
          { label: '社区匹配度', value: analysis.subredditMatch, note: '1=不匹配 / 5=高度匹配' }
        ]),
        el('div', { class: 'text-xs text-muted mt-2' }, analysis.matchNote)
      ]));

      // 讨论点
      if (analysis.discussionPoints && analysis.discussionPoints.length) {
        perfCard.appendChild(section('讨论点（提取自正文）', [
          el('ul', { class: 'discussion-list' },
            analysis.discussionPoints.map(d => el('li', { class: 'discussion-item' }, d))
          )
        ]));
      }

      // 品牌露出
      perfCard.appendChild(section('品牌/产品露出', [
        el('div', { class: 'text-sm' }, analysis.brandMention)
      ]));

      detail.appendChild(perfCard);
    } else {
      detail.appendChild(card('帖子表现分析', [
        el('div', { class: 'text-muted text-sm' }, '尚未分析，点击右上角「重新分析」生成结果。')
      ]));
    }

    // 评论列表 + 评论效果证明
    if (comments.length > 0) {
      // 评论效果证明（评论作为帖子有效性的证据）
      const evidenceCard = card('评论效果证明', []);
      const posCount = comments.filter(c => countApprovalSignals(c.text) > 0).length;
      const negCount = comments.filter(c => countNegativeSignals(c.text) > 0).length;
      const questionCount = comments.filter(c => c.text.includes('?')).length;
      const avgScore = comments.length ? Math.round(comments.reduce((s, c) => s + (c.score || 0), 0) / comments.length) : 0;
      evidenceCard.appendChild(el('div', { class: 'comment-evidence-summary' }, [
        '该帖子共录入 ' + comments.length + ' 条评论，平均分数 ' + avgScore + '。',
        avgScore >= 10 ? '评论质量较高，帖子引发了有效讨论。' : '评论互动较少，帖子讨论价值有限。',
        el('div', { class: 'comment-evidence-grid' }, [
          commentEvidenceStat(questionCount, '提问延伸', ''),
          commentEvidenceStat(posCount, '认可赞同', 'positive'),
          commentEvidenceStat(negCount, '质疑反对', 'negative')
        ])
      ]));
      detail.appendChild(evidenceCard);

      const commentsCard = card(`用户评论（${comments.length} 条）`, []);
      const sorted = [...comments].sort((a, b) => (b.score || 0) - (a.score || 0));
      const list = el('div', { class: 'evidence-list' });
      sorted.forEach(c => {
        list.appendChild(el('div', { class: 'evidence-item' }, [
          el('div', { class: 'evidence-quote' }, '"' + c.text + '"'),
          el('div', { class: 'evidence-meta' }, `${escapeHtml(c.author)} · 分数 ${c.score} · ${c.id}`)
        ]));
      });
      commentsCard.appendChild(list);
      detail.appendChild(commentsCard);
    } else {
      detail.appendChild(card('用户评论', [
        el('div', { class: 'text-muted text-sm' }, '该帖子暂无录入评论。可点击「+ 评论」补充。')
      ]));
    }

    // 该帖子评论词云图 + 情感分布（如果有评论分析）
    if (comments.length > 0 && commentAnalysis && commentAnalysis.sampleSize > 0) {
      // 仅展示本帖子评论在 Subreddit 词云中的贡献
      const postCommentTexts = comments.map(c => c.text).join(' ');
      const postWords = extractWordCloudFromText(postCommentTexts, 30);
      if (postWords.length > 0) {
        const wcCard = card('本帖子评论词云', [
          el('div', { class: 'text-xs text-muted mb-3' }, '基于本帖子 ' + comments.length + ' 条评论的关键词可视化')
        ]);
        wcCard.appendChild(renderWordCloud(postWords));
        detail.appendChild(wcCard);
      }

      // 情感分布
      const postSentiment = computePostSentiment(comments);
      if (postSentiment.total > 0) {
        const sentCard = card('本帖子评论情感分布', []);
        sentCard.appendChild(renderSentimentDistribution(postSentiment));
        detail.appendChild(sentCard);
      }
    }
  }

  // 评论信号计数（用于评论效果证明）
  function countApprovalSignals(text) {
    const APPROVAL = ['hit hard', 'underrated', 'same', 'confirmed', 'lesson', 'genuinely', 'changed my', 'changing my', 'this is real', 'this is the actual', 'everyone skips', 'underdiscussed'];
    const t = (text || '').toLowerCase();
    return APPROVAL.filter(s => t.includes(s)).length;
  }
  function countNegativeSignals(text) {
    const NEG = ['painful', 'struggle', 'hard', 'terrified', 'broke me', 'lost', 'disaster', 'killed me', 'burned', 'broke', 'scared', 'stuck', 'suspicious', 'proof', 'no breakdown', 'no screenshot', 'lottery', 'flex post', 'not reproducible', 'credibility problem', 'sounds like', 'reads as', 'instant scroll', 'feels like'];
    const t = (text || '').toLowerCase();
    return NEG.filter(s => t.includes(s)).length;
  }

  function commentEvidenceStat(num, label, cls) {
    return el('div', { class: 'comment-evidence-stat ' + cls }, [
      el('div', { class: 'num' }, String(num)),
      el('div', { class: 'lbl' }, label)
    ]);
  }

  // 从文本提取词云数据（用于单帖评论词云）
  function extractWordCloudFromText(text, topN) {
    const STOP = new Set(['the', 'a', 'an', 'is', 'are', 'was', 'were', 'has', 'have', 'had', 'do', 'does', 'did', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her', 'our', 'their', 'this', 'that', 'these', 'those', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'and', 'or', 'but', 'not', 'so', 'if', 'be', 'been', 'being', 'would', 'could', 'should', 'will', 'can', 'may', 'might', 'shall', 'will', 'just', 'than', 'then', 'also', 'very', 'really', 'too', 'all', 'any', 'some', 'no', 'yes', 'one', 'two', 'like', 'get', 'got', 'go', 'went', 'make', 'made', 'going']);
    const words = (text || '').toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length > 3 && !STOP.has(w));
    const freq = {};
    words.forEach(w => { freq[w] = (freq[w] || 0) + 1; });
    return Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, topN || 30).map(([word, count]) => ({ word, count }));
  }

  // 计算单帖评论情感分布
  function computePostSentiment(comments) {
    const pos = [], neg = [], neu = [];
    comments.forEach(c => {
      const app = countApprovalSignals(c.text);
      const negSig = countNegativeSignals(c.text);
      if (app > negSig) pos.push(c);
      else if (negSig > app) neg.push(c);
      else neu.push(c);
    });
    const pickSample = arr => arr.sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 2)
      .map(c => ({ quote: (c.text || '').slice(0, 100), fromCommentId: c.id, commentScore: c.score, level: 'DATA' }));
    return {
      positive: pos.length,
      negative: neg.length,
      neutral: neu.length,
      total: comments.length,
      samples: { positive: pickSample(pos), negative: pickSample(neg), neutral: pickSample(neu) },
      level: 'ANALYSIS'
    };
  }

  // ============ 词云图渲染（Canvas）============
  function renderWordCloud(words) {
    const canvas = el('canvas', { class: 'word-cloud-canvas' });
    setTimeout(() => drawWordCloud(canvas, words), 50);
    return canvas;
  }

  function drawWordCloud(canvas, words) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 600;
    const h = 220;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    if (!words || words.length === 0) {
      ctx.fillStyle = '#8a929e';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('暂无足够评论数据生成词云', w / 2, h / 2);
      return;
    }

    const maxCount = Math.max(...words.map(w => w.count));
    const minCount = Math.min(...words.map(w => w.count));
    const range = Math.max(1, maxCount - minCount);

    const colors = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#0891b2', '#7c3aed', '#db2777', '#ea580c'];
    const sortedWords = [...words].sort((a, b) => b.count - a.count);

    // 记录已放置的词的矩形区域
    const placed = [];
    const padding = 3; // 词间距

    const centerX = w / 2;
    const centerY = h / 2;

    for (let i = 0; i < sortedWords.length && i < 40; i++) {
      const word = sortedWords[i];
      const sizeRatio = (word.count - minCount) / range;
      const fontSize = Math.round(12 + sizeRatio * 20); // 12-32px
      ctx.font = fontSize + 'px "Segoe UI", sans-serif';
      const metrics = ctx.measureText(word.word);
      const tw = metrics.width;
      const th = fontSize;

      // 螺旋搜索：阿基米德螺旋线
      let placed_ok = false;
      const maxRadius = Math.max(w, h);

      for (let step = 0; step < maxRadius * 2 && !placed_ok; step++) {
        // 螺旋线方程：r = k * angle
        const angle = step * 0.15;
        const radius = angle * 1.8;

        if (radius > maxRadius) break;

        const x = centerX + Math.cos(angle) * radius - tw / 2;
        const y = centerY + Math.sin(angle) * radius + th / 2;

        // 边界检查
        if (x < padding || y < th + padding || x + tw + padding > w || y > h - padding) continue;

        // 碰撞检测
        const collide = placed.some(p =>
          x - padding < p.x + p.w &&
          x + tw + padding > p.x &&
          y - th - padding < p.y + p.h &&
          y + padding > p.y
        );

        if (!collide) {
          ctx.fillStyle = colors[i % colors.length];
          ctx.globalAlpha = 0.55 + sizeRatio * 0.45;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'alphabetic';
          ctx.fillText(word.word, x, y);
          placed.push({ x, y: y - th, w: tw, h: th });
          placed_ok = true;
        }
      }
    }
    ctx.globalAlpha = 1;
  }

  // ============ 情感分布渲染 ============
  function renderSentimentDistribution(sd) {
    const total = sd.total || 1;
    const posPct = Math.round(sd.positive / total * 100);
    const negPct = Math.round(sd.negative / total * 100);
    const neuPct = 100 - posPct - negPct;

    const wrap = el('div', {});
    wrap.appendChild(el('div', { class: 'sentiment-bar' }, [
      el('div', { class: 'sentiment-seg positive', style: `width:${posPct}%`, title: `正向 ${sd.positive} 条` }, posPct > 8 ? `${posPct}%` : ''),
      el('div', { class: 'sentiment-seg neutral', style: `width:${neuPct}%`, title: `中性 ${sd.neutral} 条` }, neuPct > 8 ? `${neuPct}%` : ''),
      el('div', { class: 'sentiment-seg negative', style: `width:${negPct}%`, title: `负向 ${sd.negative} 条` }, negPct > 8 ? `${negPct}%` : '')
    ]));
    wrap.appendChild(el('div', { class: 'sentiment-legend' }, [
      el('div', { class: 'sentiment-legend-item' }, [el('span', { class: 'sentiment-dot positive' }), `正向 ${sd.positive} 条 (${posPct}%)`]),
      el('div', { class: 'sentiment-legend-item' }, [el('span', { class: 'sentiment-dot neutral' }), `中性 ${sd.neutral} 条 (${neuPct}%)`]),
      el('div', { class: 'sentiment-legend-item' }, [el('span', { class: 'sentiment-dot negative' }), `负向 ${sd.negative} 条 (${negPct}%)`])
    ]));

    // 代表性评论
    wrap.appendChild(el('div', { class: 'sentiment-samples' }, [
      sentimentSampleCol('正向', sd.samples.positive, 'positive'),
      sentimentSampleCol('中性', sd.samples.neutral, 'neutral'),
      sentimentSampleCol('负向', sd.samples.negative, 'negative')
    ]));
    return wrap;
  }

  function sentimentSampleCol(label, samples, cls) {
    return el('div', { class: 'sentiment-sample-col' }, [
      el('h5', {}, label + (samples.length ? ` (${samples.length} 条)` : '')),
      ...samples.map(s => el('div', { class: 'sentiment-sample' }, '"' + escapeHtml(s.quote) + '"'))
    ]);
  }

  // ============ 品牌提及渲染 ============
  function renderBrandMention(bm) {
    return el('div', { class: 'brand-mention-item' }, [
      el('div', { class: 'brand-mention-head' }, [
        el('span', { class: 'brand-name' }, bm.brand),
        el('div', { class: 'brand-sentiment-mini' }, [
          el('span', { class: 'pos' }, `正向 ${bm.positiveMentions}`),
          el('span', { class: 'neu' }, `中性 ${bm.neutralMentions}`),
          el('span', { class: 'neg' }, `负向 ${bm.negativeMentions}`),
          el('span', { class: 'text-muted' }, `共 ${bm.totalMentions} 次`)
        ])
      ]),
      el('div', { class: 'brand-contexts' }, [
        '代表性上下文：',
        ...bm.contexts.slice(0, 2).map(c => el('div', { class: 'brand-context' },
          `[${c.sentiment === 'positive' ? '正' : c.sentiment === 'negative' ? '负' : '中'}] "${escapeHtml(c.quote)}"`
        ))
      ])
    ]);
  }

  // ============ 运营建议渲染 ============
  function renderOpSuggestion(s) {
    return el('div', { class: 'op-suggestion' }, [
      el('div', { class: 'op-suggestion-head' }, [
        el('span', { class: 'todo-priority ' + s.priority }, s.priority.toUpperCase()),
        el('span', { class: 'op-action' }, s.action)
      ]),
      el('div', { class: 'op-reason' }, s.reason)
    ]);
  }

  function metaChip(text, cls) {
    const styles = {
      sub: 'background:var(--accent-soft);color:var(--accent);padding:2px 8px;border-radius:4px;font-weight:600;font-size:11px;',
      id: 'font-family:var(--mono);color:var(--text-subtle);font-size:11px;',
      high: 'color:var(--high);font-weight:600;',
      low: 'color:var(--low);font-weight:600;',
      '': 'color:var(--text-muted);'
    };
    return el('span', { style: styles[cls] || styles[''] }, text);
  }

  function signalChip(label, sig, cls) {
    return el('div', { style: 'margin-bottom:6px;' }, [
      el('span', { class: 'text-xs text-muted', style: 'margin-right:8px;' },
        `${label}: ${sig.count} 个`),
      ...(sig.hits.length ? sig.hits.slice(0, 4).map(h => chip(h, cls)) : [el('span', { class: 'text-xs text-muted' }, '无')])
    ]);
  }

  function chip(text, cls) {
    return el('span', { class: 'chip ' + (cls || '') }, text);
  }

  function card(title, children) {
    return el('div', { class: 'card' }, [
      el('div', { class: 'card-title' }, title),
      ...children
    ]);
  }

  function section(title, children) {
    return el('div', { class: 'card-section' }, [
      el('div', { class: 'card-section-title' }, title),
      ...children
    ]);
  }

  function dimGrid(dims) {
    return el('div', { class: 'dim-grid' },
      dims.map(d => el('div', { class: 'dim-item' }, [
        el('div', { class: 'dim-label' }, [
          el('span', {}, d.label),
          el('strong', {}, d.value + '/5')
        ]),
        el('div', { class: 'dim-bar' }, [
          el('div', { class: 'dim-bar-fill l' + d.value, style: `width:${d.value * 20}%` })
        ]),
        d.note ? el('div', { class: 'text-xs text-muted mt-2' }, d.note) : null
      ].filter(Boolean)))
    );
  }

  function evidenceList(items, field, cls) {
    return el('div', { class: 'evidence-list' },
      items.map(item => el('div', { class: 'evidence-item ' + cls }, [
        el('div', { class: 'evidence-quote' }, '"' + escapeHtml(item[field]) + '"'),
        el('div', { class: 'evidence-meta' }, [
          `${item.author || ''} · 分数 ${item.commentScore || 0} · 来自 ${item.fromPostId}`,
          el('span', { class: 'level-tag ' + (item.level || 'ANALYSIS') }, levelLabelCN(item.level || 'ANALYSIS'))
        ])
      ]))
    );
  }

  // ============ 事实分析区块渲染 ============
  let _factualResult = null;
  const FACTUAL_TYPE_LABELS = {
    guide: '指南教程',
    showcase: '展示分享',
    question: '提问求助',
    discussion: '讨论交流',
    story: '经历分享',
    other: '其他'
  };

  function factualConfTag(conf) {
    const map = {
      '仅参考': 'f-conf-reference',
      '有限': 'f-conf-limited',
      '中等': 'f-conf-medium',
      '较稳定': 'f-conf-stable'
    };
    return el('span', { class: 'confidence-tag ' + (map[conf] || 'f-conf-reference') }, conf || '仅参考');
  }

  function statPill(label, value) {
    return el('span', { class: 'stat-pill' }, [
      el('span', { class: 'stat-pill-label' }, label),
      el('span', { class: 'stat-pill-value' }, String(value))
    ]);
  }

  function buildCommunityStatsTable(cs, subs) {
    const hasBenchmark = subs.some(sub => cs[sub].communityBenchmark && cs[sub].communityBenchmark.available);
    const headCells = [
      'Subreddit', '帖子数', 'Views (均/中/最高)', 'Upvotes (均/最高)',
      'Comments (均/最高)', '置信度', '表现最好的帖子', '来源'
    ];
    if (hasBenchmark) headCells.push('社区基准 Views 均值');
    const head = el('tr', {}, headCells.map(h => el('th', {}, h)));
    const rows = subs.map(sub => {
      const s = cs[sub];
      const top = s.topPost;
      const cells = [
        el('td', {}, 'r/' + sub),
        el('td', {}, fmtNum(s.postCount)),
        el('td', {}, `${fmtNum(Math.round(s.views.avg))} / ${fmtNum(Math.round(s.views.median))} / ${fmtNum(s.views.max)}`),
        el('td', {}, `${fmtNum(Math.round(s.upvotes.avg))} / ${fmtNum(s.upvotes.max)}`),
        el('td', {}, `${fmtNum(Math.round(s.comments.avg))} / ${fmtNum(s.comments.max)}`),
        el('td', {}, factualConfTag(s.confidence)),
        el('td', {}, top ? truncate(top.title, 40) : '—'),
        el('td', {}, el('span', { class: 'chip chip-sm' }, s.dataSource))
      ];
      if (hasBenchmark) {
        const cb = s.communityBenchmark || { available: false };
        if (cb.available) {
          const cmpTag = cmpBenchmarkTag(cb.niimbotVsCommunity);
          cells.push(el('td', {}, [
            el('div', {}, fmtNum(Math.round(cb.viewsAvg)) + ' (' + fmtNum(cb.postCount) + ' 条)'),
            cmpTag
          ]));
        } else {
          cells.push(el('td', { class: 'text-muted' }, '—'));
        }
      }
      return el('tr', {}, cells);
    });
    return el('div', { class: 'table-wrap' },
      el('table', { class: 'community-stats-table' }, [
        el('thead', {}, head),
        el('tbody', {}, rows)
      ])
    );
  }

  function cmpBenchmarkTag(level) {
    const map = {
      higher: { cls: 'f-conf-stable', text: '↑ 高于社区' },
      lower: { cls: 'f-conf-limited', text: '↓ 低于社区' },
      similar: { cls: 'f-conf-medium', text: '≈ 接近社区' },
      unknown: { cls: 'f-conf-reference', text: '无对比' }
    };
    const m = map[level] || map.unknown;
    return el('span', { class: 'confidence-tag ' + m.cls, style: 'margin-top:4px;display:inline-block;' }, m.text);
  }

  function buildContentTypeTable(ct, types) {
    const order = ['guide', 'showcase', 'question', 'discussion', 'story', 'other'];
    const sorted = order.filter(t => types.includes(t)).concat(types.filter(t => !order.includes(t)));
    const head = el('tr', {}, ['内容类型', '帖子数', '平均 Views', '平均 Upvotes', '平均 Comments']
      .map(h => el('th', {}, h)));
    const rows = sorted.map(t => {
      const g = ct[t];
      return el('tr', {}, [
        el('td', {}, FACTUAL_TYPE_LABELS[t] || t),
        el('td', {}, fmtNum(g.count)),
        el('td', {}, fmtNum(Math.round(g.views.avg))),
        el('td', {}, fmtNum(Math.round(g.upvotes.avg))),
        el('td', {}, fmtNum(Math.round(g.comments.avg)))
      ]);
    });
    return el('div', { class: 'table-wrap' },
      el('table', { class: 'community-stats-table' }, [
        el('thead', {}, head),
        el('tbody', {}, rows)
      ])
    );
  }

  function renderMentionList(title, mentions, isCompetitor) {
    if (!mentions || !mentions.count) return null;
    const list = mentions.list || [];
    return el('div', { class: 'mention-block' }, [
      el('div', { class: 'mention-block-title' }, `${title}（${mentions.count} 条）`),
      el('ul', { class: 'mention-list' },
        list.slice(0, 6).map(m => el('li', {}, [
          isCompetitor && m.competitors && m.competitors.length
            ? el('span', { class: 'chip chip-sm' }, m.competitors.join(' / ')) : null,
          el('span', { class: 'mention-quote' }, '"' + truncate(m.quote, 100) + '"'),
          (typeof m.likes === 'number' && m.likes > 0)
            ? el('span', { class: 'mention-likes' }, '👍 ' + m.likes) : null
        ]))
      )
    ]);
  }

  function renderTopCommentsList(top) {
    if (!top || !top.length) {
      return el('div', { class: 'mention-block' }, [
        el('div', { class: 'mention-block-title' }, '热门评论 Top 5'),
        el('div', { class: 'text-xs text-muted' }, '暂无带点赞数据的评论。')
      ]);
    }
    return el('div', { class: 'mention-block' }, [
      el('div', { class: 'mention-block-title' }, '热门评论 Top 5（按点赞排序）'),
      el('ol', { class: 'mention-list' },
        top.map(c => el('li', {}, [
          el('span', { class: 'mention-likes' }, '👍 ' + fmtNum(c.likes)),
          el('span', { class: 'mention-quote' }, '"' + truncate(c.quote, 120) + '"'),
          c.author ? el('span', { class: 'mention-author' }, c.author) : null
        ]))
      )
    ]);
  }

  function renderKeywordChips(title, arr) {
    const items = arr || [];
    return el('div', { class: 'mention-block' }, [
      el('div', { class: 'mention-block-title' }, title + (items.length ? `（${items.length}）` : '')),
      items.length === 0
        ? el('div', { class: 'text-xs text-muted' }, '暂无')
        : el('div', { class: 'chip-row' }, items.slice(0, 12).map(k => chip(`${k.keyword} ×${k.count}`)))
    ]);
  }

  function renderFactualSection(r) {
    if (!r) return null;
    const wrap = el('div', { class: 'factual-section' });

    // A. 数据来源标注卡（最重要）
    const ds = r.dataSources || {};
    const niim = ds.niimbotData || { postCount: 0, commentCount: 0, label: 'NIIMBOT 历史数据' };
    const comm = ds.communityData || { postCount: 0, commentCount: 0, label: 'Reddit 社区基准数据' };
    wrap.appendChild(el('div', { class: 'factual-card data-source-banner' }, [
      el('div', { class: 'card-section-title' }, '📊 数据来源标注'),
      el('div', { class: 'data-source-row' }, [
        el('strong', {}, niim.label + '：'),
        ` ${fmtNum(niim.postCount)} 条帖子，${fmtNum(niim.commentCount)} 条评论`
      ]),
      el('div', { class: 'data-source-row' }, [
        el('strong', {}, comm.label + '：'),
        comm.postCount > 0
          ? ` ${fmtNum(comm.postCount)} 条帖子`
          : ' 暂未导入（0 条）'
      ]),
      el('div', { class: 'data-source-warning' },
        '⚠ ' + (ds.note || '当前所有统计仅基于 NIIMBOT 自身历史样本，不代表社区整体水平')),
      el('div', { style: 'margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;' }, [
        el('button', {
          class: 'btn btn-secondary btn-sm',
          onclick: () => openImportCommunityModal()
        }, '导入社区基准数据'),
        comm.postCount > 0
          ? el('button', {
              class: 'btn btn-ghost btn-sm',
              onclick: () => {
                if (confirm('确定清空所有社区基准数据？此操作不可恢复。')) {
                  Store.clearCommunityData();
                  Analyzer.runFullAnalysis();
                  if (Analyzer.runFactualAnalysis) Analyzer.runFactualAnalysis();
                  refreshDataBadge();
                  renderPatternsPage();
                  toast('已清空社区基准数据', 'success');
                }
              }
            }, '清空社区基准数据')
          : null
      ].filter(Boolean))
    ]));

    // B. 社区表现统计表
    const cs = r.communityStats || {};
    const subKeys = Object.keys(cs);
    wrap.appendChild(el('div', { class: 'factual-card' }, [
      el('div', { class: 'card-section-title' }, '🌐 社区表现统计'),
      subKeys.length === 0
        ? el('div', { class: 'empty-state' }, el('p', {}, '暂无社区表现数据。'))
        : buildCommunityStatsTable(cs, subKeys)
    ]));

    // C. 内容类型表现分析
    const ct = r.contentTypeStats || {};
    const ctKeys = Object.keys(ct);
    wrap.appendChild(el('div', { class: 'factual-card' }, [
      el('div', { class: 'card-section-title' }, '🗂 内容类型表现分析'),
      ctKeys.length === 0
        ? el('div', { class: 'empty-state' }, el('p', {}, '暂无内容类型数据。'))
        : buildContentTypeTable(ct, ctKeys)
    ]));

    // D. 异常表现识别
    const outliers = (r.outliers && r.outliers.highOutliers) || [];
    wrap.appendChild(el('div', { class: 'factual-card' }, [
      el('div', { class: 'card-section-title' }, '✨ 异常表现识别'),
      outliers.length === 0
        ? el('div', { class: 'empty-state' }, el('p', {}, '暂无明显异常表现帖子（样本不足或无显著高于社区均值的帖子）。'))
        : el('div', { class: 'outlier-grid' },
            outliers.map(o => el('div', { class: 'outlier-card' }, [
              el('div', { class: 'outlier-title' }, [
                el('span', {}, truncate(o.title, 60)),
                el('span', { class: 'chip chip-sm' }, 'r/' + o.subreddit)
              ]),
              el('div', { class: 'outlier-stats' }, [
                statPill('Views', fmtNum(o.views)),
                statPill('社区均值', fmtNum(Math.round(o.avgViews))),
                statPill('倍数', o.multiple + 'x')
              ]),
              el('div', { class: 'outlier-tags' }, [
                el('span', { class: 'confidence-tag f-conf-stable' }, '高表现历史样本'),
                el('span', { class: 'chip chip-sm' }, o.dataSource)
              ])
            ]))
          )
    ]));

    // E. 评论深度分析
    const ci = r.commentInsights || {};
    const brandM = ci.brandMentions || { count: 0, list: [] };
    const compM = ci.competitorMentions || { count: 0, list: [] };
    wrap.appendChild(el('div', { class: 'factual-card comment-insight-section' }, [
      el('div', { class: 'card-section-title' }, '💬 评论深度分析'),
      el('div', { class: 'comment-insight-summary' }, [
        statPill('总评论数', fmtNum(ci.totalComments || 0)),
        statPill('品牌提及', fmtNum(brandM.count) + ' 条'),
        statPill('竞品提及', fmtNum(compM.count) + ' 条')
      ]),
      renderMentionList('品牌提及', brandM, false),
      renderMentionList('竞品提及', compM, true),
      renderTopCommentsList(ci.topComments),
      renderKeywordChips('用户需求关键词', ci.userNeeds),
      renderKeywordChips('使用场景关键词', ci.useCases)
    ].filter(Boolean)));

    return wrap;
  }

  // ============ 页面 3: 内容规律 ============
  function renderPatternsPage() {
    // 事实分析：在规律库概览之前调用并渲染（优雅降级，runFactualAnalysis 不存在时不报错）
    try {
      _factualResult = (Analyzer.runFactualAnalysis && typeof Analyzer.runFactualAnalysis === 'function')
        ? Analyzer.runFactualAnalysis()
        : null;
    } catch (e) {
      _factualResult = null;
    }

    const patterns = Store.getPatterns();
    const catFilter = $('#filter-pattern-category').value;
    const levelFilter = $('#filter-pattern-level').value;

    let filtered = patterns;
    if (catFilter) filtered = filtered.filter(p => p.category === catFilter);
    if (levelFilter) filtered = filtered.filter(p => p.level === levelFilter);

    // 数据概览
    const overview = $('#patterns-overview');
    overview.innerHTML = '';
    // 事实分析区块（放在「规律库概览」之前）
    const factualSection = renderFactualSection(_factualResult);
    if (factualSection) overview.appendChild(factualSection);
    if (patterns.length > 0) {
      const counts = {};
      patterns.forEach(p => { counts[p.category] = (counts[p.category] || 0) + 1; });
      const rangeDesc = patterns[0]?.timeRange || Store.getTimeRangeDescription();
      overview.appendChild(el('div', { class: 'card' }, [
        el('div', { class: 'card-section-title' }, [
          '规律库概览',
          el('span', { class: 'range-tag', style: 'background:var(--accent-soft);color:var(--accent);padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;margin-left:8px;' }, rangeDesc)
        ]),
        el('div', { class: 'chip-row' },
          Object.entries(counts).map(([cat, n]) => chip(`${categoryLabel(cat)} ×${n}`))
        )
      ]));
    }

    const list = $('#patterns-list');
    list.innerHTML = '';
    if (patterns.length === 0) {
      list.appendChild(el('div', { class: 'empty-state' }, [
        el('div', { class: 'empty-icon' }, '📚'),
        el('h3', {}, '规律库为空'),
        el('p', {}, '请先载入模拟数据或录入历史内容，然后点击「重新沉淀规律」。')
      ]));
      return;
    }

    if (filtered.length === 0) {
      list.appendChild(el('div', { class: 'empty-state' }, [
        el('h3', {}, '无匹配规律'),
        el('p', {}, '调整筛选条件查看其他规律。')
      ]));
      return;
    }

    // 排序：可复用经验（high_performance PATTERN）优先，其次其他 PATTERN，最后 INFERENCE
    const sorted = [...filtered].sort((a, b) => {
      const aScore = (a.category === 'high_performance' ? 0 : 1) * 10 + (a.level === 'PATTERN' ? 0 : 5);
      const bScore = (b.category === 'high_performance' ? 0 : 1) * 10 + (b.level === 'PATTERN' ? 0 : 5);
      return aScore - bScore;
    });

    sorted.forEach((p, idx) => {
      list.appendChild(renderPatternCardNew(p, idx === 0));
    });
  }

  // 新版规律卡片：精简、可点击展开、带 tooltip 定义
  const _patternExpanded = {};
  function renderPatternCardNew(p, defaultExpanded) {
    const key = p.id || p.title + '_' + p.category;
    const expanded = _patternExpanded[key] = _patternExpanded[key] ?? defaultExpanded;

    const experienceText = p.title.replace(/^高表现内容\s*/, '').replace(/为主$/, '');
    const isExperienceFirst = p.category === 'high_performance' && p.level === 'PATTERN';

    // 分类 tooltip 定义
    const defs = {
      high_performance: { title: '高表现规律', desc: '该规律来自 Score 进入 P75（前25%）或 ≥100 的帖子，代表社区中最成功的内容特征。' },
      low_performance: { title: '低表现规律', desc: '该规律来自 Score 处于 P25（后25%）或 ≤10 的帖子，代表需要避免的内容特征。' },
      user_need: { title: '用户需求', desc: '从评论区的提问类评论（含 how/what/how do you 等关键词）中提炼的用户真实需求。' },
      pain_point: { title: '用户痛点', desc: '从评论中含 pain/struggle/hard/broke 等痛点信号词的评论提炼，反映用户遇到的困难。' },
      hot_topic: { title: '高互动话题', desc: '评论数、提问数、讨论触发信号均较高的帖子所涉及的话题，是社区活跃讨论点。' },
      subreddit_rule: { title: '社区规律', desc: 'Subreddit 的内容偏好、评分分布、常见话题等特征，基于分位数统计得出。' },
      marketing_risk: { title: '营销风险', desc: '含营销信号词（revolutionary/game-changing/DM for/🚀 等）的帖子特征，在 Reddit 社区中通常得分较低。' },
      topic_opportunity: { title: '选题机会', desc: '当前社区讨论热度高但高表现内容较少的话题，有先发优势。' }
    };
    const levelDefs = {
      PATTERN: { title: '规律', desc: '基于 3 条以上数据聚合形成的稳定规律，可作为参考依据。' },
      INFERENCE: { title: '推测', desc: '样本不足（<3 条）或间接推断，仅供参考，建议补充更多数据验证。' }
    };
    const confDefs = {
      high: { title: '可稳定参考', desc: '基于 PATTERN 且样本数 ≥5，经过充分验证，可稳定参考。' },
      medium: { title: '可参考', desc: '基于 PATTERN 且样本数 3-4，有一定可信度，可参考使用。' },
      low: { title: '谨慎参考', desc: '基于 INFERENCE 或样本数 <3，可信度较低，需谨慎参考。' }
    };

    const catDef = defs[p.category] || { title: categoryLabel(p.category), desc: '' };
    const lvDef = levelDefs[p.level] || { title: p.level, desc: '' };
    const cfDef = confDefs[p.confidence] || confDefs.low;

    const toggleExpand = () => {
      _patternExpanded[key] = !_patternExpanded[key];
      const el = document.querySelector(`[data-pattern-key="${key}"]`);
      if (el) {
        const detail = el.querySelector('.pattern-card-detail');
        const chevron = el.querySelector('.pattern-chevron');
        if (_patternExpanded[key]) {
          detail.style.display = '';
          chevron.textContent = '▼';
        } else {
          detail.style.display = 'none';
          chevron.textContent = '▶';
        }
      }
    };

    const card = el('div', {
      class: 'pattern-card-new ' + p.category + (isExperienceFirst ? ' experience-first' : ''),
      'data-pattern-key': key
    }, [
      // 卡片头：精简展示
      el('div', { class: 'pattern-card-header', onclick: toggleExpand, style: 'cursor:pointer;' }, [
        el('div', { class: 'pattern-card-title-row' }, [
          el('span', { class: 'pattern-category-badge ' + p.category, 'data-tooltip': catDef.desc }, catDef.title),
          isExperienceFirst ? el('span', { class: 'pattern-experience-text-inline' }, experienceText) : el('span', { class: 'pattern-title-text' }, p.title),
          el('span', { class: 'pattern-chevron' }, expanded ? '▼' : '▶')
        ]),
        el('div', { class: 'pattern-card-meta-row' }, [
          el('span', { class: 'level-tag ' + p.level, 'data-tooltip': lvDef.desc }, levelLabelCN(p.level)),
          tooltipIcon(lvDef.desc, '定义'),
          el('span', { class: 'confidence-tag conf-' + (p.confidence || 'low'), 'data-tooltip': cfDef.desc }, cfDef.title),
          tooltipIcon(cfDef.desc, '置信度'),
          el('span', { class: 'pattern-sample' }, `样本 ${p.sampleSize}`),
          p.subreddit ? el('span', { class: 'chip chip-sm' }, 'r/' + p.subreddit) : null
        ].filter(Boolean))
      ]),

      // 展开详情
      el('div', { class: 'pattern-card-detail', style: expanded ? '' : 'display:none;' }, [
        // 现象
        p.content ? el('div', { class: 'pattern-detail-section' }, [
          el('div', { class: 'pattern-detail-label' }, '📌 现象'),
          el('div', { class: 'text-sm' }, p.content)
        ]) : null,
        // 数据依据
        p.evidence && p.evidence.length ? el('div', { class: 'pattern-detail-section' }, [
          el('div', { class: 'pattern-detail-label' }, `🔗 数据依据（${p.evidence.length} 条）`),
          el('div', { class: 'evidence-chips' },
            p.evidence.slice(0, 8).map(ev => ev.type === 'post'
              ? el('span', {
                  class: 'evidence-chip',
                  title: ev.title,
                  onclick: (e) => { e.stopPropagation(); switchPage('analysis'); selectPostForAnalysis(ev.id); }
                }, ev.id)
              : el('span', {
                  class: 'evidence-chip',
                  title: '评论: ' + (ev.postId || ''),
                  onclick: (e) => { e.stopPropagation(); switchPage('analysis'); selectPostForAnalysis(ev.postId); }
                }, ev.id))
          )
        ]) : null
      ].filter(Boolean))
    ]);
    return card;
  }

  // Tooltip 图标组件
  function tooltipIcon(desc, label) {
    return el('span', {
      class: 'tooltip-icon',
      'data-tooltip': desc,
      'data-tooltip-label': label || 'i',
      title: desc
    }, 'ⓘ');
  }

  // ============ 页面 4: Subreddit 社区分析 ============
  let currentSubreddit = '';
  function renderSubredditPage() {
    const state = Store.getState();
    const selector = $('#subreddit-selector');
    const content = $('#subreddit-content');

    // 填充 Subreddit 选择器
    const subreddits = [...new Set(state.posts.map(p => p.subreddit).filter(Boolean))];
    if (selector.options.length <= 1 || selector.options[0].value === '') {
      selector.innerHTML = '<option value="">选择 Subreddit</option>' +
        subreddits.map(s => `<option value="${s}">r/${s}</option>`).join('');
    }

    content.innerHTML = '';
    if (subreddits.length === 0) {
      content.appendChild(el('div', { class: 'empty-state' }, [
        el('div', { class: 'empty-icon' }, '🌐'),
        el('h3', {}, '暂无社区数据'),
        el('p', {}, '请先在「历史内容」页面录入帖子。')
      ]));
      return;
    }

    if (!currentSubreddit || !subreddits.includes(currentSubreddit)) {
      currentSubreddit = subreddits[0];
      selector.value = currentSubreddit;
    }

    const posts = state.posts.filter(p => p.subreddit === currentSubreddit);
    if (posts.length === 0) {
      content.appendChild(el('div', { class: 'empty-state' }, [
        el('h3', {}, '该社区暂无数据'),
        el('p', {}, '请选择其他社区或录入更多帖子。')
      ]));
      return;
    }

    // 0. 社区分析来源说明（不是"我只发布的那些"）
    const sourceNote = el('div', { class: 'card subreddit-source-note' }, [
      el('div', { style: 'display:flex;align-items:flex-start;gap:10px;' }, [
        el('span', { style: 'font-size:20px;flex-shrink:0;' }, '🌐'),
        el('div', {}, [
          el('div', { style: 'font-weight:700;font-size:14px;margin-bottom:4px;' }, '分析范围：r/' + currentSubreddit + ' 社区整体样本'),
          el('div', { style: 'font-size:12px;color:var(--text-muted);line-height:1.6;' }, [
            '本页洞察是基于你在工具中录入的 r/',
            el('strong', {}, currentSubreddit),
            ' 全部帖子样本（不论是否由你本人账号发布）提炼而成。',
            el('br'),
            '包含：你自己发的帖子、从社区中观察收集到的帖子、竞品帖子等——共同作为该社区偏好/规律的依据。',
            el('br'),
            el('span', { style: 'color:var(--text-subtle);' },
              `当前样本量：${posts.length} 条帖子 · ${state.comments.filter(c => posts.some(p => p.id === c.postId)).length} 条评论。样本越多，结论越可靠。`)
          ])
        ])
      ])
    ]);
    content.appendChild(sourceNote);

    // 1. 社区概览统计
    const scores = posts.map(p => (p.likes ?? p.score) || 0).sort((a, b) => a - b);
    const comments = posts.map(p => p.comments || 0).sort((a, b) => a - b);
    const avgScore = Math.round(scores.reduce((s, n) => s + n, 0) / scores.length);
    const avgComments = Math.round(comments.reduce((s, n) => s + n, 0) / comments.length);
    const p75Score = scores.length ? scores[Math.floor(scores.length * 0.75)] : 0;
    const p25Score = scores.length ? scores[Math.floor(scores.length * 0.25)] : 0;
    const highPerfCount = posts.filter(p => ((p.likes ?? p.score) || 0) >= p75Score || ((p.likes ?? p.score) || 0) >= 100).length;
    const lowPerfCount = posts.filter(p => ((p.likes ?? p.score) || 0) <= p25Score || ((p.likes ?? p.score) || 0) <= 10).length;

    content.appendChild(el('div', { class: 'card' }, [
      el('div', { class: 'card-section-title' }, `r/${currentSubreddit} 社区概览`),
      el('div', { class: 'subreddit-summary' }, [
        el('div', { class: 'sub-stat-card' }, [
          el('div', { class: 'sub-stat-value' }, String(posts.length)),
          el('div', { class: 'sub-stat-label' }, '帖子总数')
        ]),
        el('div', { class: 'sub-stat-card' }, [
          el('div', { class: 'sub-stat-value' }, String(avgScore)),
          el('div', { class: 'sub-stat-label' }, '平均分数'),
          el('span', { class: 'sub-stat-chip high' }, `P75=${p75Score}`)
        ]),
        el('div', { class: 'sub-stat-card' }, [
          el('div', { class: 'sub-stat-value' }, String(avgComments)),
          el('div', { class: 'sub-stat-label' }, '平均评论数')
        ]),
        el('div', { class: 'sub-stat-card' }, [
          el('div', { class: 'sub-stat-value' }, String(highPerfCount)),
          el('div', { class: 'sub-stat-label' }, '高表现帖子'),
          el('span', { class: 'sub-stat-chip high' }, `${Math.round(highPerfCount / posts.length * 100)}%`)
        ]),
        el('div', { class: 'sub-stat-card' }, [
          el('div', { class: 'sub-stat-value' }, String(lowPerfCount)),
          el('div', { class: 'sub-stat-label' }, '低表现帖子'),
          el('span', { class: 'sub-stat-chip low' }, `${Math.round(lowPerfCount / posts.length * 100)}%`)
        ])
      ])
    ]));

    // 2. 内容偏好分析
    const analyses = posts.map(p => Store.getPostAnalysis(p.id)).filter(Boolean);
    if (analyses.length > 0) {
      const typeCounts = {};
      analyses.forEach(a => {
        const t = a.contentType?.type || '未知';
        typeCounts[t] = (typeCounts[t] || 0) + 1;
      });
      const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
      const topType = sortedTypes[0];

      // 按表现分档统计内容类型
      const highPerfTypes = {};
      const highPosts = posts.filter(p => ((p.likes ?? p.score) || 0) >= p75Score || ((p.likes ?? p.score) || 0) >= 100);
      highPosts.forEach(p => {
        const a = Store.getPostAnalysis(p.id);
        if (a) {
          const t = a.contentType?.type || '未知';
          highPerfTypes[t] = (highPerfTypes[t] || 0) + 1;
        }
      });

      content.appendChild(el('div', { class: 'card' }, [
        el('div', { class: 'card-section-title' }, '内容偏好分析'),
        el('div', { class: 'text-sm text-muted', style: 'margin-bottom:10px;' },
          `社区最常见内容类型：<strong>${topType[0]}</strong>（${topType[1]} 条，${Math.round(topType[1] / analyses.length * 100)}%）`),
        el('div', { class: 'subreddit-content-type-list' },
          sortedTypes.map(([type, count]) => el('div', { class: 'subreddit-content-type-item' }, [
            el('span', {}, type),
            el('span', { class: 'subreddit-content-type-count' }, `${count} 条`)
          ]))
        ),
        Object.keys(highPerfTypes).length > 0 ? el('div', { style: 'margin-top:12px;' }, [
          el('div', { class: 'section-label-small' }, '高表现帖子偏好的内容类型'),
          el('div', { class: 'subreddit-content-type-list', style: 'margin-top:6px;' },
            Object.entries(highPerfTypes).sort((a, b) => b[1] - a[1]).map(([type, count]) =>
              el('div', { class: 'subreddit-content-type-item', style: 'border-left:3px solid var(--high);' }, [
                el('span', {}, type),
                el('span', { class: 'subreddit-content-type-count' }, `${count} 条`)
              ])
            )
          )
        ]) : null
      ]));

      // 3. 高表现特征归纳
      const highAnalysisList = analyses.filter((a, i) => {
        const p = posts[i];
        return p && (((p.likes ?? p.score) || 0) >= p75Score || ((p.likes ?? p.score) || 0) >= 100);
      });

      if (highAnalysisList.length >= 2) {
        const avgAuth = (highAnalysisList.reduce((s, a) => s + (a.contentFeatures?.authenticitySignals?.count || 0), 0) / highAnalysisList.length).toFixed(1);
        const avgMkt = (highAnalysisList.reduce((s, a) => s + (a.contentFeatures?.marketingSignals?.count || 0), 0) / highAnalysisList.length).toFixed(1);
        const avgMatch = Math.round(highAnalysisList.reduce((s, a) => s + (a.subredditMatch || 0), 0) / highAnalysisList.length);
        const avgMktFeel = Math.round(highAnalysisList.reduce((s, a) => s + (a.marketingFeel || 0), 0) / highAnalysisList.length);

        content.appendChild(el('div', { class: 'card' }, [
          el('div', { class: 'card-section-title' }, `高表现内容特征（${highAnalysisList.length} 条帖子）`),
          el('div', { class: 'subreddit-summary' }, [
            el('div', { class: 'sub-stat-card' }, [
              el('div', { class: 'sub-stat-value' }, avgAuth),
              el('div', { class: 'sub-stat-label' }, '真实经历信号均值'),
              el('span', { class: 'sub-stat-chip high' }, '越多越好')
            ]),
            el('div', { class: 'sub-stat-card' }, [
              el('div', { class: 'sub-stat-value' }, avgMkt),
              el('div', { class: 'sub-stat-label' }, '营销信号均值'),
              el('span', { class: 'sub-stat-chip low' }, '越少越好')
            ]),
            el('div', { class: 'sub-stat-card' }, [
              el('div', { class: 'sub-stat-value' }, avgMatch + '/5'),
              el('div', { class: 'sub-stat-label' }, '社区匹配度均值')
            ]),
            el('div', { class: 'sub-stat-card' }, [
              el('div', { class: 'sub-stat-value' }, avgMktFeel + '/5'),
              el('div', { class: 'sub-stat-label' }, '营销感均值'),
              el('span', { class: 'sub-stat-chip ' + (avgMktFeel <= 2 ? 'high' : (avgMktFeel >= 4 ? 'low' : 'medium')) },
                avgMktFeel <= 2 ? '低营销感' : (avgMktFeel >= 4 ? '高营销感' : '中等'))
            ])
          ]),
          el('div', { class: 'text-sm', style: 'margin-top:12px;line-height:1.6;' },
            avgMktFeel <= 2
              ? `💡 ${currentSubreddit} 社区偏好 <strong>真实、非营销</strong> 的内容。建议使用第一人称叙述（"I built/quit/learned"），避免 "revolutionary/game-changing/DM for" 等营销话术。`
              : avgMktFeel >= 4
              ? `💡 ${currentSubreddit} 社区对营销内容接受度较高，但仍建议控制营销信号在 3 个以下，配合真实经历叙述。`
              : `💡 ${currentSubreddit} 社区对营销内容容忍度中等。建议在真实经历叙述中自然融入产品信息，避免硬推。`)
        ]));
      }
    }

    // 4. 社区规律速览
    const patterns = Store.getPatterns().filter(p => p.subreddit === currentSubreddit);
    if (patterns.length > 0) {
      const topPatterns = patterns.filter(p => p.category === 'high_performance' && p.level === 'PATTERN').slice(0, 3);
      const needPatterns = patterns.filter(p => p.category === 'user_need').slice(0, 3);

      const patternCards = [];
      if (topPatterns.length > 0) {
        patternCards.push(el('div', { class: 'card' }, [
          el('div', { class: 'card-section-title' }, '🔥 高表现内容规律'),
          ...topPatterns.map(p => el('div', { class: 'pattern-detail-section' }, [
            el('div', { class: 'section-label-small' }, p.title),
            el('div', { class: 'text-sm' }, p.content)
          ]))
        ]));
      }
      if (needPatterns.length > 0) {
        patternCards.push(el('div', { class: 'card' }, [
          el('div', { class: 'card-section-title' }, '👥 用户高频需求'),
          ...needPatterns.map(p => el('div', { class: 'pattern-detail-section' }, [
            el('div', { class: 'section-label-small' }, p.title),
            el('div', { class: 'text-sm' }, p.content)
          ]))
        ]));
      }
      patternCards.forEach(c => content.appendChild(c));
    }

    // 5. 行动建议
    const suggestions = [];
    if (avgScore < 100) suggestions.push(`当前社区平均分数 ${avgScore}，整体偏低。建议重点研究高表现帖子的内容特征。`);
    if (highPerfCount > 0 && highPerfCount < posts.length * 0.2) suggestions.push(`高表现帖子占比仅 ${Math.round(highPerfCount / posts.length * 100)}%，竞争门槛较高。需精心打磨内容。`);
    if (analyses.length > 0) {
      const avgMktFeel = analyses.reduce((s, a) => s + (a.marketingFeel || 0), 0) / analyses.length;
      if (avgMktFeel >= 3) suggestions.push(`社区内容营销感均值 ${avgMktFeel.toFixed(1)}/5，用户对营销话术可能较敏感。建议降低营销感至 2 以下。`);
    }
    if (suggestions.length > 0) {
      content.appendChild(el('div', { class: 'card' }, [
        el('div', { class: 'card-section-title' }, '📋 社区运营建议'),
        ...suggestions.map((s, i) => el('div', { class: 'pattern-detail-section' }, [
          el('div', { class: 'section-label-small' }, `建议 ${i + 1}`),
          el('div', { class: 'text-sm' }, s)
        ]))
      ]));
    }
  }

  // ============ 指标定义面板 ============
  function renderDefinitionsPanel() {
    const container = $('#definitions-panel');
    if (!container) return;
    container.innerHTML = '';
    const defs = [
      {
        title: '高表现 / 中表现 / 低表现',
        desc: '基于该 Subreddit 内帖子分数的分位数 + 绝对阈值综合分档。高表现=分数进入 P75 或 ≥100，且评论数 ≥30 或进入 P75。',
        formula: '分数 ≥ P75(该社区) 且 评论数 ≥ 30 → high；分数 ≤ P25 或 ≤ 10 → low'
      },
      {
        title: '营销感（1-5 分）',
        desc: '基于营销信号词数量映射。信号词包括：revolutionary、game-changing、AI-powered、cutting-edge、must read、early access、sign up now、limited spots、DM for、link in profile、🚀🔥 等。标题含表情符号 +1。',
        formula: '信号词 ≥5 → 5分；≥3 → 4分；≥2 → 3分；≥1 → 2分；0 → 1分'
      },
      {
        title: '社区匹配度（1-5 分）',
        desc: '当前内容类型与该 Subreddit 高表现帖子内容类型的一致程度。高表现帖子中同类型占比越高，匹配度越高。',
        formula: '同类型占比 ≥ 50% → 5分；< 20% → 2分；样本不足 → 3分(INFERENCE)'
      },
      {
        title: '内容真实性（1-5 分）',
        desc: '基于真实经历信号词（i quit、i built、months later、here\'s the、honest、unfiltered、what worked/failed 等）数量，反向结合营销信号。',
        formula: '真实信号 ≥3 且 营销信号 ≤1 → 5分；营销信号 ≥4 → 1分'
      },
      {
        title: '用户价值（1-5 分）',
        desc: '新内容与该 Subreddit 用户高频提问的关键词重叠度。重叠度越高，说明越回应真实需求。',
        formula: '重叠度 > 15% → 5分；> 8% → 4分；< 8% → 2分'
      },
      {
        title: '讨论潜力（1-5 分）',
        desc: '内容是否包含开放性问题、讨论触发词（curious、would love to hear、AMA、thoughts?）。正文过短会降分。',
        formula: '含开放性问题 + 讨论触发词 → 5分；正文 < 200 字符 → 2分'
      },
      {
        title: '营销风险（1-5 分，分值越高风险越低）',
        desc: '反向评分：营销信号越多风险越高（分值越低）。含 DM for / limited spots / link in profile 等强营销话术直接降至 1-2 分。',
        formula: '营销信号 0 → 5分；含"DM for/limited spots" → 1-2分'
      },
      {
        title: '与历史内容重复度（1-5 分，分值越高越不重复）',
        desc: '基于 Jaccard 关键词相似度，与同 Subreddit 最相似历史帖子对比。> 40% 重叠 = 1分（高度重复）。',
        formula: 'Jaccard > 0.4 → 1分；> 0.25 → 3分；< 0.15 → 5分'
      },
      {
        title: '数据层级标识',
        desc: '每条分析结论标注来源层级。DATA=原始数据；ANALYSIS=基于数据的结构化提炼；PATTERN=多条数据聚合的规律；INFERENCE=AI推测（样本不足或间接推断）。',
        formula: '样本 < 3 → 强制降级为 INFERENCE，不形成 PATTERN'
      },
      {
        title: '情感分类（正/负/中性）',
        desc: '基于评论信号词分类：approval 信号 = 正向，pain + skepticism 信号 = 负向，其余 = 中性。不做简单情绪统计，而是分类展示代表性评论。',
        formula: 'approval > neg → 正向；neg > approval → 负向；否则中性'
      },
      {
        title: '规律置信度（高/中/低）',
        desc: '基于规律层级 + 样本数综合判定。PATTERN 且样本 ≥5 → 高（可稳定参考）；PATTERN 且样本 3-4 → 中（可参考）；INFERENCE 或样本 <3 → 低（谨慎参考，需更多数据验证）。',
        formula: 'level=PATTERN 且 sampleSize≥5 → high；=PATTERN 且 ≥3 → medium；其余 → low'
      },
      {
        title: '评估闭环校准',
        desc: '录入帖子时可选填「发布前评估预测分数」，系统对比实际分数显示偏差。偏差 ≤20 = 预测准确（绿）；实际 > 预测 = 低估（黄）；实际 < 预测 = 高估（红）。用于持续校准评估权重。',
        formula: '实际分数 - 预测分数：|diff| ≤20 → 准确；diff > 0 → 低估；diff < 0 → 高估'
      }
    ];
    const panel = el('div', { class: 'definitions-panel' });
    const head = el('div', { class: 'def-head' }, [
      el('h3', {}, '指标定义说明'),
      el('span', { class: 'def-toggle' }, '点击展开/收起 ▾')
    ]);
    const body = el('div', { class: 'def-body collapsed' });
    head.addEventListener('click', () => body.classList.toggle('collapsed'));
    body.appendChild(el('div', { class: 'def-grid' },
      defs.map(d => el('div', { class: 'def-item' }, [
        el('div', { class: 'def-item-title' }, d.title),
        el('div', { class: 'def-item-desc' }, d.desc),
        el('div', { class: 'def-item-formula' }, d.formula)
      ]))
    ));
    panel.appendChild(head);
    panel.appendChild(body);
    container.appendChild(panel);
  }

  function categoryLabel(cat) {
    return {
      high_performance: '高表现规律',
      low_performance: '低表现规律',
      user_need: '用户需求',
      pain_point: '用户痛点',
      hot_topic: '高互动话题',
      subreddit_rule: '社区规律',
      marketing_risk: '营销风险',
      topic_opportunity: '选题机会'
    }[cat] || cat;
  }

  // 规律置信度标签：可稳定参考 / 可参考 / 谨慎参考
  function confidenceLabel(c) {
    if (c === 'high') return '可稳定参考';
    if (c === 'medium') return '可参考';
    return '谨慎参考';
  }

  // 数据层级中文化
  function levelLabelCN(lv) {
    return { DATA: '原始数据', ANALYSIS: '分析结论', PATTERN: '规律', INFERENCE: '推测' }[lv] || lv;
  }

  // 性能分档中文化
  function perfLabelCN(lv) {
    return { high: '高表现', medium: '中表现', low: '低表现' }[lv] || lv;
  }

  // ============ 页面 4: 发布前评估 ============
  function renderEvaluatePage() {
    renderEvalHistory();
  }

  function renderEvalHistory() {
    const list = Store.getEvaluations();
    const container = $('#eval-history-list');
    container.innerHTML = '';
    if (list.length === 0) {
      container.appendChild(el('div', { class: 'text-muted text-sm', style: 'padding:8px;' }, '暂无评估记录。'));
      return;
    }
    list.slice(0, 8).forEach(ev => {
      container.appendChild(el('div', {
        class: 'eval-history-item',
        onclick: () => showEvaluationResult(ev)
      }, [
        el('span', { class: 'eval-history-title' }, truncate(ev.input.title || '(无标题)', 40)),
        el('span', { class: 'level-tag ' + (ev.overallScore >= 4 ? 'PATTERN' : (ev.overallScore >= 3 ? 'INFERENCE' : 'DATA')) },
          ev.overallScore + '/5')
      ]));
    });
  }

  function runEvaluation() {
    const subreddit = $('#eval-subreddit').value.trim();
    const title = $('#eval-title').value.trim();
    const body = $('#eval-body').value.trim();
    if (!subreddit || !title) {
      toast('请填写 Subreddit 和标题', 'error');
      return;
    }
    const state = Store.getState();
    const result = Analyzer.evaluateNewContent(
      { subreddit, title, body },
      state.posts,
      state.postAnalyses,
      state.commentAnalyses,
      state.patterns || []
    );
    Store.addEvaluation(result);
    showEvaluationResult(result);
    renderEvalHistory();
    toast('评估完成', 'success');
  }

  function showEvaluationResult(result) {
    const container = $('#eval-result');
    container.innerHTML = '';
    const score = result.overallScore;
    const scoreCls = score >= 5 ? 'l5' : score >= 4 ? 'l4' : score >= 3 ? 'l3' : score >= 2 ? 'l2' : 'l1';

    // 评分英雄区
    container.appendChild(el('div', { class: 'eval-score-hero' }, [
      el('div', { class: 'score-circle ' + scoreCls }, String(score)),
      el('div', { class: 'score-label' }, '综合评分 / 5')
    ]));

    // 推荐结论
    const recMap = {
      publish: { icon: '✅', text: '推荐发布', cls: 'publish' },
      revise: { icon: '✏️', text: '修改后发布', cls: 'revise' },
      not_recommended: { icon: '⚠️', text: '不建议发布', cls: 'not_recommended' }
    };
    const rec = recMap[result.recommendation] || recMap.revise;
    container.appendChild(el('div', { class: 'recommendation ' + rec.cls }, [
      el('span', { class: 'rec-icon' }, rec.icon),
      el('span', {}, rec.text)
    ]));

    // 维度评分
    const dims = result.dimensions;
    container.appendChild(el('div', { class: 'dim-section' }, [
      el('div', { class: 'dim-section-title' }, '六维评估'),
      dimGrid([
        { label: '社区匹配度', value: dims.subredditMatch, note: '' },
        { label: '内容真实性', value: dims.authenticity, note: '' },
        { label: '用户价值', value: dims.userValue, note: '' },
        { label: '讨论潜力', value: dims.discussionPotential, note: '' },
        { label: '营销风险', value: dims.marketingRisk, note: '分值越高风险越低' },
        { label: '重复度', value: dims.duplicationScore, note: '分值越高越不重复' }
      ])
    ]));

    // 判断依据
    container.appendChild(el('div', { class: 'dim-section' }, [
      el('div', { class: 'dim-section-title' }, '判断依据'),
      el('ul', { class: 'reasons-list' },
        result.reasons.map(r => el('li', { class: 'reason-item' }, [
          el('span', {}, r.text),
          el('span', { class: 'level-tag ' + r.level }, r.level)
        ]))
      )
    ]));

    // 修改建议（结构化：动作 + 原因 + 优先级 + 关联维度）
    if (result.suggestions && result.suggestions.length) {
      const priMap = {
        high: { label: '高优先级', cls: 'pri-high' },
        medium: { label: '中优先级', cls: 'pri-medium' },
        low: { label: '低优先级', cls: 'pri-low' }
      };
      container.appendChild(el('div', { class: 'dim-section' }, [
        el('div', { class: 'dim-section-title' }, '可执行的改进建议（按优先级排序）'),
        el('div', { class: 'suggestion-cards' },
          result.suggestions.map((s, i) => {
            const pri = priMap[s.priority] || priMap.medium;
            return el('div', { class: 'suggestion-card ' + pri.cls }, [
              el('div', { class: 'suggestion-card-head' }, [
                el('span', { class: 'suggestion-num' }, String(i + 1)),
                el('span', { class: 'suggestion-priority ' + pri.cls }, pri.label),
                s.dimension ? el('span', { class: 'suggestion-dim' }, '关联维度：' + s.dimension) : null
              ].filter(Boolean)),
              el('div', { class: 'suggestion-action' }, s.action || (typeof s === 'string' ? s : '')),
              s.reason ? el('div', { class: 'suggestion-reason' }, '原因：' + s.reason) : null
            ]);
          })
        )
      ]));
    }

    // 最相似历史帖子
    if (result.mostSimilarPost && result.mostSimilarPost.similarity > 0.15) {
      container.appendChild(el('div', { class: 'dim-section' }, [
        el('div', { class: 'dim-section-title' }, '最相似历史内容'),
        el('div', { class: 'evidence-item' }, [
          el('div', {}, [
            el('strong', {}, result.mostSimilarPost.id + ' '),
            el('span', {}, result.mostSimilarPost.title)
          ]),
          el('div', { class: 'text-xs text-muted mt-2' },
            `关键词重叠度 ${Math.round(result.mostSimilarPost.similarity * 100)}%`),
          el('button', {
            class: 'btn btn-sm btn-ghost mt-2',
            onclick: () => { switchPage('analysis'); selectPostForAnalysis(result.mostSimilarPost.id); }
          }, '查看该帖子 →')
        ])
      ]));
    }

    // 调用的规律
    if (result.appliedPatterns && result.appliedPatterns.length) {
      container.appendChild(el('div', { class: 'applied-patterns' }, [
        el('strong', {}, '本次评估调用的规律：'),
        el('div', { class: 'chip-row mt-2' },
          result.appliedPatterns.map(p => chip(`${p.id} · ${p.title}`))
        )
      ]));
    }
  }

  // ============ 模态框 ============
  function openModal(title, bodyBuilder) {
    $('#modal-title').textContent = title;
    const body = $('#modal-body');
    body.innerHTML = '';
    bodyBuilder(body);
    $('#modal-overlay').style.display = 'flex';
  }
  function closeModal() { $('#modal-overlay').style.display = 'none'; }

  function openAddPostModal() {
    const evaluations = Store.getEvaluations();
    const hasEvals = evaluations.length > 0;
    openModal('录入新帖子', (body) => {
      body.appendChild(el('div', { class: 'csv-help' }, '同一帖子只需录入一次，系统自动生成 Post ID。保存后自动计算分析分数，并支持「预测 vs 实际」对比。'));

      // 从评估历史选择
      if (hasEvals) {
        const evalOptions = el('div', { class: 'modal-form-group' }, [
          el('label', {}, '从发布前评估历史中选择（可选）'),
          (() => {
            const sel = el('select', { class: 'input', id: 'pf-eval-select' });
            sel.appendChild(el('option', { value: '' }, '-- 不选择，手动录入 --'));
            evaluations.slice(0, 20).forEach(ev => {
              const opt = el('option', { value: ev.id },
                `[${(ev.input.subreddit || '')}] ${truncate(ev.input.title || '(无)', 40)} · ${ev.overallScore}/5 · ${new Date(ev.createdAt).toLocaleDateString()}`
              );
              opt.dataset.evSubreddit = ev.input.subreddit || '';
              opt.dataset.evTitle = ev.input.title || '';
              opt.dataset.evBody = ev.input.body || '';
              opt.dataset.evScore = ev.overallScore || '';
              sel.appendChild(opt);
            });
            sel.addEventListener('change', (e) => {
              const opt = e.target.options[e.target.selectedIndex];
              if (opt && opt.value) {
                const fill = (id, val) => { const el = $('#' + id); if (el && val) el.value = val; };
                fill('pf-subreddit', opt.dataset.evSubreddit);
                fill('pf-title', opt.dataset.evTitle);
                fill('pf-body', opt.dataset.evBody);
                fill('pf-predictedScore', opt.dataset.evScore);
                toast('已从评估历史回填内容', 'success');
              }
            });
            return sel;
          })()
        ]);
        body.appendChild(evalOptions);
      }

      body.appendChild(postFormFields({ subreddit: '', title: '', body: '', postedAt: new Date().toISOString().slice(0, 10), url: '', likes: 0, comments: 0, views: 0, predictedScore: '', hasImage: false, imageQuality: false, imageDescription: '', authorType: 'community', brandRelation: 'none', isPublished: true }));

      // 批量评论录入区
      body.appendChild(el('div', { class: 'comments-input-section' }, [
        el('div', { class: 'comments-input-header' }, [
          el('span', { class: 'comments-input-title' }, '📝 批量录入评论（可选）'),
          el('button', {
            class: 'btn btn-ghost btn-sm',
            onclick: () => addCommentRow()
          }, '+ 添加评论')
        ]),
        el('div', { id: 'pf-comments-list', class: 'comments-input-list' })
      ]));

      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-primary', onclick: () => submitPostForm(false) }, '保存并分析')
      ]));
    });
  }

  function openEditPostModal(postId) {
    const post = Store.getPost(postId);
    if (!post) return;
    openModal('编辑帖子 · ' + post.id, (body) => {
      body.appendChild(el('div', { class: 'csv-help' }, `Post ID: ${post.id}（不可修改）。修改字段后保存将触发重新分析。`));
      body.appendChild(postFormFields({ ...post, postedAt: (post.postedAt || '').slice(0, 10) }));
      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-primary', onclick: () => submitPostForm(true, post.id) }, '保存并重新分析')
      ]));
    });
  }

  function postFormFields(data) {
    const wrap = el('div', {});
    const fields = [
      { key: 'subreddit', label: 'Subreddit', placeholder: '如 SaaS', required: true, half: true },
      { key: 'title', label: '标题', placeholder: '帖子标题', required: true },
      { key: 'body', label: '正文', placeholder: '帖子正文…', textarea: true },
      { key: 'postedAt', label: '发布日期', type: 'date', half: true },
      { key: 'url', label: 'Reddit URL', placeholder: 'https://www.reddit.com/r/...', half: true },
      { key: 'likes', label: '👍 点赞数', type: 'number', half: true, placeholder: 'Reddit 点赞数' },
      { key: 'comments', label: '💬 评论数', type: 'number', half: true },
      { key: 'views', label: '👁 浏览量', type: 'number', half: true },
      { key: 'predictedScore', label: '🎯 发布前评估分数（0-5）', type: 'number', half: true, placeholder: '发布前系统预测的分数' }
    ];
    fields.forEach(f => {
      const group = el('div', { class: 'modal-form-group', style: f.half ? 'display:inline-block;width:calc(50% - 8px);margin-right:8px;' : '' }, [
        el('label', {}, [f.label, f.required ? el('span', { class: 'req' }, ' *') : null].filter(Boolean))
      ]);
      const input = el(f.textarea ? 'textarea' : 'input', {
        class: 'input' + (f.textarea ? ' textarea' : ''),
        id: 'pf-' + f.key,
        placeholder: f.placeholder || ''
      });
      if (f.type === 'number') input.type = 'number';
      if (f.type === 'date') input.type = 'date';
      if (f.textarea) input.rows = 6;
      input.value = data[f.key] != null ? data[f.key] : '';
      group.appendChild(input);
      wrap.appendChild(group);
    });

    // 配图复选框组
    const imgRow = el('div', { class: 'image-form-row' }, [
      (() => {
        const wrap = el('label', { class: 'image-toggle', id: 'pf-hasImage-wrap' }, [
          (() => {
            const cb = el('input', { type: 'checkbox', id: 'pf-hasImage' });
            cb.checked = !!data.hasImage;
            return cb;
          })(),
          el('span', { class: 'image-toggle-label' }, '🖼 是否有配图')
        ]);
        return wrap;
      })(),
      (() => {
        const wrap = el('label', { class: 'image-toggle is-secondary', id: 'pf-imageQuality-wrap' }, [
          (() => {
            const cb = el('input', { type: 'checkbox', id: 'pf-imageQuality' });
            cb.checked = !!data.imageQuality;
            return cb;
          })(),
          el('span', { class: 'image-toggle-label' }, '✨ 配图优质')
        ]);
        const updateState = () => {
          const has = document.getElementById('pf-hasImage');
          const q = document.getElementById('pf-imageQuality');
          if (!has || !q) return;
          if (!has.checked) {
            q.checked = false;
            wrap.classList.add('disabled');
          } else {
            wrap.classList.remove('disabled');
          }
        };
        setTimeout(() => {
          const has = document.getElementById('pf-hasImage');
          if (has) {
            has.addEventListener('change', updateState);
            updateState();
          }
        }, 0);
        return wrap;
      })(),
      el('div', { class: 'image-form-hint' }, '没勾选「配图优质」= 一般或质量较差；勾选「配图优质」系统会自动作为加分项参与评分。')
    ]);
    wrap.appendChild(imgRow);

    // 配图描述（可选）
    const imgDescGroup = el('div', { class: 'modal-form-group' }, [
      el('label', {}, '配图描述（可选）'),
      (() => {
        const inp = el('input', { class: 'input', id: 'pf-imageDescription', placeholder: '如：产品使用场景照片 / 对比图 / 截图…' });
        inp.value = data.imageDescription || '';
        return inp;
      })()
    ]);
    wrap.appendChild(imgDescGroup);

    // 品牌身份与发布状态
    const identityRow = el('div', { class: 'brand-identity-row' }, [
      // authorType
      el('div', { class: 'modal-form-group', style: 'display:inline-block;width:calc(33% - 8px);margin-right:8px;' }, [
        el('label', {}, '发布者身份'),
        (() => {
          const sel = el('select', { class: 'input', id: 'pf-authorType' });
          const types = [
            { v: 'community', t: '社区普通' },
            { v: 'official', t: 'NIIMBOT 官方' },
            { v: 'personal', t: '个人账号推广' },
            { v: 'third_party', t: '第三方提及' }
          ];
          types.forEach(t => {
            const opt = el('option', { value: t.v }, t.t);
            if ((data.authorType || 'community') === t.v) opt.selected = true;
            sel.appendChild(opt);
          });
          return sel;
        })()
      ]),
      // brandRelation
      el('div', { class: 'modal-form-group', style: 'display:inline-block;width:calc(33% - 8px);margin-right:8px;' }, [
        el('label', {}, '品牌关系'),
        (() => {
          const sel = el('select', { class: 'input', id: 'pf-brandRelation' });
          const rels = [
            { v: 'none', t: '无关' },
            { v: 'official', t: '官方发布' },
            { v: 'promotional', t: '推广内容' },
            { v: 'organic_mention', t: '自然提及' }
          ];
          rels.forEach(r => {
            const opt = el('option', { value: r.v }, r.t);
            if ((data.brandRelation || 'none') === r.v) opt.selected = true;
            sel.appendChild(opt);
          });
          return sel;
        })()
      ]),
      // isPublished
      el('div', { class: 'modal-form-group', style: 'display:inline-block;width:calc(33% - 8px);' }, [
        el('label', {}, '发布状态'),
        (() => {
          const sel = el('select', { class: 'input', id: 'pf-isPublished' });
          const opts = [
            { v: 'true', t: '已发布（历史数据）' },
            { v: 'false', t: '待发布（草稿）' }
          ];
          opts.forEach(o => {
            const opt = el('option', { value: o.v }, o.t);
            if (String(data.isPublished !== false) === o.v) opt.selected = true;
            sel.appendChild(opt);
          });
          return sel;
        })()
      ])
    ]);
    wrap.appendChild(identityRow);

    // 自动分析分数提示（保存时由系统计算，不可手动填写）
    wrap.appendChild(el('div', { class: 'auto-score-hint' }, [
      el('span', { class: 'auto-score-icon' }, '🤖'),
      el('span', {}, '分析分数将在保存时由系统自动计算（0-5分），与发布前评估分数形成「预测 vs 实际」对比。')
    ]));

    return wrap;
  }

  function addCommentRow(commentData) {
    const list = $('#pf-comments-list');
    if (!list) return;
    const isAuthor = commentData?.isAuthor || commentData?.author === 'u/作者';
    const row = el('div', { class: 'comment-input-row' }, [
      el('div', { class: 'comment-input-grid-v2' }, [
        // 作者勾选框
        (() => {
          const wrap = el('label', { class: 'comment-author-toggle' }, [
            (() => {
              const cb = el('input', { type: 'checkbox', id: 'pf-comment-isAuthor' });
              cb.checked = !!isAuthor;
              cb.dataset.field = 'isAuthor';
              return cb;
            })(),
            el('span', { class: 'comment-author-toggle-label' }, '作者')
          ]);
          return wrap;
        })(),
        // 评论类型提示
        (() => {
          const tag = el('span', { class: 'comment-type-tag' }, '受众回复');
          tag.dataset.role = 'comment-type-tag';
          return tag;
        })(),
        // 评论内容
        (() => {
          const t = el('textarea', { class: 'input textarea', rows: 2, placeholder: '请输入评论内容…', id: 'pf-comment-text' });
          t.value = commentData?.text || '';
          t.dataset.field = 'text';
          return t;
        })()
      ]),
      // 扩展字段（点赞 / 品牌 / 竞品 / 需求 / 场景）
      el('div', { class: 'comment-input-extras' }, [
        (() => {
          const inp = el('input', { class: 'input input-sm', type: 'number', placeholder: '点赞', id: 'pf-comment-likes' });
          inp.value = commentData?.likes || '';
          inp.dataset.field = 'likes';
          inp.style.width = '70px';
          return inp;
        })(),
        (() => {
          const wrap = el('label', { class: 'comment-extra-toggle' }, [
            (() => {
              const cb = el('input', { type: 'checkbox', id: 'pf-comment-mentionsBrand' });
              cb.checked = !!commentData?.mentionsBrand;
              cb.dataset.field = 'mentionsBrand';
              return cb;
            })(),
            el('span', {}, '🏷 NIIMBOT')
          ]);
          return wrap;
        })(),
        (() => {
          const wrap = el('label', { class: 'comment-extra-toggle' }, [
            (() => {
              const cb = el('input', { type: 'checkbox', id: 'pf-comment-mentionsCompetitor' });
              cb.checked = !!commentData?.mentionsCompetitor;
              cb.dataset.field = 'mentionsCompetitor';
              return cb;
            })(),
            el('span', {}, '⚔ 竞品')
          ]);
          return wrap;
        })(),
        (() => {
          const inp = el('input', { class: 'input input-sm', placeholder: '竞品名称（如 Brother）', id: 'pf-comment-competitorName' });
          inp.value = commentData?.competitorName || '';
          inp.dataset.field = 'competitorName';
          inp.style.width = '140px';
          return inp;
        })(),
        (() => {
          const inp = el('input', { class: 'input input-sm', placeholder: '用户需求', id: 'pf-comment-userNeed' });
          inp.value = commentData?.userNeed || '';
          inp.dataset.field = 'userNeed';
          inp.style.width = '120px';
          return inp;
        })(),
        (() => {
          const inp = el('input', { class: 'input input-sm', placeholder: '使用场景', id: 'pf-comment-useCase' });
          inp.value = commentData?.useCase || '';
          inp.dataset.field = 'useCase';
          inp.style.width = '120px';
          return inp;
        })()
      ]),
      el('button', {
        class: 'btn btn-ghost btn-sm btn-remove-comment',
        onclick: (e) => { e.target.closest('.comment-input-row')?.remove(); }
      }, '✕')
    ]);
    // 绑定复选框变更事件：即时更新标签文字
    const cb = row.querySelector('[data-field="isAuthor"]');
    const tag = row.querySelector('[data-role="comment-type-tag"]');
    if (cb && tag) {
      const sync = () => {
        if (cb.checked) {
          tag.textContent = '作者回复（OP）';
          tag.classList.add('is-author');
        } else {
          tag.textContent = '受众回复';
          tag.classList.remove('is-author');
        }
      };
      cb.addEventListener('change', sync);
      sync();
    }
    list.appendChild(row);
    return row;
  }

  function submitPostForm(isEdit, existingId) {
    const get = (k) => { const e = $('#pf-' + k); return e ? e.value.trim() : ''; };
    const getNum = (k) => { const v = get(k); return v === '' ? undefined : Number(v); };
    const getCheck = (k) => { const e = $('#pf-' + k); return e ? !!e.checked : false; };
    const subreddit = get('subreddit').replace(/^r\//i, '');
    const title = get('title');
    if (!subreddit || !title) { toast('Subreddit 和标题为必填', 'error'); return; }

    const hasImage = getCheck('hasImage');
    const imageQuality = hasImage ? getCheck('imageQuality') : false;
    const imageDescription = get('imageDescription');
    const authorType = get('authorType') || 'community';
    const brandRelation = get('brandRelation') || 'none';
    const isPublished = get('isPublished') !== 'false';

    // 系统自动计算分析分数（基于当前内容和已有的分析引擎）
    const state = Store.getState();
    const analysisResult = Analyzer.evaluateNewContent(
      { subreddit, title, body: get('body'), hasImage, imageQuality },
      state.posts,
      state.postAnalyses,
      state.commentAnalyses,
      state.patterns || []
    );
    const autoScore = analysisResult.overallScore;

    const post = {
      subreddit,
      title,
      body: get('body'),
      postedAt: get('postedAt') ? new Date(get('postedAt')).toISOString() : new Date().toISOString(),
      url: get('url'),
      likes: getNum('likes'),
      comments: getNum('comments'),
      views: getNum('views'),
      predictedScore: getNum('predictedScore'),
      hasImage,
      imageQuality,
      imageDescription,
      isPublished,
      authorType,
      brandRelation,
      analysisScore: autoScore,
      analysisDiff: null,
      analysisEvaluatedAt: new Date().toISOString()
    };

    // 计算预测 vs 实际对比
    if (post.predictedScore != null) {
      const diff = Math.abs(post.predictedScore - autoScore);
      post.analysisDiff = {
        predicted: post.predictedScore,
        actual: autoScore,
        diff: diff,
        accuracy: diff <= 1 ? 'accurate' : (autoScore > post.predictedScore ? 'underestimated' : 'overestimated')
      };
    }

    if (isEdit && existingId) post.id = existingId;

    const result = Store.upsertPost(post);

    // 保存批量录入的评论
    const commentList = $('#pf-comments-list');
    if (commentList) {
      const rows = commentList.querySelectorAll('.comment-input-row');
      let savedCount = 0;
      let authorCount = 0;
      let audienceCount = 0;
      rows.forEach(row => {
        const getField = (field) => {
          const elNode = row.querySelector(`[data-field="${field}"]`);
          if (!elNode) return '';
          if (elNode.type === 'checkbox') return elNode.checked ? '1' : '';
          return elNode.value.trim();
        };
        const isAuthor = getField('isAuthor') === '1';
        const text = getField('text');
        const likes = parseInt(getField('likes')) || 0;
        const mentionsBrand = getField('mentionsBrand') === '1';
        const mentionsCompetitor = getField('mentionsCompetitor') === '1';
        const competitorName = getField('competitorName');
        const userNeed = getField('userNeed');
        const useCase = getField('useCase');
        if (text) {
          const author = isAuthor ? 'u/作者' : 'u/受众';
          Store.upsertComment({
            postId: result.post.id,
            author,
            text,
            score: 1,
            likes,
            mentionsBrand,
            mentionsCompetitor,
            competitorName,
            userNeed,
            useCase
          });
          savedCount++;
          if (isAuthor) authorCount++; else audienceCount++;
        }
      });
      if (savedCount > 0) {
        toast(`已保存 ${savedCount} 条评论（作者 ${authorCount} · 受众 ${audienceCount}）`, 'success');
      }
    }

    // 重新分析该帖 + 全量规律
    Analyzer.runFullAnalysis();
    Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
    closeModal();

    // 显示结果摘要
    const scoreMsg = `分析分数：${autoScore}/5`;
    const diffMsg = post.analysisDiff
      ? `· 预测 ${post.analysisDiff.predicted} vs 实际 ${autoScore}（${
          post.analysisDiff.accuracy === 'accurate' ? '✅ 准确' :
          post.analysisDiff.accuracy === 'underestimated' ? '⬆️ 实际更高' : '⬇️ 实际更低'
        }）`
      : '';
    toast(`${isEdit ? '已更新' : '已录入'} · ${scoreMsg} ${diffMsg}`, 'success');
    refreshDataBadge();
    renderHistoryPage();
  }

  function openAddCommentModal(postId) {
    const post = Store.getPost(postId);
    if (!post) return;
    openModal('为 ' + postId + ' 添加评论', (body) => {
      body.appendChild(el('div', { class: 'csv-help' }, `关联帖子：${escapeHtml(post.title)}`));
      const fields = [
        { key: 'author', label: '评论作者', placeholder: 'u/username', half: true },
        { key: 'score', label: '评论分数', type: 'number', half: true },
        { key: 'text', label: '评论内容', textarea: true }
      ];
      fields.forEach(f => {
        const group = el('div', { class: 'modal-form-group', style: f.half ? 'display:inline-block;width:calc(50% - 8px);margin-right:8px;' : '' }, [
          el('label', {}, f.label)
        ]);
        const input = el(f.textarea ? 'textarea' : 'input', { class: 'input' + (f.textarea ? ' textarea' : ''), id: 'cf-' + f.key, placeholder: f.placeholder || '' });
        if (f.type === 'number') input.type = 'number';
        if (f.textarea) input.rows = 4;
        group.appendChild(input);
        body.appendChild(group);
      });
      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-primary', onclick: () => submitCommentForm(postId) }, '保存')
      ]));
    });
  }

  function submitCommentForm(postId) {
    const author = $('#cf-author').value.trim() || 'u/anonymous';
    const text = $('#cf-text').value.trim();
    const score = $('#cf-score').value.trim();
    if (!text) { toast('评论内容不能为空', 'error'); return; }
    Store.upsertComment({
      postId, author, text,
      score: score === '' ? 1 : Number(score)
    });
    Analyzer.runFullAnalysis();
    Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
    closeModal();
    toast('评论已保存', 'success');
    renderHistoryPage();
  }

  function confirmDeletePost(postId) {
    openModal('删除帖子', (body) => {
      body.appendChild(el('p', { class: 'text-sm', style: 'margin-bottom:12px;' },
        `确认删除帖子 ${postId} 及其所有评论？此操作不可恢复。`));
      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-ghost-danger', onclick: () => deletePost(postId) }, '确认删除')
      ]));
    });
  }

  function deletePost(postId) {
    const state = Store.getState();
    state.posts = state.posts.filter(p => p.id !== postId);
    state.comments = state.comments.filter(c => c.postId !== postId);
    delete state.postAnalyses[postId];
    Store.persist();
    Analyzer.runFullAnalysis();
    Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
    closeModal();
    toast('已删除', 'success');
    refreshDataBadge();
    renderHistoryPage();
  }

  // ============ 模板下载 ============
  function downloadTemplate(type) {
    let csv = '';
    let filename = '';
    if (type === 'dashboard') {
      csv = '\uFEFFTitle,Content,Subreddit,Author,URL,Permalink,Status,Views,Upvotes,Comments,Upvote ratio,Published at,Comments,Comments,Comments\n' +
            '"Your post title","Your post body text here",r/your_subreddit,u/your_username,https://www.reddit.com/r/your_subreddit/comments/xxx/your_post_title/,/r/your_subreddit/comments/xxx/your_post_title/,Published,1500,8,19,84%,2026-08-12T10:00:00Z,"First comment text","Second comment text","Third comment text"\n' +
            '"Another post title","Another post body",r/another_sub,u/another_user,https://www.reddit.com/r/another_sub/comments/yyy/another_post_title/,/r/another_sub/comments/yyy/another_post_title/,Published,500,3,5,80%,2026-08-10T08:00:00Z,"Comment one","Comment two",\n';
      filename = 'reddit_dashboard_template.csv';
    } else if (type === 'posts') {
      csv = '\uFEFFsubreddit,title,body,postedAt,url,likes,comments,views,hasImage,imageQuality,imageDescription,isPublished,authorType,brandRelation,predictedScore\n' +
            'SaaS,帖子标题,"帖子正文内容，含换行需用双引号包裹",2026-08-01T10:00:00Z,https://reddit.com/r/SaaS/xxx,100,30,5000,true,true,产品使用场景照片,true,official,official,4.2\n' +
            'succulents,另一条标题,"正文…",2026-07-15T08:00:00Z,https://reddit.com/r/succulents/xxx,250,45,12000,false,false,,true,personal,promotional,\n';
      filename = 'reddit_posts_template.csv';
    } else if (type === 'comments') {
      csv = '\uFEFFpostId,isAuthor,text,likes,replyCount,level,parentCommentId,mentionsBrand,mentionsCompetitor,competitorName,userNeed,useCase\n' +
            'P-001,false,"普通观众评论（受众回复）",5,2,0,,false,false,,,收纳整理\n' +
            'P-001,true,"发帖人的评论（作者回复OP）",12,0,0,,true,false,,,标签机使用\n' +
            'P-001,false,"有人提到了 Brother 标签机",8,1,0,,false,true,Brother,寻找替代方案,标签分类\n';
      filename = 'reddit_comments_template.csv';
    }
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('模板已下载', 'success');
  }
  function openImportPostsModal() {
    openModal('批量导入帖子', (body) => {
      body.appendChild(el('div', { class: 'csv-help' }, [
        el('div', {}, '直接粘贴 Reddit Dashboard 导出的 CSV，格式如下：'),
        el('div', { class: 'mt-2', style: 'font-size:12px;line-height:1.8;' }, [
          el('code', {}, 'Title'), ' · ',
          el('code', {}, 'Content'), ' · ',
          el('code', {}, 'Subreddit'), ' · ',
          el('code', {}, 'Author'), ' · ',
          el('code', {}, 'URL'), ' · ',
          el('code', {}, 'Permalink'), ' · ',
          el('code', {}, 'Status'), ' · ',
          el('code', {}, 'Views'), ' · ',
          el('code', {}, 'Upvotes'), ' · ',
          el('code', {}, 'Comments'), ' (数量) · ',
          el('code', {}, 'Upvote ratio'), ' · ',
          el('code', {}, 'Published at'), ' · ',
          el('code', {}, 'Comments'), ' (评论内容，可多列)'
        ]),
        el('div', { class: 'mt-2' }, '评论直接在每行帖子后面的 Comments 列里，一条评论一列。Views/Upvotes 留空视为 0。同标题帖子自动更新。')
      ]));
      body.appendChild(el('div', { class: 'template-download-row' }, [
        el('span', { class: 'template-download-label' }, '📄 没有模板？'),
        el('button', {
          class: 'btn btn-ghost btn-sm',
          onclick: () => downloadTemplate('dashboard')
        }, '下载 Dashboard 格式模板')
      ]));
      body.appendChild(el('div', { class: 'modal-form-group' }, [
        el('label', {}, 'CSV 内容（Dashboard 格式）'),
        el('textarea', { class: 'input textarea', id: 'csv-posts-text', rows: 12, placeholder: 'Title,Content,Subreddit,Author,URL,Permalink,Status,Views,Upvotes,Comments,Upvote ratio,Published at,Comments,Comments\n"帖子标题","帖子正文",r/subreddit,u/作者,https://...,/r/...,Published,1500,8,19,84%,2026-08-12,"评论1","评论2"' })
      ]));
      body.appendChild(el('div', { class: 'csv-sample' },
        '直接从 Reddit Dashboard 复制粘贴即可。系统会自动解析标题、正文、社区、浏览量、点赞、评论数、评论内容。'
      ));

      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-primary', onclick: submitImportPosts }, '导入')
      ]));
    });
  }

  function submitImportPosts() {
    const postsText = $('#csv-posts-text').value.trim();
    if (!postsText) { toast('请粘贴 CSV 内容', 'error'); return; }
    try {
      const posts = Store.parseCsvPosts(postsText);
      if (posts.length === 0) { toast('未解析到有效帖子', 'error'); return; }
      const result = Store.importPosts(posts);

      // 处理 Dashboard 格式嵌入的评论（按帖子标题关联）
      const pending = window.__pendingEmbeddedComments || [];
      let commentAdded = 0;
      if (pending.length > 0) {
        const state = Store.getState();
        pending.forEach(c => {
          const target = state.posts.find(p =>
            (p.title || '').toLowerCase().trim() === c.postTitle.toLowerCase().trim()
          );
          if (target) {
            Store.upsertComment({
              postId: target.id,
              author: 'u/受众',
              text: c.text,
              score: 1
            });
            commentAdded++;
          }
        });
        window.__pendingEmbeddedComments = [];
      }

      Analyzer.runFullAnalysis();
      Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
      closeModal();
      let msg = `导入完成：新增 ${result.added}，更新 ${result.updated}，跳过 ${result.skipped}`;
      if (commentAdded > 0) msg += ` · 评论：新增 ${commentAdded}`;
      toast(msg, 'success');
      refreshDataBadge();
      renderHistoryPage();
    } catch (e) {
      toast('解析失败：' + e.message, 'error');
    }
  }

  function openImportCommunityModal() {
    openModal('导入社区基准数据', (body) => {
      body.appendChild(el('div', { class: 'csv-help' }, [
        el('div', {}, '导入 Reddit 社区的真实帖子数据，用于建立社区整体表现基准。'),
        el('div', { class: 'mt-2', style: 'font-size:12px;color:var(--text-muted);' },
          '⚠ 这些数据不是 NIIMBOT 自己发的帖子，而是社区其他用户的真实发布，仅作为整体表现对比基准。')
      ]));
      body.appendChild(el('div', { class: 'csv-help mt-2' }, [
        el('div', {}, '支持 Dashboard CSV 格式，字段：'),
        el('div', { class: 'mt-2', style: 'font-size:12px;line-height:1.8;' }, [
          el('code', {}, 'Title'), ' · ',
          el('code', {}, 'Content'), ' · ',
          el('code', {}, 'Subreddit'), ' · ',
          el('code', {}, 'Author'), ' · ',
          el('code', {}, 'URL'), ' · ',
          el('code', {}, 'Views'), ' · ',
          el('code', {}, 'Upvotes'), ' · ',
          el('code', {}, 'Comments'), ' · ',
          el('code', {}, 'Published at')
        ]),
        el('div', { class: 'mt-2' }, '按 URL 优先去重，URL 为空时按标题去重。同一帖子重复导入会自动跳过。')
      ]));
      body.appendChild(el('div', { class: 'template-download-row mt-2' }, [
        el('span', { class: 'template-download-label' }, '📄 没有模板？'),
        el('button', {
          class: 'btn btn-ghost btn-sm',
          onclick: () => downloadTemplate('dashboard')
        }, '下载 Dashboard 格式模板')
      ]));
      body.appendChild(el('div', { class: 'modal-form-group' }, [
        el('label', {}, 'CSV 内容（Dashboard 格式）'),
        el('textarea', {
          class: 'input textarea',
          id: 'csv-community-text',
          rows: 12,
          placeholder: 'Title,Content,Subreddit,Author,URL,Permalink,Status,Views,Upvotes,Comments,Upvote ratio,Published at\n"某用户真实帖子","正文内容",r/RealSubreddit,u/someone,https://...,/r/...,Published,2000,15,30,90%,2026-08-15T10:00:00Z'
        })
      ]));
      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-primary', onclick: submitImportCommunity }, '导入')
      ]));
    });
  }

  function submitImportCommunity() {
    const text = $('#csv-community-text').value.trim();
    if (!text) { toast('请粘贴 CSV 内容', 'error'); return; }
    try {
      const posts = Store.parseCsvPosts(text);
      if (posts.length === 0) { toast('未解析到有效帖子', 'error'); return; }
      // 嵌入评论只用于 NIIMBOT 数据导入，社区基准忽略
      window.__pendingEmbeddedComments = [];
      const result = Store.importCommunityPosts(posts);
      Analyzer.runFullAnalysis();
      if (Analyzer.runFactualAnalysis) Analyzer.runFactualAnalysis();
      closeModal();
      toast(`社区基准数据导入完成：新增 ${result.added} 条，跳过 ${result.skipped} 条`, 'success');
      refreshDataBadge();
      renderPatternsPage();
    } catch (e) {
      toast('解析失败：' + e.message, 'error');
    }
  }

  // ============ 顶部操作 ============
  function handleReset() {
    openModal('重置数据', (body) => {
      body.appendChild(el('p', { class: 'text-sm', style: 'margin-bottom:12px;' },
        '将清空所有帖子、评论、分析结果和评估记录，不可恢复。'));
      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-ghost-danger', onclick: () => { Store.resetToEmpty(); refreshDataBadge(); renderHistoryPage(); renderPatternsPage(); renderEvaluatePage(); closeModal(); toast('已重置', 'success'); } }, '确认重置')
      ]));
    });
  }

  function handleRerun() {
    if (Store.getState().posts.length === 0) { toast('暂无数据可分析', 'error'); return; }
    // 重新分析使用当前时间筛选范围
    Analyzer.runFullAnalysis(true);
    Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
    refreshDataBadge();
    updateTimeRangeDesc();
    const activePage = $('.nav-tab.active').dataset.page;
    switchPage(activePage);
    toast('分析已刷新（按当前时间范围）', 'success');
  }

  // ============ 时间筛选 ============
  function updateTimeRangeDesc() {
    $('#time-range-desc').textContent = Store.getTimeRangeDescription();
  }

  function handleTimeRangeChange() {
    const range = $('#time-range').value;
    const customStart = $('#time-start').value;
    const customEnd = $('#time-end').value;
    // 自定义范围显示日期输入
    $('#time-start').style.display = range === 'custom' ? '' : 'none';
    $('#time-end').style.display = range === 'custom' ? '' : 'none';
    Store.setTimeRange(range, { start: customStart, end: customEnd });
    updateTimeRangeDesc();
    // 仅刷新页面（不重新分析，让用户控制何时重新分析）
    const activePage = $('.nav-tab.active').dataset.page;
    if (activePage === 'history') renderHistoryPage();
    else if (activePage === 'patterns') renderPatternsPage();
  }

  // ============ 品牌词配置 ============
  function openBrandConfigModal() {
    const keywords = Store.getBrandKeywords();
    openModal('配置品牌词', (body) => {
      body.appendChild(el('div', { class: 'csv-help' }, [
        el('div', {}, '配置品牌词后，评论分析会按品牌词统计提及度、情感分布和讨论总结。'),
        el('div', { class: 'mt-2' }, '每行一个品牌词（不区分大小写）。留空则只使用自动识别（"my tool/product" 等通用提及 + 帖子标题专有名词）。')
      ]));
      body.appendChild(el('div', { class: 'modal-form-group' }, [
        el('label', {}, '品牌词列表'),
        el('textarea', {
          class: 'input textarea', id: 'brand-keywords-text', rows: 8,
          placeholder: 'Notion\nStripe\nShopify\n（每行一个）'
        }, keywords.join('\n'))
      ]));
      body.appendChild(el('div', { class: 'modal-actions' }, [
        el('button', { class: 'btn btn-ghost', onclick: closeModal }, '取消'),
        el('button', { class: 'btn btn-primary', onclick: submitBrandConfig }, '保存并重新分析')
      ]));
    });
  }

  function submitBrandConfig() {
    const text = $('#brand-keywords-text').value;
    const keywords = text.split('\n').map(s => s.trim()).filter(s => s);
    Store.setBrandKeywords(keywords);
    Analyzer.runFullAnalysis(true);
    Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
    closeModal();
    updateTimeRangeDesc();
    refreshDataBadge();
    const activePage = $('.nav-tab.active').dataset.page;
    if (activePage === 'analysis') selectPostForAnalysis(currentAnalysisPostId);
    else if (activePage === 'patterns') renderPatternsPage();
    toast(`已保存 ${keywords.length} 个品牌词`, 'success');
  }

  function fillEvalSample() {
    $('#eval-subreddit').value = 'SaaS';
    $('#eval-title').value = 'I shut down my SaaS after 18 months and $0 in revenue. Here\'s what I learned.';
    $('#eval-body').value = `18 months ago I started building a tool for indie hackers. Last week I killed it.

What went wrong:
- Built for a "market" I wasn't part of and didn't really understand
- Spent 4 months on features nobody asked for
- Never did a single sales call

What I learned:
- Distribution beats product, every time
- If you can't name 10 potential customers by name, you don't have a niche

Pivoting to something I actually use daily. AMA about the failure.`;
    toast('已填入示例内容', 'success');
  }

  // ============ 初始化 ============
  function init() {
    initMain();
  }

  function initMain() {
    // 事件绑定
    $$('.nav-tab').forEach(t => t.addEventListener('click', () => switchPage(t.dataset.page)));
    $('#btn-reset').addEventListener('click', handleReset);
    $('#btn-rerun').addEventListener('click', handleRerun);
    $('#btn-rerun-patterns').addEventListener('click', handleRerun);
    $('#btn-brand-config').addEventListener('click', openBrandConfigModal);

    $('#btn-add-post').addEventListener('click', openAddPostModal);
    $('#btn-import-posts').addEventListener('click', openImportPostsModal);

    $('#btn-evaluate').addEventListener('click', runEvaluation);
    $('#btn-eval-sample').addEventListener('click', fillEvalSample);

    $('#modal-close').addEventListener('click', closeModal);
    $('#modal-overlay').addEventListener('click', (e) => { if (e.target === $('#modal-overlay')) closeModal(); });

    // 时间筛选器
    $('#time-range').addEventListener('change', handleTimeRangeChange);
    $('#time-start').addEventListener('change', handleTimeRangeChange);
    $('#time-end').addEventListener('change', handleTimeRangeChange);

    ['filter-title', 'filter-subreddit', 'filter-level', 'sort-by'].forEach(id => {
      $('#' + id).addEventListener('input', renderPostsList);
      $('#' + id).addEventListener('change', renderPostsList);
    });
    ['filter-pattern-category', 'filter-pattern-level'].forEach(id => {
      $('#' + id).addEventListener('change', renderPatternsPage);
    });

    // Subreddit 社区分析选择器
    $('#subreddit-selector').addEventListener('change', (e) => {
      currentSubreddit = e.target.value;
      renderSubredditPage();
    });

    // 初始化：无数据时自动载入模拟数据
    const state = Store.getState();
    if (state.posts.length === 0) {
      Store.loadDemoData();
      Analyzer.runFullAnalysis(true);
      Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
      toast('已自动载入模拟数据演示', 'success');
    } else if (Object.keys(state.postAnalyses || {}).length === 0) {
      Analyzer.runFullAnalysis(true);
      Analyzer.runFactualAnalysis && Analyzer.runFactualAnalysis();
    }
    // 恢复时间筛选器 UI 状态
    const tr = Store.getTimeRange();
    $('#time-range').value = tr.range;
    if (tr.range === 'custom') {
      $('#time-start').style.display = '';
      $('#time-end').style.display = '';
      $('#time-start').value = tr.custom.start;
      $('#time-end').value = tr.custom.end;
    }
    updateTimeRangeDesc();
    refreshDataBadge();
    renderHistoryPage();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
