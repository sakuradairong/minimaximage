export type ModelName = "image-01" | "image-01-live";
export type ResponseFormat = "url" | "base64";

export interface AppConfig {
	has_api_key: boolean;
	base_url: string;
	model: ModelName;
	aspect_ratio: string | null;
	n: number;
	response_format: ResponseFormat;
}

export interface GenerateRequest {
	prompt: string;
	model: ModelName;
	aspect_ratio: string | null;
	width?: number | null;
	height?: number | null;
	n: number;
	seed?: number | null;
	response_format: ResponseFormat;
	prompt_optimizer: boolean;
	aigc_watermark: boolean;
	reference_images: string[];
	api_key?: string | null;
	output_dir?: string | null;
}

export interface GeneratedImage {
	filename: string;
	path: string;
	file_url: string;
}

export interface GenerateResponse {
	id: string;
	success_count: number;
	failed_count: number;
	status_code: number;
	status_msg: string;
	images: GeneratedImage[];
}

export interface HistoryItem {
	id: string;
	created_at: string;
	prompt: string;
	model: string;
	n: number;
	images: GeneratedImage[];
}
