#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod viewer_core;

#[tauri::command]
fn get_stats(db_path: Option<String>) -> Result<viewer_core::AppStats, String> {
    viewer_core::get_stats(db_path)
}

#[tauri::command]
fn get_companies(
    db_path: Option<String>,
    sort: Option<String>,
) -> Result<Vec<viewer_core::CompanySummary>, String> {
    viewer_core::get_companies(db_path, sort)
}

#[tauri::command]
fn get_keyword_summaries(
    db_path: Option<String>,
    sort: Option<String>,
    group_type: Option<String>,
) -> Result<Vec<viewer_core::CompanySummary>, String> {
    viewer_core::get_keyword_summaries(db_path, sort, group_type)
}

#[tauri::command]
fn get_viewer_metadata(
    db_path: Option<String>,
) -> Result<Option<viewer_core::ViewerMetadata>, String> {
    viewer_core::get_viewer_metadata(db_path)
}

#[tauri::command]
fn get_company_results(
    db_path: Option<String>,
    base_keyword_id: String,
    limit: Option<i64>,
) -> Result<Vec<viewer_core::ArticleRow>, String> {
    viewer_core::get_company_results(db_path, base_keyword_id, limit)
}

#[tauri::command]
fn get_keyword_tree(db_path: Option<String>) -> Result<Vec<viewer_core::KeywordGroupRow>, String> {
    viewer_core::get_keyword_tree(db_path)
}

#[tauri::command]
fn add_keyword_group(db_path: Option<String>, base_keyword: String) -> Result<(), String> {
    viewer_core::add_keyword_group(db_path, base_keyword)
}

#[tauri::command]
fn add_keyword_group_typed(
    db_path: Option<String>,
    base_keyword: String,
    group_type: String,
) -> Result<(), String> {
    viewer_core::add_keyword_group_typed(db_path, base_keyword, group_type)
}

#[tauri::command]
fn set_keyword_group_enabled(
    db_path: Option<String>,
    base_keyword_id: String,
    enabled: bool,
) -> Result<(), String> {
    viewer_core::set_keyword_group_enabled(db_path, base_keyword_id, enabled)
}

#[tauri::command]
fn add_candidate_keyword(
    db_path: Option<String>,
    base_keyword_id: String,
    candidate_keyword: String,
) -> Result<(), String> {
    viewer_core::add_candidate_keyword(db_path, base_keyword_id, candidate_keyword)
}

#[tauri::command]
fn set_candidate_keyword_enabled(
    db_path: Option<String>,
    candidate_keyword_id: String,
    enabled: bool,
) -> Result<(), String> {
    viewer_core::set_candidate_keyword_enabled(db_path, candidate_keyword_id, enabled)
}

#[tauri::command]
fn create_site_request(
    db_path: Option<String>,
    site_name: String,
    site_url: String,
    requester_name: Option<String>,
    requester_email: Option<String>,
    notes: Option<String>,
) -> Result<(), String> {
    viewer_core::create_site_request(
        db_path,
        site_name,
        site_url,
        requester_name,
        requester_email,
        notes,
    )
}

#[tauri::command]
fn list_site_requests(db_path: Option<String>) -> Result<Vec<viewer_core::SiteRequestRow>, String> {
    viewer_core::list_site_requests(db_path)
}

#[tauri::command]
fn update_site_request(
    db_path: Option<String>,
    request_id: String,
    status: String,
    implementer_comment: Option<String>,
) -> Result<(), String> {
    viewer_core::update_site_request(db_path, request_id, status, implementer_comment)
}

#[tauri::command]
fn create_keyword_change_request(
    db_path: Option<String>,
    request_type: String,
    group_type: String,
    base_keyword: String,
    candidate_keyword: Option<String>,
    requester_name: Option<String>,
    requester_email: Option<String>,
    reason: Option<String>,
) -> Result<(), String> {
    viewer_core::create_keyword_change_request(
        db_path,
        request_type,
        group_type,
        base_keyword,
        candidate_keyword,
        requester_name,
        requester_email,
        reason,
    )
}

#[tauri::command]
fn list_keyword_change_requests(
    db_path: Option<String>,
) -> Result<Vec<viewer_core::KeywordChangeRequestRow>, String> {
    viewer_core::list_keyword_change_requests(db_path)
}

#[tauri::command]
fn update_keyword_change_request(
    db_path: Option<String>,
    request_id: String,
    status: String,
    implementer_comment: Option<String>,
) -> Result<(), String> {
    viewer_core::update_keyword_change_request(db_path, request_id, status, implementer_comment)
}

#[tauri::command]
fn list_site_health(db_path: Option<String>) -> Result<Vec<viewer_core::SiteHealthRow>, String> {
    viewer_core::list_site_health(db_path)
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    viewer_core::open_external_url(url)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_stats,
            get_companies,
            get_keyword_summaries,
            get_viewer_metadata,
            get_company_results,
            get_keyword_tree,
            add_keyword_group,
            add_keyword_group_typed,
            set_keyword_group_enabled,
            add_candidate_keyword,
            set_candidate_keyword_enabled,
            create_site_request,
            list_site_requests,
            update_site_request,
            create_keyword_change_request,
            list_keyword_change_requests,
            update_keyword_change_request,
            list_site_health,
            open_external_url
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
