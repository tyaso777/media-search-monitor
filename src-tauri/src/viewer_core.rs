use chrono::{Local, NaiveDate};
use rusqlite::{params, Connection, OptionalExtension};
use serde::Serialize;
use std::cmp::Ordering;
use std::path::{Path, PathBuf};
use std::process::Command;
use uuid::Uuid;

const KEYWORD_NAMESPACE: Uuid = Uuid::from_u128(0x1d78b9f10ef546f78f2f4f54aefdc490);

#[derive(Serialize)]
pub struct AppStats {
    company_count: i64,
    article_count: i64,
    hit_count: i64,
    latest_run_started_at: Option<String>,
    latest_run_status: Option<String>,
}

#[derive(Serialize)]
pub struct CompanySummary {
    base_keyword_id: String,
    base_keyword: String,
    group_type: String,
    article_count: i64,
    site_count: i64,
    published_min_days: Option<i64>,
    hit_min_days: Option<i64>,
    latest_published_date: Option<String>,
    latest_hit_at: Option<String>,
}

#[derive(Serialize)]
pub struct ViewerMetadata {
    cache_name: String,
    rebuilt_at: String,
    source_hit_count: i64,
    source_item_count: i64,
    row_count: i64,
    status: String,
    error_message: Option<String>,
}

#[derive(Serialize)]
pub struct ArticleRow {
    result_item_id: String,
    site_id: String,
    site_name: String,
    title: Option<String>,
    url: String,
    published_date: Option<String>,
    published_days: Option<i64>,
    first_hit_at: String,
    hit_days: Option<i64>,
    candidate_keywords: String,
    snippet: Option<String>,
}

#[derive(Serialize)]
pub struct KeywordCandidateRow {
    candidate_keyword_id: String,
    candidate_keyword: String,
    enabled: bool,
    notes: Option<String>,
}

#[derive(Serialize)]
pub struct KeywordGroupRow {
    base_keyword_id: String,
    base_keyword: String,
    group_type: String,
    enabled: bool,
    notes: Option<String>,
    candidates: Vec<KeywordCandidateRow>,
}

#[derive(Serialize)]
pub struct SiteRequestRow {
    request_id: String,
    site_name: String,
    site_url: String,
    requester_name: Option<String>,
    requester_email: Option<String>,
    notes: Option<String>,
    status: String,
    implementer_comment: Option<String>,
    created_at: String,
    updated_at: String,
}

#[derive(Serialize)]
pub struct KeywordChangeRequestRow {
    request_id: String,
    request_type: String,
    group_type: String,
    base_keyword: String,
    candidate_keyword: Option<String>,
    requester_name: Option<String>,
    requester_email: Option<String>,
    reason: Option<String>,
    status: String,
    implementer_comment: Option<String>,
    created_at: String,
    updated_at: String,
}

#[derive(Serialize)]
pub struct SiteHealthRow {
    site_id: String,
    site_name: String,
    enabled: bool,
    requires_playwright: bool,
    status: String,
    latest_run_hits: i64,
    latest_run_errors: i64,
    total_items: i64,
    missing_published_dates: i64,
    latest_error_type: Option<String>,
    latest_error_message: Option<String>,
    latest_error_at: Option<String>,
    latest_skip_reason: Option<String>,
    latest_skip_at: Option<String>,
}

fn resolve_db_path(db_path: Option<String>) -> Result<PathBuf, String> {
    if let Some(path) = db_path.filter(|value| !value.trim().is_empty()) {
        let path = PathBuf::from(path);
        if path.exists() {
            return Ok(path);
        }
        return Err(format!("SQLite database was not found: {}", path.display()));
    }

    let candidates = default_db_path_candidates();
    if let Some(path) = candidates.iter().find(|path| path.exists()) {
        return Ok(path.clone());
    }

    let searched = candidates
        .iter()
        .map(|path| format!("- {}", path.display()))
        .collect::<Vec<_>>()
        .join("\n");
    Err(format!(
        "SQLite database was not found. Set NEWS_MONITOR_DB or launch from the project root.\nSearched:\n{searched}"
    ))
}

fn open_db(db_path: Option<String>) -> Result<Connection, String> {
    let path = resolve_db_path(db_path)?;
    Connection::open(&path).map_err(|err| format!("Failed to open {}: {err}", path.display()))
}

fn default_db_path_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(path) = std::env::var("NEWS_MONITOR_DB") {
        if !path.trim().is_empty() {
            candidates.push(PathBuf::from(path));
        }
    }

    if let Ok(cwd) = std::env::current_dir() {
        add_project_data_candidates(&mut candidates, &cwd);
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            add_project_data_candidates(&mut candidates, exe_dir);
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    add_project_data_candidates(&mut candidates, &manifest_dir);
    if let Some(project_root) = manifest_dir.parent() {
        candidates.push(project_root.join("data").join("news_monitor.sqlite"));
    }

    dedupe_paths(candidates)
}

fn add_project_data_candidates(candidates: &mut Vec<PathBuf>, start: &Path) {
    for ancestor in start.ancestors() {
        candidates.push(ancestor.join("data").join("news_monitor.sqlite"));
        if ancestor.file_name().is_some_and(|name| name == "src-tauri") {
            if let Some(project_root) = ancestor.parent() {
                candidates.push(project_root.join("data").join("news_monitor.sqlite"));
            }
        }
    }
}

fn dedupe_paths(paths: Vec<PathBuf>) -> Vec<PathBuf> {
    let mut unique = Vec::new();
    for path in paths {
        if !unique.iter().any(|existing| existing == &path) {
            unique.push(path);
        }
    }
    unique
}

fn today() -> NaiveDate {
    Local::now().date_naive()
}

fn parse_published_date(value: Option<&str>) -> Option<NaiveDate> {
    let value = value?;
    if value.trim().is_empty() {
        return None;
    }
    NaiveDate::parse_from_str(value, "%Y/%m/%d").ok()
}

fn parse_iso_date_prefix(value: &str) -> Option<NaiveDate> {
    value
        .get(0..10)
        .and_then(|date| NaiveDate::parse_from_str(date, "%Y-%m-%d").ok())
}

fn days_since(date: Option<NaiveDate>) -> Option<i64> {
    date.map(|date| today().signed_duration_since(date).num_days())
}

pub fn get_stats(db_path: Option<String>) -> Result<AppStats, String> {
    let conn = open_db(db_path)?;
    let has_summary_cache = viewer_group_summary_available(&conn)?;
    let cached_metadata = if table_exists(&conn, "viewer_metadata")? {
        conn.query_row(
            "SELECT source_item_count, source_hit_count FROM viewer_metadata WHERE cache_name = 'group_summary'",
            [],
            |row| Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?)),
        )
        .optional()
        .map_err(|err| err.to_string())?
    } else {
        None
    };
    let company_count = if has_summary_cache {
        conn.query_row("SELECT COUNT(*) FROM viewer_group_summary", [], |row| {
            row.get(0)
        })
        .map_err(|err| err.to_string())?
    } else {
        conn.query_row(
            "SELECT COUNT(*) FROM keyword_groups WHERE enabled = 1",
            [],
            |row| row.get(0),
        )
        .map_err(|err| err.to_string())?
    };
    let article_count = if let Some((source_item_count, _)) = cached_metadata {
        source_item_count
    } else {
        conn.query_row("SELECT COUNT(*) FROM search_result_items", [], |row| {
            row.get(0)
        })
        .map_err(|err| err.to_string())?
    };
    let hit_count = if let Some((_, source_hit_count)) = cached_metadata {
        source_hit_count
    } else {
        conn.query_row("SELECT COUNT(*) FROM search_result_hits", [], |row| {
            row.get(0)
        })
        .map_err(|err| err.to_string())?
    };
    let latest_run = conn
        .query_row(
            "SELECT started_at, status FROM search_runs ORDER BY started_at DESC LIMIT 1",
            [],
            |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)),
        )
        .ok();

    Ok(AppStats {
        company_count,
        article_count,
        hit_count,
        latest_run_started_at: latest_run.as_ref().map(|row| row.0.clone()),
        latest_run_status: latest_run.map(|row| row.1),
    })
}

pub fn get_companies(
    db_path: Option<String>,
    sort: Option<String>,
) -> Result<Vec<CompanySummary>, String> {
    let conn = open_db(db_path)?;
    ensure_keyword_group_type_column(&conn)?;
    get_companies_by_type(conn, sort, "company".to_string())
}

pub fn get_keyword_summaries(
    db_path: Option<String>,
    sort: Option<String>,
    group_type: Option<String>,
) -> Result<Vec<CompanySummary>, String> {
    let conn = open_db(db_path)?;
    ensure_keyword_group_type_column(&conn)?;
    get_companies_by_type(conn, sort, normalize_group_type(group_type.as_deref()))
}

pub fn get_viewer_metadata(db_path: Option<String>) -> Result<Option<ViewerMetadata>, String> {
    let conn = open_db(db_path)?;
    if !table_exists(&conn, "viewer_metadata")? {
        return Ok(None);
    }
    conn.query_row(
        r#"
        SELECT cache_name, rebuilt_at, source_hit_count, source_item_count,
               row_count, status, error_message
        FROM viewer_metadata
        WHERE cache_name = 'group_summary'
        "#,
        [],
        |row| {
            Ok(ViewerMetadata {
                cache_name: row.get(0)?,
                rebuilt_at: row.get(1)?,
                source_hit_count: row.get(2)?,
                source_item_count: row.get(3)?,
                row_count: row.get(4)?,
                status: row.get(5)?,
                error_message: row.get(6)?,
            })
        },
    )
    .optional()
    .map_err(|err| err.to_string())
}

fn ensure_keyword_group_type_column(conn: &Connection) -> Result<(), String> {
    let mut stmt = conn
        .prepare("PRAGMA table_info(keyword_groups)")
        .map_err(|err| err.to_string())?;
    let columns = stmt
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(|err| err.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())?;
    if !columns.iter().any(|column| column == "group_type") {
        conn.execute(
            "ALTER TABLE keyword_groups ADD COLUMN group_type TEXT NOT NULL DEFAULT 'company'",
            [],
        )
        .map_err(|err| err.to_string())?;
    }
    Ok(())
}

fn ensure_request_tables(conn: &Connection) -> Result<(), String> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS site_requests (
            request_id TEXT PRIMARY KEY,
            site_name TEXT NOT NULL,
            site_url TEXT NOT NULL,
            requester_name TEXT,
            requester_email TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            implementer_comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS keyword_change_requests (
            request_id TEXT PRIMARY KEY,
            request_type TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'company',
            base_keyword TEXT NOT NULL,
            candidate_keyword TEXT,
            requester_name TEXT,
            requester_email TEXT,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            implementer_comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        "#,
    )
    .map_err(|err| err.to_string())
}

fn now_string() -> String {
    Local::now().format("%Y-%m-%dT%H:%M:%S%:z").to_string()
}

fn optional_trimmed(value: Option<String>) -> Option<String> {
    value.and_then(|value| {
        let trimmed = value.trim().to_string();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed)
        }
    })
}

fn normalize_request_status(value: Option<&str>) -> String {
    match value.unwrap_or("new").trim().to_ascii_lowercase().as_str() {
        "reviewing" => "reviewing".to_string(),
        "accepted" => "accepted".to_string(),
        "rejected" => "rejected".to_string(),
        "done" => "done".to_string(),
        _ => "new".to_string(),
    }
}

fn normalize_request_type(value: &str) -> String {
    match value.trim().to_ascii_lowercase().as_str() {
        "add_parent" => "add_parent".to_string(),
        "add_candidate" => "add_candidate".to_string(),
        "delete" => "delete".to_string(),
        _ => "add".to_string(),
    }
}

fn get_companies_by_type(
    conn: Connection,
    sort: Option<String>,
    group_type: String,
) -> Result<Vec<CompanySummary>, String> {
    if viewer_group_summary_available(&conn)? {
        return get_cached_companies_by_type(&conn, sort, group_type);
    }

    let mut stmt = conn
        .prepare(
            r#"
            SELECT
                kg.base_keyword_id,
                kg.base_keyword,
                COALESCE(kg.group_type, 'company') AS group_type,
                COALESCE(COUNT(DISTINCT i.result_item_id), 0) AS article_count,
                COALESCE(COUNT(DISTINCT i.site_id), 0) AS site_count,
                MAX(i.published_date) AS latest_published_date,
                MAX(h.first_seen_at) AS latest_hit_at
            FROM keyword_groups kg
            LEFT JOIN search_result_hits h ON h.base_keyword_id = kg.base_keyword_id
            LEFT JOIN search_result_items i ON i.result_item_id = h.result_item_id
            WHERE kg.enabled = 1
              AND COALESCE(kg.group_type, 'company') = ?
            GROUP BY kg.base_keyword_id, kg.base_keyword, kg.group_type
            "#,
        )
        .map_err(|err| err.to_string())?;
    let rows = stmt
        .query_map(params![group_type], |row| {
            Ok(CompanySummary {
                base_keyword_id: row.get(0)?,
                base_keyword: row.get(1)?,
                group_type: row.get(2)?,
                article_count: row.get(3)?,
                site_count: row.get(4)?,
                published_min_days: None,
                hit_min_days: None,
                latest_published_date: row.get(5)?,
                latest_hit_at: row.get(6)?,
            })
        })
        .map_err(|err| err.to_string())?;
    let mut companies: Vec<CompanySummary> = rows
        .collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())?;

    for company in &mut companies {
        let latest_published: Option<String> = conn
            .query_row(
                r#"
                SELECT MAX(i.published_date)
                FROM search_result_hits h
                JOIN search_result_items i ON i.result_item_id = h.result_item_id
                WHERE h.base_keyword_id = ?
                  AND i.published_date IS NOT NULL
                  AND i.published_date != ''
                "#,
                params![company.base_keyword_id],
                |row| row.get(0),
            )
            .map_err(|err| err.to_string())?;
        company.published_min_days = days_since(parse_published_date(latest_published.as_deref()));

        let hit_min: Option<String> = conn
            .query_row(
                "SELECT MAX(first_seen_at) FROM search_result_hits WHERE base_keyword_id = ?",
                params![company.base_keyword_id],
                |row| row.get(0),
            )
            .map_err(|err| err.to_string())?;
        company.hit_min_days = hit_min
            .as_deref()
            .and_then(parse_iso_date_prefix)
            .and_then(|date| days_since(Some(date)));
    }

    match sort.unwrap_or_else(|| "name".to_string()).as_str() {
        "published" => companies.sort_by(|a, b| {
            compare_optional_days(a.published_min_days, b.published_min_days)
                .then_with(|| a.base_keyword.cmp(&b.base_keyword))
        }),
        "hit" => companies.sort_by(|a, b| {
            compare_optional_days(a.hit_min_days, b.hit_min_days)
                .then_with(|| a.base_keyword.cmp(&b.base_keyword))
        }),
        _ => companies.sort_by(|a, b| a.base_keyword.cmp(&b.base_keyword)),
    }
    Ok(companies)
}

fn get_cached_companies_by_type(
    conn: &Connection,
    sort: Option<String>,
    group_type: String,
) -> Result<Vec<CompanySummary>, String> {
    let mut stmt = conn
        .prepare(
            r#"
            SELECT
                group_id,
                group_name,
                group_type,
                article_count,
                site_count,
                latest_published_date,
                latest_hit_at,
                published_min_days,
                hit_min_days
            FROM viewer_group_summary
            WHERE group_type = ?
            "#,
        )
        .map_err(|err| err.to_string())?;
    let rows = stmt
        .query_map(params![group_type], |row| {
            Ok(CompanySummary {
                base_keyword_id: row.get(0)?,
                base_keyword: row.get(1)?,
                group_type: row.get(2)?,
                article_count: row.get(3)?,
                site_count: row.get(4)?,
                latest_published_date: row.get(5)?,
                latest_hit_at: row.get(6)?,
                published_min_days: row.get(7)?,
                hit_min_days: row.get(8)?,
            })
        })
        .map_err(|err| err.to_string())?;
    let mut companies: Vec<CompanySummary> = rows
        .collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())?;

    match sort.unwrap_or_else(|| "name".to_string()).as_str() {
        "published" => companies.sort_by(|a, b| {
            compare_optional_days(a.published_min_days, b.published_min_days)
                .then_with(|| a.base_keyword.cmp(&b.base_keyword))
        }),
        "hit" => companies.sort_by(|a, b| {
            compare_optional_days(a.hit_min_days, b.hit_min_days)
                .then_with(|| a.base_keyword.cmp(&b.base_keyword))
        }),
        _ => companies.sort_by(|a, b| a.base_keyword.cmp(&b.base_keyword)),
    }
    Ok(companies)
}

fn viewer_group_summary_available(conn: &Connection) -> Result<bool, String> {
    if !table_exists(conn, "viewer_group_summary")? {
        return Ok(false);
    }
    let count: i64 = conn
        .query_row("SELECT COUNT(*) FROM viewer_group_summary", [], |row| {
            row.get(0)
        })
        .map_err(|err| err.to_string())?;
    Ok(count > 0)
}

fn table_exists(conn: &Connection, table_name: &str) -> Result<bool, String> {
    conn.query_row(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        params![table_name],
        |_| Ok(()),
    )
    .optional()
    .map(|value| value.is_some())
    .map_err(|err| err.to_string())
}

fn invalidate_viewer_cache(conn: &Connection) -> Result<(), String> {
    for table in ["viewer_group_summary", "viewer_result_rows"] {
        if table_exists(conn, table)? {
            conn.execute(&format!("DELETE FROM {table}"), [])
                .map_err(|err| err.to_string())?;
        }
    }
    if table_exists(conn, "viewer_metadata")? {
        conn.execute(
            "DELETE FROM viewer_metadata WHERE cache_name IN ('group_summary', 'result_rows')",
            [],
        )
        .map_err(|err| err.to_string())?;
    }
    Ok(())
}

fn compare_optional_days(a: Option<i64>, b: Option<i64>) -> Ordering {
    match (a, b) {
        (Some(a), Some(b)) => a.cmp(&b),
        (Some(_), None) => Ordering::Less,
        (None, Some(_)) => Ordering::Greater,
        (None, None) => Ordering::Equal,
    }
}

pub fn get_company_results(
    db_path: Option<String>,
    base_keyword_id: String,
    limit: Option<i64>,
    offset: Option<i64>,
) -> Result<Vec<ArticleRow>, String> {
    let conn = open_db(db_path)?;
    let limit = limit.unwrap_or(100).clamp(1, 5000);
    let offset = offset.unwrap_or(0).max(0);
    if viewer_result_rows_available_for_group(&conn, &base_keyword_id)? {
        return get_cached_company_results(&conn, base_keyword_id, limit, offset);
    }

    let mut stmt = conn
        .prepare(
            r#"
            SELECT
                i.result_item_id,
                i.site_id,
                COALESCE(s.site_name, i.site_id) AS site_name,
                i.title,
                i.url,
                i.published_date,
                MIN(h.first_seen_at) AS first_hit_at,
                GROUP_CONCAT(DISTINCT h.candidate_keyword) AS candidate_keywords,
                i.snippet
            FROM search_result_hits h
            JOIN search_result_items i ON i.result_item_id = h.result_item_id
            LEFT JOIN sites s ON s.site_id = i.site_id
            WHERE h.base_keyword_id = ?
            GROUP BY i.result_item_id
            ORDER BY
                CASE WHEN i.published_date IS NULL OR i.published_date = '' THEN 1 ELSE 0 END,
                i.published_date DESC,
                first_hit_at DESC
            LIMIT ?
            OFFSET ?
            "#,
        )
        .map_err(|err| err.to_string())?;
    let rows = stmt
        .query_map(params![base_keyword_id, limit, offset], |row| {
            let published_date: Option<String> = row.get(5)?;
            let first_hit_at: String = row.get(6)?;
            Ok(ArticleRow {
                result_item_id: row.get(0)?,
                site_id: row.get(1)?,
                site_name: row.get(2)?,
                title: row.get(3)?,
                url: row.get(4)?,
                published_days: days_since(parse_published_date(published_date.as_deref())),
                published_date,
                hit_days: parse_iso_date_prefix(&first_hit_at)
                    .and_then(|date| days_since(Some(date))),
                first_hit_at,
                candidate_keywords: row.get::<_, Option<String>>(7)?.unwrap_or_default(),
                snippet: row.get(8)?,
            })
        })
        .map_err(|err| err.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())
}

fn get_cached_company_results(
    conn: &Connection,
    base_keyword_id: String,
    limit: i64,
    offset: i64,
) -> Result<Vec<ArticleRow>, String> {
    let mut stmt = conn
        .prepare(
            r#"
            SELECT
                result_item_id,
                site_id,
                site_name,
                title,
                url,
                published_date,
                published_days,
                first_hit_at,
                hit_days,
                candidate_keywords,
                snippet
            FROM viewer_result_rows
            WHERE group_id = ?
            ORDER BY cache_rank
            LIMIT ?
            OFFSET ?
            "#,
        )
        .map_err(|err| err.to_string())?;
    let rows = stmt
        .query_map(params![base_keyword_id, limit, offset], |row| {
            Ok(ArticleRow {
                result_item_id: row.get(0)?,
                site_id: row.get(1)?,
                site_name: row.get(2)?,
                title: row.get(3)?,
                url: row.get(4)?,
                published_date: row.get(5)?,
                published_days: row.get(6)?,
                first_hit_at: row.get(7)?,
                hit_days: row.get(8)?,
                candidate_keywords: row.get(9)?,
                snippet: row.get(10)?,
            })
        })
        .map_err(|err| err.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())
}

fn viewer_result_rows_available_for_group(
    conn: &Connection,
    group_id: &str,
) -> Result<bool, String> {
    if !table_exists(conn, "viewer_result_rows")? {
        return Ok(false);
    }
    let count: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM viewer_result_rows WHERE group_id = ?",
            params![group_id],
            |row| row.get(0),
        )
        .map_err(|err| err.to_string())?;
    Ok(count > 0)
}

pub fn get_keyword_tree(db_path: Option<String>) -> Result<Vec<KeywordGroupRow>, String> {
    let conn = open_db(db_path)?;
    ensure_keyword_group_type_column(&conn)?;
    let mut stmt = conn
        .prepare(
            "SELECT base_keyword_id, base_keyword, COALESCE(group_type, 'company'), enabled, notes FROM keyword_groups ORDER BY group_type, base_keyword",
        )
        .map_err(|err| err.to_string())?;
    let group_rows = stmt
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)? != 0,
                row.get::<_, Option<String>>(4)?,
            ))
        })
        .map_err(|err| err.to_string())?;
    let mut groups = Vec::new();
    for row in group_rows {
        let (base_keyword_id, base_keyword, group_type, enabled, notes) =
            row.map_err(|err| err.to_string())?;
        let mut candidates_stmt = conn
            .prepare(
                r#"
                SELECT candidate_keyword_id, candidate_keyword, enabled, notes
                FROM keyword_candidates
                WHERE base_keyword_id = ?
                ORDER BY candidate_keyword
                "#,
            )
            .map_err(|err| err.to_string())?;
        let candidates = candidates_stmt
            .query_map(params![base_keyword_id], |row| {
                Ok(KeywordCandidateRow {
                    candidate_keyword_id: row.get(0)?,
                    candidate_keyword: row.get(1)?,
                    enabled: row.get::<_, i64>(2)? != 0,
                    notes: row.get(3)?,
                })
            })
            .map_err(|err| err.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|err| err.to_string())?;
        groups.push(KeywordGroupRow {
            base_keyword_id,
            base_keyword,
            group_type,
            enabled,
            notes,
            candidates,
        });
    }
    Ok(groups)
}

pub fn add_keyword_group(db_path: Option<String>, base_keyword: String) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_keyword_group_type_column(&conn)?;
    let base_keyword = normalize_keyword(&base_keyword)?;
    let id = keyword_group_id(&base_keyword, "company");
    conn.execute(
        r#"
        INSERT INTO keyword_groups (base_keyword_id, base_keyword, group_type, enabled, notes)
        VALUES (?, ?, 'company', 1, NULL)
        ON CONFLICT(base_keyword_id) DO UPDATE SET
            base_keyword = excluded.base_keyword,
            group_type = excluded.group_type,
            enabled = 1
        "#,
        params![id, base_keyword],
    )
    .map_err(|err| err.to_string())?;
    invalidate_viewer_cache(&conn)?;
    Ok(())
}

pub fn add_keyword_group_typed(
    db_path: Option<String>,
    base_keyword: String,
    group_type: String,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_keyword_group_type_column(&conn)?;
    let base_keyword = normalize_keyword(&base_keyword)?;
    let group_type = normalize_group_type(Some(&group_type));
    let id = keyword_group_id(&base_keyword, &group_type);
    conn.execute(
        r#"
        INSERT INTO keyword_groups (base_keyword_id, base_keyword, group_type, enabled, notes)
        VALUES (?, ?, ?, 1, NULL)
        ON CONFLICT(base_keyword_id) DO UPDATE SET
            base_keyword = excluded.base_keyword,
            group_type = excluded.group_type,
            enabled = 1
        "#,
        params![id, base_keyword, group_type],
    )
    .map_err(|err| err.to_string())?;
    invalidate_viewer_cache(&conn)?;
    Ok(())
}

pub fn set_keyword_group_enabled(
    db_path: Option<String>,
    base_keyword_id: String,
    enabled: bool,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_keyword_group_type_column(&conn)?;
    conn.execute(
        "UPDATE keyword_groups SET enabled = ? WHERE base_keyword_id = ?",
        params![if enabled { 1 } else { 0 }, base_keyword_id],
    )
    .map_err(|err| err.to_string())?;
    invalidate_viewer_cache(&conn)?;
    Ok(())
}

pub fn add_candidate_keyword(
    db_path: Option<String>,
    base_keyword_id: String,
    candidate_keyword: String,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    let candidate_keyword = normalize_keyword(&candidate_keyword)?;
    let (base_keyword, group_type): (String, String) = conn
        .query_row(
            "SELECT base_keyword, COALESCE(group_type, 'company') FROM keyword_groups WHERE base_keyword_id = ?",
            params![base_keyword_id],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .map_err(|err| err.to_string())?;
    let id = keyword_candidate_id(&base_keyword, &candidate_keyword, &group_type);
    conn.execute(
        r#"
        INSERT INTO keyword_candidates (
            candidate_keyword_id, base_keyword_id, candidate_keyword, enabled, notes
        )
        VALUES (?, ?, ?, 1, NULL)
        ON CONFLICT(candidate_keyword_id) DO UPDATE SET
            candidate_keyword = excluded.candidate_keyword,
            enabled = 1
        "#,
        params![id, base_keyword_id, candidate_keyword],
    )
    .map_err(|err| err.to_string())?;
    invalidate_viewer_cache(&conn)?;
    Ok(())
}

pub fn set_candidate_keyword_enabled(
    db_path: Option<String>,
    candidate_keyword_id: String,
    enabled: bool,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    conn.execute(
        "UPDATE keyword_candidates SET enabled = ? WHERE candidate_keyword_id = ?",
        params![if enabled { 1 } else { 0 }, candidate_keyword_id],
    )
    .map_err(|err| err.to_string())?;
    invalidate_viewer_cache(&conn)?;
    Ok(())
}

pub fn create_site_request(
    db_path: Option<String>,
    site_name: String,
    site_url: String,
    requester_name: Option<String>,
    requester_email: Option<String>,
    notes: Option<String>,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_request_tables(&conn)?;
    let site_name = normalize_keyword(&site_name)?;
    let site_url = normalize_keyword(&site_url)?;
    let now = now_string();
    conn.execute(
        r#"
        INSERT INTO site_requests (
            request_id, site_name, site_url, requester_name, requester_email,
            notes, status, implementer_comment, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'new', NULL, ?, ?)
        "#,
        params![
            Uuid::new_v4().to_string(),
            site_name,
            site_url,
            optional_trimmed(requester_name),
            optional_trimmed(requester_email),
            optional_trimmed(notes),
            now,
            now
        ],
    )
    .map_err(|err| err.to_string())?;
    Ok(())
}

pub fn list_site_requests(db_path: Option<String>) -> Result<Vec<SiteRequestRow>, String> {
    let conn = open_db(db_path)?;
    ensure_request_tables(&conn)?;
    let mut stmt = conn
        .prepare(
            r#"
            SELECT request_id, site_name, site_url, requester_name, requester_email,
                   notes, status, implementer_comment, created_at, updated_at
            FROM site_requests
            ORDER BY created_at DESC
            "#,
        )
        .map_err(|err| err.to_string())?;
    let rows = stmt
        .query_map([], |row| {
            Ok(SiteRequestRow {
                request_id: row.get(0)?,
                site_name: row.get(1)?,
                site_url: row.get(2)?,
                requester_name: row.get(3)?,
                requester_email: row.get(4)?,
                notes: row.get(5)?,
                status: row.get(6)?,
                implementer_comment: row.get(7)?,
                created_at: row.get(8)?,
                updated_at: row.get(9)?,
            })
        })
        .map_err(|err| err.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())
}

pub fn update_site_request(
    db_path: Option<String>,
    request_id: String,
    status: String,
    implementer_comment: Option<String>,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_request_tables(&conn)?;
    conn.execute(
        r#"
        UPDATE site_requests
        SET status = ?, implementer_comment = ?, updated_at = ?
        WHERE request_id = ?
        "#,
        params![
            normalize_request_status(Some(&status)),
            optional_trimmed(implementer_comment),
            now_string(),
            request_id
        ],
    )
    .map_err(|err| err.to_string())?;
    Ok(())
}

pub fn create_keyword_change_request(
    db_path: Option<String>,
    request_type: String,
    group_type: String,
    base_keyword: String,
    candidate_keyword: Option<String>,
    requester_name: Option<String>,
    requester_email: Option<String>,
    reason: Option<String>,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_request_tables(&conn)?;
    let base_keyword = normalize_keyword(&base_keyword)?;
    let now = now_string();
    conn.execute(
        r#"
        INSERT INTO keyword_change_requests (
            request_id, request_type, group_type, base_keyword, candidate_keyword,
            requester_name, requester_email, reason, status, implementer_comment,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', NULL, ?, ?)
        "#,
        params![
            Uuid::new_v4().to_string(),
            normalize_request_type(&request_type),
            normalize_group_type(Some(&group_type)),
            base_keyword,
            optional_trimmed(candidate_keyword),
            optional_trimmed(requester_name),
            optional_trimmed(requester_email),
            optional_trimmed(reason),
            now,
            now
        ],
    )
    .map_err(|err| err.to_string())?;
    Ok(())
}

pub fn list_keyword_change_requests(
    db_path: Option<String>,
) -> Result<Vec<KeywordChangeRequestRow>, String> {
    let conn = open_db(db_path)?;
    ensure_request_tables(&conn)?;
    let mut stmt = conn
        .prepare(
            r#"
            SELECT request_id, request_type, group_type, base_keyword, candidate_keyword,
                   requester_name, requester_email, reason, status, implementer_comment,
                   created_at, updated_at
            FROM keyword_change_requests
            ORDER BY created_at DESC
            "#,
        )
        .map_err(|err| err.to_string())?;
    let rows = stmt
        .query_map([], |row| {
            Ok(KeywordChangeRequestRow {
                request_id: row.get(0)?,
                request_type: row.get(1)?,
                group_type: row.get(2)?,
                base_keyword: row.get(3)?,
                candidate_keyword: row.get(4)?,
                requester_name: row.get(5)?,
                requester_email: row.get(6)?,
                reason: row.get(7)?,
                status: row.get(8)?,
                implementer_comment: row.get(9)?,
                created_at: row.get(10)?,
                updated_at: row.get(11)?,
            })
        })
        .map_err(|err| err.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| err.to_string())
}

pub fn update_keyword_change_request(
    db_path: Option<String>,
    request_id: String,
    status: String,
    implementer_comment: Option<String>,
) -> Result<(), String> {
    let conn = open_db(db_path)?;
    ensure_request_tables(&conn)?;
    conn.execute(
        r#"
        UPDATE keyword_change_requests
        SET status = ?, implementer_comment = ?, updated_at = ?
        WHERE request_id = ?
        "#,
        params![
            normalize_request_status(Some(&status)),
            optional_trimmed(implementer_comment),
            now_string(),
            request_id
        ],
    )
    .map_err(|err| err.to_string())?;
    Ok(())
}

pub fn list_site_health(db_path: Option<String>) -> Result<Vec<SiteHealthRow>, String> {
    let conn = open_db(db_path)?;
    let latest_run_id: Option<String> = conn
        .query_row(
            "SELECT run_id FROM search_runs ORDER BY started_at DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .ok();

    let mut stmt = conn
        .prepare(
            r#"
            SELECT site_id, site_name, enabled, requires_playwright
            FROM sites
            ORDER BY site_name
            "#,
        )
        .map_err(|err| err.to_string())?;
    let site_rows = stmt
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)? != 0,
                row.get::<_, i64>(3)? != 0,
            ))
        })
        .map_err(|err| err.to_string())?;

    let mut rows = Vec::new();
    for site_row in site_rows {
        let (site_id, site_name, enabled, requires_playwright) =
            site_row.map_err(|err| err.to_string())?;
        let latest_run_hits = if let Some(run_id) = latest_run_id.as_ref() {
            count_scalar(
                &conn,
                "SELECT COUNT(*) FROM search_result_hits WHERE site_id = ? AND run_id = ?",
                params![site_id, run_id],
            )?
        } else {
            0
        };
        let latest_run_errors = if let Some(run_id) = latest_run_id.as_ref() {
            count_scalar(
                &conn,
                "SELECT COUNT(*) FROM fetch_errors WHERE site_id = ? AND run_id = ?",
                params![site_id, run_id],
            )?
        } else {
            0
        };
        let total_items = count_scalar(
            &conn,
            "SELECT COUNT(*) FROM search_result_items WHERE site_id = ?",
            params![site_id],
        )?;
        let missing_published_dates = count_scalar(
            &conn,
            r#"
            SELECT COUNT(*)
            FROM search_result_items
            WHERE site_id = ?
              AND (published_date IS NULL OR published_date = '')
            "#,
            params![site_id],
        )?;
        let latest_error = conn
            .query_row(
                r#"
                SELECT error_type, error_message, created_at
                FROM fetch_errors
                WHERE site_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                "#,
                params![site_id],
                |row| {
                    Ok((
                        row.get::<_, String>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, String>(2)?,
                    ))
                },
            )
            .ok();
        let latest_skip = conn
            .query_row(
                r#"
                SELECT reason, created_at
                FROM crawl_skips
                WHERE site_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                "#,
                params![site_id],
                |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)),
            )
            .ok();
        let status = if !enabled {
            "disabled"
        } else if latest_run_errors > 0 {
            "error"
        } else if latest_run_id.is_some() && latest_run_hits == 0 {
            "warning"
        } else if missing_published_dates > 0 {
            "notice"
        } else {
            "ok"
        }
        .to_string();

        rows.push(SiteHealthRow {
            site_id,
            site_name,
            enabled,
            requires_playwright,
            status,
            latest_run_hits,
            latest_run_errors,
            total_items,
            missing_published_dates,
            latest_error_type: latest_error.as_ref().map(|row| row.0.clone()),
            latest_error_message: latest_error.as_ref().map(|row| row.1.clone()),
            latest_error_at: latest_error.map(|row| row.2),
            latest_skip_reason: latest_skip.as_ref().map(|row| row.0.clone()),
            latest_skip_at: latest_skip.map(|row| row.1),
        });
    }

    rows.sort_by(|a, b| {
        site_status_rank(&a.status)
            .cmp(&site_status_rank(&b.status))
            .then_with(|| a.site_name.cmp(&b.site_name))
    });
    Ok(rows)
}

fn count_scalar<P>(conn: &Connection, sql: &str, params: P) -> Result<i64, String>
where
    P: rusqlite::Params,
{
    conn.query_row(sql, params, |row| row.get(0))
        .map_err(|err| err.to_string())
}

fn site_status_rank(status: &str) -> i32 {
    match status {
        "error" => 0,
        "warning" => 1,
        "notice" => 2,
        "disabled" => 3,
        _ => 4,
    }
}

pub fn open_external_url(url: String) -> Result<(), String> {
    let url = url.trim();
    if !(url.starts_with("https://") || url.starts_with("http://")) {
        return Err("Only http and https URLs can be opened".to_string());
    }

    #[cfg(target_os = "windows")]
    {
        Command::new("cmd")
            .args(["/C", "start", "", url])
            .spawn()
            .map_err(|err| format!("Failed to open browser: {err}"))?;
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(url)
            .spawn()
            .map_err(|err| format!("Failed to open browser: {err}"))?;
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        Command::new("xdg-open")
            .arg(url)
            .spawn()
            .map_err(|err| format!("Failed to open browser: {err}"))?;
    }

    Ok(())
}

fn normalize_keyword(value: &str) -> Result<String, String> {
    let normalized = value.trim().to_string();
    if normalized.is_empty() {
        return Err("Keyword must not be empty".to_string());
    }
    Ok(normalized)
}

fn normalize_group_type(value: Option<&str>) -> String {
    match value
        .unwrap_or("company")
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "topic" => "topic".to_string(),
        _ => "company".to_string(),
    }
}

fn keyword_group_id(base_keyword: &str, group_type: &str) -> String {
    let key = if group_type == "company" {
        format!("keyword-group:{base_keyword}")
    } else {
        format!("keyword-group:{group_type}:{base_keyword}")
    };
    let id = Uuid::new_v5(&KEYWORD_NAMESPACE, key.as_bytes());
    format!("kwg_{}", &id.simple().to_string()[..12])
}

fn keyword_candidate_id(base_keyword: &str, candidate_keyword: &str, group_type: &str) -> String {
    let key = if group_type == "company" {
        format!("keyword-candidate:{base_keyword}\0{candidate_keyword}")
    } else {
        format!("keyword-candidate:{group_type}\0{base_keyword}\0{candidate_keyword}")
    };
    let id = Uuid::new_v5(&KEYWORD_NAMESPACE, key.as_bytes());
    format!("kwc_{}", &id.simple().to_string()[..12])
}
