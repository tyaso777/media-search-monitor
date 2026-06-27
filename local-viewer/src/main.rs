use serde::Serialize;
use serde_json::{json, Value};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;
use std::time::Duration;

#[path = "../../src-tauri/src/viewer_core.rs"]
mod viewer_core;

const INDEX_HTML: &str = include_str!("../../ui/index.html");
const APP_JS: &str = include_str!("../../ui/app.js");
const API_JS: &str = include_str!("../../ui/api.js");
const STYLES_CSS: &str = include_str!("../../ui/styles.css");

fn main() -> Result<(), String> {
    let options = Options::from_args()?;
    let bind_address = format!("127.0.0.1:{}", options.port.unwrap_or(0));
    let listener = TcpListener::bind(&bind_address).map_err(|err| err.to_string())?;
    let address = listener.local_addr().map_err(|err| err.to_string())?;
    let url = format!("http://{address}/");
    println!("News Monitor Local Viewer: {url}");
    if !options.no_open {
        open_browser(&url);
    }

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                if let Err(err) = handle_connection(stream) {
                    eprintln!("request error: {err}");
                }
            }
            Err(err) => eprintln!("connection error: {err}"),
        }
    }
    Ok(())
}

struct Options {
    no_open: bool,
    port: Option<u16>,
}

impl Options {
    fn from_args() -> Result<Self, String> {
        let mut no_open = false;
        let mut port = None;
        let mut args = std::env::args().skip(1);
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--no-open" => no_open = true,
                "--port" => {
                    let value = args
                        .next()
                        .ok_or_else(|| "--port requires a value".to_string())?;
                    port = Some(
                        value
                            .parse::<u16>()
                            .map_err(|_| "--port must be 0-65535".to_string())?,
                    );
                }
                "--help" | "-h" => {
                    println!(
                        "Usage: news-monitor-local-viewer.exe [--no-open] [--port PORT]\n\nStarts a localhost UI for data/news_monitor.sqlite."
                    );
                    std::process::exit(0);
                }
                _ => return Err(format!("unknown argument: {arg}")),
            }
        }
        Ok(Self { no_open, port })
    }
}

fn handle_connection(mut stream: TcpStream) -> Result<(), String> {
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|err| err.to_string())?;
    let request = read_request(&mut stream)?;
    let response = route_request(&request);
    stream
        .write_all(response.as_bytes())
        .map_err(|err| err.to_string())
}

struct HttpRequest {
    method: String,
    path: String,
    body: String,
}

fn read_request(stream: &mut TcpStream) -> Result<HttpRequest, String> {
    let mut buffer = Vec::new();
    let mut temp = [0_u8; 4096];
    let mut header_end = None;

    loop {
        let read = stream.read(&mut temp).map_err(|err| err.to_string())?;
        if read == 0 {
            break;
        }
        buffer.extend_from_slice(&temp[..read]);
        if let Some(position) = find_header_end(&buffer) {
            header_end = Some(position);
            break;
        }
        if buffer.len() > 1024 * 1024 {
            return Err("request header is too large".to_string());
        }
    }

    let header_end = header_end.ok_or_else(|| "invalid HTTP request".to_string())?;
    let headers_text = String::from_utf8_lossy(&buffer[..header_end]).to_string();
    let mut lines = headers_text.lines();
    let request_line = lines
        .next()
        .ok_or_else(|| "missing request line".to_string())?;
    let mut request_parts = request_line.split_whitespace();
    let method = request_parts.next().unwrap_or_default().to_string();
    let path = request_parts
        .next()
        .unwrap_or("/")
        .split('?')
        .next()
        .unwrap_or("/")
        .to_string();

    let mut content_length = 0_usize;
    for line in lines {
        if let Some((name, value)) = line.split_once(':') {
            if name.trim().eq_ignore_ascii_case("content-length") {
                content_length = value.trim().parse::<usize>().unwrap_or(0);
            }
        }
    }

    let body_start = header_end + 4;
    while buffer.len().saturating_sub(body_start) < content_length {
        let read = stream.read(&mut temp).map_err(|err| err.to_string())?;
        if read == 0 {
            break;
        }
        buffer.extend_from_slice(&temp[..read]);
    }
    let body_bytes = &buffer[body_start..buffer.len().min(body_start + content_length)];
    let body = String::from_utf8_lossy(body_bytes).to_string();

    Ok(HttpRequest { method, path, body })
}

fn find_header_end(buffer: &[u8]) -> Option<usize> {
    buffer.windows(4).position(|window| window == b"\r\n\r\n")
}

fn route_request(request: &HttpRequest) -> String {
    if request.method == "GET" {
        return match request.path.as_str() {
            "/" | "/index.html" => ok("text/html; charset=utf-8", INDEX_HTML),
            "/app.js" => ok("text/javascript; charset=utf-8", APP_JS),
            "/api.js" => ok("text/javascript; charset=utf-8", API_JS),
            "/styles.css" => ok("text/css; charset=utf-8", STYLES_CSS),
            _ => not_found(),
        };
    }

    if request.method == "POST" && request.path.starts_with("/api/invoke/") {
        let command = request.path.trim_start_matches("/api/invoke/");
        let params = serde_json::from_str::<Value>(&request.body).unwrap_or_else(|_| json!({}));
        return match dispatch(command, &params) {
            Ok(value) => json_response(200, json!({ "ok": true, "value": value })),
            Err(error) => json_response(500, json!({ "ok": false, "error": error })),
        };
    }

    method_not_allowed()
}

fn dispatch(command: &str, params: &Value) -> Result<Value, String> {
    let db_path = opt_string(params, "dbPath", "db_path");
    match command {
        "get_stats" => to_value(viewer_core::get_stats(db_path)),
        "get_companies" => to_value(viewer_core::get_companies(
            db_path,
            opt_string(params, "sort", "sort"),
        )),
        "get_keyword_summaries" => to_value(viewer_core::get_keyword_summaries(
            db_path,
            opt_string(params, "sort", "sort"),
            opt_string(params, "groupType", "group_type"),
        )),
        "get_viewer_metadata" => to_value(viewer_core::get_viewer_metadata(db_path)),
        "get_company_results" => to_value(viewer_core::get_company_results(
            db_path,
            req_string(params, "baseKeywordId", "base_keyword_id")?,
            opt_i64(params, "limit", "limit"),
            opt_i64(params, "offset", "offset"),
            opt_string_array(params, "siteIds", "site_ids"),
            opt_string_array(params, "candidateKeywords", "candidate_keywords"),
            opt_string(params, "titleFilter", "title_filter"),
            opt_string(params, "snippetFilter", "snippet_filter"),
            opt_i64(params, "publishedDays", "published_days"),
            opt_i64(params, "hitDays", "hit_days"),
            opt_string(params, "sortColumn", "sort_column"),
            opt_string(params, "sortDirection", "sort_direction"),
        )),
        "get_company_result_filters" => to_value(viewer_core::get_company_result_filters(
            db_path,
            req_string(params, "baseKeywordId", "base_keyword_id")?,
        )),
        "get_keyword_tree" => to_value(viewer_core::get_keyword_tree(db_path)),
        "add_keyword_group" => to_value(viewer_core::add_keyword_group(
            db_path,
            req_string(params, "baseKeyword", "base_keyword")?,
        )),
        "add_keyword_group_typed" => to_value(viewer_core::add_keyword_group_typed(
            db_path,
            req_string(params, "baseKeyword", "base_keyword")?,
            req_string(params, "groupType", "group_type")?,
        )),
        "set_keyword_group_enabled" => to_value(viewer_core::set_keyword_group_enabled(
            db_path,
            req_string(params, "baseKeywordId", "base_keyword_id")?,
            req_bool(params, "enabled", "enabled")?,
        )),
        "add_candidate_keyword" => to_value(viewer_core::add_candidate_keyword(
            db_path,
            req_string(params, "baseKeywordId", "base_keyword_id")?,
            req_string(params, "candidateKeyword", "candidate_keyword")?,
        )),
        "set_candidate_keyword_enabled" => to_value(viewer_core::set_candidate_keyword_enabled(
            db_path,
            req_string(params, "candidateKeywordId", "candidate_keyword_id")?,
            req_bool(params, "enabled", "enabled")?,
        )),
        "create_site_request" => to_value(viewer_core::create_site_request(
            db_path,
            req_string(params, "siteName", "site_name")?,
            req_string(params, "siteUrl", "site_url")?,
            opt_string(params, "requesterName", "requester_name"),
            opt_string(params, "requesterEmail", "requester_email"),
            opt_string(params, "notes", "notes"),
        )),
        "list_site_requests" => to_value(viewer_core::list_site_requests(db_path)),
        "update_site_request" => to_value(viewer_core::update_site_request(
            db_path,
            req_string(params, "requestId", "request_id")?,
            req_string(params, "status", "status")?,
            opt_string(params, "implementerComment", "implementer_comment"),
        )),
        "create_keyword_change_request" => to_value(viewer_core::create_keyword_change_request(
            db_path,
            req_string(params, "requestType", "request_type")?,
            req_string(params, "groupType", "group_type")?,
            req_string(params, "baseKeyword", "base_keyword")?,
            opt_string(params, "candidateKeyword", "candidate_keyword"),
            opt_string(params, "requesterName", "requester_name"),
            opt_string(params, "requesterEmail", "requester_email"),
            opt_string(params, "reason", "reason"),
        )),
        "list_keyword_change_requests" => {
            to_value(viewer_core::list_keyword_change_requests(db_path))
        }
        "update_keyword_change_request" => to_value(viewer_core::update_keyword_change_request(
            db_path,
            req_string(params, "requestId", "request_id")?,
            req_string(params, "status", "status")?,
            opt_string(params, "implementerComment", "implementer_comment"),
        )),
        "list_site_health" => to_value(viewer_core::list_site_health(db_path)),
        "open_external_url" => to_value(viewer_core::open_external_url(req_string(
            params, "url", "url",
        )?)),
        "shutdown_server" => {
            thread::spawn(|| {
                thread::sleep(Duration::from_millis(250));
                std::process::exit(0);
            });
            Ok(Value::Null)
        }
        _ => Err(format!("unknown command: {command}")),
    }
}

fn to_value<T: Serialize>(result: Result<T, String>) -> Result<Value, String> {
    result.and_then(|value| serde_json::to_value(value).map_err(|err| err.to_string()))
}

fn opt_string(params: &Value, camel: &str, snake: &str) -> Option<String> {
    params
        .get(camel)
        .or_else(|| params.get(snake))
        .and_then(|value| value.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn req_string(params: &Value, camel: &str, snake: &str) -> Result<String, String> {
    opt_string(params, camel, snake).ok_or_else(|| format!("missing parameter: {camel}"))
}

fn opt_i64(params: &Value, camel: &str, snake: &str) -> Option<i64> {
    params
        .get(camel)
        .or_else(|| params.get(snake))
        .and_then(|value| value.as_i64())
}

fn opt_string_array(params: &Value, camel: &str, snake: &str) -> Option<Vec<String>> {
    let values = params.get(camel).or_else(|| params.get(snake))?.as_array()?;
    Some(
        values
            .iter()
            .filter_map(|value| value.as_str())
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToOwned::to_owned)
            .collect(),
    )
}

fn req_bool(params: &Value, camel: &str, snake: &str) -> Result<bool, String> {
    params
        .get(camel)
        .or_else(|| params.get(snake))
        .and_then(|value| value.as_bool())
        .ok_or_else(|| format!("missing parameter: {camel}"))
}

fn ok(content_type: &str, body: &str) -> String {
    response(200, "OK", content_type, body)
}

fn not_found() -> String {
    response(404, "Not Found", "text/plain; charset=utf-8", "Not Found")
}

fn method_not_allowed() -> String {
    response(
        405,
        "Method Not Allowed",
        "text/plain; charset=utf-8",
        "Method Not Allowed",
    )
}

fn json_response(status: u16, payload: Value) -> String {
    let reason = if status == 200 {
        "OK"
    } else {
        "Internal Server Error"
    };
    response(
        status,
        reason,
        "application/json; charset=utf-8",
        &payload.to_string(),
    )
}

fn response(status: u16, reason: &str, content_type: &str, body: &str) -> String {
    format!(
        "HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n{body}",
        body.as_bytes().len()
    )
}

fn open_browser(url: &str) {
    if let Err(err) = viewer_core::open_external_url(url.to_string()) {
        eprintln!("failed to open browser: {err}");
    }
}
