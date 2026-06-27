import { invoke, isLocalViewer } from "./api.js";

const ARTICLE_PAGE_SIZE = 100;

const state = {
  sort: "name",
  groupType: "company",
  targetView: "keyword-targets",
  adminGroupType: "company",
  adminPanel: "admin-keywords-panel",
  articleSort: "published",
  companies: [],
  selectedCompany: null,
  articleRows: [],
  articleTotal: 0,
  articleLoading: false,
  articleFullyLoaded: false,
  articleRequestSequence: 0,
  articleFilterOptions: {
    sites: [],
    keywords: [],
  },
  viewerMetadata: null,
  selectedArticleKeywords: new Set(),
  copyMode: "recent",
  columnFilters: {
    site: new Set(),
    keyword: new Set(),
    title: "",
    snippet: "",
    publishedDays: null,
    hitDays: null,
  },
  columnSort: {
    column: null,
    direction: "asc",
  },
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
  shutdownButton: document.querySelector("#shutdown-button"),
  shutdownOverlay: document.querySelector(".shutdown-overlay"),
  groupListTitle: document.querySelector("#group-list-title"),
  companySort: document.querySelector("#company-sort"),
  groupTypeTabs: document.querySelectorAll(".group-type-tab"),
  targetViewTabs: document.querySelectorAll(".target-view-tab"),
  targetPanels: document.querySelectorAll(".target-panel"),
  adminGroupTypeTabs: document.querySelectorAll(".admin-group-type-tab"),
  adminSubtabs: document.querySelectorAll(".admin-subtab"),
  adminSubpanels: document.querySelectorAll(".admin-subpanel"),
  companyCount: document.querySelector("#company-count"),
  viewerCacheStatus: document.querySelector("#viewer-cache-status"),
  companyList: document.querySelector("#company-list"),
  selectedCompany: document.querySelector("#selected-company"),
  selectedCompanyMeta: document.querySelector("#selected-company-meta"),
  selectedPublishedMin: document.querySelector("#selected-published-min"),
  selectedHitMin: document.querySelector("#selected-hit-min"),
  copyModeButtons: document.querySelectorAll(".copy-mode-button"),
  copyModeLabel: document.querySelector("#copy-mode-label"),
  copyUnitLabel: document.querySelector("#copy-unit-label"),
  copyDays: document.querySelector("#copy-days"),
  copyValueInput: document.querySelector("#copy-value-input"),
  copyMarkdownButton: document.querySelector("#copy-markdown-button"),
  copyTopRecords: document.querySelector("#copy-top-records"),
  copyTargetCount: document.querySelector("#copy-target-count"),
  copyStatus: document.querySelector("#copy-status"),
  articleBody: document.querySelector("#article-body"),
  tableWrap: document.querySelector(".table-wrap"),
  articleLoadStatus: document.querySelector("#article-load-status"),
  articleLoadMoreButton: document.querySelector("#article-load-more-button"),
  columnFilterButtons: document.querySelectorAll(".column-filter-button"),
  columnFilterPopover: document.querySelector("#column-filter-popover"),
  keywordGroupList: document.querySelector("#keyword-group-list"),
  candidateList: document.querySelector("#candidate-list"),
  keywordDetailTitle: document.querySelector("#keyword-detail-title"),
  keywordDetailMeta: document.querySelector("#keyword-detail-meta"),
  keywordParentStatus: document.querySelector("#keyword-parent-status"),
  siteTargetCount: document.querySelector("#site-target-count"),
  siteTargetBody: document.querySelector("#site-target-body"),
  adminKeywordGroupList: document.querySelector("#admin-keyword-group-list"),
  adminCandidateList: document.querySelector("#admin-candidate-list"),
  adminKeywordDetailTitle: document.querySelector("#admin-keyword-detail-title"),
  adminKeywordDetailMeta: document.querySelector("#admin-keyword-detail-meta"),
  adminParentStatus: document.querySelector("#admin-parent-status"),
  requestTocItems: document.querySelectorAll(".request-toc-item"),
  requestTocCount: document.querySelector("#request-toc-count"),
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
  keywordRequestExistingBaseField: document.querySelector("#keyword-request-existing-base-field"),
  keywordRequestExistingBase: document.querySelector("#keyword-request-existing-base"),
  keywordRequestBase: document.querySelector("#keyword-request-base"),
  keywordRequestBaseStatus: document.querySelector("#keyword-request-base-status"),
  keywordRequestCandidate: document.querySelector("#keyword-request-candidate"),
  keywordRequestCandidateOptions: document.querySelector("#keyword-request-candidate-options"),
  keywordRequesterName: document.querySelector("#keyword-requester-name"),
  keywordRequesterEmail: document.querySelector("#keyword-requester-email"),
  keywordRequestReason: document.querySelector("#keyword-request-reason"),
  requestList: document.querySelector("#request-list"),
  adminRequestList: document.querySelector("#admin-request-list"),
  siteHealthList: document.querySelector("#site-health-list"),
};

function daysLabel(days) {
  if (days === null || days === undefined) return "-";
  return `${days}日前`;
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
  const labels = {
    add: "追加希望",
    add_parent: "親キーワード追加希望",
    add_candidate: "子キーワード追加希望",
    delete: "削除希望",
  };
  return labels[requestType] ?? requestType;
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
  renderKeywordRequestOptions();
}

function keywordRequestGroupsForType() {
  return state.keywordGroups
    .filter((group) => group.group_type === els.keywordRequestGroupType.value)
    .sort((a, b) => compareText(a.base_keyword, b.base_keyword));
}

function selectedKeywordRequestGroup() {
  const baseKeyword = els.keywordRequestBase.value.trim();
  if (!baseKeyword) return null;
  return keywordRequestGroupsForType().find((group) => group.base_keyword === baseKeyword) ?? null;
}

function renderKeywordRequestOptions() {
  const groups = keywordRequestGroupsForType();
  const selectedBase = els.keywordRequestBase.value.trim();
  const requestType = els.keywordRequestType.value;
  const shouldSelectExisting = requestType === "add_candidate" || requestType === "delete";
  els.keywordRequestExistingBaseField.hidden = !shouldSelectExisting;
  els.keywordRequestExistingBase.innerHTML = [
    `<option value="">既存キーワードを選択</option>`,
    ...groups.map((group) => `<option value="${escapeText(group.base_keyword)}">${escapeText(group.base_keyword)}</option>`),
  ].join("");
  els.keywordRequestExistingBase.value = groups.some((group) => group.base_keyword === selectedBase)
    ? selectedBase
    : "";

  const selectedGroup = selectedKeywordRequestGroup();
  els.keywordRequestCandidateOptions.innerHTML = selectedGroup
    ? selectedGroup.candidates
        .map((candidate) => `<option value="${escapeText(candidate.candidate_keyword)}"></option>`)
        .join("")
    : "";

  const label = groupTypeLabel(els.keywordRequestGroupType.value);
  if (!els.keywordRequestBase.value.trim()) {
    els.keywordRequestBaseStatus.textContent =
      shouldSelectExisting
        ? `${label}の既存親キーワードを選んでください。`
        : `新しい${label}の親キーワードを入力してください。既存DB内に同じ親キーワードがある場合は登録できません。`;
  } else if (selectedGroup) {
    els.keywordRequestBaseStatus.textContent = shouldSelectExisting
      ? `既存の${label}「${selectedGroup.base_keyword}」が選択されています。子キーワード欄には既存候補も表示されます。`
      : `既存DB内に同じ${label}「${selectedGroup.base_keyword}」があります。親キーワード追加ではなく、既存親キーワードへの子キーワード追加を選んでください。`;
  } else if (shouldSelectExisting) {
    els.keywordRequestBaseStatus.textContent = `既存の${label}が選ばれていません。先に「既存キーワードから選ぶ」で親キーワードを選択してください。`;
  } else {
    els.keywordRequestBaseStatus.textContent = `新しい${label}の親キーワードとして登録希望を出します。`;
  }
}

function validateKeywordRequestForm() {
  const requestType = els.keywordRequestType.value;
  const selectedGroup = selectedKeywordRequestGroup();
  const shouldSelectExisting = requestType === "add_candidate" || requestType === "delete";
  if (requestType === "add_parent" && selectedGroup) {
    els.keywordRequestBase.setCustomValidity("既存DB内に同じ親キーワードがあります。既存親キーワードへの子キーワード追加を選んでください。");
  } else if (shouldSelectExisting && !selectedGroup) {
    els.keywordRequestBase.setCustomValidity("既存キーワードから親キーワードを選択してください。");
  } else {
    els.keywordRequestBase.setCustomValidity("");
  }
  renderKeywordRequestOptions();
  return els.keywordRequestForm.reportValidity();
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

function formatCacheDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function markdownEscape(value) {
  return String(value ?? "")
    .replaceAll("\\", "\\\\")
    .replaceAll("|", "\\|")
    .replaceAll("\r", " ")
    .replaceAll("\n", " ")
    .trim();
}

function setActiveRequestTocItem(activeItem) {
  els.requestTocItems.forEach((item) => item.classList.toggle("active", item === activeItem));
}

function updateRequestTocCount() {
  if (!els.requestTocCount) return;
  els.requestTocCount.textContent = `件数 ${state.siteRequests.length + state.keywordRequests.length}`;
}

function articleComparator(a, b) {
  if (state.columnSort.column) {
    const direction = state.columnSort.direction === "desc" ? -1 : 1;
    const result = compareArticleColumn(a, b, state.columnSort.column);
    if (result) return result * direction;
  }

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

function compareArticleColumn(a, b, column) {
  if (column === "published") {
    return compareOptionalDays(a.published_days, b.published_days) || compareText(b.published_date, a.published_date);
  }
  if (column === "hit") {
    return compareOptionalDays(a.hit_days, b.hit_days) || compareText(b.first_hit_at, a.first_hit_at);
  }
  if (column === "site") return compareText(a.site_name, b.site_name);
  if (column === "title") return compareText(a.title, b.title);
  if (column === "keyword") return compareText(a.candidate_keywords, b.candidate_keywords);
  if (column === "snippet") return compareText(a.snippet, b.snippet);
  return 0;
}

function resetColumnFilters() {
  state.columnFilters = {
    site: new Set(),
    keyword: new Set(),
    title: "",
    snippet: "",
    publishedDays: null,
    hitDays: null,
  };
  state.columnSort = { column: null, direction: "asc" };
}

function isColumnFilterActive(column) {
  if (state.columnSort.column === column) return true;
  const filters = state.columnFilters;
  if (column === "published") return filters.publishedDays !== null;
  if (column === "hit") return filters.hitDays !== null;
  if (column === "site") return filters.site.size > 0;
  if (column === "keyword") return filters.keyword.size > 0 || state.selectedArticleKeywords.size > 0;
  if (column === "title") return Boolean(filters.title.trim());
  if (column === "snippet") return Boolean(filters.snippet.trim());
  return false;
}

function updateColumnFilterIndicators() {
  els.columnFilterButtons.forEach((button) => {
    button.classList.toggle("active", isColumnFilterActive(button.dataset.column));
  });
}

function setTargetView(viewId) {
  state.targetView = viewId;
  els.targetViewTabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.targetView === viewId);
  });
  els.targetPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === viewId);
  });
}

function setAdminPanel(panelId) {
  state.adminPanel = panelId;
  els.adminSubtabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.adminPanel === panelId);
  });
  els.adminSubpanels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === panelId);
  });
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
  els.groupListTitle.textContent = groupTypeLabel(state.groupType);
  els.companyCount.textContent = "読み込み中";
  els.viewerCacheStatus.textContent = "一覧データ: 読み込み中";
  els.companyList.innerHTML = `<div class="company-loading">一覧データを読み込み中</div>`;
  try {
    const [companies, metadata] = await Promise.all([
      invoke("get_keyword_summaries", {
        sort: state.sort,
        groupType: state.groupType,
      }),
      invoke("get_viewer_metadata", {}),
    ]);
    state.companies = companies;
    state.viewerMetadata = metadata;
    els.companyCount.textContent = `${state.companies.length}件`;
    els.viewerCacheStatus.textContent = metadata?.rebuilt_at
      ? `一覧データ更新: ${formatCacheDateTime(metadata.rebuilt_at)}`
      : "一覧データ: 未作成";
    renderCompanies();
    if (!state.selectedCompany && state.companies.length > 0) {
      await selectCompany(state.companies[0].base_keyword_id);
    } else if (
      state.selectedCompany &&
      !state.companies.some((company) => company.base_keyword_id === state.selectedCompany.base_keyword_id)
    ) {
      state.selectedCompany = null;
      state.articleRows = [];
      if (state.companies.length > 0) {
        await selectCompany(state.companies[0].base_keyword_id);
      }
    }
  } catch (error) {
    els.companyList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
    els.companyCount.textContent = "取得失敗";
    els.viewerCacheStatus.textContent = "一覧データ: 取得失敗";
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
  state.articleTotal = 0;
  state.articleLoading = false;
  state.articleFullyLoaded = false;
  state.articleRequestSequence += 1;
  state.selectedArticleKeywords = new Set();
  state.articleFilterOptions = { sites: [], keywords: [] };
  resetColumnFilters();
  closeColumnFilterPopover();
  renderCompanies();
  els.selectedCompany.textContent = company.base_keyword;
  els.selectedCompanyMeta.textContent = `記事 ${company.article_count} / サイト ${company.site_count}`;
  els.selectedPublishedMin.textContent = daysLabel(company.published_min_days);
  els.selectedHitMin.textContent = daysLabel(company.hit_min_days);
  els.articleBody.innerHTML = `<tr><td colspan="6" class="empty">読み込み中</td></tr>`;
  renderArticleKeywordFilter();
  renderArticleLoadStatus();

  await loadArticleFilterOptions();
  await loadCompanyResults(false);
}

async function loadArticleFilterOptions() {
  if (!state.selectedCompany) return;
  try {
    state.articleFilterOptions = await invoke("get_company_result_filters", {
      baseKeywordId: state.selectedCompany.base_keyword_id,
    });
  } catch (error) {
    state.articleFilterOptions = { sites: [], keywords: [] };
    els.dbStatus.textContent = `フィルター候補を読み込めませんでした: ${error}`;
  }
}

function currentArticleQueryParams(append) {
  return {
    baseKeywordId: state.selectedCompany.base_keyword_id,
    limit: ARTICLE_PAGE_SIZE,
    offset: append ? state.articleRows.length : 0,
    siteIds: [...state.columnFilters.site],
    candidateKeywords: [...state.columnFilters.keyword],
    titleFilter: state.columnFilters.title,
    snippetFilter: state.columnFilters.snippet,
    publishedDays: state.columnFilters.publishedDays,
    hitDays: state.columnFilters.hitDays,
    sortColumn: state.columnSort.column || state.articleSort,
    sortDirection: state.columnSort.column ? state.columnSort.direction : "asc",
  };
}

async function loadCompanyResults(append) {
  if (!state.selectedCompany || state.articleLoading) return;
  if (append && state.articleFullyLoaded) return;
  const requestedBaseKeywordId = state.selectedCompany.base_keyword_id;
  const requestSequence = state.articleRequestSequence + 1;
  state.articleRequestSequence = requestSequence;
  let loadedSuccessfully = false;
  state.articleLoading = true;
  renderArticleLoadStatus();
  try {
    const page = await invoke("get_company_results", currentArticleQueryParams(append));
    if (state.articleRequestSequence !== requestSequence || state.selectedCompany?.base_keyword_id !== requestedBaseKeywordId) {
      return;
    }
    const rows = page.rows || [];
    state.articleTotal = page.total ?? rows.length;
    state.articleRows = append ? [...state.articleRows, ...rows] : rows;
    state.articleFullyLoaded = rows.length < ARTICLE_PAGE_SIZE;
    renderArticleKeywordFilter();
    renderArticles();
    loadedSuccessfully = true;
  } catch (error) {
    els.articleBody.innerHTML = `<tr><td colspan="6" class="error">${escapeText(error)}</td></tr>`;
  } finally {
    if (state.articleRequestSequence !== requestSequence) return;
    state.articleLoading = false;
    renderArticleLoadStatus();
    if (loadedSuccessfully) {
      maybeAutoLoadMoreArticles();
    }
  }
}

function articleKeywordOptions() {
  return (state.articleFilterOptions.keywords || [])
    .map((option) => [option.value, option.hit_count, option.label])
    .sort((a, b) => compareText(a[2] || a[0], b[2] || b[0]));
}

function siteOptions() {
  return (state.articleFilterOptions.sites || [])
    .map((option) => [option.value, option.hit_count, option.label])
    .sort((a, b) => compareText(a[2] || a[0], b[2] || b[0]));
}

function renderArticleKeywordFilter() {
  state.columnFilters.keyword = new Set(state.selectedArticleKeywords);
  updateCopyPreview();
}

function filteredArticleRows() {
  return state.articleRows;
}

async function reloadArticleResults() {
  state.articleRows = [];
  state.articleTotal = 0;
  state.articleFullyLoaded = false;
  els.articleBody.innerHTML = `<tr><td colspan="6" class="empty">読み込み中</td></tr>`;
  renderArticleLoadStatus();
  await loadCompanyResults(false);
}

function rowsForMarkdownCopy() {
  const maxDays = currentCopyDays();
  return filteredArticleRows().filter(
    (row) => row.published_days !== null && row.published_days !== undefined && row.published_days <= maxDays,
  );
}

function rowsForTopRecordsMarkdownCopy() {
  return filteredArticleRows().slice(0, currentCopyTopRecords());
}

function currentCopyDays() {
  const days = Number.parseInt(els.copyDays.value, 10);
  return Number.isFinite(days) ? Math.max(0, Math.min(3650, days)) : 1;
}

function setCopyDays(days) {
  const nextDays = Math.max(0, Math.min(3650, days));
  els.copyDays.value = String(nextDays);
  updateCopyPreview();
}

function currentCopyTopRecords() {
  const count = Number.parseInt(els.copyTopRecords.value, 10);
  return Number.isFinite(count) ? Math.max(1, Math.min(5000, count)) : 5;
}

function setCopyTopRecords(count) {
  const nextCount = Math.max(1, Math.min(5000, count));
  els.copyTopRecords.value = String(nextCount);
  updateCopyPreview();
}

function updateCopyPreview() {
  const isRecentMode = state.copyMode === "recent";
  const rows = isRecentMode ? rowsForMarkdownCopy() : rowsForTopRecordsMarkdownCopy();
  const value = isRecentMode ? currentCopyDays() : currentCopyTopRecords();
  const days = currentCopyDays();
  const topRecords = currentCopyTopRecords();
  els.copyDays.value = String(days);
  els.copyTopRecords.value = String(topRecords);
  els.copyValueInput.value = String(value);
  els.copyValueInput.min = isRecentMode ? "0" : "1";
  els.copyValueInput.max = isRecentMode ? "3650" : "5000";
  els.copyModeLabel.textContent = isRecentMode ? "直近掲載日で" : "上位レコードで";
  els.copyUnitLabel.textContent = isRecentMode ? "日以内をコピー" : "件をコピー";
  els.copyTargetCount.textContent = `（対象 ${rows.length}件）`;
  els.copyModeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.copyMode === state.copyMode);
  });
}

function applyCopyValueInput() {
  const normalized = els.copyValueInput.value.replace(/\D/g, "");
  if (els.copyValueInput.value !== normalized) {
    els.copyValueInput.value = normalized;
  }
  if (!normalized) {
    els.copyStatus.textContent = "";
    return;
  }
  const parsed = Number.parseInt(normalized, 10);
  if (state.copyMode === "top") {
    setCopyTopRecords(Number.isFinite(parsed) ? parsed : 5);
  } else {
    setCopyDays(Number.isFinite(parsed) ? parsed : 1);
  }
  els.copyStatus.textContent = "";
}

function closeColumnFilterPopover() {
  if (!els.columnFilterPopover) return;
  els.columnFilterPopover.hidden = true;
  els.columnFilterPopover.innerHTML = "";
}

function openColumnFilterPopover(column, anchor) {
  if (!els.columnFilterPopover) return;
  const rect = anchor.getBoundingClientRect();
  els.columnFilterPopover.innerHTML = renderColumnFilterPopover(column);
  els.columnFilterPopover.hidden = false;
  els.columnFilterPopover.style.left = `${Math.min(rect.left, window.innerWidth - 310)}px`;
  els.columnFilterPopover.style.top = `${rect.bottom + 6}px`;
  bindColumnFilterPopover(column);
}

function renderColumnFilterPopover(column) {
  const sortButtons = `
    <div class="column-filter-section">
      <button type="button" data-action="sort-asc">昇順</button>
      <button type="button" data-action="sort-desc">降順</button>
    </div>
  `;
  if (column === "published" || column === "hit") {
    const value = column === "published" ? state.columnFilters.publishedDays : state.columnFilters.hitDays;
    return `
      <div class="column-filter-title">${column === "published" ? "掲載日" : "ヒット日"}</div>
      ${sortButtons}
      <label class="column-filter-field">
        <span>直近N日以内</span>
        <input data-role="days-filter" type="number" min="0" max="3650" value="${value ?? ""}" placeholder="例: 7" />
      </label>
      <div class="column-filter-actions">
        <button type="button" data-action="apply-days">適用</button>
        <button type="button" data-action="clear">クリア</button>
      </div>
    `;
  }
  if (column === "site" || column === "keyword") {
    const options = column === "site" ? siteOptions() : articleKeywordOptions();
    const selected = column === "site" ? state.columnFilters.site : state.columnFilters.keyword;
    const list = options
      .map(
        ([value, count, label]) => `
          <label class="column-filter-check">
            <input type="checkbox" value="${escapeText(value)}" ${selected.has(value) ? "checked" : ""} />
            <span>${escapeText(label || value)}</span>
            <em>${count}</em>
          </label>
        `,
      )
      .join("");
    return `
      <div class="column-filter-title">${column === "site" ? "サイト" : "候補キーワード"}</div>
      ${sortButtons}
      <label class="column-filter-field">
        <span>候補検索</span>
        <input data-role="option-search" type="search" placeholder="絞り込み" />
      </label>
      <div class="column-filter-toggle-row">
        <button type="button" data-action="check-all">全件チェック</button>
        <button type="button" data-action="uncheck-all">全解除</button>
      </div>
      <div class="column-filter-checklist">${list || '<span class="filter-empty">候補なし</span>'}</div>
      <div class="column-filter-actions">
        <button type="button" data-action="apply-checks">適用</button>
        <button type="button" data-action="clear">クリア</button>
      </div>
    `;
  }
  const textValue = column === "title" ? state.columnFilters.title : state.columnFilters.snippet;
  return `
    <div class="column-filter-title">${column === "title" ? "タイトル" : "スニペット"}</div>
    ${sortButtons}
    <label class="column-filter-field">
      <span>含まれる文字</span>
      <input data-role="text-filter" type="search" value="${escapeText(textValue)}" placeholder="例: 携帯" />
    </label>
    <div class="column-filter-actions">
      <button type="button" data-action="apply-text">適用</button>
      <button type="button" data-action="clear">クリア</button>
    </div>
  `;
}

function bindColumnFilterPopover(column) {
  const popover = els.columnFilterPopover;
  popover.querySelector('[data-action="sort-asc"]')?.addEventListener("click", async () => {
    state.columnSort = { column, direction: "asc" };
    await reloadArticleResults();
    closeColumnFilterPopover();
  });
  popover.querySelector('[data-action="sort-desc"]')?.addEventListener("click", async () => {
    state.columnSort = { column, direction: "desc" };
    await reloadArticleResults();
    closeColumnFilterPopover();
  });
  popover.querySelector('[data-action="apply-days"]')?.addEventListener("click", async () => {
    const input = popover.querySelector('[data-role="days-filter"]');
    const parsed = Number.parseInt(input.value, 10);
    const value = Number.isFinite(parsed) ? Math.max(0, Math.min(3650, parsed)) : null;
    if (column === "published") state.columnFilters.publishedDays = value;
    if (column === "hit") state.columnFilters.hitDays = value;
    await reloadArticleResults();
    closeColumnFilterPopover();
  });
  popover.querySelector('[data-action="apply-text"]')?.addEventListener("click", async () => {
    const input = popover.querySelector('[data-role="text-filter"]');
    if (column === "title") state.columnFilters.title = input.value;
    if (column === "snippet") state.columnFilters.snippet = input.value;
    await reloadArticleResults();
    closeColumnFilterPopover();
  });
  popover.querySelector('[data-action="apply-checks"]')?.addEventListener("click", async () => {
    const values = new Set(
      [...popover.querySelectorAll('.column-filter-check input:checked')].map((input) => input.value),
    );
    if (column === "site") state.columnFilters.site = values;
    if (column === "keyword") {
      state.columnFilters.keyword = values;
      state.selectedArticleKeywords = new Set(values);
      renderArticleKeywordFilter();
    }
    await reloadArticleResults();
    closeColumnFilterPopover();
  });
  popover.querySelector('[data-action="check-all"]')?.addEventListener("click", () => {
    popover.querySelectorAll(".column-filter-check:not([hidden]) input").forEach((input) => {
      input.checked = true;
    });
  });
  popover.querySelector('[data-action="uncheck-all"]')?.addEventListener("click", () => {
    popover.querySelectorAll(".column-filter-check:not([hidden]) input").forEach((input) => {
      input.checked = false;
    });
  });
  popover.querySelector('[data-action="clear"]')?.addEventListener("click", async () => {
    if (column === "published") state.columnFilters.publishedDays = null;
    if (column === "hit") state.columnFilters.hitDays = null;
    if (column === "site") state.columnFilters.site = new Set();
    if (column === "keyword") {
      state.columnFilters.keyword = new Set();
      state.selectedArticleKeywords = new Set();
      renderArticleKeywordFilter();
    }
    if (column === "title") state.columnFilters.title = "";
    if (column === "snippet") state.columnFilters.snippet = "";
    if (state.columnSort.column === column) state.columnSort = { column: null, direction: "asc" };
    await reloadArticleResults();
    closeColumnFilterPopover();
  });
  popover.querySelector('[data-role="option-search"]')?.addEventListener("input", (event) => {
    const query = event.target.value.trim().toLocaleLowerCase();
    popover.querySelectorAll(".column-filter-check").forEach((label) => {
      label.hidden = query && !label.textContent.toLocaleLowerCase().includes(query);
    });
  });
  popover.querySelector('[data-role="text-filter"]')?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") popover.querySelector('[data-action="apply-text"]')?.click();
  });
  popover.querySelector('[data-role="days-filter"]')?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") popover.querySelector('[data-action="apply-days"]')?.click();
  });
}

function buildMarkdown(rows, heading) {
  const title = state.selectedCompany?.base_keyword || "検索結果";
  const lines = [
    `## ${markdownEscape(title)} ${markdownEscape(heading)}`,
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
  const markdown = buildMarkdown(rows, `掲載日直近${currentCopyDays()}日分`);
  try {
    await navigator.clipboard.writeText(markdown);
    els.copyStatus.textContent = `${rows.length}件をコピーしました`;
  } catch (error) {
    els.copyStatus.textContent = `コピーできませんでした: ${error}`;
  }
}

async function copyTopRecordsMarkdown() {
  const topRecords = currentCopyTopRecords();
  const rows = rowsForTopRecordsMarkdownCopy();
  if (!rows.length) {
    els.copyStatus.textContent = "対象記事がありません";
    return;
  }
  const markdown = buildMarkdown(rows, `上位${topRecords}レコード`);
  try {
    await navigator.clipboard.writeText(markdown);
    els.copyStatus.textContent = `${rows.length}件をコピーしました`;
  } catch (error) {
    els.copyStatus.textContent = `コピーできませんでした: ${error}`;
  }
}

async function copyCurrentMarkdown() {
  if (state.copyMode === "top") {
    await copyTopRecordsMarkdown();
  } else {
    await copyRecentMarkdown();
  }
}

function renderArticles() {
  const rows = filteredArticleRows();
  updateColumnFilterIndicators();
  if (!rows.length) {
    const message = state.articleRows.length ? "条件に合う記事がありません" : "記事がありません";
    els.articleBody.innerHTML = `<tr><td colspan="6" class="empty">${message}</td></tr>`;
    updateCopyPreview();
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
  updateCopyPreview();
}

function renderArticleLoadStatus() {
  if (!els.articleLoadStatus || !els.articleLoadMoreButton) return;
  const total = state.articleTotal || 0;
  const loaded = state.articleRows.length;
  if (state.articleLoading) {
    els.articleLoadStatus.textContent = "記事一覧を読み込み中";
  } else if (!state.selectedCompany) {
    els.articleLoadStatus.textContent = "";
  } else {
    els.articleLoadStatus.textContent = `表示 ${loaded} / ${total} 件`;
  }
  els.articleLoadMoreButton.hidden = !state.selectedCompany || loaded >= total || state.articleFullyLoaded;
  els.articleLoadMoreButton.disabled = state.articleLoading;
}

function canLoadMoreArticles() {
  const total = state.articleTotal || 0;
  return Boolean(
    state.selectedCompany &&
      !state.articleLoading &&
      !state.articleFullyLoaded &&
      state.articleRows.length > 0 &&
      state.articleRows.length < total,
  );
}

function maybeAutoLoadMoreArticles() {
  const scroller = els.tableWrap;
  if (!scroller || !canLoadMoreArticles()) return;
  const distanceToBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
  if (distanceToBottom <= 300) {
    loadCompanyResults(true);
  }
}

async function loadKeywordTree() {
  try {
    state.keywordGroups = await invoke("get_keyword_tree", {});
    renderKeywordGroups();
    renderAdminKeywordGroups();
    renderKeywordRequestOptions();
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

function candidateEffectiveEnabled(group, candidate) {
  return Boolean(group.enabled && candidate.enabled);
}

function effectiveStatusText(group, candidate) {
  if (!group.enabled) return "親無効";
  if (!candidate.enabled) return "無効";
  return "有効";
}

function renderParentStatus(element, group) {
  if (!element) return;
  element.hidden = false;
  element.className = `parent-status ${group.enabled ? "status-on" : "status-off"}`;
  if (group.enabled) {
    element.innerHTML = `親キーワード: <strong>有効</strong>。有効な候補キーワードが検索対象になります。`;
    return;
  }
  element.innerHTML =
    `親キーワード: <strong>無効</strong>。この配下の候補キーワードは検索対象外です。` +
    `候補キーワードごとの個別設定は保持されています。`;
}

function candidateStatusBadges(group, candidate) {
  const effectiveEnabled = candidateEffectiveEnabled(group, candidate);
  const personalClass = candidate.enabled ? "status-on" : "status-off";
  const effectiveClass = effectiveEnabled ? "status-on" : "status-off";
  return `
    <span class="status-badge ${personalClass}">個別: ${candidate.enabled ? "有効" : "無効"}</span>
    <span class="status-badge ${effectiveClass}">実効: ${effectiveStatusText(group, candidate)}</span>
  `;
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
  renderParentStatus(els.keywordParentStatus, group);
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
    const effectiveEnabled = candidateEffectiveEnabled(group, candidate);
    row.className = `candidate-row ${effectiveEnabled ? "" : "effective-disabled"} ${
      candidate.enabled ? "" : "disabled-row"
    }`;
    row.innerHTML = `
      <div>
        <div class="keyword-name">${escapeText(candidate.candidate_keyword)}</div>
        <div class="row-sub">${candidateStatusBadges(group, candidate)}</div>
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
  if (els.adminParentStatus) els.adminParentStatus.hidden = true;
  els.newCandidateInput.disabled = true;
  els.addCandidateButton.disabled = true;
  els.adminCandidateList.innerHTML = `<div class="empty">${groupTypeLabel(state.adminGroupType)}の親キーワードはありません</div>`;
}

function selectAdminKeywordGroup(baseKeywordId) {
  const group = state.keywordGroups.find((item) => item.base_keyword_id === baseKeywordId);
  if (!group) return;
  state.adminSelectedKeywordGroup = group;
  els.adminKeywordDetailTitle.textContent = group.base_keyword;
  renderParentStatus(els.adminParentStatus, group);
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
    const effectiveEnabled = candidateEffectiveEnabled(group, candidate);
    row.className = `candidate-row ${effectiveEnabled ? "" : "effective-disabled"} ${
      candidate.enabled ? "" : "disabled-row"
    }`;
    row.innerHTML = `
      <div>
        <div class="keyword-name">${escapeText(candidate.candidate_keyword)}</div>
        <div class="row-sub">${candidateStatusBadges(group, candidate)}</div>
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
    updateRequestTocCount();
    renderRequestList();
    renderAdminRequestList();
  } catch (error) {
    if (els.requestTocCount) els.requestTocCount.textContent = "件数 -";
    els.requestList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
    els.adminRequestList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
  }
}

async function loadSiteHealth() {
  try {
    state.siteHealthRows = await invoke("list_site_health", {});
    renderSiteHealth();
    renderSiteTargets();
  } catch (error) {
    els.siteHealthList.innerHTML = `<div class="error">${escapeText(error)}</div>`;
    if (els.siteTargetBody) {
      els.siteTargetBody.innerHTML = `<tr><td colspan="7" class="error">${escapeText(error)}</td></tr>`;
    }
    if (els.siteTargetCount) els.siteTargetCount.textContent = "取得失敗";
  }
}

function renderSiteTargets() {
  if (!els.siteTargetBody) return;
  if (els.siteTargetCount) {
    els.siteTargetCount.textContent = `${state.siteHealthRows.length}件`;
  }
  if (!state.siteHealthRows.length) {
    els.siteTargetBody.innerHTML = `<tr><td colspan="7" class="empty">対象サイトはまだありません</td></tr>`;
    return;
  }
  els.siteTargetBody.innerHTML = state.siteHealthRows
    .map((row) => {
      const hasDbHit = row.total_items > 0;
      const latestError = row.latest_error_message
        ? `${row.latest_error_type || ""} ${row.latest_error_message}`
        : "-";
      return `
        <tr>
          <td>
            <div class="site-target-name">${escapeText(row.site_name)}</div>
            <div class="row-sub">${siteHealthLabel(row.status)}</div>
          </td>
          <td><code>${escapeText(row.site_id)}</code></td>
          <td><span class="status-badge ${row.enabled ? "status-on" : "status-off"}">${row.enabled ? "有効" : "無効"}</span></td>
          <td>${row.requires_playwright ? "必要" : "不要"}</td>
          <td><span class="status-badge ${hasDbHit ? "status-on" : "status-off"}">${hasDbHit ? "あり" : "なし"}</span></td>
          <td>${row.total_items}</td>
          <td class="site-target-error">${escapeText(latestError)}</td>
        </tr>
      `;
    })
    .join("");
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
        <article class="request-card request-list-item">
          <div>
            <div class="request-list-item-title">${escapeText(request.title)}</div>
            <div class="request-list-item-meta">${escapeText(request.kind === "site" ? "サイト追加" : "キーワード変更")} / ${escapeText(request.detail)}</div>
            <div class="request-list-item-meta">${escapeText(request.requester || "-")} ${escapeText(request.email || "")}</div>
            ${request.notes ? `<p>${escapeText(request.notes)}</p>` : ""}
            ${request.comment ? `<div class="implementer-comment">${escapeText(request.comment)}</div>` : ""}
          </div>
          <div>
            <span class="status-badge">${statusLabel(request.status)}</span>
          </div>
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

els.targetViewTabs.forEach((button) => {
  button.addEventListener("click", () => setTargetView(button.dataset.targetView));
});

els.adminSubtabs.forEach((button) => {
  button.addEventListener("click", () => setAdminPanel(button.dataset.adminPanel));
});

els.requestTocItems.forEach((item, index) => {
  item.classList.toggle("active", index === 0);
  item.addEventListener("click", (event) => {
    event.preventDefault();
    const target = document.querySelector(item.getAttribute("href"));
    if (!target) return;
    setActiveRequestTocItem(item);
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

els.refreshButton.addEventListener("click", loadAll);

if (isLocalViewer() && els.shutdownButton) {
  els.shutdownButton.hidden = false;
  els.shutdownButton.addEventListener("click", async () => {
    const ok = window.confirm("News Monitor Local Viewerを終了します。ブラウザのタブも閉じてください。");
    if (!ok) return;
    els.dbStatus.textContent = "終了中です";
    try {
      await invoke("shutdown_server", {});
      document.body.classList.add("server-stopped");
      els.shutdownOverlay?.setAttribute("aria-hidden", "false");
      els.dbStatus.textContent = "サーバーを終了しました。このタブを閉じてください。";
    } catch (error) {
      els.dbStatus.textContent = `終了できませんでした: ${error}`;
    }
  });
}

els.companySort.addEventListener("change", async () => {
  state.sort = els.companySort.value;
  await loadCompanies();
});

els.groupTypeTabs.forEach((button) => {
  button.addEventListener("click", async () => {
    state.groupType = button.dataset.groupType;
    state.selectedCompany = null;
    state.articleRows = [];
    state.articleTotal = 0;
    state.articleFilterOptions = { sites: [], keywords: [] };
    state.selectedArticleKeywords = new Set();
    resetColumnFilters();
    closeColumnFilterPopover();
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

els.columnFilterButtons.forEach((button) => {
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const isSameColumn =
      !els.columnFilterPopover.hidden && els.columnFilterPopover.dataset.column === button.dataset.column;
    if (isSameColumn) {
      closeColumnFilterPopover();
      return;
    }
    els.columnFilterPopover.dataset.column = button.dataset.column;
    openColumnFilterPopover(button.dataset.column, button);
  });
});

document.addEventListener("pointerdown", (event) => {
  if (
    els.columnFilterPopover?.hidden === false &&
    !els.columnFilterPopover.contains(event.target) &&
    !event.target.closest(".column-filter-button")
  ) {
    closeColumnFilterPopover();
  }
});

els.copyMarkdownButton.addEventListener("click", copyCurrentMarkdown);
els.copyModeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.copyMode = button.dataset.copyMode;
    els.copyStatus.textContent = "";
    updateCopyPreview();
  });
});
els.copyValueInput.addEventListener("input", applyCopyValueInput);
els.copyValueInput.addEventListener("change", applyCopyValueInput);
els.articleLoadMoreButton.addEventListener("click", () => loadCompanyResults(true));
els.tableWrap?.addEventListener("scroll", maybeAutoLoadMoreArticles);

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
  if (!validateKeywordRequestForm()) return;
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
  updateKeywordRequestPlaceholders();
  await loadRequests();
});

els.keywordRequestGroupType.addEventListener("change", updateKeywordRequestPlaceholders);
els.keywordRequestType.addEventListener("change", renderKeywordRequestOptions);
els.keywordRequestExistingBase.addEventListener("change", () => {
  els.keywordRequestBase.value = els.keywordRequestExistingBase.value;
  els.keywordRequestCandidate.value = "";
  els.keywordRequestBase.setCustomValidity("");
  renderKeywordRequestOptions();
});
els.keywordRequestBase.addEventListener("input", () => {
  els.keywordRequestBase.setCustomValidity("");
  renderKeywordRequestOptions();
});
updateKeywordRequestPlaceholders();

loadAll();
