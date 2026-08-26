# 让 pytest 把 backend/ 加入 sys.path，从而能 `from app.database import ...`。
# 没有这个文件时，pytest 只会把 backend/tests/ 放进 sys.path，导致 `No module named 'app'`。
