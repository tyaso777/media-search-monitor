const invoke = window.__TAURI__.core.invoke;

const state = {
  sort: "name",
  groupType: "company",
  adminGroupType: "company",
  articleSort: "published",
  companies: [],
  selectedCompany: null,
  articleRows: [],
  selectedArticleKeywords: new Set(),
  keywordGroups: [],
  selectedKeywordGroup: null,
  adminSelectedKeywordGroup: null,
  siteRequests: [],
  keywordRequests: [],
  siteHealthRows: [],
};

const els = {
  dbStatus: document.querySelector("#db-status"),
  refreshButton: document.querySelector("#refresh-button"),
  groupListTitle: document.querySelector("#group-list-title"),
  companySort: document.querySelector("#company-sort"),
  groupTypeTabs: document.querySelectorAll(".group-type-tab"),
  adminGroupTypeTabs: document.querySelectorAll(".admin-group-type-tab"),
  companyCount: document.querySelector("#company-count"),
  companyList: document.querySelector("#company-list"),
  selectedCompany: document.querySelector("#selected-company"),
  selectedCompanyMeta: document.querySelector("#selected-company-meta"),
  selectedPublishedMin: document.querySelector("#selected-published-min"),
  selectedHitMin: document.querySelector("#selected-hit-min"),
  articleSort: document.querySelector("#article-sort"),
  copyDays: document.querySelector("#copy-days"),
  copyMarkdownButton: document.querySelector("#copy-markdown-button"),
  copyStatus: document.querySelector("#copy-status"),
  articleKeywordFilter: document.querySelector("#article-keyword-filter"),
  clearKeywordFilter: document.querySelector("#clear-keyword-filter"),
  articleBody: document.querySelector("#article-body"),
  keywordGroupList: document.querySelector("#keyword-group-list"),
  candidateList: document.querySelector("#candidate-list"),
  keywordDetailTitle: document.querySelector("#keyword-detail-title"),
  keywordDetailMeta: document.querySelector("#keyword-detail-meta"),
  adminKeywordGroupList: document.querySelector("#admin-keyword-group-list"),
  adminCandidateList: document.querySelector("#admin-candidate-list"),
  adminKeywordDetailTitle: document.querySelector("#admin-keyword-detail-title"),
  adminKeywordDetailMeta: document.querySelector("#admin-keyword-detail-meta"),
  addGroupForm: document.querySelector("#add-group-form"),
  newGroupType: document.querySelector("#new-group-type"),
  newGroupInput: document.querySelector("#new-group-input"),
  addCandidateForm: document.querySelector("#add-candidate-form"),
  newCandidateInput: document.querySelector("#new-candidate-input"),
  addCandidateButton: document.querySelector("#add-candidate-button"),
  siteRequestForm: document.querySelector("#site-request-form"),
  siteRequestName: document.querySelector("#site-request-name"),
  siteRequestUrl: document.querySelector("#site-request-url"),
  siteRequesterName: document.querySelector("#site-requester-name"),
  siteRequesterEmail: document.querySelector("#site-requester-email"),
  siteRequestNotes: document.querySelector("#site-request-notes"),
  keywordRequestForm: document.querySelector("#keyword-request-form"),
  keywordRequestType: document.querySelector("#keyword-request-type"),
  keywordRequestGroupType: document.querySelector("#keyword-request-group-type"),
  keywordRequestBase: document.querySelector("#keyword-request-base"),
  keywordRequestCandidate: document.querySelector("#keyword-request-candidate"),
  keywordRequesterName: document.querySelector("#keyword-requester-name"),
  keywordRequesterEmail: document.querySelector("#keyword-requester-email"),
  keywordRequestReason: document.querySelector("#keyword-request-reason"),
  requestList: document.querySelector("#request-list"),
  adminRequestList: document.querySelector("#admin-request-list"),
  siteHealthList: document.querySelector("#site-health-list"),
};

function daysLabel(days) {
  if (days === null || days === undefined) return "-";
  return `${days}日`;
}

function toneForDays(days) {
  if (days === null || days === undefined) return "stale";
  if (days <= 0) return "hot";
  if (days <= 2) return "warm";
  if (days <= 7) return "mild";
  return "stale";
}

function groupTypeLabel(groupType) {
  return groupType === "topic" ? "トピック" : "会社";
}

function requestTypeLabel(requestType) {
  return requestType === "delete" ? "削除希望" : "追加希望";
}

function statusLabel(status) {
  const labels = {
    new: "未対応",
    reviewing: "確認中",
    accepted: "採用",
    rejected: "見送り",
    done: "実装済み",
  };
  return labels[status] ?? status;
}

function siteHealthLabel(status) {
  const labels = {
    ok: "正常",
    notice: "日付欠落あり",
    warning: "最新run 0件",
    error: "エラーあり",
    disabled: "無効",
  };
  return labels[status] ?? status;
}

function updateKeywordRequestPlaceholders() {
  const isTopic = els.keywordRequestGroupType.value === "topic";
  els.keywordRequestBase.placeholder = isTopic ? "例: 生成AI" : "例: トヨタ自動車";
  els.keywordRequestCandidate.placeholder = isTopic
    ? "例: LLM、大規模言語モデル"
    : "例: トヨタ、TOYOTA";
}

function activeMetric(company) {
  return state.sort === "hit" ? company.hit_min_days : company.published_min_days;
}

function escapeText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function splitCandidateKeywords(value) {
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function compareOptionalDays(a, b) {
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  return a - b;
}

function compareText(a, b) {
  return String(a ?? "").localeCompare(String(b ?? ""), "ja");
}

function markdownEscape(value) {
  return String(value ?? "")
    .replaceAll("\\", "\\\\")
    .replaceAll("|", "\\|")
    .replaceAll("\r", " ")
    .replaceAll("\n", " ")
    .trim();
}

function articleComparator(a, b) {
  if (state.articleSort === "hit") {
    return (
      compareOptionalDays(a.hit_days, b.hit_days) ||
      compareText(b.first_hit_at, a.first_hit_at) ||
      compareText(a.site_name, b.site_name) ||
      compareText(a.title, b.title)
    );
  }

  if (state.articleSort === "site") {
    return (
      compareText(a.site_name, b.site_name) ||
      compareOptionalDays(a.published_days, b.published_days) ||
      compareText(b.published_date, a.published_date) ||
      compareText(a.title, b.title)
    );
  }

  return (
    compareOptionalDays(a.published_days, b.published_days) ||
    compareText(b.published_date, a.published_date) ||
    compareOptionalDays(a.hit_days, b.hit_days) ||
    compareText(a.site_name, b.site_name) ||
    compareText(a.title, b.title)
  );
}

async function loadAll() {
  await Promise.all([loadStats(), loadCompanies(), loadKeywordTree(), loadRequests(), loadSiteHealth()]);
}

async function loadStats() {
  try {
    const stats = await invoke("get_stats", {});
    els.dbStatus.textContent = `会社・トピック ${stats.company_count} / 記事 ${stats.article_count} / ヒット ${stats.hit_count}`;
  } catch (error) {
    els.dbStatus.textContent = `DB読み込みエラー: ${error}`;
  }
}

async function loadCompanies() {
  try {
    state.companies = await invoke("get_keyword_summaries", {
      sort: state.sort,
      groupType: state.groupType,
    });
    els.groupListTitle.textContent = groupTypeLabel(state.groupType);
    els.companyCount.textContent = `${state.companies.length}件`;
    renderCompanies();
    if (!state.selectedCompany && state.companies.length > 0) {
      await selectCompany(state.companies[0].base_keyword_id);
    }
  } catch (error) {
    els.companyList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
  }
}

function renderCompanies() {
  els.companyList.innerHTML = "";
  for (const company of state.companies) {
    const metric = activeMetric(company);
    const row = document.createElement("button");
    row.type = "button";
    row.className = `company-row ${toneForDays(metric)} ${
      state.selectedCompany?.base_keyword_id === company.base_keyword_id ? "active" : ""
    }`;
    row.innerHTML = `
      <div>
        <div class="company-name">${escapeText(company.base_keyword)}</div>
        <div class="row-sub">記事 ${company.article_count} / サイト ${company.site_count}</div>
      </div>
      <div class="metric-pill">
        <span>${state.sort === "hit" ? "ヒット" : "掲載"}</span>
        <strong>${daysLabel(metric)}</strong>
      </div>
    `;
    row.addEventListener("click", () => selectCompany(company.base_keyword_id));
    els.companyList.appendChild(row);
  }
}

async function selectCompany(baseKeywordId) {
  const company = state.companies.find((item) => item.base_keyword_id === baseKeywordId);
  if (!company) return;
  state.selectedCompany = company;
  state.articleRows = [];
  state.selectedArticleKeywords = new Set();
  renderCompanies();
  els.selectedCompany.textContent = company.base_keyword;
  els.selectedCompanyMeta.textContent = `記事 ${company.article_count} / サイト ${company.site_count}`;
  els.selectedPublishedMin.textContent = daysLabel(company.published_min_days);
  els.selectedHitMin.textContent = daysLabel(company.hit_min_days);
  els.articleBody.innerHTML = `<tr><td colspan="6" class="empty">読み込み中</td></tr>`;
  renderArticleKeywordFilter();

  try {
    state.articleRows = await invoke("get_company_results", {
      baseKeywordId: baseKeywordId,
      limit: 5000,
    });
    renderArticleKeywordFilter();
    renderArticles();
  } catch (error) {
    els.articleBody.innerHTML = `<tr><td colspan="6" class="error">${escapeText(error)}</td></tr>`;
  }
}

function articleKeywordOptions() {
  const counts = new Map();
  for (const row of state.articleRows) {
    for (const keyword of splitCandidateKeywords(row.candidate_keywords)) {
      counts.set(keyword, (counts.get(keyword) ?? 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => compareText(a[0], b[0]));
}

function renderArticleKeywordFilter() {
  const options = articleKeywordOptions();
  els.articleKeywordFilter.innerHTML = "";
  els.clearKeywordFilter.disabled = state.selectedArticleKeywords.size === 0;

  if (!options.length) {
    els.articleKeywordFilter.innerHTML = `<span class="filter-empty">候補キーワードなし</span>`;
    return;
  }

  for (const [keyword, count] of options) {
    const label = document.createElement("label");
    label.className = "check-pill";
    label.innerHTML = `
      <input type="checkbox" value="${escapeText(keyword)}" ${state.selectedArticleKeywords.has(keyword) ? "checked" : ""} />
      <span>${escapeText(keyword)}</span>
      <em>${count}</em>
    `;
    label.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) {
        state.selectedArticleKeywords.add(keyword);
      } else {
        state.selectedArticleKeywords.delete(keyword);
      }
      renderArticleKeywordFilter();
      renderArticles();
    });
    els.articleKeywordFilter.appendChild(label);
  }
}

function filteredArticleRows() {
  const selected = state.selectedArticleKeywords;
  const rows =
    selected.size === 0
      ? [...state.articleRows]
      : state.articleRows.filter((row) =>
          splitCandidateKeywords(row.candidate_keywords).some((keyword) => selected.has(keyword)),
        );
  return rows.sort(articleComparator);
}

function rowsForMarkdownCopy() {
  const days = Number.parseInt(els.copyDays.value, 10);
  const maxDays = Number.isFinite(days) ? Math.max(0, days) : 1;
  return filteredArticleRows().filter(
    (row) => row.published_days !== null && row.published_days !== undefined && row.published_days <= maxDays,
  );
}

function buildMarkdown(rows) {
  const title = state.selectedCompany?.base_keyword || "検索結果";
  const days = Number.parseInt(els.copyDays.value, 10);
  const maxDays = Number.isFinite(days) ? Math.max(0, days) : 1;
  const lines = [
    `## ${markdownEscape(title)} 掲載日直近${maxDays}日分`,
    "",
    "| 掲載日 | サイト | タイトル | 候補キーワード | スニペット |",
    "|---|---|---|---|---|",
  ];
  for (const row of rows) {
    const titleText = markdownEscape(row.title || row.url);
    const url = String(row.url || "").replaceAll(")", "%29");
    lines.push(
      `| ${markdownEscape(row.published_date || "-")} | ${markdownEscape(row.site_name)} | [${titleText}](${url}) | ${markdownEscape(row.candidate_keywords)} | ${markdownEscape(row.snippet || "")} |`,
    );
  }
  return `${lines.join("\n")}\n`;
}

async function copyRecentMarkdown() {
  const rows = rowsForMarkdownCopy();
  if (!rows.length) {
    els.copyStatus.textContent = "対象記事がありません";
    return;
  }
  const markdown = buildMarkdown(rows);
  try {
    await navigator.clipboard.writeText(markdown);
    els.copyStatus.textContent = `${rows.length}件をコピーしました`;
  } catch (error) {
    els.copyStatus.textContent = `コピーできませんでした: ${error}`;
  }
}

function renderArticles() {
  const rows = filteredArticleRows();
  if (!rows.length) {
    const message = state.articleRows.length ? "条件に合う記事がありません" : "記事がありません";
    els.articleBody.innerHTML = `<tr><td colspan="6" class="empty">${message}</td></tr>`;
    return;
  }
  els.articleBody.innerHTML = rows
    .map((row) => {
      const publishedTone = toneForDays(row.published_days);
      const hitTone = toneForDays(row.hit_days);
      return `
        <tr>
          <td><span class="tone ${publishedTone}"></span>${escapeText(row.published_date || "-")}<div class="row-sub">${daysLabel(row.published_days)}</div></td>
          <td><span class="tone ${hitTone}"></span>${escapeText((row.first_hit_at || "").slice(0, 10))}<div class="row-sub">${daysLabel(row.hit_days)}</div></td>
          <td>${escapeText(row.site_name)}</td>
          <td><a class="title-link" href="${escapeText(row.url)}" target="_blank" rel="noreferrer">${escapeText(row.title || row.url)}</a></td>
          <td>${escapeText(row.candidate_keywords)}</td>
          <td><div class="snippet">${escapeText(row.snippet || "")}</div></td>
        </tr>
      `;
    })
    .join("");
  els.articleBody.querySelectorAll(".title-link").forEach((link) => {
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      const url = link.getAttribute("href");
      if (!url) return;
      try {
        await invoke("open_external_url", { url });
      } catch (error) {
        els.dbStatus.textContent = `URLを開けませんでした: ${error}`;
      }
    });
  });
}

async function loadKeywordTree() {
  try {
    state.keywordGroups = await invoke("get_keyword_tree", {});
    renderKeywordGroups();
    renderAdminKeywordGroups();
    if (!state.selectedKeywordGroup && state.keywordGroups.length > 0) {
      selectKeywordGroup(state.keywordGroups[0].base_keyword_id);
    }
    if (
      !state.adminSelectedKeywordGroup ||
      state.adminSelectedKeywordGroup.group_type !== state.adminGroupType
    ) {
      selectFirstAdminKeywordGroupForType();
    } else {
      selectAdminKeywordGroup(state.adminSelectedKeywordGroup.base_keyword_id);
    }
  } catch (error) {
    els.keywordGroupList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
    els.adminKeywordGroupList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
  }
}

function renderKeywordGroups() {
  els.keywordGroupList.innerHTML = "";
  for (const group of state.keywordGroups) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `keyword-view-row ${group.enabled ? "" : "disabled-row"} ${
      state.selectedKeywordGroup?.base_keyword_id === group.base_keyword_id ? "active" : ""
    }`;
    row.innerHTML = `
      <div>
        <div class="keyword-name">${escapeText(group.base_keyword)}</div>
        <div class="row-sub">${group.candidates.length}候補</div>
      </div>
      <span class="type-badge">${groupTypeLabel(group.group_type)}</span>
    `;
    row.addEventListener("click", () => selectKeywordGroup(group.base_keyword_id));
    els.keywordGroupList.appendChild(row);
  }
}

function selectKeywordGroup(baseKeywordId) {
  const group = state.keywordGroups.find((item) => item.base_keyword_id === baseKeywordId);
  if (!group) return;
  state.selectedKeywordGroup = group;
  renderKeywordGroups();
  els.keywordDetailTitle.textContent = group.base_keyword;
  els.keywordDetailMeta.textContent = `${groupTypeLabel(group.group_type)} / 候補 ${group.candidates.length}件`;
  renderCandidates(group);
}

function renderCandidates(group) {
  if (!group.candidates.length) {
    els.candidateList.innerHTML = `<div class="empty">候補キーワードがありません</div>`;
    return;
  }
  els.candidateList.innerHTML = "";
  for (const candidate of group.candidates) {
    const row = document.createElement("div");
    row.className = `candidate-row ${candidate.enabled ? "" : "disabled-row"}`;
    row.innerHTML = `
      <div>
        <div class="keyword-name">${escapeText(candidate.candidate_keyword)}</div>
        <div class="row-sub">${candidate.enabled ? "有効" : "無効"}</div>
      </div>
    `;
    els.candidateList.appendChild(row);
  }
}

function renderAdminKeywordGroups() {
  els.adminKeywordGroupList.innerHTML = "";
  const groups = state.keywordGroups.filter((group) => group.group_type === state.adminGroupType);
  if (!groups.length) {
    els.adminKeywordGroupList.innerHTML = `<div class="empty">${groupTypeLabel(state.adminGroupType)}の親キーワードはありません</div>`;
    return;
  }
  for (const group of groups) {
    const row = document.createElement("div");
    row.className = `keyword-row ${group.enabled ? "" : "disabled-row"}`;
    row.innerHTML = `
      <button type="button" class="keyword-name">${escapeText(group.base_keyword)}</button>
      <span class="type-badge">${groupTypeLabel(group.group_type)}</span>
      <button type="button" class="status-toggle">${group.enabled ? "無効化" : "有効化"}</button>
    `;
    row.querySelector(".keyword-name").addEventListener("click", () => {
      selectAdminKeywordGroup(group.base_keyword_id);
    });
    row.querySelector(".status-toggle").addEventListener("click", async () => {
      await invoke("set_keyword_group_enabled", {
        baseKeywordId: group.base_keyword_id,
        enabled: !group.enabled,
      });
      await loadKeywordTree();
      await loadCompanies();
    });
    els.adminKeywordGroupList.appendChild(row);
  }
}

function selectFirstAdminKeywordGroupForType() {
  const group = state.keywordGroups.find((item) => item.group_type === state.adminGroupType);
  if (group) {
    selectAdminKeywordGroup(group.base_keyword_id);
    return;
  }
  state.adminSelectedKeywordGroup = null;
  els.adminKeywordDetailTitle.textContent = "候補キーワード";
  els.adminKeywordDetailMeta.textContent = `${groupTypeLabel(state.adminGroupType)}の親キーワードを選択してください`;
  els.newCandidateInput.disabled = true;
  els.addCandidateButton.disabled = true;
  els.adminCandidateList.innerHTML = `<div class="empty">${groupTypeLabel(state.adminGroupType)}の親キーワードはありません</div>`;
}

function selectAdminKeywordGroup(baseKeywordId) {
  const group = state.keywordGroups.find((item) => item.base_keyword_id === baseKeywordId);
  if (!group) return;
  state.adminSelectedKeywordGroup = group;
  els.adminKeywordDetailTitle.textContent = group.base_keyword;
  els.adminKeywordDetailMeta.textContent = `${groupTypeLabel(group.group_type)} / 候補 ${group.candidates.length}件`;
  els.newCandidateInput.disabled = false;
  els.addCandidateButton.disabled = false;
  renderAdminCandidates(group);
}

function renderAdminCandidates(group) {
  if (!group.candidates.length) {
    els.adminCandidateList.innerHTML = `<div class="empty">候補キーワードがありません</div>`;
    return;
  }
  els.adminCandidateList.innerHTML = "";
  for (const candidate of group.candidates) {
    const row = document.createElement("div");
    row.className = `candidate-row ${candidate.enabled ? "" : "disabled-row"}`;
    row.innerHTML = `
      <div>
        <div class="keyword-name">${escapeText(candidate.candidate_keyword)}</div>
      </div>
      <button type="button" class="status-toggle">${candidate.enabled ? "無効化" : "有効化"}</button>
    `;
    row.querySelector(".status-toggle").addEventListener("click", async () => {
      await invoke("set_candidate_keyword_enabled", {
        candidateKeywordId: candidate.candidate_keyword_id,
        enabled: !candidate.enabled,
      });
      await loadKeywordTree();
    });
    els.adminCandidateList.appendChild(row);
  }
}

async function loadRequests() {
  try {
    const [siteRequests, keywordRequests] = await Promise.all([
      invoke("list_site_requests", {}),
      invoke("list_keyword_change_requests", {}),
    ]);
    state.siteRequests = siteRequests;
    state.keywordRequests = keywordRequests;
    renderRequestList();
    renderAdminRequestList();
  } catch (error) {
    els.requestList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
    els.adminRequestList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
  }
}

async function loadSiteHealth() {
  try {
    state.siteHealthRows = await invoke("list_site_health", {});
    renderSiteHealth();
  } catch (error) {
    els.siteHealthList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
  }
}

function renderSiteHealth() {
  if (!state.siteHealthRows.length) {
    els.siteHealthList.innerHTML = `<div class="empty">サイト状態はまだありません</div>`;
    return;
  }
  els.siteHealthList.innerHTML = state.siteHealthRows
    .map((row) => {
      const details = [];
      if (row.latest_error_message) {
        details.push(`最新エラー: ${row.latest_error_type || ""} ${row.latest_error_message}`);
      }
      if (row.latest_skip_reason) {
        details.push(`最新スキップ: ${row.latest_skip_reason}`);
      }
      return `
        <article class="request-card site-health-card ${escapeText(row.status)}">
          <div class="request-card-head">
            <strong>${escapeText(row.site_name)}</strong>
            <span class="status-badge">${siteHealthLabel(row.status)}</span>
          </div>
          <div class="row-sub">${escapeText(row.site_id)} / ${row.requires_playwright ? "Playwright" : "HTTP"}</div>
          <div class="health-metrics">
            <span>最新ヒット ${row.latest_run_hits}</span>
            <span>最新エラー ${row.latest_run_errors}</span>
            <span>総記事 ${row.total_items}</span>
            <span>日付欠落 ${row.missing_published_dates}</span>
          </div>
          ${details.length ? `<div class="implementer-comment">${escapeText(details.join(" / "))}</div>` : ""}
        </article>
      `;
    })
    .join("");
}

function allRequestsForDisplay() {
  const sites = state.siteRequests.map((request) => ({
    kind: "site",
    id: request.request_id,
    title: request.site_name,
    detail: request.site_url,
    requester: request.requester_name,
    email: request.requester_email,
    notes: request.notes,
    status: request.status,
    comment: request.implementer_comment,
    createdAt: request.created_at,
  }));
  const keywords = state.keywordRequests.map((request) => ({
    kind: "keyword",
    id: request.request_id,
    title: `${requestTypeLabel(request.request_type)}: ${request.base_keyword}`,
    detail: `${groupTypeLabel(request.group_type)} / ${request.candidate_keyword || "親キーワード"}`,
    requester: request.requester_name,
    email: request.requester_email,
    notes: request.reason,
    status: request.status,
    comment: request.implementer_comment,
    createdAt: request.created_at,
  }));
  return [...sites, ...keywords].sort((a, b) => compareText(b.createdAt, a.createdAt));
}

function renderRequestList() {
  const requests = allRequestsForDisplay();
  if (!requests.length) {
    els.requestList.innerHTML = `<div class="empty">要望はまだありません</div>`;
    return;
  }
  els.requestList.innerHTML = requests
    .map(
      (request) => `
        <article class="request-card">
          <div class="request-card-head">
            <strong>${escapeText(request.title)}</strong>
            <span class="status-badge">${statusLabel(request.status)}</span>
          </div>
          <div class="row-sub">${escapeText(request.kind === "site" ? "サイト追加" : "キーワード変更")} / ${escapeText(request.detail)}</div>
          <div class="request-meta">${escapeText(request.requester || "-")} ${escapeText(request.email || "")}</div>
          ${request.notes ? `<p>${escapeText(request.notes)}</p>` : ""}
          ${request.comment ? `<div class="implementer-comment">${escapeText(request.comment)}</div>` : ""}
        </article>
      `,
    )
    .join("");
}

function renderAdminRequestList() {
  const requests = allRequestsForDisplay();
  if (!requests.length) {
    els.adminRequestList.innerHTML = `<div class="empty">要望はまだありません</div>`;
    return;
  }
  els.adminRequestList.innerHTML = "";
  for (const request of requests) {
    const card = document.createElement("article");
    card.className = "request-card admin-request-card";
    card.innerHTML = `
      <div class="request-card-head">
        <strong>${escapeText(request.title)}</strong>
        <span class="type-badge">${escapeText(request.kind === "site" ? "サイト" : "キーワード")}</span>
      </div>
      <div class="row-sub">${escapeText(request.detail)}</div>
      <div class="form-row">
        <select class="request-status">
          <option value="new">未対応</option>
          <option value="reviewing">確認中</option>
          <option value="accepted">採用</option>
          <option value="rejected">見送り</option>
          <option value="done">実装済み</option>
        </select>
        <button type="button" class="save-request">保存</button>
      </div>
      <textarea class="request-comment" placeholder="実装者コメント">${escapeText(request.comment || "")}</textarea>
    `;
    card.querySelector(".request-status").value = request.status;
    card.querySelector(".save-request").addEventListener("click", async () => {
      const status = card.querySelector(".request-status").value;
      const implementerComment = card.querySelector(".request-comment").value;
      if (request.kind === "site") {
        await invoke("update_site_request", {
          requestId: request.id,
          status,
          implementerComment,
        });
      } else {
        await invoke("update_keyword_change_request", {
          requestId: request.id,
          status,
          implementerComment,
        });
      }
      await loadRequests();
    });
    els.adminRequestList.appendChild(card);
  }
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
    document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
    button.classList.add("active");
    document.querySelector(`#${button.dataset.view}`).classList.add("active");
  });
});

els.refreshButton.addEventListener("click", loadAll);

els.companySort.addEventListener("change", async () => {
  state.sort = els.companySort.value;
  await loadCompanies();
});

els.groupTypeTabs.forEach((button) => {
  button.addEventListener("click", async () => {
    state.groupType = button.dataset.groupType;
    state.selectedCompany = null;
    state.articleRows = [];
    state.selectedArticleKeywords = new Set();
    els.groupTypeTabs.forEach((tab) => tab.classList.toggle("active", tab === button));
    els.selectedCompany.textContent = `${groupTypeLabel(state.groupType)}を選択`;
    els.selectedCompanyMeta.textContent = "記事一覧を表示します";
    els.selectedPublishedMin.textContent = "-";
    els.selectedHitMin.textContent = "-";
    renderArticleKeywordFilter();
    renderArticles();
    await loadCompanies();
  });
});

els.adminGroupTypeTabs.forEach((button) => {
  button.addEventListener("click", () => {
    state.adminGroupType = button.dataset.groupType;
    els.adminGroupTypeTabs.forEach((tab) => tab.classList.toggle("active", tab === button));
    renderAdminKeywordGroups();
    selectFirstAdminKeywordGroupForType();
  });
});

els.articleSort.addEventListener("change", () => {
  state.articleSort = els.articleSort.value;
  renderArticles();
});

els.copyMarkdownButton.addEventListener("click", copyRecentMarkdown);

els.clearKeywordFilter.addEventListener("click", () => {
  state.selectedArticleKeywords = new Set();
  renderArticleKeywordFilter();
  renderArticles();
});

els.addGroupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = els.newGroupInput.value;
  if (!value.trim()) return;
  await invoke("add_keyword_group_typed", {
    baseKeyword: value,
    groupType: els.newGroupType.value,
  });
  els.newGroupInput.value = "";
  await loadKeywordTree();
  await loadCompanies();
});

els.addCandidateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.adminSelectedKeywordGroup) return;
  const value = els.newCandidateInput.value;
  if (!value.trim()) return;
  await invoke("add_candidate_keyword", {
    baseKeywordId: state.adminSelectedKeywordGroup.base_keyword_id,
    candidateKeyword: value,
  });
  els.newCandidateInput.value = "";
  await loadKeywordTree();
});

els.siteRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await invoke("create_site_request", {
    siteName: els.siteRequestName.value,
    siteUrl: els.siteRequestUrl.value,
    requesterName: els.siteRequesterName.value,
    requesterEmail: els.siteRequesterEmail.value,
    notes: els.siteRequestNotes.value,
  });
  els.siteRequestForm.reset();
  await loadRequests();
});

els.keywordRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await invoke("create_keyword_change_request", {
    requestType: els.keywordRequestType.value,
    groupType: els.keywordRequestGroupType.value,
    baseKeyword: els.keywordRequestBase.value,
    candidateKeyword: els.keywordRequestCandidate.value,
    requesterName: els.keywordRequesterName.value,
    requesterEmail: els.keywordRequesterEmail.value,
    reason: els.keywordRequestReason.value,
  });
  els.keywordRequestForm.reset();
  await loadRequests();
});

els.keywordRequestGroupType.addEventListener("change", updateKeywordRequestPlaceholders);
updateKeywordRequestPlaceholders();

loadAll();
