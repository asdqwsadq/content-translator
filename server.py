"""
content-translator MCP Server
Multi-language translation and polishing using Xiaomi MiMo API
"""

import json
import os
import sys
from typing import Any

import requests

# Load environment
API_BASE = os.environ.get("MIMO_API_BASE", "https://token-plan-cn.xiaomimimo.com/v1")
API_KEY = os.environ.get("MIMO_API_KEY", "")
MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5-pro")

STYLE_PROMPTS = {
    "formal": "Translate the following text in a formal, elegant style. Preserve the original meaning and nuance.",
    "casual": "Translate the following text in a casual, conversational style. Sound natural and friendly.",
    "professional": "Translate the following text in a professional, business-appropriate style. Use precise terminology.",
}

TOOLS = [
    {
        "name": "translate",
        "description": "翻译文本 - 支持多种语言的高质量翻译与润色",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要翻译的文本"},
                "source_lang": {
                    "type": "string",
                    "description": "源语言代码 (auto=自动检测)",
                    "default": "auto",
                },
                "target_lang": {
                    "type": "string",
                    "description": "目标语言代码 (zh, en, ja, ko, fr, de, es, ru, ar, pt, it, nl, pl, tr, vi, th, id, ms, hi, bn 等)",
                },
                "style": {
                    "type": "string",
                    "enum": ["formal", "casual", "professional"],
                    "description": "翻译风格: formal(正式), casual(随意), professional(专业)",
                    "default": "formal",
                },
            },
            "required": ["text", "target_lang"],
        },
    }
]

LANGUAGE_MAP = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "ar": "Arabic",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "hi": "Hindi",
    "bn": "Bengali",
}


def call_mimo_api(
    text: str,
    source_lang: str,
    target_lang: str,
    style: str = "formal",
) -> str:
    """Call Xiaomi MiMo API for translation."""
    if not API_KEY:
        return "错误: API密钥未配置，请设置 MIMO_API_KEY 环境变量"

    source_name = LANGUAGE_MAP.get(source_lang, source_lang) if source_lang != "auto" else "auto"
    target_name = LANGUAGE_MAP.get(target_lang, target_lang)

    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["formal"])

    if source_lang == "auto":
        system_prompt = (
            f"You are a professional translator and copy editor. "
            f"{style_prompt} "
            f"First, detect the language of the input text. "
            f"Then translate to {target_name} ({target_lang}). "
            f"Output ONLY the translated text, nothing else."
        )
    else:
        system_prompt = (
            f"You are a professional translator and copy editor. "
            f"{style_prompt} "
            f"Translate FROM {source_name} ({source_lang}) TO {target_name} ({target_lang}). "
            f"Output ONLY the translated text, nothing else."
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    try:
        resp = requests.post(
            f"{API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.Timeout:
        return "错误: 请求超时，请稍后重试"
    except requests.exceptions.HTTPError as e:
        return f"错误: API请求失败 (HTTP {resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        return f"错误: {str(e)}"


def handle_mcp_request(raw: str) -> str:
    """Handle a single MCP JSON-RPC request."""
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None,
            }
        )

    req_id = req.get("id")
    method = req.get("method", "")

    if method == "initialize":
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "content-translator",
                        "version": "1.0.0",
                    },
                },
            }
        )

    elif method == "tools/list":
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }
        )

    elif method == "tools/call":
        params = req.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if name == "translate":
            text = arguments.get("text", "")
            source_lang = arguments.get("source_lang", "auto")
            target_lang = arguments.get("target_lang", "")
            style = arguments.get("style", "formal")

            if not text:
                result_text = "错误: 请输入要翻译的文本"
            elif not target_lang:
                result_text = "错误: 请指定目标语言"
            else:
                result_text = call_mimo_api(text, source_lang, target_lang, style)

            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                    },
                }
            )
        else:
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {name}",
                    },
                }
            )

    elif method == "notifications/initialized":
        return ""

    else:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
        )


def main():
    """Main loop: read JSON-RPC from stdin, write results to stdout."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        response = handle_mcp_request(line)
        if response:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
