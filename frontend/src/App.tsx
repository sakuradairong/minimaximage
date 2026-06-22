// @ts-nocheck
import { useEffect, useMemo, useState } from "react";
import { Copy, ImagePlus, Loader2, Save, Sparkles, Wand2 } from "lucide-react";
import { api } from "./api";
import type {
	AppConfig,
	GenerateRequest,
	GeneratedImage,
	HistoryItem,
	ModelName,
} from "./types";

const aspectRatios = [
	"1:1",
	"16:9",
	"4:3",
	"3:2",
	"2:3",
	"3:4",
	"9:16",
	"21:9",
];
const promptTemplates = [
	"人物肖像",
	"风景摄影",
	"产品展示",
	"科幻场景",
	"动漫角色",
	"美食摄影",
];

const defaultConfig: AppConfig = {
	has_api_key: false,
	base_url: "https://api.minimaxi.com",
	model: "image-01",
	aspect_ratio: "1:1",
	n: 1,
	response_format: "url",
};

export function App() {
	const [config, setConfig] = useState<AppConfig>(defaultConfig);
	const [apiKey, setApiKey] = useState("");
	const [prompt, setPrompt] = useState("");
	const [referenceText, setReferenceText] = useState("");
	const [model, setModel] = useState<ModelName>("image-01");
	const [aspectRatio, setAspectRatio] = useState<string | null>("1:1");
	const [customSize, setCustomSize] = useState(false);
	const [width, setWidth] = useState(1024);
	const [height, setHeight] = useState(1024);
	const [n, setN] = useState(1);
	const [seed, setSeed] = useState("");
	const [responseFormat, setResponseFormat] = useState<"url" | "base64">("url");
	const [promptOptimizer, setPromptOptimizer] = useState(false);
	const [watermark, setWatermark] = useState(false);
	const [outputDir, setOutputDir] = useState("./output");
	const [images, setImages] = useState<GeneratedImage[]>([]);
	const [history, setHistory] = useState<HistoryItem[]>([]);
	const [selectedImage, setSelectedImage] = useState<GeneratedImage | null>(
		null,
	);
	const [message, setMessage] = useState("正在连接本地服务...");
	const [busy, setBusy] = useState(false);

	useEffect(() => {
		void refreshConfig();
		void refreshHistory();
	}, []);

	async function refreshConfig() {
		try {
			const loaded = await api.getConfig();
			setConfig(loaded);
			setModel(loaded.model);
			setAspectRatio(loaded.aspect_ratio ?? "1:1");
			setN(loaded.n);
			setResponseFormat(loaded.response_format);
			setMessage(
				loaded.has_api_key ? "Ready — 已配置 API Key" : "请先配置 API Key",
			);
		} catch (error) {
			setMessage(`连接失败：${String(error)}`);
		}
	}

	async function refreshHistory() {
		try {
			setHistory(await api.history());
		} catch {
			// History is non-critical.
		}
	}

	async function saveConfig() {
		setBusy(true);
		try {
			const saved = await api.saveConfig({
				api_key: apiKey || undefined,
				base_url: config.base_url,
				model,
				aspect_ratio: aspectRatio,
				n,
				response_format: responseFormat,
			});
			setConfig(saved);
			setApiKey("");
			setMessage("配置已保存");
		} catch (error) {
			setMessage(`保存失败：${String(error)}`);
		} finally {
			setBusy(false);
		}
	}

	const requestPreview = useMemo(() => {
		const payload = buildPayload();
		return JSON.stringify(
			{
				model: payload.model,
				prompt: payload.prompt || "<YOUR_PROMPT>",
				response_format: payload.response_format,
				n: payload.n,
				prompt_optimizer: payload.prompt_optimizer,
				...(payload.aspect_ratio ? { aspect_ratio: payload.aspect_ratio } : {}),
				...(payload.width && payload.height
					? { width: payload.width, height: payload.height }
					: {}),
				...(payload.seed ? { seed: payload.seed } : {}),
				...(payload.reference_images.length
					? {
							subject_reference: payload.reference_images.map((url) => ({
								type: "character",
								image_file: url,
							})),
						}
					: {}),
			},
			null,
			2,
		);
	}, [
		prompt,
		model,
		aspectRatio,
		customSize,
		width,
		height,
		n,
		seed,
		responseFormat,
		promptOptimizer,
		referenceText,
	]);

	function buildPayload(): GenerateRequest {
		return {
			prompt: prompt.trim(),
			model,
			aspect_ratio: customSize ? null : aspectRatio,
			width: customSize ? width : null,
			height: customSize ? height : null,
			n,
			seed: seed.trim() ? Number(seed) : null,
			response_format: responseFormat,
			prompt_optimizer: promptOptimizer,
			aigc_watermark: watermark,
			reference_images: referenceText
				.split("\n")
				.map((line) => line.trim())
				.filter(Boolean),
			api_key: apiKey || null,
			output_dir: outputDir || null,
		};
	}

	async function generate() {
		if (!prompt.trim()) {
			setMessage("请输入图片描述");
			return;
		}
		setBusy(true);
		setMessage("正在生成图片...");
		try {
			const result = await api.generate(buildPayload());
			setImages(result.images);
			setSelectedImage(result.images[0] ?? null);
			setMessage(`完成：保存 ${result.images.length} 张图片到 ${outputDir}`);
			await refreshHistory();
		} catch (error) {
			setMessage(`生成失败：${String(error)}`);
		} finally {
			setBusy(false);
		}
	}

	async function copyApiReference() {
		const curl = `curl --request POST \\\n  --url '${config.base_url}/v1/image_generation' \\\n  --header 'Authorization: Bearer YOUR_API_KEY' \\\n  --header 'Content-Type: application/json' \\\n  --data '${requestPreview.replaceAll("'", "'\\''")}'`;
		await navigator.clipboard.writeText(curl);
		setMessage("已复制 curl 到剪贴板");
	}

	return (
		<main className="app-shell">
			<aside className="sidebar">
				<div className="brand">
					<Sparkles size={22} /> minimaximage
				</div>
				<nav>
					<a className="active">图片生成</a>
					<a>
						生成历史 <span>{history.length}</span>
					</a>
					<a>API Key</a>
					<a>文件管理</a>
				</nav>
				<section className="history">
					<h3>生成历史</h3>
					{history.length === 0 ? (
						<p>暂无生成记录</p>
					) : (
						history.map((item) => (
							<button
								key={item.id}
								onClick={() => {
									setImages(item.images);
									setSelectedImage(item.images[0] ?? null);
									setPrompt(item.prompt);
								}}
							>
								<span>{item.prompt.slice(0, 28) || item.id}</span>
								<small>{new Date(item.created_at).toLocaleString()}</small>
							</button>
						))
					)}
				</section>
			</aside>

			<section className="workspace">
				<header className="topbar">
					<div>
						<h1>图片生成</h1>
						<p>使用 AI 根据文本描述或参考图片生成高质量图片</p>
					</div>
					<div className="api-key-box">
						<input
							value={apiKey}
							onChange={(event) => setApiKey(event.target.value)}
							placeholder={
								config.has_api_key ? "已保存 API Key，可留空" : "输入 API Key"
							}
							type="password"
						/>
						<button onClick={saveConfig} disabled={busy}>
							<Save size={16} /> 保存
						</button>
					</div>
				</header>

				<div className="content-grid">
					<section className="panel form-panel">
						<h2>提示词模板</h2>
						<div className="chips">
							{promptTemplates.map((template) => (
								<button
									key={template}
									onClick={() =>
										setPrompt(
											(value) => `${value}${value ? "，" : ""}${template}`,
										)
									}
								>
									{template}
								</button>
							))}
						</div>

						<label className="field">
							<span>
								图片描述 <em>{prompt.length} / 1500</em>
							</span>
							<textarea
								value={prompt}
								maxLength={1500}
								onChange={(event) => setPrompt(event.target.value)}
								placeholder="例如：A cinematic portrait of a fluffy cat wearing a top hat, studio lighting..."
							/>
						</label>

						<label className="switch-row">
							<input
								type="checkbox"
								checked={promptOptimizer}
								onChange={(event) => setPromptOptimizer(event.target.checked)}
							/>
							<Wand2 size={16} /> 自动优化提示词
						</label>

						<label className="field">
							<span>参考图片 URL（可选，用于图生图，每行一个）</span>
							<textarea
								className="small"
								value={referenceText}
								onChange={(event) => setReferenceText(event.target.value)}
								placeholder="https://example.com/reference.jpg"
							/>
						</label>

						<h2>基础设置</h2>
						<div className="settings-grid">
							<label className="field">
								<span>模型</span>
								<select
									value={model}
									onChange={(event) =>
										setModel(event.target.value as ModelName)
									}
								>
									<option value="image-01">image-01 — 标准图像生成模型</option>
									<option value="image-01-live">
										image-01-live — 支持画风设置的模型
									</option>
								</select>
							</label>
							<label className="field">
								<span>生成数量</span>
								<input
									type="number"
									min={1}
									max={9}
									value={n}
									onChange={(event) => setN(Number(event.target.value))}
								/>
							</label>
							<label className="field">
								<span>格式</span>
								<select
									value={responseFormat}
									onChange={(event) =>
										setResponseFormat(event.target.value as "url" | "base64")
									}
								>
									<option value="url">url</option>
									<option value="base64">base64</option>
								</select>
							</label>
							<label className="field">
								<span>随机种子</span>
								<input
									value={seed}
									onChange={(event) => setSeed(event.target.value)}
									placeholder="可选"
								/>
							</label>
						</div>

						<label className="switch-row">
							<input
								type="checkbox"
								checked={customSize}
								onChange={(event) => setCustomSize(event.target.checked)}
							/>{" "}
							自定义尺寸
						</label>
						{!customSize ? (
							<div className="ratio-grid">
								{aspectRatios.map((ratio) => (
									<button
										key={ratio}
										className={aspectRatio === ratio ? "selected" : ""}
										onClick={() => setAspectRatio(ratio)}
									>
										<span>{ratio.includes(":") ? "▭" : "□"}</span>
										{ratio}
									</button>
								))}
							</div>
						) : (
							<div className="settings-grid two">
								<label className="field">
									<span>宽度</span>
									<input
										type="number"
										value={width}
										onChange={(event) => setWidth(Number(event.target.value))}
									/>
								</label>
								<label className="field">
									<span>高度</span>
									<input
										type="number"
										value={height}
										onChange={(event) => setHeight(Number(event.target.value))}
									/>
								</label>
							</div>
						)}

						<h2>高级设置</h2>
						<label className="switch-row">
							<input
								type="checkbox"
								checked={watermark}
								onChange={(event) => setWatermark(event.target.checked)}
							/>{" "}
							添加 AIGC 水印
						</label>
						<label className="field">
							<span>输出目录</span>
							<input
								value={outputDir}
								onChange={(event) => setOutputDir(event.target.value)}
							/>
						</label>

						<button className="primary" onClick={generate} disabled={busy}>
							{busy ? (
								<Loader2 className="spin" size={18} />
							) : (
								<ImagePlus size={18} />
							)}{" "}
							生成图片
						</button>
					</section>

					<section className="panel result-panel">
						<div className="panel-title">
							<h2>生成结果</h2>
							<span>{message}</span>
						</div>
						{selectedImage ? (
							<div className="preview">
								<img
									src={selectedImage.file_url}
									alt={selectedImage.filename}
								/>
								<div className="image-meta">
									<strong>{selectedImage.filename}</strong>
									<code>{selectedImage.path}</code>
								</div>
							</div>
						) : (
							<div className="empty-result">
								<ImagePlus size={42} />
								生成的图片将在此处显示
							</div>
						)}
						<div className="thumbs">
							{images.map((image) => (
								<button
									key={image.path}
									className={
										selectedImage?.path === image.path ? "selected" : ""
									}
									onClick={() => setSelectedImage(image)}
								>
									<img src={image.file_url} alt={image.filename} />
								</button>
							))}
						</div>

						<div className="api-reference">
							<div className="panel-title">
								<h2>API 参考</h2>
								<button onClick={copyApiReference}>
									<Copy size={14} /> 复制
								</button>
							</div>
							<pre>{`curl --request POST \\\n  --url '${config.base_url}/v1/image_generation' \\\n  --header 'Authorization: Bearer YOUR_API_KEY' \\\n  --header 'Content-Type: application/json' \\\n  --data '${requestPreview}'`}</pre>
						</div>

						<div className="tips">
							<h2>使用技巧</h2>
							<ul>
								<li>
									提示词越详细，生成效果越好，建议包含主体、风格、光线、构图。
								</li>
								<li>英文提示词通常更稳定。</li>
								<li>开启自动优化提示词可让模型改进描述。</li>
								<li>相同随机种子可以复现相似结果。</li>
							</ul>
						</div>
					</section>
				</div>
			</section>
		</main>
	);
}
