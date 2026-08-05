from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from sprite_sheet_cleaner.app.ai_protocol.messages import decode_message, encode_message


def _provider_for(message: dict[str, object]):
    provider_id = str(message.get("provider_id") or "")
    model_path = Path(str(message.get("model_path") or ""))
    model_id = str(message.get("model_id") or "")
    compute = str(message.get("compute") or "auto")
    if provider_id == "rembg":
        from sprite_sheet_cleaner.ai_worker.rembg_provider import RembgProvider

        return RembgProvider(model_id=model_id or "u2net", model_dir=model_path.parent)
    if provider_id == "ben2":
        from sprite_sheet_cleaner.ai_worker.ben2_provider import Ben2Provider

        return Ben2Provider(model_path, preference=compute)
    raise ValueError(f"Unknown AI provider: {provider_id}")


def run() -> int:
    providers: dict[tuple[str, str, str], object] = {}
    for line in sys.stdin.buffer:
        try:
            message = decode_message(line)
            message_type = message["message_type"]
            if message_type == "hello":
                try:
                    from sprite_sheet_cleaner.ai_worker.capabilities import discover_capabilities

                    capabilities = discover_capabilities()
                    backend_list = list(capabilities.execution_providers)
                    warning_list = list(capabilities.warnings)
                except Exception as exc:
                    backend_list = ["CPUExecutionProvider"]
                    warning_list = [str(exc)]
                response = {
                    "protocol_version": 1,
                    "message_type": "capabilities",
                    "request_id": message.get("request_id"),
                    "provider_id": "placeholder",
                    "backends": backend_list,
                    "warnings": warning_list,
                }
            elif message_type == "infer":
                input_path = Path(str(message.get("input_path") or ""))
                output_path = Path(str(message.get("output_path") or ""))
                if (
                    not input_path.is_file()
                    or output_path.parent.resolve() != input_path.parent.resolve()
                    or output_path == input_path
                    or output_path.suffix.lower() != ".png"
                ):
                    raise ValueError("AI worker input/output paths are invalid.")
                provider_id = str(message.get("provider_id") or "")
                model_id = str(message.get("model_id") or "")
                model_path = str(message.get("model_path") or "")
                key = (provider_id, model_id, model_path)
                provider = providers.get(key)
                if provider is None:
                    provider = _provider_for(message)
                    providers[key] = provider
                with Image.open(input_path) as source:
                    result = provider.remove(source.convert("RGBA"), {}, cancelled=None)
                Image.fromarray(result.matte, mode="L").save(output_path, format="PNG")
                response = {
                    "protocol_version": 1,
                    "message_type": "result",
                    "request_id": message.get("request_id"),
                    "backend": result.backend,
                    "warnings": result.warnings,
                    "output_path": str(output_path),
                }
            elif message_type == "shutdown":
                response = {
                    "protocol_version": 1,
                    "message_type": "shutdown_ack",
                    "request_id": message.get("request_id"),
                }
                sys.stdout.buffer.write(encode_message(response))
                sys.stdout.buffer.flush()
                return 0
            else:
                response = {
                    "protocol_version": 1,
                    "message_type": "error",
                    "request_id": message.get("request_id"),
                    "error_code": "provider_not_installed",
                    "message": "No AI provider is installed in this worker.",
                }
        except Exception as exc:
            response = {
                "protocol_version": 1,
                "message_type": "error",
                "error_code": "invalid_message",
                "message": str(exc),
            }
        sys.stdout.buffer.write(encode_message(response))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
