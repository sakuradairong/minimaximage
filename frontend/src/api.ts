import type {
	AppConfig,
	GenerateRequest,
	GenerateResponse,
	HistoryItem,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
	const response = await fetch(url, {
		headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
		...init,
	});
	if (!response.ok) {
		let message = `${response.status} ${response.statusText}`;
		try {
			const payload = await response.json();
			message = payload.detail ?? message;
		} catch {
			// Keep default message.
		}
		throw new Error(String(message));
	}
	return (await response.json()) as T;
}

export const api = {
	health: () => request<{ status: string; app: string }>("/api/health"),
	getConfig: () => request<AppConfig>("/api/config"),
	saveConfig: (config: Partial<AppConfig> & { api_key?: string }) =>
		request<AppConfig>("/api/config", {
			method: "POST",
			body: JSON.stringify(config),
		}),
	generate: (payload: GenerateRequest) =>
		request<GenerateResponse>("/api/images/generate", {
			method: "POST",
			body: JSON.stringify(payload),
		}),
	history: () => request<HistoryItem[]>("/api/images/history"),
};
