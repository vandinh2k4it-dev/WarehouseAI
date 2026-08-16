# -*- coding: utf-8 -*-
"""Test cố định trong file (không gõ qua PowerShell) để loại trừ khả năng
PowerShell làm sai lệch ký tự tiếng Việt khi truyền qua `python -c`."""
import requests

msg = "Sản phẩm nào đang sắp hết hàng?"
print("Câu hỏi gửi đi (repr để thấy rõ từng ký tự):")
print(repr(msg))
print()

r = requests.post("http://localhost:8000/chatbot/ask", json={"message": msg})
print("Status:", r.status_code)
data = r.json()
print("Reply:", data["reply"])
print("Tool calls:", data["tool_calls"])
