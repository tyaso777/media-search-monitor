export async function invoke(command, params = {}) {
  const tauriInvoke = window.__TAURI__?.core?.invoke;
  if (tauriInvoke) {
    return tauriInvoke(command, params);
  }

  const response = await fetch(`/api/invoke/${encodeURIComponent(command)}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(params),
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.ok) {
    throw new Error(payload?.error || `HTTP ${response.status}`);
  }
  return payload.value;
}

export function isLocalViewer() {
  return !window.__TAURI__?.core?.invoke;
}
