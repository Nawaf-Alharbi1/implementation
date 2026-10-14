import os
import sys

# السماح باستيراد ملفات agents/ من داخل tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# بدون تأخير مصطنع في الـ Mock أثناء الاختبارات
os.environ["MOCK_LATENCY"] = "0"
