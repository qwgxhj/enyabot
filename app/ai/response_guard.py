class ResponseGuard:
    def review(self, text: str, max_length: int = 800) -> str:
        text = (text or "").strip()
        if len(text) > max_length:
            text = text[: max_length - 3] + "..."
        return text
